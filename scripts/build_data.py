"""Filter raw Crossref items into papers and attribute them to Japanese institutions.

Input : data/raw/<venue>_<year>.json   Crossref items
        data/openalex.json             affiliations missing in Crossref (fill_openalex.py)
        data/track_labels.tsv          circuits/technology labels for joint venues
Output: data/papers.json
"""
import csv
import html
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import organizations  # noqa: E402
import universities  # noqa: E402
from conferences import CONFERENCES, FETCH_YEARS, needs_track  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"

# Non-paper items that IEEE registers in the proceedings.
NON_PAPER = re.compile(
    r"^\s*("
    r"tutorial|forum|short course|evening session|panel|plenary|keynote|special event|"
    r"session\b|index\b|author index|index to authors|sponsors?|committee|welcome|foreword|"
    r"message|preface|front ?matter|back ?matter|table of contents|contents|copyright|cover|"
    r"title page|program|conference|organizing|reviewers|technical program|executive committee|"
    r"student research preview|demonstration session|ise[- ]|women in circuits|"
    r"[FT]\d+:|SC\d|EE\d|ES\d|SE\d|F\d\.\d|T\d+\b|"
    r"introduction to|the [0-9]+(st|nd|rd|th) .* (conference|symposium)|"
    # journal front matter / editorials
    r"guest editorial|editorial|corrections? to|erratum|errata|retraction|expression of concern|"
    r"information for authors|ieee journal of solid-state circuits|techrxiv|new associate editor|"
    r"introducing|together, we|new invited paper|blank page|[0-9]{4} index|in memoriam|obituary|"
    r"ieee open access|become a|get published|member get|share your preprint|"
    r"[0-9]{4} ieee (international|asian|custom|european|symposium)"
    r")",
    re.I,
)
NON_PAPER_ANY = re.compile(r"\b(session overview|overview of session|call for papers)\b", re.I)

# Fallback for joint-venue papers that have no curated label yet.
TECH_WORDS = re.compile(
    r"\b(FETs?|MOSFETs?|FinFETs?|transistors?|nanosheets?|GAA|CFET|gate[- ]all[- ]around|gate stack|"
    r"channel|MoS2|WSe2|2D material|IGZO|oxide semiconductor|ferroelectric|HZO|FeFET|anneal\w*|"
    r"TDDB|BTI|reliability|interconnect|BEOL|FEOL|contact resistance|dielectric|wafer|hybrid bonding|"
    r"EUV|lithograph\w*|epitax\w*|DTCO|platform technology|technology platform|cell technology|"
    r"device|devices|process integration|scaling|junction)\b", re.I)
CIRCUIT_WORDS = re.compile(
    r"\b(ADC|DAC|PLL|DLL|SoC|processor|accelerator|transceiver|receiver|transmitter|amplifier|LNA|"
    r"converter|regulator|LDO|macro|oscillator|synthesizer|CDR|SerDes|sensor|readout|TOPS/W|Gb/s|"
    r"pJ/b|fJ|dB|chip|IC|CIM|compute-in-memory|computing-in-memory|PUF|TRNG|interface)\b", re.I)


def clean_title(t: str) -> str:
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    return re.sub(r"\s+", " ", t).strip()


def is_paper(item) -> bool:
    title = clean_title((item.get("title") or [""])[0])
    if not item.get("author") or not title:
        return False
    return not (NON_PAPER.search(title) or NON_PAPER_ANY.search(title))


def author_name(a) -> str:
    return " ".join(x for x in (a.get("given"), a.get("family")) if x).strip() or a.get("name", "")


