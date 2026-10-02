"""Generate the static TopSSCS site from data/papers.json into site/ (or $SITE_DIR).

Axes: edition (live / frozen) x scope (Japan, other countries, world) x kind
(universities / companies & institutes) x counting mode (full / first author /
fractional, switched client-side). Every page carries Japanese and English text;
site.js shows one language.
"""
import datetime as dt
import html
import json
import os
import re
import shutil
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import organizations  # noqa: E402
import universities  # noqa: E402
from conferences import BY_ID, CONFERENCES, TIER_WEIGHT, weight  # noqa: E402
from conferences import EDITIONS as _EDITIONS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SITE = Path(os.environ.get("SITE_DIR") or ROOT / "site")
POINTS = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
TABLE_LIMIT = 100  # rows shown per ranking table
_FETCHED = ROOT / "data" / "fetched_at.txt"
UPDATED = _FETCHED.read_text(encoding="utf-8").strip() if _FETCHED.exists() else dt.date.today().isoformat()
# Google Analytics 4 measurement ID (GitHub Actions repository variable); no tag when unset.
GA_ID = os.environ.get("GA_MEASUREMENT_ID", "").strip()
if GA_ID and not re.fullmatch(r"G-[A-Z0-9]+", GA_ID):
    raise SystemExit(f"invalid GA_MEASUREMENT_ID: {GA_ID!r}")

EDITION_EN = {"live": "2022–2026 LIVE", "2021-2025": "2021–2025 Final"}
EDITIONS = [dict(e, en=EDITION_EN[e["id"]]) for e in _EDITIONS]

# scope: country code (None = world), path prefix, ja, en
SCOPES = [
    {"id": "jp", "cc": "JP", "path": "", "ja": "日本", "en": "Japan"},
    {"id": "us", "cc": "US", "path": "us/", "ja": "アメリカ", "en": "USA"},
    {"id": "cn", "cc": "CN", "path": "cn/", "ja": "中国", "en": "China"},
    {"id": "kr", "cc": "KR", "path": "kr/", "ja": "韓国", "en": "Korea"},
    {"id": "tw", "cc": "TW", "path": "tw/", "ja": "台湾", "en": "Taiwan"},
    {"id": "world", "cc": None, "path": "world/", "ja": "世界", "en": "World"},
]
KINDS = {
    "univ": {"prefix": "", "ja": "大学", "en": "Universities", "en1": "University"},
    "org": {"prefix": "orgs/", "ja": "企業・研究機関", "en": "Companies & Institutes", "en1": "Company / Institute"},
}
MODES = [
    ("full", "フルカウント", "Full count", "関わった機関すべてに1本ずつ", "1 per involved institution"),
    ("first", "筆頭著者", "First author", "筆頭著者の所属機関のみに1本", "1 to the first author's institutions"),
    ("frac", "著者按分", "Fractional", "1本を著者数で等分して所属に配分", "1 split evenly over authors and their affiliations"),
]
COUNTRY_NAMES = {"JP": ("日本", "Japan"), "US": ("アメリカ", "USA"), "CN": ("中国", "China"), "KR": ("韓国", "Korea"),
                 "TW": ("台湾", "Taiwan"), "DE": ("ドイツ", "Germany"), "NL": ("オランダ", "Netherlands"),
                 "BE": ("ベルギー", "Belgium"), "CH": ("スイス", "Switzerland"), "GB": ("イギリス", "UK"),
                 "SG": ("シンガポール", "Singapore"), "HK": ("香港", "Hong Kong"), "MO": ("マカオ", "Macau"),
                 "IT": ("イタリア", "Italy"), "FR": ("フランス", "France"), "CA": ("カナダ", "Canada"),
                 "IN": ("インド", "India"), "IL": ("イスラエル", "Israel")}
# categorical slots 1-6 of the validated reference palette, in fixed order (see src/style.css)
SERIES = ["isscc", "vlsi", "jssc", "cicc", "asscc", "esscirc"]

esc = html.escape


def T(ja, en):
    """Bilingual inline text; CSS shows one side."""
    if ja == en:
        return ja
    return f'<span class="l-ja">{ja}</span><span class="l-en" lang="en">{en}</span>'


def country_name(cc):
    ja, en = COUNTRY_NAMES.get(cc, (cc, cc))
    return T(ja, en)


# --------------------------------------------------------------- entities ---

