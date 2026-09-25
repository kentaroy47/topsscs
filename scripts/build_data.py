"""Filter raw Crossref items into papers and attribute them to Japanese universities.

Input : data/raw/<conf>_<year>.json
Output: data/papers.json  (all eligible papers, with matched universities/authors)
"""
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from universities import match  # noqa: E402
from conferences import CONFERENCES, YEARS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"

# Non-paper items that IEEE registers in the proceedings.
NON_PAPER = re.compile(
    r"^\s*("
    r"tutorial|forum|short course|evening session|panel|plenary|keynote|special event|"
    r"session\b|index\b|author index|index to authors|sponsors?|committee|welcome|foreword|"
    r"message|preface|front ?matter|back ?matter|table of contents|contents|copyright|cover|"
    r"title page|program|conference|organizing|reviewers|technical program|executive committee|"
    r"student research preview|demonstration session|ise[- ]|women in circuits|"
    r"[FT]\d+:|SC\d|EE\d|ES\d|SE\d|F\d\.\d|T\d+\b|"
    r"introduction to|the [0-9]+(st|nd|rd|th) .* (conference|symposium)"
    r")",
    re.I,
)
NON_PAPER_ANY = re.compile(r"\b(session overview|overview of session|call for papers)\b", re.I)


def clean_title(t: str) -> str:
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    return re.sub(r"\s+", " ", t).strip()


def is_paper(item) -> bool:
    authors = item.get("author") or []
    title = clean_title((item.get("title") or [""])[0])
    if not authors or not title:
        return False
    if NON_PAPER.search(title) or NON_PAPER_ANY.search(title):
        return False
    return True


def author_name(a) -> str:
    return " ".join(x for x in (a.get("given"), a.get("family")) if x).strip() or a.get("name", "")


def main():
    papers, seen = [], set()
    dropped = []
    for conf in CONFERENCES:
        for year in YEARS:
            path = RAW / f"{conf['id']}_{year}.json"
            if not path.exists():
                continue
            for item in json.loads(path.read_text(encoding="utf-8")):
                doi = item["DOI"].lower()
                title = clean_title((item.get("title") or [""])[0])
                key = (conf["id"], year, re.sub(r"\W", "", title.lower()))
                if doi in seen or key in seen:
                    continue
                if not is_paper(item):
                    dropped.append((conf["id"], year, title))
                    continue
                seen.add(doi)
                seen.add(key)
                univs = {}
                for a in item["author"]:
                    name = author_name(a)
                    for aff in a.get("affiliation") or []:
                        slug = match(html.unescape(aff["name"]))
                        if slug:
                            univs.setdefault(slug, [])
                            if name not in univs[slug]:
                                univs[slug].append(name)
                papers.append({
                    "doi": doi,
                    "conf": conf["id"],
                    "year": year,
                    "title": title,
                    "authors": [author_name(a) for a in item["author"]],
                    "universities": univs,
                })
    out = ROOT / "data" / "papers.json"
    out.write_text(json.dumps(papers, ensure_ascii=False, indent=1), encoding="utf-8")
    (ROOT / "data" / "dropped.txt").write_text(
        "\n".join(f"{c}\t{y}\t{t}" for c, y, t in dropped), encoding="utf-8")
    jp = sum(1 for p in papers if p["universities"])
    print(f"{len(papers)} papers ({jp} with Japanese universities), {len(dropped)} non-paper items dropped")


if __name__ == "__main__":
    main()