def norm_name(name: str) -> str:
    s = unicodedata.normalize("NFKD", name)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[.\-'’‐]", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def family_key(name: str) -> str:
    parts = norm_name(name).split()
    return parts[-1] if parts else ""


def heuristic_track(title: str) -> str:
    t, c = len(TECH_WORDS.findall(title)), len(CIRCUIT_WORDS.findall(title))
    return "T" if t > c else "C"


def load_track_labels():
    path = DATA / "track_labels.tsv"
    labels = {}
    if path.exists():
        with path.open(encoding="utf-8") as f:
            for row in csv.reader(f, delimiter="\t"):
                if len(row) >= 2 and not row[0].startswith("#"):
                    labels[row[0].lower()] = row[1]
    return labels


def openalex_affs(oa_authors, idx, name):
    """Affiliations for the idx-th Crossref author from OpenAlex authorships."""
    if not oa_authors:
        return []
    fam = family_key(name)
    if idx < len(oa_authors) and family_key(oa_authors[idx]["name"]) == fam:
        return oa_authors[idx]["affs"]
    cands = [a for a in oa_authors if family_key(a["name"]) == fam]
    return cands[0]["affs"] if len(cands) == 1 else []


def assign_author_keys(papers):
    """Merge author spellings: same ORCID -> one person; a bare name joins the ORCID
    group that uses the same normalized spelling when that group is unique."""
    spellings = defaultdict(Counter)
    orcid_by_norm = defaultdict(set)
    for p in papers:
        for a in p["authors"]:
            if a["orcid"]:
                orcid_by_norm[norm_name(a["name"])].add(a["orcid"])
    for p in papers:
        for a in p["authors"]:
            n = norm_name(a["name"])
            if a["orcid"]:
                k = "orcid:" + a["orcid"]
            elif len(orcid_by_norm.get(n, ())) == 1:
                k = "orcid:" + next(iter(orcid_by_norm[n]))
            else:
                k = "name:" + n
            a["key"] = k
            spellings[k][a["name"]] += 1
    display = {k: c.most_common(1)[0][0] for k, c in spellings.items()}
    for p in papers:
        for a in p["authors"]:
            a["display"] = display[a["key"]]
            del a["orcid"]


def main():
    openalex = {}
    if (DATA / "openalex.json").exists():
        openalex = json.loads((DATA / "openalex.json").read_text(encoding="utf-8"))
    track_labels = load_track_labels()

    papers, seen, dropped = [], set(), []
    stats = Counter()
    for conf in CONFERENCES:
        for year in FETCH_YEARS:
            path = RAW / f"{conf['id']}_{year}.json"
            if not path.exists():
                continue
            for item in json.loads(path.read_text(encoding="utf-8")):
                doi = item["DOI"].lower()
                title = clean_title((item.get("title") or [""])[0])
                key = (conf["id"], year, re.sub(r"\W", "", title.lower()))
                if doi in seen or key in seen or not doi.startswith(("10.1109/", "10.23919/")):
                    continue
                if not is_paper(item):
                    dropped.append((conf["id"], year, title))
                    continue
                seen.update((doi, key))

                authors = []
                for idx, a in enumerate(item["author"]):
                    name = author_name(a)
                    affs = [html.unescape(x["name"]) for x in a.get("affiliation") or []]
                    if not affs:
                        affs = openalex_affs(openalex.get(doi), idx, name)
                        stats["openalex_filled" if affs else "no_affiliation"] += 1
                    authors.append({
                        "name": name,
                        "orcid": (a.get("ORCID") or "").rsplit("/", 1)[-1] or None,
                        "affs": [{"u": universities.match(x), "o": organizations.match(x)} for x in affs],
                    })

                track = None
                if needs_track(conf["id"], year):
                    track = track_labels.get(doi)
                    if track is None:
                        track = heuristic_track(title)
                        stats["track_heuristic"] += 1
                papers.append({"doi": doi, "conf": conf["id"], "year": year, "title": title,
                               "track": track, "authors": authors})

    assign_author_keys(papers)
    (DATA / "papers.json").write_text(json.dumps(papers, ensure_ascii=False, indent=0), encoding="utf-8")
    (DATA / "dropped.txt").write_text("\n".join(f"{c}\t{y}\t{t}" for c, y, t in dropped), encoding="utf-8")
    jp = sum(1 for p in papers if any(f["u"] for a in p["authors"] for f in a["affs"]))
    print(f"{len(papers)} papers ({jp} with Japanese universities), {len(dropped)} non-paper items dropped")
    print(dict(stats))


if __name__ == "__main__":
    main()
