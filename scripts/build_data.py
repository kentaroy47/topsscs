"""Filter raw Crossref items into papers and attribute them to Japanese institutions.

Input : data/raw/<venue>_<year>.json   Crossref items
        data/openalex.json             OpenAlex authorships (fill_openalex.py): affiliations missing
                                       in Crossref, and institutions outside Japan
        data/track_labels.tsv          circuits/technology labels for joint venues
Output: data/papers.json, data/institutions.json

Japanese institutions come from the curated matchers (universities.py /
organizations.py) applied to Crossref affiliation strings; institutions in other
countries come from OpenAlex institution IDs.
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
import global_orgs  # noqa: E402
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


def openalex_author(oa_authors, idx, name):
    """The OpenAlex authorship of the idx-th Crossref author, or None."""
    if not oa_authors:
        return None
    fam = family_key(name)
    if idx < len(oa_authors) and family_key(oa_authors[idx]["name"]) == fam:
        return oa_authors[idx]
    cands = [a for a in oa_authors if family_key(a["name"]) == fam]
    return cands[0] if len(cands) == 1 else None


def norm_aff(aff: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", aff.lower()).strip()


def learn_aff_institutions(raw_items, openalex):
    """Affiliation string -> OpenAlex institution IDs, learned from authors that have
    exactly one Crossref affiliation and OpenAlex institutions. Used for authors whose
    OpenAlex record has no institution."""
    seen = defaultdict(Counter)
    for doi, item in raw_items:
        oa = openalex.get(doi)
        for idx, a in enumerate(item.get("author") or []):
            affs = a.get("affiliation") or []
            if len(affs) != 1:
                continue
            oa_a = openalex_author(oa, idx, author_name(a))
            if oa_a and oa_a["insts"]:
                seen[norm_aff(html.unescape(affs[0]["name"]))][tuple(sorted(i["id"] for i in oa_a["insts"]))] += 1
    table = {}
    for key, c in seen.items():
        ids, n = c.most_common(1)[0]
        if n / sum(c.values()) >= 0.6:
            table[key] = list(ids)
    return table


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
    raw_items = []
    for conf in CONFERENCES:
        for year in FETCH_YEARS:
            path = RAW / f"{conf['id']}_{year}.json"
            if path.exists():
                raw_items += [(conf["id"], year, i) for i in json.loads(path.read_text(encoding="utf-8"))]
    aff_table = learn_aff_institutions([(i["DOI"].lower(), i) for _, _, i in raw_items], openalex)
    # OpenAlex institution -> group (brand / parent company), see global_orgs.py
    lineage_path = DATA / "openalex_institutions.json"
    oa_insts = json.loads(lineage_path.read_text(encoding="utf-8")) if lineage_path.exists() else {}
    for authors in openalex.values():
        for a in authors:
            for inst in a["insts"]:
                oa_insts.setdefault(inst["id"], {"name": inst["name"], "cc": inst["cc"],
                                                 "type": inst["type"], "lineage": [inst["id"]]})
    group_of, registry = {}, {}
    for iid in oa_insts:
        g = global_orgs.canonical(iid, oa_insts)
        if g:
            group_of[iid] = g[0]
            registry[g[0]] = {"name": g[1], "cc": g[2], "type": g[3]}

    papers, seen, dropped = [], set(), []
    stats = Counter()
    for conf_id, year, item in raw_items:
        doi = item["DOI"].lower()
        title = clean_title((item.get("title") or [""])[0])
        key = (conf_id, year, re.sub(r"\W", "", title.lower()))
        if doi in seen or key in seen or not doi.startswith(("10.1109/", "10.23919/")):
            continue
        if not is_paper(item):
            dropped.append((conf_id, year, title))
            continue
        seen.update((doi, key))

        authors = []
        oa = openalex.get(doi)
        for idx, a in enumerate(item["author"]):
            name = author_name(a)
            oa_a = openalex_author(oa, idx, name)
            affs = [html.unescape(x["name"]) for x in a.get("affiliation") or []]
            if not affs:
                affs = oa_a["affs"] if oa_a else []
                stats["openalex_filled" if affs else "no_affiliation"] += 1
            # institutions outside Japan: OpenAlex IDs (Japan is covered by the curated matchers)
            ids = [i["id"] for i in oa_a["insts"]] if oa_a else []
            if not ids:
                ids = [x for aff in affs for x in aff_table.get(norm_aff(aff), [])]
                if ids:
                    stats["institution_from_string"] += 1
            groups = [group_of[x] for x in ids if x in group_of]
            abroad = [x for x in dict.fromkeys(groups) if registry[x]["cc"] != "JP"]
            authors.append({
                "name": name,
                "orcid": (a.get("ORCID") or "").rsplit("/", 1)[-1] or None,
                "affs": [{"u": universities.match(x), "o": organizations.match(x)} for x in affs],
                "x": abroad,
            })

        track = None
        if needs_track(conf_id, year):
            track = track_labels.get(doi)
            if track is None:
                track = heuristic_track(title)
                stats["track_heuristic"] += 1
        papers.append({"doi": doi, "conf": conf_id, "year": year, "title": title,
                       "track": track, "authors": authors})

    assign_author_keys(papers)
    used = {x for p in papers for a in p["authors"] for x in a["x"]}
    (DATA / "institutions.json").write_text(
        json.dumps({k: registry[k] for k in sorted(used)}, ensure_ascii=False, indent=0), encoding="utf-8")
    (DATA / "papers.json").write_text(json.dumps(papers, ensure_ascii=False, indent=0), encoding="utf-8")
    (DATA / "dropped.txt").write_text("\n".join(f"{c}\t{y}\t{t}" for c, y, t in dropped), encoding="utf-8")
    jp = sum(1 for p in papers if any(f["u"] for a in p["authors"] for f in a["affs"]))
    print(f"{len(papers)} papers ({jp} with Japanese universities), {len(dropped)} non-paper items dropped")
    print(dict(stats))


if __name__ == "__main__":
    main()
