export function Footer() {
  return (
    <footer className="border-t border-border py-6 mt-16">
      <div className="mx-auto max-w-5xl px-4 text-center text-sm text-muted-foreground">
        <p>
          A project by{" "}
          <a
            href="https://epsteindata.cc"
            className="font-medium text-foreground hover:underline"
            target="_blank"
            rel="noopener noreferrer"
          >
            EpsteinData.cc
          </a>
          {" "}&middot;{" "}
          <a
            href="https://github.com/chaollapark/epsteindata"
            className="font-medium text-foreground hover:underline"
            target="_blank"
            rel="noopener noreferrer"
          >
            Contribute on GitHub
          </a>
        </p>
      </div>
    </footer>
  );
}
