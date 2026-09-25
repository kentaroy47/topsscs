"""Fetch SSCS conference papers (with author affiliations) from Crossref.

Output: data/raw/<conf>_<year>.json  (list of Crossref work items)
"""
import datetime, json, re, sys, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
MAILTO = "kyoshioka47@keio.jp"

# conf id -> (crossref query, regex that the container-title must match)
CONFS = {
    "isscc": ("International Solid-State Circuits Conference",
              r"^\d{4} IEEE International Solid[- ]+State Circuits Conference \(ISSCC\)$"),
    "vlsi": ("Symposium on VLSI Circuits Technology",
             r"^\d{4} (IEEE )?(IEEE/JSAP )?Symposium on VLSI (Technology and Circuits|Circuits)\b"),
    "cicc": ("Custom Integrated Circuits Conference",
             r"^\d{4} IEEE Custom Integrated Circuits Conference \(CICC\)$"),
    "asscc": ("Asian Solid-State Circuits Conference",
              r"^\d{4} IEEE Asian Solid-State Circuits Conference \(A-SSCC\)$"),
    "esscirc": ("European Solid-State Circuits Conference ESSCIRC ESSERC",
                r"(ESSCIRC|ESSERC)"),
}


def fetch(query, year):
    items, offset = [], 0
    while True:
        params = {
            "query.container-title": query,
            "filter": f"from-pub-date:{year}-01-01,until-pub-date:{year}-12-31,type:proceedings-article",
            "rows": 1000,
            "offset": offset,
            "select": "DOI,title,container-title,author,published,page",
            "mailto": MAILTO,
        }
        url = "https://api.crossref.org/works?" + urllib.parse.urlencode(params)
        for attempt in range(5):
            try:
                msg = json.load(urllib.request.urlopen(url, timeout=180))["message"]
                break
            except Exception as e:  # noqa: BLE001
                print("  retry", attempt, e, file=sys.stderr)
                time.sleep(5 * (attempt + 1))
        else:
            raise RuntimeError(url)
        batch = msg["items"]
        items += batch
        # relevance-ranked: the target proceedings sit in the first pages
        if len(batch) < 1000 or len(items) >= 3000:
            return items
        offset += 1000


def main():
    years = range(2022, 2027)
    only = sys.argv[1:]
    for conf, (query, pat) in CONFS.items():
        if only and conf not in only:
            continue
        rx = re.compile(pat)
        for y in years:
            out = RAW / f"{conf}_{y}.json"
            items = [i for i in fetch(query, y) if rx.search((i.get("container-title") or [""])[0])]
            # keep one container per conf/year (drop e.g. workshop volumes)
            out.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
            cts = sorted({(i.get("container-title") or [""])[0] for i in items})
            print(conf, y, len(items), cts)
    (ROOT / "data" / "fetched_at.txt").write_text(datetime.date.today().isoformat(), encoding="utf-8")


if __name__ == "__main__":
    main()
