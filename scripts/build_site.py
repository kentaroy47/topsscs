"""Generate the static TopSSCS site from data/papers.json into site/.

Axes: edition (live / frozen) x entity (universities / organizations) x counting
mode (full / first author / author-fractional, switched client-side).
"""
import datetime as dt
import html
import json
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import organizations  # noqa: E402
import universities  # noqa: E402
from conferences import BY_ID, CONFERENCES, EDITIONS, TIER_WEIGHT, weight  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
POINTS = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
_FETCHED = ROOT / "data" / "fetched_at.txt"
UPDATED = _FETCHED.read_text(encoding="utf-8").strip() if _FETCHED.exists() else dt.date.today().isoformat()

ENTITIES = {
    "univ": {"key": "u", "prefix": "", "detail": "universities", "label": "大学", "names": universities.BY_SLUG},
    "org": {"key": "o", "prefix": "orgs/", "detail": "institutions", "label": "企業・研究機関",
            "names": organizations.BY_SLUG},
}
MODES = [
    ("full", "フルカウント", "関わった機関すべてに1本ずつ"),
    ("first", "筆頭著者", "筆頭著者の所属機関のみに1本"),
    ("frac", "著者按分", "1本を著者数で等分し、各著者の所属に配分"),
]
# categorical slots 1-6 of the validated reference palette, in fixed order (see src/style.css)
SERIES = ["isscc", "vlsi", "jssc", "cicc", "asscc", "esscirc"]

esc = html.escape


# ---------------------------------------------------------------- counting --

def credits(paper, ent, mode):
    """{slug: credit} for one paper."""
    k = ENTITIES[ent]["key"]
    out = defaultdict(float)
    authors = paper["authors"]
    if mode == "full":
        for a in authors:
            for f in a["affs"]:
                if f[k]:
                    out[f[k]] = 1.0
    elif mode == "first":
        for f in authors[0]["affs"] if authors else []:
            if f[k]:
                out[f[k]] = 1.0
    else:
        n = len(authors)
        for a in authors:
            if not a["affs"]:
                continue
            share = 1.0 / n / len(a["affs"])
            for f in a["affs"]:
                if f[k]:
                    out[f[k]] += share
    return out


def tally(papers, ent, mode):
    c = Counter()
    for p in papers:
        for s, v in credits(p, ent, mode).items():
            c[s] += v
    return c


def competition_rank(values):
    """values sorted desc -> standard competition ranks (1, 2, 2, 4)."""
    ranks, prev, rank = [], None, 0
    for i, v in enumerate(values, 1):
        rv = round(v, 6)
        if rv != prev:
            rank, prev = i, rv
        ranks.append(rank)
    return ranks


def rank_rows(counter, names):
    rows = sorted(((s, v) for s, v in counter.items() if v > 1e-9),
                  key=lambda kv: (-round(kv[1], 6), names[kv[0]][1]))
    ranks = competition_rank([v for _, v in rows])
    return [{"slug": s, "count": v, "rank": r} for (s, v), r in zip(rows, ranks)]


def points_for(rank, conf):
    return (POINTS[rank - 1] if rank <= len(POINTS) else 0) * weight(conf)


def championship(by_conf_counts, names):
    """by_conf_counts: {conf: Counter}. Returns (rows, {conf: {slug: row}})."""
    total = Counter()
    per_conf = {}
    for c, counter in by_conf_counts.items():
        table = rank_rows(counter, names)
        per_conf[c] = {r["slug"]: r for r in table}
        for r in table:
            total[r["slug"]] += points_for(r["rank"], c)
    rows = sorted(total.items(), key=lambda kv: (-round(kv[1], 6), names[kv[0]][1]))
    ranks = competition_rank([v for _, v in rows])
    return [{"slug": s, "points": v, "rank": r} for (s, v), r in zip(rows, ranks)], per_conf


def fmt_count(v, mode):
    return f"{v:.2f}" if mode == "frac" else f"{round(v):d}"


def fmt(x):
    return f"{round(x, 2):g}"


def wfmt(w):
    return f"{w:.1f}"


# ------------------------------------------------------------------- html ---

class Page:
    def __init__(self, path):
        self.path = path  # relative to site root, e.g. "orgs/isscc/index.html"
        self.depth = path.count("/")

    def href(self, target):
        return "../" * self.depth + target


