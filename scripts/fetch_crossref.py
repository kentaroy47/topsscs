"""Fetch SSCS conference/journal papers (with author affiliations) from Crossref.

Output: data/raw/<venue>_<year>.json  (list of Crossref work items)
"""
import datetime, json, re, sys, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
MAILTO = "kyoshioka47@keio.jp"
YEARS = range(2022, 2027)

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

# journal id -> ISSN
JOURNALS = {
    "jssc": "0018-9200",
}

SELECT = "DOI,title,container-title,author,published,published-print,published-online,page,volume,issue"


def get(url):
    for attempt in range(5):
        try:
            return json.load(urllib.request.urlopen(url, timeout=180))["message"]
        except Exception as e:  # noqa: BLE001
            print("  retry", attempt, e, file=sys.stderr)
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(url)


def fetch(query, year):
    items, offset = [], 0
    while True:
        params = {
            "query.container-title": query,
            "filter": f"from-pub-date:{year}-01-01,until-pub-date:{year}-12-31,type:proceedings-article",
            "rows": 1000,
            "offset": offset,
            "select": SELECT,
            "mailto": MAILTO,
        }
        batch = get("https://api.crossref.org/works?" + urllib.parse.urlencode(params))["items"]
        items += batch
        # relevance-ranked: the target proceedings sit in the first pages
        if len(batch) < 1000 or len(items) >= 3000:
            return items
        offset += 1000


def fetch_journal(issn):
    """All works of a journal published online since the year before the window."""
    items, cursor = [], "*"
    while True:
        params = {
            "filter": f"from-pub-date:{YEARS[0] - 1}-01-01,type:journal-article",
            "rows": 1000,
            "cursor": cursor,
            "select": SELECT,
            "mailto": MAILTO,
        }
        msg = get(f"https://api.crossref.org/journals/{issn}/works?" + urllib.parse.urlencode(params))
        items += msg["items"]
        if len(msg["items"]) < 1000:
            return items
        cursor = msg["next-cursor"]


def issue_year(item):
    """Year of the print issue; early-access papers fall back to their online year."""
    for key in ("published-print", "published-online", "published"):
        parts = (item.get(key) or {}).get("date-parts") or [[None]]
        if parts[0][0]:
            return parts[0][0]
    return None


def main():
    only = sys.argv[1:]
    for conf, (query, pat) in CONFS.items():
        if only and conf not in only:
            continue
        rx = re.compile(pat)
        for y in YEARS:
            out = RAW / f"{conf}_{y}.json"
            items = [i for i in fetch(query, y) if rx.search((i.get("container-title") or [""])[0])]
            out.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
            cts = sorted({(i.get("container-title") or [""])[0] for i in items})
            print(conf, y, len(items), cts)
    for jid, issn in JOURNALS.items():
        if only and jid not in only:
            continue
        items = fetch_journal(issn)
        for y in YEARS:
            sel = [i for i in items if issue_year(i) == y]
            (RAW / f"{jid}_{y}.json").write_text(json.dumps(sel, ensure_ascii=False), encoding="utf-8")
            print(jid, y, len(sel))
    (ROOT / "data" / "fetched_at.txt").write_text(datetime.date.today().isoformat(), encoding="utf-8")


if __name__ == "__main__":
    main()
