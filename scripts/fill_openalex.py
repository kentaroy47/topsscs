"""Fill author affiliations missing in Crossref from OpenAlex (looked up by DOI).

Crossref lacks affiliations for most 2021 IEEE proceedings. For every paper with
at least one author without an affiliation, fetch the OpenAlex authorships.

Output: data/openalex.json  {doi: [{"name": str, "affs": [str, ...]}, ...]}
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "openalex.json"
MAILTO = "kyoshioka47@keio.jp"


def get(url):
    for attempt in range(5):
        try:
            return json.load(urllib.request.urlopen(url, timeout=120))
        except Exception as e:  # noqa: BLE001
            print("  retry", attempt, e, file=sys.stderr)
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(url)


def authorship_affs(a):
    affs = list(a.get("raw_affiliation_strings") or [])
    if not affs:
        for inst in a.get("institutions") or []:
            name = inst.get("display_name") or ""
            if inst.get("country_code") == "JP":
                name += ", Japan"
            affs.append(name)
    return [x for x in affs if x]


def main():
    cache = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    need = []
    for path in sorted(RAW.glob("*.json")):
        for item in json.loads(path.read_text(encoding="utf-8")):
            authors = item.get("author") or []
            if authors and any(not a.get("affiliation") for a in authors):
                doi = item["DOI"].lower()
                if doi not in cache:
                    need.append(doi)
    print(f"{len(need)} DOIs to look up ({len(cache)} cached)")
    for i in range(0, len(need), 50):
        chunk = need[i:i + 50]
        params = {
            "filter": "doi:" + "|".join(chunk),
            "per-page": 50,
            "select": "doi,authorships",
            "mailto": MAILTO,
        }
        data = get("https://api.openalex.org/works?" + urllib.parse.urlencode(params, safe=":|/"))
        found = set()
        for w in data["results"]:
            doi = (w.get("doi") or "").replace("https://doi.org/", "").lower()
            found.add(doi)
            cache[doi] = [{"name": (a.get("author") or {}).get("display_name") or a.get("raw_author_name") or "",
                           "affs": authorship_affs(a)} for a in w.get("authorships") or []]
        for doi in chunk:
            cache.setdefault(doi, [])  # remember misses too
        print(f"  {i + len(chunk)}/{len(need)} (found {len(found)})")
        OUT.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    OUT.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