def layout(pg, title, body, description=""):
    desc = description or ("TopSSCSは、ISSCC・VLSI・JSSC・CICC・A-SSCC・ESSERCの論文数をもとに、"
                           "日本の大学・企業の集積回路研究を比較できるランキングサイトです。")
    h = pg.href
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<link rel="stylesheet" href="{h('assets/style.css')}">
<script src="{h('assets/site.js')}" defer></script>
</head>
<body>
<a class="skip-link" href="#main">本文へ移動</a>
<header class="site-header"><div class="header-inner">
<a class="brand" href="{h('index.html')}" aria-label="TopSSCS トップ">Top<span>SSCS</span></a>
<nav aria-label="主要ナビゲーション"><a href="{h('index.html')}">大学</a><a href="{h('orgs/index.html')}">企業・研究機関</a><a href="{h('methodology.html')}">集計方法</a></nav>
</div></header>
<main id="main" class="page-shell">
{body}
</main>
<footer class="site-footer">
<p><strong>TopSSCS</strong> 固体回路系トップ国際会議・論文誌における日本の大学・企業の論文活動を可視化</p>
<p>Data: Crossref / OpenAlex · Updated {UPDATED} · <a href="{h('methodology.html')}">集計ルール</a></p>
</footer>
</body>
</html>
"""


def intro(ent):
    who = "日本の大学" if ent == "univ" else "日本の企業・研究機関"
    return f"""<section class="page-intro">
