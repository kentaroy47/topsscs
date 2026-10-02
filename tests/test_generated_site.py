"""Check a built site with SITE_DIR=/path/to/site python -m unittest discover -s tests."""
import os
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_site as site


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.ids = [], set()
        self.scopes, self.modes = [], []
        self.in_scope = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        for attr in ("href", "src"):
            if attr in attrs:
                self.links.append(attrs[attr])
        if tag == "option":
            self.links.append(attrs["value"])
        if tag == "nav" and attrs.get("class") == "scope-switch":
            self.in_scope = True
        if tag == "a" and self.in_scope:
            self.scopes.append(attrs)
        if attrs.get("class") == "mode-panel":
            self.modes.append(attrs["data-mode"])

    def handle_endtag(self, tag):
        if tag == "nav":
            self.in_scope = False


@unittest.skipUnless(os.environ.get("SITE_DIR"), "Set SITE_DIR to validate generated HTML")
class GeneratedSiteTest(unittest.TestCase):
    def test_all_internal_links_and_ranking_variants(self):
        root = Path(os.environ["SITE_DIR"]).resolve()
        parsed = {}
        for path in root.rglob("*.html"):
            parser = PageParser()
            parser.feed(path.read_text(encoding="utf-8"))
            parsed[path] = parser
        self.assertGreater(len(parsed), 168)
        assets = {p.resolve() for p in (root / "assets").iterdir()}
        for path, parser in parsed.items():
            for href in set(parser.links):
                url = urlsplit(href)
                if url.scheme or url.netloc:
                    continue
                # The generated tree has no symlinks. Normalize '..' without
                # querying the filesystem for every repeated navigation link.
                target = Path(os.path.abspath(path.parent / unquote(url.path))) if url.path else path
                self.assertTrue(target in parsed or target in assets, f"{path}: broken link {href}")
                if url.fragment and target in parsed:
                    self.assertIn(unquote(url.fragment), parsed[target].ids, f"{path}: missing anchor {href}")
        for edition in site.EDITIONS:
            for scope in site.SCOPES:
                for kind in site.KINDS:
                    for rel in ["index.html"] + [c["id"] + "/index.html" for c in site.CONFERENCES]:
                        path = root / site.scope_path(edition, scope, kind, rel)
                        self.assertIn(path, parsed)
                        parser = parsed[path]
                        self.assertEqual(parser.modes, ["full", "first", "frac"])
                        self.assertEqual(len(parser.scopes), 6)
                        selected = [a for a in parser.scopes if a.get("aria-current") == "true"]
                        self.assertEqual(len(selected), 1)
                        self.assertEqual(Path(os.path.abspath(path.parent / selected[0]["href"])), path)


if __name__ == "__main__":
    unittest.main()
