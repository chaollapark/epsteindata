"""EpsteinGraph.com — scrape the processed document database via its REST API.

API base: https://api.epsteingraph.com

Endpoints:
  GET /api/stats                  — site-wide statistics
  GET /api/trending               — trending searches (last 24h)
  GET /api/person-redirects       — list of short-name redirects
  GET /api/people/top             — top people (limit capped at 200, offset ignored)
      ?limit=200&order_by=mentions&role=...&public_figures=true
  GET /api/people/{slug}          — person detail + paginated documents
      ?limit=100&offset=0&sort=doc_id&doc_types=...&data_source=...&date_from=...&date_to=...
  GET /api/people/{slug}/timeline — monthly document counts for a person
  GET /api/graph                  — connection graph (nodes + edges, capped at 200 nodes)
      ?limit=200&min_shared=1&role=...&public_figures=true
  GET /api/person-lookup?q=...    — person name search (returns slug)

Data sources: epstein_transparency_act, oversight_09082025, oversight_11122025, CASE18-2868, BLACKBOOK

Document types: flight_log, email, letter, phone_record, legal_filing, court_order,
    indictment, plea_agreement, search_warrant, fbi_report, police_report,
    interview_notes, financial_record, photograph, receipt, travel_document,
    subpoena, witness_statement, grand_jury, correspondence, memo, news_clipping,
    deposition, medical_record, property_record, will_testament, audio, video, other, unknown

People discovery strategy:
  The /api/people/top endpoint is capped at 200 results and ignores offset.
  To discover all 50K+ people we use a breadth-first snowball crawl:
    1. Seed with top 200 by mentions
    2. Seed with top 200 per role (19 roles) and public_figures=true
    3. Seed with graph nodes
    4. For each scraped person, extract connection names
    5. Resolve connection names → slugs via /api/person-lookup
    6. Add newly discovered slugs to the crawl queue
    7. Repeat until no new people are found
"""

import json
import logging
import os
from collections import deque
from typing import Generator, Tuple
from urllib.parse import quote

from .base import BaseSource

logger = logging.getLogger("epstein_scraper")

API_BASE = "https://api.epsteingraph.com"

DOCS_PER_PAGE = 100

KNOWN_ROLES = [
    "academic", "actor", "artist", "author", "business", "diplomat",
    "financier", "government", "judge", "lawyer", "media", "model",
    "musician", "other public figure", "philanthropist", "politician",
    "royalty", "scientist", "socialite",
]