<h1>日本の集積回路研究を、競争でもっと面白く。</h1>
<p class="lede">固体回路系トップ国際会議・論文誌（ISSCC・VLSI・JSSC・CICC・A-SSCC・ESSERC）の論文数をもとに{who}が競うスコアボード</p>
</section>"""


def controls(pg, ed, ent, current, other_paths):
    """Entity switch, edition selector, counting-mode switch, venue tabs."""
    ep = ed["path"]
    tp = ENTITIES[ent]["prefix"]
    out = ['<div class="switches">', '<nav class="entity-switch" aria-label="集計対象">']
    for e, meta in ENTITIES.items():
        cur = ' aria-current="true"' if e == ent else ""
        out.append(f'<a href="{pg.href(ep + meta["prefix"] + "index.html")}"{cur}>{meta["label"]}</a>')
    out.append("</nav>")
    out.append('<label class="edition-selector">Edition <select data-nav>')
    for e in EDITIONS:
        sel = " selected" if e["id"] == ed["id"] else ""
        out.append(f'<option value="{pg.href(other_paths[e["id"]])}"{sel}>{esc(e["label"])}</option>')
    out.append("</select></label>")
    out.append('<div class="mode-switch" role="radiogroup" aria-label="カウント方式">')
    for m, label, hint in MODES:
        checked = "true" if m == "full" else "false"
        out.append(f'<button type="button" role="radio" aria-checked="{checked}" data-mode="{m}" title="{esc(hint)}">{label}</button>')
    out.append("</div></div>")
    cur_all = ' aria-current="true"' if current == "all" else ""
    out.append('<nav class="field-tabs" aria-label="ランキングを選択">')
    out.append(f'<a class="field-tab championship-tab" href="{pg.href(ep + tp + "index.html")}"{cur_all}>総合</a>')
    prev_tier = None
    for c in CONFERENCES:
        if c["tier"] != prev_tier:
            out.append(f'<span class="tier-tag">Tier {c["tier"]}</span>')
            prev_tier = c["tier"]
        cur = ' aria-current="true"' if current == c["id"] else ""
        out.append(f'<a class="field-tab" href="{pg.href(ep + tp + c["id"] + "/index.html")}"{cur} lang="en">{esc(c["short"])}</a>')
    out.append("</nav>")
    return "\n".join(out)


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


def write(path, text):
    p = SITE / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def mode_panels(render):
    """render(mode) for each counting mode; site.js shows the selected one."""
    return "\n".join(f'<div class="mode-panel" data-mode="{m}"{"" if m == "full" else " hidden"}>{render(m)}</div>'
                     for m, _, _ in MODES)


# ------------------------------------------------------------------ builder -

class Builder:
    def __init__(self, papers, ed, ent):
        self.ed, self.ent = ed, ent
        self.meta = ENTITIES[ent]
        self.names = self.meta["names"]
        self.papers = [p for p in papers if p["year"] in ed["years"]]
        self.ry = defaultdict(set)
        for p in self.papers:
            self.ry[p["conf"]].add(p["year"])
        self.confs = [c["id"] for c in CONFERENCES if c["id"] in self.ry]
        self.by_conf = {c: [p for p in self.papers if p["conf"] == c] for c in self.confs}
        self.base = ed["path"] + self.meta["prefix"]

    def name(self, slug):
        return self.names[slug][0]

    def detail_path(self, slug, conf=None):
        mid = f"{conf}/" if conf else ""
        return f'{self.base}{mid}{self.meta["detail"]}/{slug}/index.html'

    def other_paths(self, rel):
        """The same page in each edition (rel is relative to the entity root)."""
        return {e["id"]: e["path"] + self.meta["prefix"] + rel for e in EDITIONS}

    def latest_overall(self):
        cands = [(max(self.ry[c]), BY_ID[c]["month"], c) for c in self.confs if BY_ID[c]["kind"] == "conference"]
        y, _, c = max(cands)
        return c, y

    def champ(self, mode, exclude=None):
        counts = {}
        for c in self.confs:
            ps = self.by_conf[c]
            if exclude:
                ps = [p for p in ps if (p["conf"], p["year"]) != exclude]
            counts[c] = tally(ps, self.ent, mode)
        return championship(counts, self.names)

    # -- championship page --------------------------------------------------
    def build_index(self):
        pg = Page(self.base + "index.html")
        live = self.ed["live"]
        lc, ly = self.latest_overall()
        self.results = {m: self.champ(m) for m, _, _ in MODES}

        def render(mode):
            rows, per_conf = self.results[mode]
            prev = {r["slug"]: r for r in self.champ(mode, exclude=(lc, ly))[0]} if live else {}
            trs = []
            for r in rows:
                s = r["slug"]
                link = f'<a class="university-link" href="{pg.href(self.detail_path(s))}">{esc(self.name(s))}</a>'
                tail, pts = "", fmt(r["points"])
                if live:
                    p = prev.get(s)
                    tail = f'<td class="rank-change">{change_badge(r["rank"], p["rank"] if p else None)}</td>'
                    pts += delta(r["points"] - (p["points"] if p else 0), "points")
                trs.append(f'<tr>{rank_cell(r["rank"])}<td>{link}</td><td class="numeric">{pts}</td>{tail}</tr>')
            head_prev = '<th scope="col" class="rank-change">前回</th>' if live else ""
            table = (f'<div class="table-wrap"><table class="ranking-table">'
                     f'<thead><tr><th scope="col">順位</th><th scope="col">{self.meta["label"]}</th>'
                     f'<th scope="col" class="numeric">ポイント</th>{head_prev}</tr></thead>'
                     f'<tbody>{"".join(trs)}</tbody></table></div>')
            head = "".join(f'<th class="numeric" lang="en">{esc(BY_ID[c]["short"])}<span class="tier-label">'
                           f'Tier {BY_ID[c]["tier"]} ×{wfmt(weight(c))}</span></th>' for c in self.confs)
            brs = []
            for r in rows:
                s = r["slug"]
                cells = []
                for c in self.confs:
                    e = per_conf[c].get(s)
                    if e:
                        pv = points_for(e["rank"], c)
                        cells.append(f'<td class="numeric{" scored" if pv else ""}"><span class="bd-rank">{e["rank"]}位</span>'
                                     f'<span class="bd-pts">{fmt(pv)}pt</span><span class="bd-n">{fmt_count(e["count"], mode)}本</span></td>')
                    else:
                        cells.append('<td class="numeric muted">–</td>')
                brs.append(f'<tr>{rank_cell(r["rank"])}<td>{esc(self.name(s))}</td>{"".join(cells)}'
                           f'<td class="numeric">{fmt(r["points"])}</td></tr>')
            bd = (f'<section class="breakdown"><div class="ranking-head"><div><h2>会議・論文誌別内訳</h2>'
                  f'<p class="ranking-context">各会議・論文誌での順位・獲得ポイント（重み適用後）・論文数</p></div></div>'
                  f'<div class="table-wrap"><table class="championship-breakdown"><thead><tr><th scope="col">順位</th>'
                  f'<th scope="col">{self.meta["label"]}</th>{head}<th scope="col" class="numeric">合計</th></tr></thead>'
                  f'<tbody>{"".join(brs)}</tbody></table></div></section>')
            return table + bd

        note_prev = (f"「前回」は {esc(BY_ID[lc]['short'])} {ly} 反映前との比較です。" if live
                     else "確定版は期間を固定した集計です。")
        latest = f" · Latest: {esc(BY_ID[lc]['short'])} {ly} added" if live else ""
        unit = "大学" if self.ent == "univ" else "機関"
        body = f"""{intro(self.ent)}
{controls(pg, self.ed, self.ent, "all", self.other_paths("index.html"))}
<section class="ranking-card" aria-labelledby="ranking-title">
<div class="ranking-head"><div>
<p class="eyebrow">{esc(self.ed["label"])} · {tier_summary(self.confs)}</p>
<h2 id="ranking-title">{self.meta["label"]}総合ランキング</h2>
<p class="ranking-context">Updated: {UPDATED}{latest}</p>
</div><p class="record-count">{len(self.results["full"][0])}{unit}</p></div>
{self.live_status()}
{mode_panels(render)}
<p class="status">会議・論文誌ごとの順位をF1方式でポイント化し、Tierの重みを掛けて合計したランキングです。{note_prev}<a href="{pg.href('methodology.html#championship')}">集計ルール</a></p>
</section>"""
        write(pg.path, layout(pg, f"TopSSCS | {self.meta['label']}総合ランキング {self.ed['label']}", body))

    def live_status(self, conf=None):
        if not self.ed["live"]:
            return ""
        last = max(self.ed["years"])
        confs = [conf] if conf else self.confs
        done = [BY_ID[c]["short"] for c in confs if last in self.ry[c]]
        todo = [BY_ID[c]["short"] for c in confs if last not in self.ry[c]]
        parts = []
        if done:
            parts.append(f'<p><strong>{last} reflected:</strong> {", ".join(done)}</p>')
        if todo:
            parts.append(f'<p><strong>Not yet reflected:</strong> {", ".join(todo)}（{min(self.ed["years"])}–{last - 1}を集計）</p>')
        return f'<div class="live-status">{"".join(parts)}</div>'

    # -- venue page ----------------------------------------------------------
    def build_conf(self, conf):
        c = BY_ID[conf]
        pg = Page(self.base + conf + "/index.html")
        live = self.ed["live"]
        ps = self.by_conf[conf]
        ly = max(self.ry[conf])
        k = self.meta["key"]
        involved = [p for p in ps if any(f[k] for a in p["authors"] for f in a["affs"])]

        def render(mode):
            table = rank_rows(tally(ps, self.ent, mode), self.names)
            prev = {}
            if live:
                prev = {r["slug"]: r for r in rank_rows(tally([p for p in ps if p["year"] != ly], self.ent, mode), self.names)}
            trs = []
            for r in table:
                s = r["slug"]
                link = f'<a class="university-link" href="{pg.href(self.detail_path(s, conf))}">{esc(self.name(s))}</a>'
                tail, cnt = "", fmt_count(r["count"], mode)
                if live:
                    p = prev.get(s)
                    cnt += delta(r["count"] - (p["count"] if p else 0), mode)
                    tail = f'<td class="rank-change">{change_badge(r["rank"], p["rank"] if p else None)}</td>'
                trs.append(f'<tr>{rank_cell(r["rank"])}<td>{link}</td><td class="numeric">{cnt}</td>{tail}</tr>')
            if not trs:
                return '<p class="empty">該当する論文はまだありません。</p>'
            head_prev = '<th scope="col" class="rank-change">前回</th>' if live else ""
            return (f'<div class="table-wrap"><table class="ranking-table"><thead><tr>'
                    f'<th scope="col">順位</th><th scope="col">{self.meta["label"]}</th>'
                    f'<th scope="col" class="numeric">論文数</th>{head_prev}</tr></thead><tbody>{"".join(trs)}</tbody></table></div>')

        per_year = Counter(p["year"] for p in ps)
        per_year_jp = Counter(p["year"] for p in involved)
        yrs = " · ".join(f"{y}: {per_year_jp[y]}/{per_year[y]}" for y in sorted(self.ry[conf]))
        track_note = f" · {c['joint_from']}年以降は回路系トラックのみ" if c.get("joint_from") else ""
        latest = f" · Latest: {esc(c['short'])} {ly} added" if live else ""
        prev_note = f"「前回」は {esc(c['short'])} {ly} 反映前との比較です。" if live else ""
        body = f"""{intro(self.ent)}
{controls(pg, self.ed, self.ent, conf, self.other_paths(conf + "/index.html"))}
<section class="ranking-card" aria-labelledby="ranking-title">
<div class="ranking-head"><div>
<p class="eyebrow">{self.meta["label"]}別集計 · Tier {c["tier"]}（総合ポイント ×{wfmt(weight(conf))}）</p>
<h2 id="ranking-title"><span lang="en">{esc(c["short"])}</span> {self.meta["label"]}ランキング</h2>
<p class="ranking-context">{esc(self.ed["label"])} · <a href="{c["url"]}" lang="en">{esc(c["name"])}</a> · {len(ps):,} papers{track_note}
<span class="japan-paper-presence">（日本の{self.meta["label"]}関与 {len(involved)} papers・{100 * len(involved) / max(1, len(ps)):.2f}%）</span></p>
<p class="ranking-context">Updated: {UPDATED}{latest} · 年別（関与/全体）: {yrs}</p>
</div></div>
{self.live_status(conf)}
{mode_panels(render)}
<p class="status">名前から、所属著者と論文の内訳を確認できます。{prev_note}</p>
</section>"""
        write(pg.path, layout(pg, f"{c['short']} {self.meta['label']}ランキング {self.ed['label']} | TopSSCS", body))
        for slug in tally(ps, self.ent, "full"):
            self.build_entity_conf(conf, slug)

    # -- entity x venue page -------------------------------------------------
    def build_entity_conf(self, conf, slug):
        c = BY_ID[conf]
        pg = Page(self.detail_path(slug, conf))
        k = self.meta["key"]
        ps = sorted((p for p in self.by_conf[conf] if slug in credits(p, self.ent, "full")),
                    key=lambda p: (-p["year"], p["title"]))
        authors, disp = Counter(), {}
        for p in ps:
            for a in {a["key"]: a for a in p["authors"] if any(f[k] == slug for f in a["affs"])}.values():
                authors[a["key"]] += 1
                disp[a["key"]] = a["display"]
        rows = sorted(authors.items(), key=lambda kv: (-kv[1], disp[kv[0]]))
        ranks = competition_rank([v for _, v in rows])
        orcid_tag = ' <span class="orcid">ORCID</span>'
        trs = "".join(f'<tr>{rank_cell(r)}<td lang="en"><span class="author-link">{esc(disp[a])}</span>'
                      f'{orcid_tag if a.startswith("orcid:") else ""}</td>'
                      f'<td class="numeric">{n}</td></tr>' for (a, n), r in zip(rows, ranks))
        counts = {m: sum(credits(p, self.ent, m).get(slug, 0) for p in ps) for m, _, _ in MODES}
        items = "\n".join(self.paper_item(p, slug) for p in ps)
        body = f"""<a class="back-link" href="{pg.href(self.base + conf + "/index.html")}">← <span lang="en">{esc(c["short"])}</span> {self.meta["label"]}ランキングへ戻る</a>
