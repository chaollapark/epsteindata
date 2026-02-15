"""Source registry."""

from .courtlistener import CourtListenerSource
from .direct_urls import DirectURLsSource
from .documentcloud import DocumentCloudSource
from .doj import DOJSource
from .epsteingraph import EpsteinGraphSource
from .fbi_vault import FBIVaultSource
from .house_oversight import HouseOversightSource
from .internet_archive import InternetArchiveSource
from .torrents import TorrentSource

ALL_SOURCES = {
    "doj": DOJSource,
    "direct_urls": DirectURLsSource,
    "fbi_vault": FBIVaultSource,
    "internet_archive": InternetArchiveSource,
    "documentcloud": DocumentCloudSource,
    "house_oversight": HouseOversightSource,
    "courtlistener": CourtListenerSource,
    "torrents": TorrentSource,
    "epsteingraph": EpsteinGraphSource,
}