class EpsteinGraphSource(BaseSource):
    """Scrape structured data from epsteingraph.com's public API.

    Unlike other sources that download raw PDFs, this source pulls the
    pre-processed document metadata, AI summaries, people profiles,
    connections, and timelines — saving them as JSON files.

    Uses a breadth-first snowball crawl to discover people beyond the
    200-person API cap.
    """

    name = "epsteingraph"

    def discover(self) -> Generator[Tuple[str, dict], None, None]:
        yield from ()

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self):
        logger.info(f"[{self.name}] Starting epsteingraph.com scrape...")
        out_dir = os.path.join(self.config.data_dir, self.name)
        os.makedirs(out_dir, exist_ok=True)

        state = self.db.get_source_state(self.name) or {}
        completed_slugs = set(state.get("completed_slugs", []))
        failed_slugs = set(state.get("failed_slugs", []))
        # Names we already tried to look up (avoid re-querying)
        looked_up_names = set(state.get("looked_up_names", []))

        # 1. Site-wide metadata
        self._fetch_site_metadata(out_dir)

        # 2. Seed the crawl queue with all discoverable people
        queue = deque()
        known_slugs = set(completed_slugs)  # slugs already queued or done

        seed_slugs = self._seed_people(out_dir)
        for slug in seed_slugs:
            if slug not in known_slugs:
                queue.append(slug)
                known_slugs.add(slug)
        logger.info(f"[{self.name}] Seed: {len(seed_slugs)} unique people, "
                    f"{len(completed_slugs)} already done, "
                    f"{len(queue)} to scrape")

        # 3. Fetch graph data
        self._fetch_graph(out_dir)

        # 4. Breadth-first crawl: scrape each person, discover new people
        scraped_this_run = 0
        total_known = len(known_slugs)

        while queue:
            slug = queue.popleft()

            if slug in completed_slugs:
                continue

            logger.info(f"[{self.name}] [{scraped_this_run+1}] "
                        f"Scraping: {slug} (queue={len(queue)}, known={total_known})")

            try:
                new_names = self._fetch_person(slug, out_dir)
                completed_slugs.add(slug)
                scraped_this_run += 1

                # Resolve new connection names → slugs and enqueue
                for name in new_names:
                    if name in looked_up_names:
                        continue
                    looked_up_names.add(name)

                    resolved_slug = self._lookup_person(name)
                    if resolved_slug and resolved_slug not in known_slugs:
                        queue.append(resolved_slug)
                        known_slugs.add(resolved_slug)
                        total_known += 1

                # Save state periodically
                if scraped_this_run % 25 == 0:
                    self._save_state(state, completed_slugs, failed_slugs, looked_up_names)
                    logger.info(f"[{self.name}] Progress: {len(completed_slugs)} done, "
                                f"{len(queue)} queued, {total_known} known")

            except Exception as e:
                failed_slugs.add(slug)
                logger.error(f"[{self.name}] Failed {slug}: {e}")

        # Final save
        state["completed"] = True
        self._save_state(state, completed_slugs, failed_slugs, looked_up_names)
        logger.info(f"[{self.name}] Done. "
                    f"Scraped {len(completed_slugs)}, "
                    f"failed {len(failed_slugs)}, "
                    f"total known {total_known}.")

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------

    def _save_state(self, state: dict, completed: set, failed: set, looked_up: set):
        state["completed_slugs"] = list(completed)
        state["failed_slugs"] = list(failed)
        state["looked_up_names"] = list(looked_up)
        self.db.save_source_state(self.name, state)

    # ------------------------------------------------------------------
    # API helpers
    # ------------------------------------------------------------------

    def _api_get(self, path: str, params: dict = None) -> dict:
        """GET an API endpoint with rate limiting."""
        url = f"{API_BASE}{path}"
        if params:
            parts = []
            for k, v in params.items():
                if v is not None:
                    parts.append(f"{k}={v}")
            if parts:
                url = f"{url}?{'&'.join(parts)}"
        return self.downloader.fetch_json(
            url, self.name, self.source_config.rate_limit
        )

    def _save_json(self, data, out_dir: str, *path_parts: str):
        dest = os.path.join(out_dir, *path_parts)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # Seed discovery: gather as many slugs as possible from list endpoints
    # ------------------------------------------------------------------

    def _seed_people(self, out_dir: str) -> list:
        """Collect seed slugs from /people/top (various filters) + graph nodes."""
        seen = {}  # slug → person dict

        # Top 200 by mentions
        self._collect_top_people(seen, {})

        # Top 200 per role
        for role in KNOWN_ROLES:
            self._collect_top_people(seen, {"role": role})

        # Public figures
        self._collect_top_people(seen, {"public_figures": "true"})

        # Graph nodes (all min_shared levels)
        for ms in [1, 10, 100]:
            try:
                data = self._api_get("/api/graph", {"limit": 200, "min_shared": ms})
                for node in data.get("nodes", []):
                    slug = node.get("slug")
                    if slug and slug not in seen:
                        seen[slug] = {
                            "slug": slug,
                            "name": node.get("name", slug),
                            "mentions": node.get("mentions", 0),
                            "count": node.get("documents", 0),
                        }
            except Exception as e:
                logger.error(f"[{self.name}] Graph seed failed (min_shared={ms}): {e}")

        # Person redirects (well-known names)
        try:
            data = self._api_get("/api/person-redirects")
            for name in data.get("redirects", []):
                resolved = self._lookup_person(name)
                if resolved and resolved not in seen:
                    seen[resolved] = {"slug": resolved, "name": name}
        except Exception as e:
            logger.error(f"[{self.name}] Redirect seed failed: {e}")

        # Save the full seed list
        people_list = sorted(seen.values(), key=lambda p: p.get("mentions", 0), reverse=True)
        self._save_json({"total": len(people_list), "people": people_list},
                        out_dir, "all_people.json")

        return [p["slug"] for p in people_list]

    def _collect_top_people(self, seen: dict, extra_params: dict):
        """Fetch /api/people/top with given filters and merge into seen."""
        params = {"limit": 200, "order_by": "mentions"}
        params.update(extra_params)
        try:
            data = self._api_get("/api/people/top", params)
            for p in data.get("people", []):
                slug = p.get("slug")
                if slug and slug not in seen:
                    seen[slug] = p
        except Exception as e:
            logger.error(f"[{self.name}] people/top failed (params={extra_params}): {e}")

    # ------------------------------------------------------------------
    # Person lookup (name → slug)
    # ------------------------------------------------------------------

    def _lookup_person(self, name: str) -> str | None:
        """Resolve a person name to a slug via /api/person-lookup."""
        try:
            encoded = quote(name, safe="")
            data = self._api_get(f"/api/person-lookup?q={encoded}")
            if data.get("match"):
                return data.get("slug")
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Fetch graph data
    # ------------------------------------------------------------------

    def _fetch_graph(self, out_dir: str):
        logger.info(f"[{self.name}] Fetching connection graph...")
        for min_shared in [1, 10, 100, 1000]:
            try:
                data = self._api_get("/api/graph", {
                    "limit": 200,
                    "min_shared": min_shared,
                })
                self._save_json(data, out_dir, "graph", f"graph_min{min_shared}.json")
                logger.info(f"[{self.name}] Graph min_shared={min_shared}: "
                            f"{len(data.get('nodes', []))} nodes, "
                            f"{len(data.get('edges', []))} edges")
            except Exception as e:
                logger.error(f"[{self.name}] Graph fetch failed (min_shared={min_shared}): {e}")

    # ------------------------------------------------------------------
    # Site metadata
    # ------------------------------------------------------------------

    def _fetch_site_metadata(self, out_dir: str):
        logger.info(f"[{self.name}] Fetching site metadata...")
        for endpoint, filename in [
            ("/api/stats", "stats.json"),
            ("/api/trending", "trending.json"),
            ("/api/person-redirects", "person_redirects.json"),
        ]:
            try:
                data = self._api_get(endpoint)
                self._save_json(data, out_dir, filename)
                logger.info(f"[{self.name}] Saved {filename}")
            except Exception as e:
                logger.error(f"[{self.name}] Failed {endpoint}: {e}")

    # ------------------------------------------------------------------
    # Per-person scrape
    # ------------------------------------------------------------------

    def _fetch_person(self, slug: str, out_dir: str) -> set:
        """Fetch profile, documents (paginated), and timeline.

        Returns a set of connection names found (for snowball discovery).
        """
        person_dir = os.path.join(out_dir, "people", slug)
        new_names = set()

        # 1. Profile + first page of documents
        data = self._api_get(f"/api/people/{slug}", {
            "limit": DOCS_PER_PAGE,
            "offset": 0,
            "sort": "doc_id",
        })

        total_docs = data.get("total_documents", 0)
        all_documents = list(data.get("documents", []))

        # Extract connection names for snowball crawl
        for conn in data.get("connections", []):
            name = conn.get("connected_person")
            if name:
                new_names.add(name)

        # Save profile (without documents array to keep it small)
        profile = {k: v for k, v in data.items() if k != "documents"}
        self._save_json(profile, person_dir, "profile.json")

        # 2. Paginate remaining documents
        offset = DOCS_PER_PAGE
        while offset < total_docs:
            try:
                page_data = self._api_get(f"/api/people/{slug}", {
                    "limit": DOCS_PER_PAGE,
                    "offset": offset,
                    "sort": "doc_id",
                })
                docs = page_data.get("documents", [])
                if not docs:
                    break
                all_documents.extend(docs)
                offset += DOCS_PER_PAGE
            except Exception as e:
                logger.error(f"[{self.name}] Docs page failed for {slug} "
                             f"at offset {offset}: {e}")
                break

        # Save all documents
        self._save_json({
            "slug": slug,
            "total_documents": total_docs,
            "fetched": len(all_documents),
            "documents": all_documents,
        }, person_dir, "documents.json")

        logger.info(f"[{self.name}] {slug}: {len(all_documents)}/{total_docs} docs, "
                    f"{len(new_names)} connections")

        # 3. Timeline
        try:
            timeline = self._api_get(f"/api/people/{slug}/timeline")
            self._save_json(timeline, person_dir, "timeline.json")
        except Exception as e:
            logger.error(f"[{self.name}] Timeline failed for {slug}: {e}")

        # Register in documents table for tracking
        api_url = f"{API_BASE}/api/people/{slug}"
        if not self.db.url_exists(api_url):
            doc_id = self.db.insert_document(
                url=api_url,
                source=self.name,
                source_id=slug,
                filename=f"{slug}.json",
                title=data.get("person", {}).get("canonical_name", slug),
                metadata={
                    "total_documents": total_docs,
                    "fetched_documents": len(all_documents),
                    "person": data.get("person", {}),
                    "person_stats": data.get("person_stats", {}),
                },
            )
            self.db.update_download(
                doc_id, "downloaded",
                local_path=os.path.join(person_dir, "profile.json"),
                sha256=None, file_size=0,
            )

        return new_names