<section class="detail-heading">
<p class="eyebrow">{self.meta["label"]} × 会議・論文誌</p>
<h1>{esc(self.name(slug))}</h1>
<p class="lede"><span lang="en">{esc(c["short"])}</span> / {esc(self.ed["label"])} · <a href="{pg.href(self.detail_path(slug))}">{self.meta["label"]}ページ</a></p>
<p class="stat-line">対象論文 <strong>{len(ps)}</strong> 本 <span class="stat-detail">· 筆頭著者 {fmt_count(counts["first"], "first")} 本 · 著者按分 {fmt_count(counts["frac"], "frac")} 本 · 所属著者 {len(rows)}名</span></p>
</section>
<section>
<div class="ranking-head"><div><h2>所属著者</h2>
<p class="ranking-context">ORCID が一致する著者は同一人物としてまとめています。それ以外は表記ごとに別人として扱います。</p></div></div>
<div class="table-wrap"><table class="ranking-table">
<thead><tr><th scope="col">順位</th><th scope="col">著者</th><th scope="col" class="numeric">論文数</th></tr></thead>
<tbody>{trs}</tbody></table></div>
</section>
<section class="papers">
<div class="ranking-head"><div><h2>対象論文</h2>
<p class="ranking-context">太字は{esc(self.name(slug))}所属として確認できた著者です。</p></div></div>
<ol class="paper-list">
{items}
</ol>
</section>"""
        write(pg.path, layout(pg, f"{self.name(slug)} × {c['short']} | TopSSCS", body))

    def paper_item(self, p, slug):
        k = self.meta["key"]
        c = BY_ID[p["conf"]]
        names = []
        for a in p["authors"]:
            n = esc(a["name"])
            names.append(f"<strong>{n}</strong>" if any(f[k] == slug for f in a["affs"]) else n)
        insts = []
        for meta in ENTITIES.values():
            mk = meta["key"]
            for s in dict.fromkeys(f[mk] for a in p["authors"] for f in a["affs"] if f[mk]):
                insts.append(esc(meta["names"][s][0]))
        return f"""<li class="paper-item">