def slugify(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def build_registry():
    """eid -> {kind, cc, ja, en, slug}."""
    reg, used = {}, set()

    def add(eid, kind, cc, ja, en, slug):
        base = slug or eid.lower()
        slug = base if base not in used else f"{base}-{eid.lower().replace(':', '-')}"
        used.add(slug)
        reg[eid] = {"kind": kind, "cc": cc, "ja": ja, "en": en, "slug": slug}

    for slug, (ja, en) in universities.BY_SLUG.items():
        add("u:" + slug, "univ", "JP", ja, en, slug)
    for slug, (ja, en) in organizations.BY_SLUG.items():
        add("o:" + slug, "org", "JP", ja, en, slug)
    insts = json.loads((ROOT / "data" / "institutions.json").read_text(encoding="utf-8"))
    for iid, inst in sorted(insts.items(), key=lambda kv: kv[1]["name"]):
        kind = "univ" if inst["type"] == "education" else "org"
        add(iid, kind, inst["cc"], inst["name"], inst["name"], slugify(inst["name"]))
    return reg


REG = {}


def author_entities(a):
    eids = []
    for f in a["affs"]:
        if f["u"]:
            eids.append("u:" + f["u"])
        if f["o"]:
            eids.append("o:" + f["o"])
    eids += a.get("x", [])
    return list(dict.fromkeys(eids))


def attach_credits(p):
    """p["c"][mode] = {eid: credit}, all institutions of every country and kind."""
    ents = [author_entities(a) for a in p["authors"]]
    full = {e: 1.0 for es in ents for e in es}
    first = {e: 1.0 for e in ents[0]} if ents else {}
    frac = defaultdict(float)
    n = len(ents)
    for es in ents:
        for e in es:
            frac[e] += 1.0 / n / len(es)
    p["c"] = {"full": full, "first": first, "frac": dict(frac)}
    p["ents"] = ents


def in_scope(eid, scope, kind):
    e = REG[eid]
    return e["kind"] == kind and (scope["cc"] is None or e["cc"] == scope["cc"])


def ename(eid):
    e = REG[eid]
    return T(esc(e["ja"]), esc(e["en"]))


# ---------------------------------------------------------------- ranking ---

def competition_rank(values):
    """values sorted desc -> standard competition ranks (1, 2, 2, 4)."""
    ranks, prev, rank = [], None, 0
    for i, v in enumerate(values, 1):
        rv = round(v, 6)
        if rv != prev:
            rank, prev = i, rv
        ranks.append(rank)
    return ranks


def tally(papers, scope, kind, mode):
    c = Counter()
    for p in papers:
        for e, v in p["c"][mode].items():
            if in_scope(e, scope, kind):
                c[e] += v
    return c


def rank_rows(counter):
    rows = sorted(((e, v) for e, v in counter.items() if v > 1e-9), key=lambda kv: (-round(kv[1], 6), REG[kv[0]]["en"]))
    ranks = competition_rank([v for _, v in rows])
    return [{"eid": e, "count": v, "rank": r} for (e, v), r in zip(rows, ranks)]


def points_for(rank, conf):
    return (POINTS[rank - 1] if rank <= len(POINTS) else 0) * weight(conf)


def championship(by_conf_counts):
    total, per_conf = Counter(), {}
    for c, counter in by_conf_counts.items():
        table = rank_rows(counter)
        per_conf[c] = {r["eid"]: r for r in table}
        for r in table:
            total[r["eid"]] += points_for(r["rank"], c)
    rows = sorted(total.items(), key=lambda kv: (-round(kv[1], 6), REG[kv[0]]["en"]))
    ranks = competition_rank([v for _, v in rows])
    return [{"eid": e, "points": v, "rank": r} for (e, v), r in zip(rows, ranks)], per_conf


def fmt_count(v, mode):
    return f"{v:.2f}" if mode == "frac" else f"{round(v):d}"


def fmt(x):
    return f"{round(x, 2):g}"


def wfmt(w):
    return f"{w:.1f}"


# ------------------------------------------------------------------- html ---

class Page:
    def __init__(self, path):
        self.path = path
        self.depth = path.count("/")

    def href(self, target):
        return "../" * self.depth + target


def analytics_tag():
    if not GA_ID:
        return ""
    return (f'<script async src="https://www.googletagmanager.com/gtag/js?id={GA_ID}"></script>\n'
            "<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}"
            f"gtag('js',new Date());gtag('config','{GA_ID}');</script>\n")


# Runs before first paint so the chosen language never flashes.
LANG_BOOT = ("<script>(function(){var l=new URLSearchParams(location.search).get('lang');"
             "if(l==='en'||l==='ja'){try{localStorage.setItem('topsscs-lang',l);}catch(e){}}"
             "else{try{l=localStorage.getItem('topsscs-lang');}catch(e){}}"
             "if(l==='en'){document.documentElement.setAttribute('data-lang','en');"
             "document.documentElement.lang='en';}})();</script>")


def layout(pg, title_ja, title_en, body):
    h = pg.href
    creator = '<a href="https://github.com/kentaroy47" lang="en">Kentaro Yoshioka</a>'
    desc_ja = ("TopSSCSは、ISSCC・VLSI・JSSC・CICC・A-SSCC・ESSERCの論文数をもとに、"
               "大学・企業の集積回路研究を国別・世界で比較できるランキングサイトです。")
    return f"""<!DOCTYPE html>
<html lang="ja" data-title-en="{esc(title_en)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title_ja)}</title>
{LANG_BOOT}
<meta name="description" content="{esc(desc_ja)}">
<meta property="og:title" content="{esc(title_ja)}">
<meta property="og:description" content="{esc(desc_ja)}">
{analytics_tag()}<link rel="stylesheet" href="{h('assets/style.css')}">
<script src="{h('assets/site.js')}" defer></script>
</head>
<body>
<a class="skip-link" href="#main">{T("本文へ移動", "Skip to content")}</a>
<header class="site-header"><div class="header-inner">
<a class="brand" href="{h('index.html')}" aria-label="TopSSCS">Top<span>SSCS</span></a>
<nav aria-label="Main"><a href="{h('index.html')}">{T("ランキング", "Rankings")}</a><a href="{h('methodology.html')}">{T("集計方法", "Methodology")}</a>
<button type="button" class="lang-toggle" data-lang-toggle aria-label="Switch to English"><span class="l-ja" lang="en">EN</span><span class="l-en" lang="ja">日本語</span></button></nav>
</div></header>
<main id="main" class="page-shell">
{body}
</main>
<footer class="site-footer">
<p><strong>TopSSCS</strong> {T("固体回路系トップ国際会議・論文誌における大学・企業の論文活動を可視化",
                              "Paper activity of universities and companies at top solid-state circuits venues")}</p>
<p>Data: Crossref / OpenAlex · Updated {UPDATED} · <a href="{h('methodology.html')}">{T("集計ルール", "Methodology")}</a></p>
<p class="footer-disclaimer">{T(
    f"本サイトは {creator} がAIを活用して作成しました。内容には誤りが含まれる可能性があります。正確な情報は原論文・公式情報をご確認ください。",
    f"Created by {creator} with the assistance of AI. This site may contain errors. Please verify information against the original papers and official sources.")}</p>
</footer>
</body>
</html>
"""


def intro(scope, kind):
    k = KINDS[kind]
    if scope["cc"] is None:
        who = T(f"世界の{k['ja']}が競う", f"{k['en']} worldwide compete")
    else:
        who = T(f"{scope['ja']}の{k['ja']}が競う", f"{k['en']} in {scope['en']} compete")
    return f"""<section class="page-intro">
<h1>{T("集積回路研究を、競争でもっと面白く。", "Making IC research more fun through competition.")}</h1>
<p class="lede">{T("固体回路系トップ国際会議・論文誌（ISSCC・VLSI・JSSC・CICC・A-SSCC・ESSERC）の論文数をもとに",
                  "A scoreboard where ")}{who}{T("スコアボード",
                  ", based on papers at the top solid-state circuits venues (ISSCC, VLSI, JSSC, CICC, A-SSCC, ESSERC).")}</p>
</section>"""


def rank_cell(rank):
    return f'<td class="{"rank top-rank" if rank <= 3 else "rank"}">{rank}</td>'


def change_badge(cur_rank, prev_rank):
    if prev_rank is None:
        return '<span class="badge new">NEW</span>'
    d = prev_rank - cur_rank
    if d > 0:
        return f'<span class="up">↑{d}</span>'
    if d < 0:
        return f'<span class="down">↓{-d}</span>'
    return '<span class="flat">→</span>'


def delta(n, mode):
    if abs(n) < 1e-9:
        return '<span class="delta">±0</span>'
    s = fmt(abs(n)) if mode == "points" else fmt_count(abs(n), mode)
    return f'<span class="delta {"increase" if n > 0 else "decrease"}">{"+" if n > 0 else "−"}{s}</span>'


def tier_summary(confs):
    parts = []
    for t, w in sorted(TIER_WEIGHT.items()):
        names = [BY_ID[c]["short"] for c in confs if BY_ID[c]["tier"] == t]
        if names:
            parts.append(f'Tier {t} ×{wfmt(w)}: {esc(", ".join(names))}')
    return " · ".join(parts)


def mode_panels(render):
    """render(mode) for each counting mode; site.js shows the selected one."""
    return "\n".join(f'<div class="mode-panel" data-mode="{m}"{"" if m == "full" else " hidden"}>{render(m)}</div>'
                     for m, *_ in MODES)


def write(path, text):
    p = SITE / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def truncated_note(n_all):
    if n_all <= TABLE_LIMIT:
        return ""
    return f'<p class="status">{T(f"上位{TABLE_LIMIT}件を表示（全{n_all}件）", f"Top {TABLE_LIMIT} of {n_all} shown")}</p>'


# ------------------------------------------------------------------ edition -

class Edition:
    """All computed data for one edition."""

    def __init__(self, papers, ed):
        self.ed = ed
        self.papers = [p for p in papers if p["year"] in ed["years"]]
        self.ry = defaultdict(set)
        for p in self.papers:
            self.ry[p["conf"]].add(p["year"])
        self.confs = [c["id"] for c in CONFERENCES if c["id"] in self.ry]
        self.by_conf = {c: [p for p in self.papers if p["conf"] == c] for c in self.confs}
        self.by_entity = defaultdict(list)
        for p in self.papers:
            for e in p["c"]["full"]:
                self.by_entity[e].append(p)
        self.shown = set()  # entities appearing in any displayed table -> get detail pages
        self.cache = {}

    def latest_overall(self):
        y, _, c = max((max(self.ry[c]), BY_ID[c]["month"], c) for c in self.confs if BY_ID[c]["kind"] == "conference")
        return c, y

    def champ(self, scope, kind, mode, exclude=None):
        key = ("champ", scope["id"], kind, mode, exclude)
        if key not in self.cache:
            counts = {}
            for c in self.confs:
                ps = self.by_conf[c]
                if exclude:
                    ps = [p for p in ps if (p["conf"], p["year"]) != exclude]
                counts[c] = tally(ps, scope, kind, mode)
            self.cache[key] = championship(counts)
        return self.cache[key]

    def conf_rows(self, conf, scope, kind, mode, exclude_year=None):
        key = ("conf", conf, scope["id"], kind, mode, exclude_year)
        if key not in self.cache:
            ps = [p for p in self.by_conf[conf] if p["year"] != exclude_year]
            self.cache[key] = rank_rows(tally(ps, scope, kind, mode))
        return self.cache[key]


# ------------------------------------------------------------------- pages --

def scope_path(ed, scope, kind, rel):
    return ed["path"] + scope["path"] + KINDS[kind]["prefix"] + rel


def inst_path(ed, eid, conf=None):
    return f'{ed["path"]}inst/{REG[eid]["slug"]}/' + (f"{conf}/" if conf else "") + "index.html"


def controls(pg, E, scope, kind, current):
    ed = E.ed
    rel = "index.html" if current == "all" else f"{current}/index.html"
    out = ['<div class="switches">', f'<nav class="scope-switch" aria-label="Country">']
    for s in SCOPES:
        cur = ' aria-current="true"' if s["id"] == scope["id"] else ""
        out.append(f'<a href="{pg.href(scope_path(ed, s, kind, rel))}"{cur}>{T(s["ja"], s["en"])}</a>')
    out.append("</nav></div><div class=\"switches\">")
    out.append('<nav class="entity-switch" aria-label="Kind">')
    for k, meta in KINDS.items():
        cur = ' aria-current="true"' if k == kind else ""
        out.append(f'<a href="{pg.href(scope_path(ed, scope, k, rel))}"{cur}>{T(meta["ja"], meta["en"])}</a>')
    out.append("</nav>")
    out.append('<label class="edition-selector">Edition <select data-nav>')
    for e in EDITIONS:
        sel = " selected" if e["id"] == ed["id"] else ""
        out.append(f'<option value="{pg.href(scope_path(e, scope, kind, rel))}" data-ja="{esc(e["label"])}" '
                   f'data-en="{esc(e["en"])}"{sel}>{esc(e["label"])}</option>')
    out.append("</select></label>")
    out.append('<div class="mode-switch" role="radiogroup" aria-label="Counting">')
    for m, ja, en, hja, hen in MODES:
        checked = "true" if m == "full" else "false"
        out.append(f'<button type="button" role="radio" aria-checked="{checked}" data-mode="{m}" '
                   f'title="{esc(hja)} / {esc(hen)}">{T(ja, en)}</button>')
    out.append("</div></div>")
    cur_all = ' aria-current="true"' if current == "all" else ""
    out.append('<nav class="field-tabs" aria-label="Venue">')
    out.append(f'<a class="field-tab championship-tab" href="{pg.href(scope_path(ed, scope, kind, "index.html"))}"{cur_all}>'
               f'{T("総合", "Overall")}</a>')
    prev_tier = None
    for c in CONFERENCES:
        if c["tier"] != prev_tier:
            out.append(f'<span class="tier-tag">Tier {c["tier"]}</span>')
            prev_tier = c["tier"]
        cur = ' aria-current="true"' if current == c["id"] else ""
        out.append(f'<a class="field-tab" href="{pg.href(scope_path(ed, scope, kind, c["id"] + "/index.html"))}"{cur} '
                   f'lang="en">{esc(c["short"])}</a>')
    out.append("</nav>")
    return "\n".join(out)


def live_status(E, conf=None):
    if not E.ed["live"]:
        return ""
    last = max(E.ed["years"])
    confs = [conf] if conf else E.confs
    done = [BY_ID[c]["short"] for c in confs if last in E.ry[c]]
    todo = [BY_ID[c]["short"] for c in confs if last not in E.ry[c]]
    parts = []
    if done:
        parts.append(f'<p><strong>{last} reflected:</strong> {", ".join(done)}</p>')
    if todo:
        lo = min(E.ed["years"])
        parts.append(f'<p><strong>Not yet reflected:</strong> {", ".join(todo)}'
                     f'{T(f"（{lo}–{last - 1}を集計）", f" ({lo}–{last - 1} counted)")}</p>')
    return f'<div class="live-status">{"".join(parts)}</div>'


def entity_link(pg, E, eid, conf=None, show_cc=False):
    """Link to an institution page (registers the page for generation)."""
    E.shown.add(eid)
    link = f'<a class="university-link" href="{pg.href(inst_path(E.ed, eid, conf))}">{ename(eid)}</a>'
    if show_cc and REG[eid]["cc"]:
        link += f' <span class="cc">{esc(REG[eid]["cc"])}</span>'
    return link


def build_index(E, scope, kind):
    ed = E.ed
    pg = Page(scope_path(ed, scope, kind, "index.html"))
    live = ed["live"]
    lc, ly = E.latest_overall()
    k = KINDS[kind]
    world = scope["cc"] is None

    def render(mode):
        rows, per_conf = E.champ(scope, kind, mode)
        prev = {r["eid"]: r for r in E.champ(scope, kind, mode, exclude=(lc, ly))[0]} if live else {}
        trs = []
        for r in rows[:TABLE_LIMIT]:
            e = r["eid"]
            link = entity_link(pg, E, e, show_cc=world)
            tail, pts = "", fmt(r["points"])
            if live:
                p = prev.get(e)
                tail = f'<td class="rank-change">{change_badge(r["rank"], p["rank"] if p else None)}</td>'
                pts += delta(r["points"] - (p["points"] if p else 0), "points")
            trs.append(f'<tr>{rank_cell(r["rank"])}<td>{link}</td><td class="numeric">{pts}</td>{tail}</tr>')
        head_prev = f'<th scope="col" class="rank-change">{T("前回", "Prev")}</th>' if live else ""
        table = (f'<div class="table-wrap"><table class="ranking-table"><thead><tr>'
                 f'<th scope="col">{T("順位", "Rank")}</th><th scope="col">{T(k["ja"], k["en1"])}</th>'
                 f'<th scope="col" class="numeric">{T("ポイント", "Points")}</th>{head_prev}</tr></thead>'
                 f'<tbody>{"".join(trs)}</tbody></table></div>{truncated_note(len(rows))}')
        head = "".join(f'<th class="numeric" lang="en">{esc(BY_ID[c]["short"])}<span class="tier-label">'
                       f'Tier {BY_ID[c]["tier"]} ×{wfmt(weight(c))}</span></th>' for c in E.confs)
        brs = []
        for r in rows[:min(TABLE_LIMIT, 50)]:
            e = r["eid"]
            cells = []
            for c in E.confs:
                x = per_conf[c].get(e)
                if x:
                    pv = points_for(x["rank"], c)
                    cells.append(f'<td class="numeric{" scored" if pv else ""}"><span class="bd-rank">#{x["rank"]}</span>'
                                 f'<span class="bd-pts">{fmt(pv)}pt</span><span class="bd-n">{fmt_count(x["count"], mode)}'
                                 f'{T("本", "")}</span></td>')
                else:
                    cells.append('<td class="numeric muted">–</td>')
            brs.append(f'<tr>{rank_cell(r["rank"])}<td>{ename(e)}</td>{"".join(cells)}'
                       f'<td class="numeric">{fmt(r["points"])}</td></tr>')
        bd = (f'<section class="breakdown"><div class="ranking-head"><div><h2>{T("会議・論文誌別内訳", "Breakdown by venue")}</h2>'
              f'<p class="ranking-context">{T("各会議・論文誌での順位・獲得ポイント（重み適用後）・論文数", "Rank, points (weighted) and papers per venue")}'
              f'</p></div></div><div class="table-wrap"><table class="championship-breakdown"><thead><tr>'
              f'<th scope="col">{T("順位", "Rank")}</th><th scope="col">{T(k["ja"], k["en1"])}</th>{head}'
              f'<th scope="col" class="numeric">{T("合計", "Total")}</th></tr></thead>'
              f'<tbody>{"".join(brs)}</tbody></table></div></section>')
        return table + bd

    rows_full = E.champ(scope, kind, "full")[0]
    note_prev = (T(f"「前回」は {BY_ID[lc]['short']} {ly} 反映前との比較です。",
                   f"“Prev” compares with the ranking before {BY_ID[lc]['short']} {ly} was added.") if live
                 else T("確定版は期間を固定した集計です。", "The final edition is a frozen five-year window."))
    latest = f" · Latest: {esc(BY_ID[lc]['short'])} {ly} added" if live else ""
    title_scope = T(f"{scope['ja']}の{k['ja']}総合ランキング", f"{k['en']} in {scope['en']}: overall ranking") \
        if not world else T(f"世界の{k['ja']}総合ランキング", f"World {k['en'].lower()}: overall ranking")
    body = f"""{intro(scope, kind)}
{controls(pg, E, scope, kind, "all")}
<section class="ranking-card" aria-labelledby="ranking-title">
<div class="ranking-head"><div>
<p class="eyebrow">{T(esc(ed["label"]), esc(ed["en"]))} · {tier_summary(E.confs)}</p>
<h2 id="ranking-title">{title_scope}</h2>
<p class="ranking-context">Updated: {UPDATED}{latest}</p>
</div><p class="record-count">{len(rows_full)}</p></div>
{live_status(E)}
{mode_panels(render)}
<p class="status">{T("会議・論文誌ごとの順位をF1方式でポイント化し、Tierの重みを掛けて合計したランキングです。",
                    "Venue ranks are converted to F1-style points, weighted by tier, and summed. ")}{note_prev}
<a href="{pg.href('methodology.html#championship')}">{T("集計ルール", "Methodology")}</a></p>
</section>"""
    tja = f"TopSSCS | {scope['ja']} {k['ja']}総合ランキング {ed['label']}"
    ten = f"TopSSCS | {k['en']} in {scope['en']}: overall {ed['en']}"
    write(pg.path, layout(pg, tja, ten, body))


def build_conf(E, scope, kind, conf):
    ed = E.ed
    c = BY_ID[conf]
    k = KINDS[kind]
    pg = Page(scope_path(ed, scope, kind, conf + "/index.html"))
    live = ed["live"]
    ps = E.by_conf[conf]
    ly = max(E.ry[conf])
    world = scope["cc"] is None
    involved = [p for p in ps if any(in_scope(e, scope, kind) for e in p["c"]["full"])]

    def render(mode):
        table = E.conf_rows(conf, scope, kind, mode)
        prev = {r["eid"]: r for r in E.conf_rows(conf, scope, kind, mode, exclude_year=ly)} if live else {}
        trs = []
        for r in table[:TABLE_LIMIT]:
            e = r["eid"]
            link = entity_link(pg, E, e, conf, show_cc=world)
            tail, cnt = "", fmt_count(r["count"], mode)
            if live:
                p = prev.get(e)
                cnt += delta(r["count"] - (p["count"] if p else 0), mode)
                tail = f'<td class="rank-change">{change_badge(r["rank"], p["rank"] if p else None)}</td>'
            trs.append(f'<tr>{rank_cell(r["rank"])}<td>{link}</td><td class="numeric">{cnt}</td>{tail}</tr>')
        if not trs:
            return f'<p class="empty">{T("該当する論文はまだありません。", "No papers yet.")}</p>'
        head_prev = f'<th scope="col" class="rank-change">{T("前回", "Prev")}</th>' if live else ""
        return (f'<div class="table-wrap"><table class="ranking-table"><thead><tr>'
                f'<th scope="col">{T("順位", "Rank")}</th><th scope="col">{T(k["ja"], k["en1"])}</th>'
                f'<th scope="col" class="numeric">{T("論文数", "Papers")}</th>{head_prev}</tr></thead>'
                f'<tbody>{"".join(trs)}</tbody></table></div>{truncated_note(len(table))}')

    per_year = Counter(p["year"] for p in ps)
    per_year_in = Counter(p["year"] for p in involved)
    yrs = " · ".join(f"{y}: {per_year_in[y]}/{per_year[y]}" for y in sorted(E.ry[conf]))
    track_note = T(f" · {c['joint_from']}年以降は回路系トラックのみ", f" · circuits track only from {c['joint_from']}") \
        if c.get("joint_from") else ""
    latest = f" · Latest: {esc(c['short'])} {ly} added" if live else ""
    prev_note = T(f"「前回」は {c['short']} {ly} 反映前との比較です。", f"“Prev” compares with the ranking before {c['short']} {ly}.") \
        if live else ""
    where = T("世界", "worldwide") if world else T(scope["ja"], scope["en"])
    body = f"""{intro(scope, kind)}
{controls(pg, E, scope, kind, conf)}
<section class="ranking-card" aria-labelledby="ranking-title">
<div class="ranking-head"><div>
<p class="eyebrow">Tier {c["tier"]} · {T("総合ポイント", "overall points")} ×{wfmt(weight(conf))}</p>
<h2 id="ranking-title"><span lang="en">{esc(c["short"])}</span> · {where} · {T(k["ja"], k["en"])}</h2>
<p class="ranking-context">{T(esc(ed["label"]), esc(ed["en"]))} · <a href="{c["url"]}" lang="en">{esc(c["name"])}</a> · {len(ps):,} papers{track_note}
<span class="japan-paper-presence">（{T("関与論文", "involved")} {len(involved)} · {100 * len(involved) / max(1, len(ps)):.2f}%）</span></p>
<p class="ranking-context">Updated: {UPDATED}{latest} · {T("年別（関与/全体）", "by year (involved/all)")}: {yrs}</p>
</div></div>
{live_status(E, conf)}
{mode_panels(render)}
<p class="status">{T("名前から、所属著者と論文の内訳を確認できます。", "Follow a name for its authors and papers. ")}{prev_note}</p>
</section>"""
    tja = f"{c['short']} {scope['ja']} {k['ja']}ランキング {ed['label']} | TopSSCS"
    ten = f"{c['short']} {k['en']} ranking, {scope['en']} {ed['en']} | TopSSCS"
    write(pg.path, layout(pg, tja, ten, body))


def paper_item(p, eid):
    c = BY_ID[p["conf"]]
    names = []
    for a, es in zip(p["authors"], p["ents"]):
        n = esc(a["name"])
        names.append(f"<strong>{n}</strong>" if eid in es else n)
    insts = [ename(e) for e in dict.fromkeys(e for es in p["ents"] for e in es)]
    return f"""<li class="paper-item">
<div class="paper-meta"><span lang="en">{esc(c["short"])}</span><br>{p["year"]}</div>
<div><a class="paper-title" href="https://doi.org/{esc(p["doi"])}" lang="en">{esc(p["title"])}</a></div>
<a class="doi-link" href="https://doi.org/{esc(p["doi"])}">DOI</a>
<div class="paper-coauthors" lang="en">{", ".join(names)}</div>
<div class="paper-univs">{" · ".join(insts)}</div>
</li>"""


def scope_for(eid):
    cc = REG[eid]["cc"]
    return next((s for s in SCOPES if s["cc"] == cc), None)


def standing(E, eid, conf=None):
    """[(scope label, rank)] in the institution's own country (if listed) and the world, full count."""
    kind = REG[eid]["kind"]
    out = []
    for s in [scope_for(eid), SCOPES[-1]]:
        if s is None:
            continue
        if conf:
            rows = {r["eid"]: r for r in E.conf_rows(conf, s, kind, "full")}
        else:
            rows = {r["eid"]: r for r in E.champ(s, kind, "full")[0]}
        r = rows.get(eid)
        if r:
            out.append((T(s["ja"], s["en"]), r))
    return out


def build_entity(E, eid):
    ed = E.ed
    e = REG[eid]
    pg = Page(inst_path(ed, eid))
    ps = sorted(E.by_entity[eid], key=lambda p: (-p["year"], p["conf"], p["title"]))
    kind = e["kind"]
    st = " · ".join(f'{label} <strong>{r["rank"]}</strong>{T("位", "")} ({fmt(r["points"])} pt)' for label, r in standing(E, eid))
    trs = []
    for c in CONFERENCES:
        cid = c["id"]
        cps = [p for p in ps if p["conf"] == cid]
        label = esc(c["short"])
        if cps:
            label = f'<a href="{pg.href(inst_path(ed, eid, cid))}">{label}</a>'
        cnt = {m: sum(p["c"][m].get(eid, 0) for p in cps) for m, *_ in MODES}
        ranks = []
        if cps:
            for s in [scope_for(eid), SCOPES[-1]]:
                if s is None:
                    continue
                r = {x["eid"]: x for x in E.conf_rows(cid, s, kind, "full")}.get(eid)
                ranks.append(f'{T(s["ja"], s["en"])} #{r["rank"]}' if r else "")
        trs.append(f'<tr><td lang="en">{label} <span class="tier-label">Tier {c["tier"]}</span></td>'
                   f'<td class="numeric">{fmt_count(cnt["full"], "full")}</td>'
                   f'<td class="numeric">{fmt_count(cnt["first"], "first")}</td>'
                   f'<td class="numeric">{fmt_count(cnt["frac"], "frac")}</td>'
                   f'<td class="numeric">{" · ".join(x for x in ranks if x) or "–"}</td></tr>')
    items = "\n".join(paper_item(p, eid) for p in ps)
    sc = scope_for(eid) or SCOPES[-1]
    back = pg.href(scope_path(ed, sc, kind, "index.html"))
    body = f"""<a class="back-link" href="{back}">← {T("総合ランキングへ戻る", "Back to overall ranking")}</a>
<section class="detail-heading">
<p class="eyebrow">{T(KINDS[kind]["ja"], KINDS[kind]["en1"])} · {country_name(e["cc"])} · {T(esc(ed["label"]), esc(ed["en"]))}</p>
<h1>{ename(eid)}</h1>
{f'<p class="lede l-ja" lang="en">{esc(e["en"])}</p>' if e["ja"] != e["en"] else ""}
<p class="stat-line">{st}{" · " if st else ""}{T("対象論文", "Papers")} <strong>{len(ps)}</strong></p>
</section>
<section>
<div class="ranking-head"><div><h2>{T("年別の推移", "Papers per year")}</h2>
<p class="ranking-context">{T("会議・論文誌別の論文数（フルカウント）", "Papers per venue (full count)")}</p></div></div>
{trend_chart(ps, sorted(ed["years"]))}
</section>
<section>
<div class="ranking-head"><div><h2>{T("会議・論文誌別", "By venue")}</h2>
<p class="ranking-context">{T("順位はフルカウントでの値です。", "Ranks use the full count.")}</p></div></div>
<div class="table-wrap"><table class="univ-table">
<thead><tr><th scope="col">{T("会議・論文誌", "Venue")}</th><th scope="col" class="numeric">{T("フル", "Full")}</th>
<th scope="col" class="numeric">{T("筆頭", "First")}</th><th scope="col" class="numeric">{T("按分", "Frac.")}</th>
<th scope="col" class="numeric">{T("順位", "Rank")}</th></tr></thead>
<tbody>{"".join(trs)}</tbody></table></div>
</section>
<section class="papers">
<div class="ranking-head"><div><h2>{T("対象論文", "Papers")}</h2>
<p class="ranking-context">{T("太字はこの機関の所属として確認できた著者です。", "Bold: authors affiliated with this institution.")}</p></div></div>
<ol class="paper-list">
{items}
</ol>
</section>"""
    write(pg.path, layout(pg, f"{e['ja']} | TopSSCS", f"{e['en']} | TopSSCS", body))
    for cid in {p["conf"] for p in ps}:
        build_entity_conf(E, eid, cid, [p for p in ps if p["conf"] == cid])


def build_entity_conf(E, eid, conf, ps):
    ed = E.ed
    c = BY_ID[conf]
    pg = Page(inst_path(ed, eid, conf))
    authors, disp = Counter(), {}
    for p in ps:
        for a in {a["key"]: a for a, es in zip(p["authors"], p["ents"]) if eid in es}.values():
            authors[a["key"]] += 1
            disp[a["key"]] = a["display"]
    rows = sorted(authors.items(), key=lambda kv: (-kv[1], disp[kv[0]]))
    ranks = competition_rank([v for _, v in rows])
    orcid_tag = ' <span class="orcid">ORCID</span>'
    trs = "".join(f'<tr>{rank_cell(r)}<td lang="en"><span class="author-link">{esc(disp[a])}</span>'
                  f'{orcid_tag if a.startswith("orcid:") else ""}</td>'
                  f'<td class="numeric">{n}</td></tr>' for (a, n), r in zip(rows, ranks))
    cnt = {m: sum(p["c"][m].get(eid, 0) for p in ps) for m, *_ in MODES}
    st = " · ".join(f'{label} #{r["rank"]}' for label, r in standing(E, eid, conf))
    items = "\n".join(paper_item(p, eid) for p in sorted(ps, key=lambda p: (-p["year"], p["title"])))
    body = f"""<a class="back-link" href="{pg.href(inst_path(ed, eid))}">← {ename(eid)}</a>
<section class="detail-heading">
<p class="eyebrow"><span lang="en">{esc(c["short"])}</span> · {T(esc(ed["label"]), esc(ed["en"]))}</p>
<h1>{ename(eid)}</h1>
<p class="stat-line">{T("対象論文", "Papers")} <strong>{len(ps)}</strong> <span class="stat-detail">· {T("筆頭著者", "first author")} {fmt_count(cnt["first"], "first")} · {T("著者按分", "fractional")} {fmt_count(cnt["frac"], "frac")}{" · " + st if st else ""}</span></p>
</section>
<section>
<div class="ranking-head"><div><h2>{T("所属著者", "Affiliated authors")}</h2>
<p class="ranking-context">{T("ORCID が一致する著者は同一人物としてまとめています。それ以外は表記ごとに別人として扱います。",
                              "Authors sharing an ORCID are merged; other spellings are listed separately.")}</p></div></div>
<div class="table-wrap"><table class="ranking-table">
<thead><tr><th scope="col">{T("順位", "Rank")}</th><th scope="col">{T("著者", "Author")}</th><th scope="col" class="numeric">{T("論文数", "Papers")}</th></tr></thead>
<tbody>{trs}</tbody></table></div>
</section>
<section class="papers">
<div class="ranking-head"><div><h2>{T("対象論文", "Papers")}</h2></div></div>
<ol class="paper-list">
{items}
</ol>
</section>"""
    write(pg.path, layout(pg, f"{REG[eid]['ja']} × {c['short']} | TopSSCS", f"{REG[eid]['en']} × {c['short']} | TopSSCS", body))


# ------------------------------------------------------------------- chart --

def trend_chart(papers, years):
    """Stacked bars: papers per year, one segment per venue (fixed palette order)."""
    counts = {y: Counter(p["conf"] for p in papers if p["year"] == y) for y in years}
    series = [c for c in SERIES if any(counts[y][c] for y in years)]
    ymax = max([sum(counts[y].values()) for y in years] + [1])
    step = next(s for s in (1, 2, 5, 10, 20, 50, 100, 200) if ymax / s <= 6)
    top = ((ymax + step - 1) // step) * step
    W, H, L, R, Tp, B = 560, 220, 34, 8, 16, 26
    pw, ph = W - L - R, H - Tp - B
    bw = min(56, pw / len(years) * 0.56)
    out = [f'<figure class="trend"><svg viewBox="0 0 {W} {H}" role="img" aria-label="papers per year and venue">']
    for v in range(0, top + 1, step):
        y = Tp + ph - ph * v / top
        out.append(f'<line class="grid" x1="{L}" x2="{W - R}" y1="{y:.1f}" y2="{y:.1f}"/>'
                   f'<text class="axis" x="{L - 6}" y="{y + 4:.1f}" text-anchor="end">{v}</text>')
    for i, yr in enumerate(years):
        cx = L + pw * (i + 0.5) / len(years)
        x = cx - bw / 2
        base = Tp + ph
        segs = [(c, counts[yr][c]) for c in series if counts[yr][c]]
        for j, (c, n) in enumerate(segs):
            h = ph * n / top
            y0 = base - h
            tip = f"{yr} {BY_ID[c]['short']}: {n}"
            if j == len(segs) - 1:  # top segment: 4px rounded data end
                r = min(4, h)
                d = (f"M{x:.1f},{base:.1f} V{y0 + r:.1f} Q{x:.1f},{y0:.1f} {x + r:.1f},{y0:.1f} "
                     f"H{x + bw - r:.1f} Q{x + bw:.1f},{y0:.1f} {x + bw:.1f},{y0 + r:.1f} V{base:.1f} Z")
                out.append(f'<path class="seg s-{c}" d="{d}"><title>{tip}</title></path>')
            else:  # 2px surface gap above each lower segment
                out.append(f'<rect class="seg s-{c}" x="{x:.1f}" y="{y0 + 2:.1f}" width="{bw:.1f}" '
                           f'height="{max(h - 2, 0.5):.1f}"><title>{tip}</title></rect>')
            base = y0
        total = sum(n for _, n in segs)
        if total:
            out.append(f'<text class="bar-total" x="{cx:.1f}" y="{base - 5:.1f}" text-anchor="middle">{total}</text>')
        out.append(f'<text class="axis" x="{cx:.1f}" y="{H - 8}" text-anchor="middle">{yr}</text>')
    out.append("</svg>")
    out.append('<figcaption class="legend">' + "".join(
        f'<span><i class="s-{c}"></i>{esc(BY_ID[c]["short"])}</span>' for c in series) + "</figcaption>")
    head = "".join(f'<th class="numeric">{y}</th>' for y in years)
    rows = "".join(f'<tr><td lang="en">{esc(BY_ID[c]["short"])}</td>' +
                   "".join(f'<td class="numeric">{counts[y][c] or "–"}</td>' for y in years) + "</tr>" for c in series)
    out.append(f'<details class="trend-table"><summary>{T("数値表を表示", "Show table")}</summary><div class="table-wrap"><table>'
               f'<thead><tr><th>{T("会議・論文誌", "Venue")}</th>{head}</tr></thead><tbody>{rows}</tbody></table></div></details>')
    out.append("</figure>")
    return "".join(out)


# -------------------------------------------------------------- methodology -

def build_methodology(all_papers, papers):
    pg = Page("methodology.html")
    ry = defaultdict(set)
    for p in papers:
        ry[p["conf"]].add(p["year"])
    conf_rows = "\n".join(
        f'<tr><td lang="en"><strong>{esc(c["short"])}</strong></td><td lang="en">{esc(c["name"])}</td>'
        f'<td>Tier {c["tier"]} (×{wfmt(weight(c["id"]))})</td>'
        f'<td>{", ".join(str(y) for y in sorted(ry.get(c["id"], [])))}</td></tr>' for c in CONFERENCES)
    pts = "".join(f"<td>{i}</td>" for i in range(1, 11))
    pv = "".join(f"<td>{fmt(p * TIER_WEIGHT[1])}</td>" for p in POINTS)
    pv2 = "".join(f"<td>{fmt(p * TIER_WEIGHT[2])}</td>" for p in POINTS)
    t1 = esc(", ".join(c["short"] for c in CONFERENCES if c["tier"] == 1))
    t2 = esc(", ".join(c["short"] for c in CONFERENCES if c["tier"] == 2))
    excluded = Counter(p["conf"] for p in all_papers if p.get("track") == "T")
    kept = Counter(p["conf"] for p in all_papers if p.get("track") in ("C", "U"))
    exc_ja = "、".join(f'{BY_ID[c]["short"]} {excluded[c]}本（回路系 {kept[c]}本を集計）' for c in excluded)
    exc_en = "; ".join(f'{BY_ID[c]["short"]}: {excluded[c]} excluded ({kept[c]} circuits papers counted)' for c in excluded)
    scopes_ja = "・".join(s["ja"] for s in SCOPES if s["cc"])
    scopes_en = ", ".join(s["en"] for s in SCOPES if s["cc"])
    table = f"""<div class="table-wrap"><table>
<thead><tr><th>{T("略称", "Venue")}</th><th>{T("名称", "Name")}</th><th>{T("Tier（重み）", "Tier (weight)")}</th><th>{T("収録済みの年", "Years")}</th></tr></thead>
<tbody>{conf_rows}</tbody></table></div>"""
    points = f"""<div class="table-wrap"><table class="points-table">
<thead><tr><th>{T("順位", "Rank")}</th>{pts}</tr></thead>
<tbody><tr><th>Tier 1</th>{pv}</tr><tr><th>Tier 2</th>{pv2}</tr></tbody></table></div>"""
    body = f"""<a class="back-link" href="index.html">← {T("ランキングへ戻る", "Back to rankings")}</a>
<article class="prose l-ja">
<p class="eyebrow">集計方針</p>
<h1>集計方法</h1>
<p>TopSSCS は、IEEE Solid-State Circuits Society（SSCS）系のトップ国際会議・論文誌における大学・企業・研究機関の論文活動を、論文に記載された所属に基づいて集計します。<a href="https://topcsuniv.org/japan/">TopCsUniv</a> の集計方式を固体回路分野に当てはめた非公式版です。</p>
<h2>対象会議・論文誌</h2>
{table}
<ul>
<li><strong>2022–2026 LIVE</strong> は最新の5年間です。2026年の会議が未開催、または論文メタデータ未公開の会議は2022–2025を集計します。<strong>2021–2025 確定版</strong> は期間を固定した集計です。</li>
<li>JSSC は印刷版の掲載号の年で集計します。印刷版が未刊行の早期公開（Early Access）論文はオンライン公開年で数えます。編集記事、特集号の序文、訂正記事などは除外します。</li>
<li>VLSI Symposium（2022年〜 Technology and Circuits 合同開催）と ESSERC（2024年〜 ESSCIRC と ESSDERC の統合）は、<strong>回路系トラックの論文だけ</strong>を対象にします。論文タイトルを LLM で回路系／技術・デバイス系に分類し（data/track_labels.tsv）、どちらとも言えない講演は回路系に含めます。分類前の新しい論文にはキーワードによる暫定判定を使います。除外: {exc_ja}。</li>
</ul>
<h2 id="scopes">国別・世界ランキング</h2>
<ul>
<li>国別ランキング（{scopes_ja}）は、その国の機関だけで各会議・論文誌の順位を付けてポイント化します。世界ランキングはすべての国の機関で順位を付けます。</li>
<li><strong>日本の機関</strong>は、論文に記載された所属文字列を独自の辞書（大学・企業・研究機関）で判定します。東京工業大学と東京医科歯科大学は東京科学大学として集計し、グループ会社は親会社にまとめます。海外企業は日本拠点の所属だけを「（日本拠点）」として数えます。</li>
<li><strong>日本以外の機関</strong>は OpenAlex の機関ID・国・種別を使います。種別が education の機関を大学、それ以外を企業・研究機関とします。OpenAlex に機関がない著者は、同じ所属文字列が他の論文で対応付けられた機関で補います。</li>
<li>表は各ページ上位{TABLE_LIMIT}件までを表示します。</li>
</ul>
<h2>対象と数え方</h2>
<ul>
<li>論文リストと著者所属は Crossref に登録された IEEE Xplore のメタデータから取得しています。Crossref に所属がない著者（主に2021年の会議論文）は OpenAlex の所属情報で補います。</li>
<li>チュートリアル、ショートコース、フォーラム、パネル、セッション概要、索引などの論文以外の項目は除外します。</li>
<li>所属は現在の所属ではなく、論文に記載された所属を使用します。「Formerly」「Emeritus」などの旧所属表記は数えません。</li>
</ul>
<h2 id="modes">カウント方式</h2>
<ul>
<li><strong>フルカウント</strong>（既定）: 論文に関わった機関すべてに1本ずつ数えます。同じ機関の著者が複数いても1本です。</li>
<li><strong>筆頭著者</strong>: 筆頭著者の所属機関だけに1本を数えます。筆頭著者が複数の所属を持つ場合は、それぞれに1本です。</li>
<li><strong>著者按分</strong>: 1本の論文を著者数で等分し、各著者の持ち分をその著者の所属機関数でさらに等分して配分します。</li>
</ul>
<h2 id="championship">総合ランキング</h2>
<p>各会議・論文誌で論文数に基づく順位をポイントへ変換し、Tierの重みを掛けて合計します。ポイント配分は F1 の上位10位の基本配点を参考にしています。</p>
<ul>
<li><strong>Tier 1（×{wfmt(TIER_WEIGHT[1])}）</strong>: {t1}</li>
<li><strong>Tier 2（×{wfmt(TIER_WEIGHT[2])}）</strong>: {t2}</li>
</ul>
{points}
<ul>
<li>同点は標準競技順位（例: 1位、2位、2位、4位）とし、同順位には同じポイントを付与します。</li>
<li>その会議・論文誌で論文が0本の機関には順位を付けず、0ポイントとします。</li>
<li>LIVE版の「前回」列は、最も新しく反映した会議・年を除いた場合との比較です（随時掲載のJSSCは起点にしません）。</li>
</ul>
<h2>著者表示</h2>
<p>ORCID が一致する著者は同一人物としてまとめ、最も多い表記で表示します。ORCID のない表記は、同じ綴りの ORCID 著者が1人だけいる場合にその人物へまとめます。</p>
<h2>読み方の注意</h2>
<p>このランキングは、選定した国際会議・論文誌での論文数を示すものです。研究の総合的な質、影響力、教育力、組織全体の優劣を測るものではありません。所属表記の揺れや欠落、OpenAlex の機関判定、トラック分類の誤りにより、取りこぼしや誤判定が含まれる可能性があります。</p>
<p>本サイトはアクセス解析に Google Analytics（Cookie）を使用しています。</p>
</article>
<article class="prose l-en" lang="en">
<p class="eyebrow">Methodology</p>
<h1>How the rankings are computed</h1>
<p>TopSSCS counts papers by universities, companies and research institutes at the top venues of the IEEE Solid-State Circuits Society (SSCS), using the affiliations printed in each paper. It is an unofficial adaptation of <a href="https://topcsuniv.org/japan/">TopCsUniv</a> to solid-state circuits.</p>
<h2>Venues</h2>
{table}
<ul>
<li><strong>2022–2026 LIVE</strong> is the latest five-year window; venues whose 2026 edition has not happened or is not yet in the metadata contribute 2022–2025. <strong>2021–2025 Final</strong> is a frozen window.</li>
<li>JSSC papers count in the year of their print issue; early-access papers without a print issue count in their online year. Editorials, special-issue introductions and corrections are excluded.</li>
<li>For the VLSI Symposium (joint Technology and Circuits since 2022) and ESSERC (merged ESSCIRC and ESSDERC since 2024) only <strong>circuits-track papers</strong> count. Titles were classified as circuits or technology/devices by an LLM (data/track_labels.tsv); talks that fit neither are counted. New, unlabeled papers get a provisional keyword-based label. Excluded: {exc_en}.</li>
</ul>
<h2 id="scopes-en">Country and world rankings</h2>
<ul>
<li>Country rankings ({scopes_en}) rank only that country's institutions at each venue before converting ranks to points; the world ranking ranks institutions of all countries together.</li>
<li><strong>Japanese institutions</strong> are matched from the affiliation strings with a curated dictionary of universities, companies and institutes. Tokyo Tech and Tokyo Medical and Dental University count as Institute of Science Tokyo; group companies are merged into the parent; foreign companies count only for affiliations at their Japanese sites.</li>
<li><strong>Institutions outside Japan</strong> use OpenAlex institution IDs, countries and types: type “education” is a university, everything else a company or institute. Authors without an OpenAlex institution inherit the institution that the same affiliation string maps to in other papers.</li>
<li>Tables show the top {TABLE_LIMIT} entries.</li>
</ul>
<h2>What is counted</h2>
<ul>
<li>Paper lists and affiliations come from IEEE Xplore metadata registered with Crossref; authors without a Crossref affiliation (mostly 2021 proceedings) are filled from OpenAlex.</li>
<li>Tutorials, short courses, forums, panels, session overviews, indexes and other non-paper items are excluded.</li>
<li>Affiliations are those printed on the paper, not current ones. “Formerly” or “Emeritus” affiliations are ignored.</li>
</ul>
<h2 id="modes-en">Counting modes</h2>
<ul>
<li><strong>Full count</strong> (default): every institution on a paper gets 1, however many of its authors there are.</li>
<li><strong>First author</strong>: only the first author's institutions get 1 each.</li>
<li><strong>Fractional</strong>: each paper is split evenly over its authors, and each author's share evenly over their institutions.</li>
</ul>
<h2 id="championship-en">Overall ranking</h2>
<p>At each venue, institutions are ranked by paper count; ranks become points (after the Formula 1 top-ten scale), are multiplied by the tier weight, and summed.</p>
<ul>
<li><strong>Tier 1 (×{wfmt(TIER_WEIGHT[1])})</strong>: {t1}</li>
<li><strong>Tier 2 (×{wfmt(TIER_WEIGHT[2])})</strong>: {t2}</li>
</ul>
{points}
<ul>
<li>Ties use standard competition ranking (1, 2, 2, 4) and share the same points.</li>
<li>Institutions with no paper at a venue get no rank and no points there.</li>
<li>In the LIVE edition, “Prev” compares with the ranking before the most recently added conference (JSSC, published continuously, is never the reference).</li>
</ul>
<h2>Authors</h2>
<p>Authors sharing an ORCID are merged and shown with their most frequent spelling. A spelling without ORCID joins an ORCID author only if exactly one ORCID author uses that spelling.</p>
<h2>Caveats</h2>
<p>The rankings count papers at selected venues. They do not measure research quality, impact, teaching, or overall institutional standing. Affiliation spelling variations, missing data, OpenAlex institution matching and track classification can cause omissions or misattributions.</p>
<p>This site uses Google Analytics (cookies) to measure traffic.</p>
</article>"""
    write(pg.path, layout(pg, "集計方法 | TopSSCS", "Methodology | TopSSCS", body))


def main():
    global REG
    REG = build_registry()
    all_papers = json.loads((ROOT / "data" / "papers.json").read_text(encoding="utf-8"))
    papers = [p for p in all_papers if p.get("track") != "T"]  # circuits track only on joint venues
    for p in papers:
        attach_credits(p)
    if SITE.exists():
        shutil.rmtree(SITE)
    (SITE / "assets").mkdir(parents=True)
    shutil.copy(ROOT / "src" / "style.css", SITE / "assets" / "style.css")
    shutil.copy(ROOT / "src" / "site.js", SITE / "assets" / "site.js")
    for ed in EDITIONS:
        E = Edition(papers, ed)
        for scope in SCOPES:
            for kind in KINDS:
                build_index(E, scope, kind)
                for c in E.confs:
                    build_conf(E, scope, kind, c)
        for eid in sorted(E.shown):
            build_entity(E, eid)
        print(f"{ed['label']}: {len(E.shown)} institution pages")
    build_methodology(all_papers, papers)
    n = sum(1 for _ in SITE.rglob("*.html"))
    size = sum(f.stat().st_size for f in SITE.rglob("*") if f.is_file())
    print(f"{n} pages, {size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
