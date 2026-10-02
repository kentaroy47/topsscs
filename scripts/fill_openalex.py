"""Fetch OpenAlex authorships for every paper (looked up by DOI).

Used for (1) affiliations missing in Crossref (mostly 2021 proceedings) and
(2) institution IDs / countries / types for institutions outside Japan.

Output: data/openalex.json, data/openalex_institutions.json (institution lineage)
  {doi: [{"name": str, "affs": [raw affiliation strings],
          "insts": [{"id": "I123", "name": str, "cc": "US", "type": "education"}]}, ...]}
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


def authorship(a):
    affs = list(a.get("raw_affiliation_strings") or [])
    insts = []
    for inst in a.get("institutions") or []:
        if not inst.get("id"):
            continue
        insts.append({"id": inst["id"].rsplit("/", 1)[-1], "name": inst.get("display_name") or "",
                      "cc": inst.get("country_code") or "", "type": inst.get("type") or ""})
    if not affs:
        affs = [i["name"] + (", Japan" if i["cc"] == "JP" else "") for i in insts if i["name"]]
    return {"name": (a.get("author") or {}).get("display_name") or a.get("raw_author_name") or "",
            "affs": affs, "insts": insts}


def main():
    cache = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    # entries from the old format (no "insts") are refetched
    cache = {k: v for k, v in cache.items() if v and all("insts" in a for a in v)}
    need = []
    for path in sorted(RAW.glob("*.json")):
        for item in json.loads(path.read_text(encoding="utf-8")):
            doi = item["DOI"].lower()
            if item.get("author") and doi not in cache and doi.startswith(("10.1109/", "10.23919/")):
                need.append(doi)
    need = sorted(set(need))
    print(f"{len(need)} DOIs to look up ({len(cache)} cached)")
    found_total = 0
    for i in range(0, len(need), 50):
        chunk = need[i:i + 50]
        params = {"filter": "doi:" + "|".join(chunk), "per-page": 50,
                  "select": "doi,authorships", "mailto": MAILTO}
        data = get("https://api.openalex.org/works?" + urllib.parse.urlencode(params, safe=":|/"))
        for w in data["results"]:
            doi = (w.get("doi") or "").replace("https://doi.org/", "").lower()
            cache[doi] = [authorship(a) for a in w.get("authorships") or []]
            found_total += 1
        if (i // 50) % 20 == 0:
            print(f"  {i + len(chunk)}/{len(need)} (found {found_total})")
            OUT.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    OUT.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    print(f"done: found {found_total}/{len(need)}")


def fetch_lineage():
    """Institution lineage (self, parent, grandparent, ...) for every institution seen."""
    cache = json.loads(OUT.read_text(encoding="utf-8"))
    out_path = ROOT / "data" / "openalex_institutions.json"
    known = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    ids = sorted({i["id"] for v in cache.values() for a in v for i in a["insts"]} - set(known))
    while ids:
        print(f"{len(ids)} institutions to look up")
        for i in range(0, len(ids), 50):
            chunk = ids[i:i + 50]
            params = {"filter": "openalex_id:" + "|".join(chunk), "per-page": 50,
                      "select": "id,display_name,type,country_code,lineage", "mailto": MAILTO}
            for r in get("https://api.openalex.org/institutions?" + urllib.parse.urlencode(params, safe=":|/"))["results"]:
                known[r["id"].rsplit("/", 1)[-1]] = {
                    "name": r["display_name"], "cc": r.get("country_code") or "", "type": r.get("type") or "",
                    "lineage": [x.rsplit("/", 1)[-1] for x in r.get("lineage") or []]}
            for x in chunk:
                known.setdefault(x, None)
        # ancestors we have not seen yet
        ids = sorted({x for v in known.values() if v for x in v["lineage"]} - set(known))
    out_path.write_text(json.dumps(known, ensure_ascii=False, indent=0), encoding="utf-8")


if __name__ == "__main__":
    if "--lineage" not in sys.argv:
        main()
    fetch_lineage()