<div class="paper-meta"><span lang="en">{esc(c["short"])}</span><br>{p["year"]}</div>
<div><a class="paper-title" href="https://doi.org/{esc(p["doi"])}" lang="en">{esc(p["title"])}</a></div>
<a class="doi-link" href="https://doi.org/{esc(p["doi"])}">DOI</a>
<div class="paper-coauthors" lang="en">{", ".join(names)}</div>
<div class="paper-univs">{"、".join(insts)}</div>
</li>"""

    # -- entity page -----------------------------------------------------------
    def build_entity(self, slug):
        pg = Page(self.detail_path(slug))
        ps = sorted((p for p in self.papers if slug in credits(p, self.ent, "full")),
                    key=lambda p: (-p["year"], p["conf"], p["title"]))
        rows_full, per_conf_full = self.results["full"]
        champ_row = {r["slug"]: r for r in rows_full}.get(slug, {"rank": "–", "points": 0})
        trs = []
        for c in CONFERENCES:
            cid = c["id"]
            cps = [p for p in ps if p["conf"] == cid]
            e = per_conf_full.get(cid, {}).get(slug)
            label = esc(c["short"])
            if cps:
                label = f'<a href="{pg.href(self.detail_path(slug, cid))}">{label}</a>'
            cnt = {m: sum(credits(p, self.ent, m).get(slug, 0) for p in cps) for m, _, _ in MODES}
            trs.append(f'<tr><td lang="en">{label} <span class="tier-label">Tier {c["tier"]}</span></td>'
                       f'<td class="numeric">{fmt_count(cnt["full"], "full")}</td>'
                       f'<td class="numeric">{fmt_count(cnt["first"], "first")}</td>'
                       f'<td class="numeric">{fmt_count(cnt["frac"], "frac")}</td>'
                       f'<td class="numeric">{str(e["rank"]) + "位" if e else "–"}</td>'
                       f'<td class="numeric">{fmt(points_for(e["rank"], cid)) if e else "0"}</td></tr>')
        ja, en = self.names[slug]
        items = "\n".join(self.paper_item(p, slug) for p in ps)
        body = f"""<a class="back-link" href="{pg.href(self.base + "index.html")}">← {self.meta["label"]}総合ランキングへ戻る</a>
<section class="detail-heading">
<p class="eyebrow">{self.meta["label"]} · {esc(self.ed["label"])}</p>
<h1>{esc(ja)}</h1>
<p class="lede" lang="en">{esc(en)}</p>
<p class="stat-line">総合 <strong>{champ_row["rank"]}</strong> 位 · <strong>{fmt(champ_row["points"])}</strong> pt · 対象論文 <strong>{len(ps)}</strong> 本</p>
</section>
<section>
<div class="ranking-head"><div><h2>年別の推移</h2>
<p class="ranking-context">会議・論文誌別の論文数（フルカウント）</p></div></div>
{trend_chart(ps, sorted(self.ed["years"]))}
</section>
<section>
<div class="ranking-head"><div><h2>会議・論文誌別</h2>
<p class="ranking-context">順位・ポイントはフルカウントでの値です。</p></div></div>
<div class="table-wrap"><table class="univ-table">
<thead><tr><th scope="col">会議・論文誌</th><th scope="col" class="numeric">フル</th><th scope="col" class="numeric">筆頭</th>
<th scope="col" class="numeric">按分</th><th scope="col" class="numeric">順位</th><th scope="col" class="numeric">ポイント</th></tr></thead>
<tbody>{"".join(trs)}</tbody></table></div>
</section>
<section class="papers">
<div class="ranking-head"><div><h2>対象論文</h2>
<p class="ranking-context">太字は{esc(ja)}所属として確認できた著者です。</p></div></div>
<ol class="paper-list">
{items}
</ol>
</section>"""
        write(pg.path, layout(pg, f"{ja} | TopSSCS", body))

    def build(self):
        self.build_index()
        for c in self.confs:
            self.build_conf(c)
        for slug in tally(self.papers, self.ent, "full"):
            self.build_entity(slug)
        return len(self.results["full"][0])


# ------------------------------------------------------------------- chart --

def trend_chart(papers, years):
    """Stacked bars: papers per year, one segment per venue (fixed palette order)."""
    counts = {y: Counter(p["conf"] for p in papers if p["year"] == y) for y in years}
    series = [c for c in SERIES if any(counts[y][c] for y in years)]
    ymax = max([sum(counts[y].values()) for y in years] + [1])
    step = 1 if ymax <= 5 else 2 if ymax <= 10 else 5 if ymax <= 30 else 10 if ymax <= 60 else 20
    top = ((ymax + step - 1) // step) * step
    W, H, L, R, T, B = 560, 220, 34, 8, 16, 26
    pw, ph = W - L - R, H - T - B
    bw = min(56, pw / len(years) * 0.56)
    out = [f'<figure class="trend"><svg viewBox="0 0 {W} {H}" role="img" aria-label="年別・会議別の論文数">']
    for v in range(0, top + 1, step):
        y = T + ph - ph * v / top
        out.append(f'<line class="grid" x1="{L}" x2="{W - R}" y1="{y:.1f}" y2="{y:.1f}"/>'
                   f'<text class="axis" x="{L - 6}" y="{y + 4:.1f}" text-anchor="end">{v}</text>')
    for i, yr in enumerate(years):
        cx = L + pw * (i + 0.5) / len(years)
        x = cx - bw / 2
        base = T + ph
        segs = [(c, counts[yr][c]) for c in series if counts[yr][c]]
        for j, (c, n) in enumerate(segs):
            h = ph * n / top
            y0 = base - h
            tip = f"{yr} {BY_ID[c]['short']}: {n}本"
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
    out.append(f'<details class="trend-table"><summary>数値表を表示</summary><div class="table-wrap"><table>'
               f'<thead><tr><th>会議・論文誌</th>{head}</tr></thead><tbody>{rows}</tbody></table></div></details>')
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
        f'<td>Tier {c["tier"]}（×{wfmt(weight(c["id"]))}）</td>'
        f'<td>{", ".join(str(y) for y in sorted(ry.get(c["id"], [])))}</td></tr>' for c in CONFERENCES)
    pts = "".join(f"<td>{i}</td>" for i in range(1, 11))
    pv = "".join(f"<td>{fmt(p * TIER_WEIGHT[1])}</td>" for p in POINTS)
    pv2 = "".join(f"<td>{fmt(p * TIER_WEIGHT[2])}</td>" for p in POINTS)
    t1 = esc(", ".join(c["short"] for c in CONFERENCES if c["tier"] == 1))
    t2 = esc(", ".join(c["short"] for c in CONFERENCES if c["tier"] == 2))
    excluded = Counter(p["conf"] for p in all_papers if p.get("track") == "T")
    kept = Counter(p["conf"] for p in all_papers if p.get("track") in ("C", "U"))
    exc = "、".join(f'{BY_ID[c]["short"]} {excluded[c]}本（回路系 {kept[c]}本を集計）' for c in excluded)
    body = f"""<a class="back-link" href="index.html">← ランキングへ戻る</a>
<article class="prose">
<p class="eyebrow">集計方針</p>
<h1>集計方法</h1>
<p>TopSSCS は、IEEE Solid-State Circuits Society（SSCS）系のトップ国際会議・論文誌における日本の大学・企業・研究機関の論文活動を、論文に記載された所属に基づいて集計します。<a href="https://topcsuniv.org/japan/">TopCsUniv</a> の集計方式を固体回路分野に当てはめた非公式版です。</p>

<h2>対象会議・論文誌</h2>
<div class="table-wrap"><table>
<thead><tr><th>略称</th><th>名称</th><th>Tier（重み）</th><th>収録済みの年</th></tr></thead>
<tbody>{conf_rows}</tbody></table></div>
<ul>
<li><strong>2022–2026 LIVE</strong> は最新の5年間です。2026年の会議が未開催、または論文メタデータ未公開の会議は2022–2025を集計します。<strong>2021–2025 確定版</strong> は期間を固定した集計です。</li>
<li>JSSC は印刷版の掲載号の年で集計します。印刷版が未刊行の早期公開（Early Access）論文はオンライン公開年で数えます。編集記事、特集号の序文、訂正記事などは除外します。</li>
<li>VLSI Symposium（2022年〜 Technology and Circuits 合同開催）と ESSERC（2024年〜 ESSCIRC と ESSDERC の統合）は、<strong>回路系トラックの論文だけ</strong>を対象にします。論文タイトルを LLM で回路系／技術・デバイス系に分類し（data/track_labels.tsv）、どちらとも言えない講演は回路系に含めます。分類前の新しい論文にはキーワードによる暫定判定を使います。技術・デバイス系として除外した論文: {exc}。</li>
</ul>

<h2>対象と数え方</h2>
<ul>
<li>論文リストと著者所属は Crossref に登録された IEEE Xplore のメタデータから取得しています。Crossref に所属がない著者（主に2021年の会議論文）は OpenAlex の所属情報で補います。</li>
<li>チュートリアル、ショートコース、フォーラム、パネル、セッション概要、索引などの論文以外の項目は除外します。</li>
<li>所属は現在の所属ではなく、論文に記載された所属を使用します。「Formerly」「Emeritus」などの旧所属表記は数えません。</li>
<li>東京工業大学と東京医科歯科大学は、統合後の東京科学大学として集計します。</li>
</ul>

<h2 id="modes">カウント方式</h2>
<p>ランキングページの切替ボタンで、3つのカウント方式を選べます（選択はブラウザに記憶されます）。</p>
<ul>
<li><strong>フルカウント</strong>（既定）: 論文に関わった機関すべてに1本ずつ数えます。同じ機関の著者が複数いても1本です。</li>
<li><strong>筆頭著者</strong>: 筆頭著者（第一著者）の所属機関だけに1本を数えます。筆頭著者が複数の所属を持つ場合は、それぞれに1本です。</li>
<li><strong>著者按分</strong>: 1本の論文を著者数で等分し、各著者の持ち分をその著者の所属数でさらに等分して各機関に配分します。大型共著論文の影響を抑えた指標です。</li>
</ul>

<h2 id="championship">総合ランキング</h2>
<p>各会議・論文誌で論文数に基づく順位をポイントへ変換し、Tierの重みを掛けて合計します。ポイント配分は F1 の上位10位の基本配点を参考にしています。</p>
<ul>
<li><strong>Tier 1（×{wfmt(TIER_WEIGHT[1])}）</strong>: {t1}</li>
<li><strong>Tier 2（×{wfmt(TIER_WEIGHT[2])}）</strong>: {t2}</li>
</ul>
<div class="table-wrap"><table class="points-table">
<thead><tr><th>順位</th>{pts}</tr></thead>
<tbody><tr><th>Tier 1</th>{pv}</tr><tr><th>Tier 2</th>{pv2}</tr></tbody></table></div>
<ul>
<li>同点は標準競技順位（例: 1位、2位、2位、4位）とし、同順位には同じポイントを付与します。</li>
<li>その会議・論文誌で論文が0本の機関には順位を付けず、0ポイントとします。</li>
<li>総合ポイントが同じ機関は同順位です。</li>
<li>LIVE版の「前回」列は、最も新しく反映した会議・年を除いた場合との比較です（随時掲載のJSSCは起点にしません）。</li>
</ul>

<h2 id="organizations">企業・研究機関</h2>
<ul>
<li>日本の企業・公的研究機関を対象にします。グループ会社は親会社にまとめます（例: ソニーセミコンダクタソリューションズ → ソニー、NSITEXE → デンソー）。</li>
<li>海外企業は、所属表記が日本の拠点である場合だけ「（日本拠点）」として数えます。</li>
</ul>

<h2>著者表示</h2>
<p>ORCID が一致する著者は同一人物としてまとめ、最も多い表記で表示します。ORCID のない表記は、同じ綴りの ORCID 著者が1人だけいる場合にその人物へまとめます。それ以外は論文に記載された表記ごとに別の著者として扱います。</p>

<h2>読み方の注意</h2>
<p>このランキングは、選定した国際会議・論文誌での論文数を示すものです。研究の総合的な質、影響力、教育力、組織全体の優劣を測るものではありません。所属表記の揺れや欠落、トラック分類の誤りにより、取りこぼしや誤判定が含まれる可能性があります。</p>
</article>"""
    write(pg.path, layout(pg, "集計方法 | TopSSCS", body))


def main():
    all_papers = json.loads((ROOT / "data" / "papers.json").read_text(encoding="utf-8"))
    papers = [p for p in all_papers if p.get("track") != "T"]  # circuits track only on joint venues
    if SITE.exists():
        shutil.rmtree(SITE)
    (SITE / "assets").mkdir(parents=True)
    shutil.copy(ROOT / "src" / "style.css", SITE / "assets" / "style.css")
    shutil.copy(ROOT / "src" / "site.js", SITE / "assets" / "site.js")
    for ed in EDITIONS:
        for ent in ENTITIES:
            n = Builder(papers, ed, ent).build()
            print(f"{ed['label']} / {ENTITIES[ent]['label']}: {n}")
    build_methodology(all_papers, papers)


if __name__ == "__main__":
    main()
