"""Generate the static TopSSCS site from data/papers.json into site/."""
import datetime as dt
import html
import json
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from conferences import BY_ID, CONFERENCES, EDITION, YEARS  # noqa: E402
from universities import BY_SLUG  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
POINTS = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
_FETCHED = ROOT / "data" / "fetched_at.txt"
UPDATED = _FETCHED.read_text(encoding="utf-8").strip() if _FETCHED.exists() else dt.date.today().isoformat()

esc = html.escape


# ---------------------------------------------------------------- ranking ---

def competition_rank(items, key):
    """Standard competition ranking (1, 2, 2, 4). items must be sorted desc by key."""
    ranks, prev, rank = [], None, 0
    for i, it in enumerate(items, 1):
        if key(it) != prev:
            rank, prev = i, key(it)
        ranks.append(rank)
    return ranks


def conf_counts(papers, conf, exclude=None):
    c = Counter()
    for p in papers:
        if p["conf"] != conf or (exclude and (p["conf"], p["year"]) == exclude):
            continue
        for slug in p["universities"]:
            c[slug] += 1
    return c


def rank_table(counter):
    rows = sorted(counter.items(), key=lambda kv: (-kv[1], BY_SLUG[kv[0]][1]))
    ranks = competition_rank(rows, key=lambda kv: kv[1])
    return [{"slug": s, "count": n, "rank": r} for (s, n), r in zip(rows, ranks)]


def championship(papers, confs, exclude=None):
    """Return (rows, per-conf rank tables)."""
    total = Counter()
    per_conf = {}
    for c in confs:
        table = rank_table(conf_counts(papers, c, exclude))
        per_conf[c] = {r["slug"]: r for r in table}
        for r in table:
            total[r["slug"]] += POINTS[r["rank"] - 1] if r["rank"] <= len(POINTS) else 0
    slugs = set().union(*[set(t) for t in per_conf.values()]) if per_conf else set()
    for s in slugs:
        total.setdefault(s, 0)
    rows = sorted(total.items(), key=lambda kv: (-kv[1], BY_SLUG[kv[0]][1]))
    ranks = competition_rank(rows, key=lambda kv: kv[1])
    return [{"slug": s, "points": n, "rank": r} for (s, n), r in zip(rows, ranks)], per_conf


def points_for(rank):
    return POINTS[rank - 1] if rank <= len(POINTS) else 0


# ------------------------------------------------------------------ html ----

def rel(depth):
    return "../" * depth or "./"


def page(title, body, depth, description=""):
    r = rel(depth)
    desc = description or "TopSSCSは、ISSCC・VLSI・CICC・A-SSCC・ESSERCの論文数をもとに、日本の大学の集積回路研究を比較できるランキングサイトです。"
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<link rel="stylesheet" href="{r}assets/style.css">
</head>
<body>
<a class="skip-link" href="#main">本文へ移動</a>
<header class="site-header"><div class="header-inner">
<a class="brand" href="{r}index.html" aria-label="TopSSCS トップ">Top<span>SSCS</span></a>
<nav aria-label="主要ナビゲーション"><a href="{r}index.html">ランキング</a><a href="{r}methodology.html">集計方法</a></nav>
</div></header>
<main id="main" class="page-shell">
{body}
</main>
<footer class="site-footer">
<p><strong>TopSSCS</strong> 固体回路系トップ国際会議における日本の大学の論文活動を可視化</p>
<p>Data: Crossref (IEEE Xplore metadata) · Updated {UPDATED} · <a href="{r}methodology.html">集計ルール</a></p>
</footer>
</body>
</html>
"""


def intro():
    return """<section class="page-intro">
<h1>日本の集積回路研究を、競争でもっと面白く。</h1>
<p class="lede">固体回路系トップ国際会議（ISSCC・VLSI・CICC・A-SSCC・ESSERC）の論文数をもとに日本の大学が競うスコアボード</p>
</section>"""


def tabs(depth, current):
    r = rel(depth)
    cur_all = ' aria-current="true"' if current == "all" else ""
    out = ['<nav class="field-tabs" aria-label="ランキングを選択">',
           f'<a class="field-tab championship-tab" href="{r}index.html"{cur_all}>総合</a>']
    for c in CONFERENCES:
        cur = ' aria-current="true"' if current == c["id"] else ""
        out.append(f'<a class="field-tab" href="{r}{c["id"]}/index.html"{cur} lang="en">{esc(c["short"])}</a>')
    out.append("</nav>")
    return "\n".join(out)


def rank_cell(rank):
    cls = "rank top-rank" if rank <= 3 else "rank"
    return f'<td class="{cls}">{rank}</td>'


def change_badge(cur_rank, prev_rank):
    if prev_rank is None:
        return '<span class="badge new">NEW</span>'
    d = prev_rank - cur_rank
    if d > 0:
        return f'<span class="up">↑{d}</span>'
    if d < 0:
        return f'<span class="down">↓{-d}</span>'
    return '<span class="flat">→</span>'


def delta(n):
    if n > 0:
        return f'<span class="delta increase">+{n}</span>'
    if n < 0:
        return f'<span class="delta decrease">{n}</span>'
    return '<span class="delta">±0</span>'


def uname(slug):
    return BY_SLUG[slug][0]


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ------------------------------------------------------------- analysis -----

def reflected_years(papers):
    ry = defaultdict(set)
    for p in papers:
        ry[p["conf"]].add(p["year"])
    return {c: sorted(v) for c, v in ry.items()}


def latest_unit(ry, conf):
    y = max(ry[conf])
    return (conf, y)


def latest_overall(ry):
    return max(((max(ys), BY_ID[c]["month"], c) for c, ys in ry.items()))


# ---------------------------------------------------------------- pages -----

def build_index(papers, ry):
    confs = [c["id"] for c in CONFERENCES if c["id"] in ry]
    rows, per_conf = championship(papers, confs)
    ly, _, lc = latest_overall(ry)
    prev_rows, _ = championship(papers, confs, exclude=(lc, ly))
    prev = {r["slug"]: r for r in prev_rows}

    trs = []
    for r in rows:
        s = r["slug"]
        p = prev.get(s)
        dp = r["points"] - (p["points"] if p else 0)
        pr = p["rank"] if p else None
        trs.append(
            f'<tr>{rank_cell(r["rank"])}'
            f'<td><a class="university-link" href="universities/{s}/index.html">{esc(uname(s))}</a></td>'
            f'<td class="numeric point-count-cell">{r["points"]}{delta(dp)}</td>'
            f'<td class="rank-change">{change_badge(r["rank"], pr)}</td></tr>')

    # breakdown table: rank (points) per conference
    head = "".join(f'<th class="numeric" lang="en">{esc(BY_ID[c]["short"])}</th>' for c in confs)
    brs = []
    for r in rows:
        s = r["slug"]
        cells = []
        for c in confs:
            e = per_conf[c].get(s)
            if e:
                pts = points_for(e["rank"])
                cls = "numeric" + (" scored" if pts else "")
                cells.append(f'<td class="{cls}"><span class="bd-rank">{e["rank"]}位</span>'
                             f'<span class="bd-pts">{pts}pt</span><span class="bd-n">{e["count"]}本</span></td>')
            else:
                cells.append('<td class="numeric muted">–</td>')
        brs.append(f'<tr>{rank_cell(r["rank"])}<td><a class="university-link" href="universities/{s}/index.html">'
                   f'{esc(uname(s))}</a></td>{"".join(cells)}<td class="numeric">{r["points"]}</td></tr>')

    status = live_status(ry)
    body = f"""{intro()}
{tabs(0, "all")}
<section class="ranking-card" aria-labelledby="ranking-title">
<div class="ranking-head"><div>
<p class="eyebrow">{EDITION} LIVE · {len(confs)}会議・同一ウェイト</p>
<h2 id="ranking-title">大学総合ランキング</h2>
<p class="ranking-context">{" / ".join(esc(BY_ID[c]["short"]) for c in confs)} · Updated: {UPDATED} · Latest: {esc(BY_ID[lc]["short"])} {ly} added</p>
</div><p class="record-count">{len(rows)}大学</p></div>
{status}
<div class="table-wrap"><table class="ranking-table" id="championship-summary">
<thead><tr><th scope="col">順位</th><th scope="col">大学</th><th scope="col" class="numeric">ポイント</th><th scope="col" class="rank-change">前回</th></tr></thead>
<tbody>
{chr(10).join(trs)}
</tbody></table></div>
<p class="status">会議別順位をF1方式でポイント化した大学総合ランキングです。「前回」は {esc(BY_ID[lc]["short"])} {ly} 反映前との比較です。<a href="methodology.html#championship">集計ルール</a></p>
</section>

<section class="breakdown" aria-labelledby="bd-title">
<div class="ranking-head"><div><h2 id="bd-title">会議別内訳</h2>
<p class="ranking-context">各会議での順位・獲得ポイント・論文数</p></div></div>
<div class="table-wrap"><table class="championship-breakdown">
<thead><tr><th scope="col">順位</th><th scope="col">大学</th>{head}<th scope="col" class="numeric">合計</th></tr></thead>
<tbody>
{chr(10).join(brs)}
</tbody></table></div>
</section>"""
    write(SITE / "index.html", page("TopSSCS | 日本の大学 固体回路トップ国際会議ランキング", body, 0))
    return rows, per_conf


def live_status(ry, conf=None):
    parts = []
    confs = [conf] if conf else [c["id"] for c in CONFERENCES]
    reflected = [f'{BY_ID[c]["short"]}' for c in confs if 2026 in ry.get(c, [])]
    pending = [f'{BY_ID[c]["short"]}' for c in confs if 2026 not in ry.get(c, [])]
    if reflected:
        parts.append(f'<p><strong>2026 reflected:</strong> {", ".join(reflected)}</p>')
    if pending:
        parts.append(f'<p><strong>Not yet reflected:</strong> {", ".join(pending)}（2022–2025を集計）</p>')
    return f'<div class="live-status">{"".join(parts)}</div>'


def build_conf(papers, ry, conf):
    c = BY_ID[conf]
    lu = latest_unit(ry, conf)
    table = rank_table(conf_counts(papers, conf))
    prev = {r["slug"]: r for r in rank_table(conf_counts(papers, conf, exclude=lu))}
    cp = [p for p in papers if p["conf"] == conf]
    jp = [p for p in cp if p["universities"]]
    years = ry[conf]

    trs = []
    for r in table:
        s = r["slug"]
        p = prev.get(s)
        trs.append(
            f'<tr>{rank_cell(r["rank"])}'
            f'<td><a class="university-link" href="universities/{s}/index.html">{esc(uname(s))}</a></td>'
            f'<td class="numeric paper-count-cell">{r["count"]}{delta(r["count"] - (p["count"] if p else 0))}</td>'
            f'<td class="rank-change">{change_badge(r["rank"], p["rank"] if p else None)}</td></tr>')

    per_year = Counter(p["year"] for p in cp)
    per_year_jp = Counter(p["year"] for p in jp)
    yrs = " · ".join(f"{y}: {per_year_jp[y]}/{per_year[y]}" for y in years)
    body = f"""{intro()}
{tabs(1, conf)}
<section class="ranking-card" aria-labelledby="ranking-title">
<div class="ranking-head"><div>
<p class="eyebrow">大学別集計</p>
<h2 id="ranking-title"><span lang="en">{esc(c["short"])}</span> 大学ランキング</h2>
<p class="ranking-context">{EDITION} LIVE · <a href="{c["url"]}" lang="en">{esc(c["name"])}</a> · {len(cp):,} papers
<span class="japan-paper-presence">（日本の大学関与論文 {len(jp)} papers・{100 * len(jp) / max(1, len(cp)):.2f}%）</span></p>
<p class="ranking-context">Updated: {UPDATED} · Latest: {esc(c["short"])} {lu[1]} added · 年別（日本の大学関与/全体）: {yrs}</p>
</div><p class="record-count">{len(table)}大学</p></div>
{live_status(ry, conf)}
<div class="table-wrap"><table class="ranking-table">
<thead><tr><th scope="col">順位</th><th scope="col">大学</th><th scope="col" class="numeric">論文数</th><th scope="col" class="rank-change">前回</th></tr></thead>
<tbody>
{chr(10).join(trs) if trs else '<tr><td colspan="4" class="empty">該当する論文はまだありません。</td></tr>'}
</tbody></table></div>
<p class="status">大学名から、所属著者と論文の内訳を確認できます。「前回」は {esc(c["short"])} {lu[1]} 反映前との比較です。</p>
</section>"""
    write(SITE / conf / "index.html",
          page(f"{c['short']} {EDITION} LIVE 大学ランキング | TopSSCS", body, 1))

    for r in table:
        build_univ_conf(papers, conf, r["slug"])


def paper_item(p, highlight=None, depth=0):
    c = BY_ID[p["conf"]]
    authors = []
    hl = set(highlight or [])
    for a in p["authors"]:
        authors.append(f"<strong>{esc(a)}</strong>" if a in hl else esc(a))
    univs = "、".join(esc(uname(s)) for s in p["universities"])
    return f"""<li class="paper-item">
<div class="paper-meta"><span lang="en">{esc(c["short"])}</span><br>{p["year"]}</div>
<div><a class="paper-title" href="https://doi.org/{esc(p["doi"])}" lang="en">{esc(p["title"])}</a></div>
<a class="doi-link" href="https://doi.org/{esc(p["doi"])}">DOI</a>
<div class="paper-coauthors" lang="en">{", ".join(authors)}</div>
<div class="paper-univs">{univs}</div>
</li>"""


def build_univ_conf(papers, conf, slug):
    c = BY_ID[conf]
    ps = sorted((p for p in papers if p["conf"] == conf and slug in p["universities"]),
                key=lambda p: (-p["year"], p["title"]))
    ac = Counter(a for p in ps for a in p["universities"][slug])
    rows = sorted(ac.items(), key=lambda kv: (-kv[1], kv[0]))
    ranks = competition_rank(rows, key=lambda kv: kv[1])
    trs = "\n".join(f'<tr>{rank_cell(rk)}<td lang="en"><span class="author-link">{esc(a)}</span></td>'
                    f'<td class="numeric">{n}</td></tr>' for (a, n), rk in zip(rows, ranks))
    items = "\n".join(paper_item(p, p["universities"][slug]) for p in ps)
    body = f"""<a class="back-link" href="../../index.html">← <span lang="en">{esc(c["short"])}</span> 大学ランキングへ戻る</a>
<section class="detail-heading">
<p class="eyebrow">大学 × 会議</p>
<h1>{esc(uname(slug))}</h1>
<p class="lede"><span lang="en">{esc(c["short"])}</span> / {EDITION} LIVE · <a href="../../../universities/{slug}/index.html">大学ページ</a></p>
<p class="stat-line">対象論文 <strong>{len(ps)}</strong> 本 <span class="stat-detail">· 所属著者 {len(rows)}表記</span></p>
</section>
<section>
<div class="ranking-head"><div><h2>論文表記の著者名</h2>
<p class="ranking-context">著者名は論文に記載された表記をそのまま使用しており、同一人物の名寄せは行っていません。</p></div></div>
<div class="table-wrap"><table class="ranking-table">
<thead><tr><th scope="col">順位</th><th scope="col">著者</th><th scope="col" class="numeric">論文数</th></tr></thead>
<tbody>{trs}</tbody></table></div>
</section>
<section class="papers">
<div class="ranking-head"><div><h2>対象論文</h2>
<p class="ranking-context">太字は{esc(uname(slug))}所属として確認できた著者です。</p></div></div>
<ol class="paper-list">
{items}
</ol>
</section>"""
    write(SITE / conf / "universities" / slug / "index.html",
          page(f"{uname(slug)} × {c['short']} | TopSSCS", body, 3))


def build_univ(papers, slug, champ_row, per_conf):
    ps = sorted((p for p in papers if slug in p["universities"]),
                key=lambda p: (-p["year"], p["conf"], p["title"]))
    rows = []
    for c in CONFERENCES:
        e = per_conf.get(c["id"], {}).get(slug)
        if e:
            rows.append(f'<tr><td lang="en"><a href="../../{c["id"]}/universities/{slug}/index.html">{esc(c["short"])}</a></td>'
                        f'<td class="numeric">{e["count"]}</td><td class="numeric">{e["rank"]}位</td>'
                        f'<td class="numeric">{points_for(e["rank"])}</td></tr>')
        else:
            rows.append(f'<tr><td lang="en">{esc(c["short"])}</td><td class="numeric">0</td>'
                        f'<td class="numeric muted">–</td><td class="numeric">0</td></tr>')
    by_year = Counter(p["year"] for p in ps)
    ystr = " · ".join(f"{y}: {by_year[y]}" for y in YEARS)
    items = "\n".join(paper_item(p, p["universities"][slug]) for p in ps)
    ja, en = BY_SLUG[slug]
    body = f"""<a class="back-link" href="../../index.html">← 総合ランキングへ戻る</a>
<section class="detail-heading">
<p class="eyebrow">大学</p>
<h1>{esc(ja)}</h1>
<p class="lede" lang="en">{esc(en)}</p>
<p class="stat-line">総合 <strong>{champ_row["rank"]}</strong> 位 · <strong>{champ_row["points"]}</strong> pt · 対象論文 <strong>{len(ps)}</strong> 本</p>
<p class="ranking-context">年別: {ystr}</p>
</section>
<section>
<div class="ranking-head"><div><h2>会議別</h2></div></div>
<div class="table-wrap"><table class="univ-table">
<thead><tr><th scope="col">会議</th><th scope="col" class="numeric">論文数</th><th scope="col" class="numeric">順位</th><th scope="col" class="numeric">ポイント</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table></div>
</section>
<section class="papers">
<div class="ranking-head"><div><h2>対象論文</h2>
<p class="ranking-context">太字は{esc(ja)}所属として確認できた著者です。</p></div></div>
<ol class="paper-list">
{items}
</ol>
</section>"""
    write(SITE / "universities" / slug / "index.html", page(f"{ja} | TopSSCS", body, 2))


def build_methodology(ry):
    conf_rows = "\n".join(
        f'<tr><td lang="en"><strong>{esc(c["short"])}</strong></td><td lang="en">{esc(c["name"])}</td>'
        f'<td>{", ".join(str(y) for y in ry.get(c["id"], []))}</td></tr>' for c in CONFERENCES)
    pts = "".join(f"<td>{i}</td>" for i in range(1, 11))
    pv = "".join(f"<td>{p}</td>" for p in POINTS)
    body = f"""<a class="back-link" href="index.html">← ランキングへ戻る</a>
<article class="prose">
<p class="eyebrow">集計方針</p>
<h1>集計方法</h1>
<p>TopSSCS は、IEEE Solid-State Circuits Society（SSCS）系のトップ国際会議における日本の大学の論文活動を、論文公開時点の所属情報に基づいて集計します。<a href="https://topcsuniv.org/japan/">TopCsUniv</a> の集計方式を固体回路分野に当てはめた非公式版です。</p>

<h2>対象会議</h2>
<div class="table-wrap"><table>
<thead><tr><th>略称</th><th>会議名</th><th>反映済みの年</th></tr></thead>
<tbody>{conf_rows}</tbody></table></div>
<ul>
<li>期間は {EDITION} の5年間（LIVE）です。2026年の会議が未開催、または論文メタデータ未公開の会議は2022–2025を集計します。</li>
<li>VLSI Symposium は Technology と Circuits の合同開催、ESSERC（2024年〜）は ESSCIRC と ESSDERC の統合会議のため、会議全体の論文を対象としています。2022–2023 は ESSCIRC のみです。</li>
</ul>

<h2>対象と数え方</h2>
<ul>
<li>論文リストと著者所属は Crossref に登録された IEEE Xplore のメタデータから取得しています。</li>
<li>チュートリアル、ショートコース、フォーラム、パネル、セッション概要、索引などの論文以外の項目は除外します。</li>
<li>大学ランキングはフルカウント方式です。同じ大学の著者が複数いても、その大学には1論文として数えます。</li>
<li>複数の日本の大学による共著論文は、各大学に1論文ずつ数えます。</li>
<li>所属は現在の所属ではなく、論文に記載された所属を使用します。「Formerly」「Emeritus」などの旧所属表記は数えません。</li>
<li>東京工業大学と東京医科歯科大学は、統合後の東京科学大学として集計します。</li>
</ul>

<h2 id="championship">大学総合ランキング</h2>
<p>各会議で大学別論文数に基づく順位をポイントへ変換し、大学ごとに合計します。会議の重みはすべて同じです。ポイント配分は F1 の上位10位の基本配点を参考にしています。</p>
<div class="table-wrap"><table class="points-table">
<thead><tr><th>会議順位</th>{pts}</tr></thead>
<tbody><tr><th>ポイント</th>{pv}</tr></tbody></table></div>
<ul>
<li>同点は標準競技順位（例: 1位、2位、2位、4位）とし、同順位には同じポイントを付与します。</li>
<li>その会議で論文が0本の大学には順位を付けず、0ポイントとします。</li>
<li>総合ポイントが同じ大学は同順位です。</li>
<li>「前回」列は、最も新しく反映した会議・年を除いた場合の順位との比較です。</li>
</ul>

<h2>著者表示</h2>
<p>著者名は論文に記載された表記をそのまま使用しており、同一人物の名寄せは行っていません。著者の所属欄から大学を確認できた場合だけ著者一覧へ反映します。</p>

<h2>読み方の注意</h2>
<p>このランキングは、選定した国際会議での論文数を示すものです。研究の総合的な質、影響力、教育力、大学全体の優劣を測るものではありません。Crossref の所属表記の揺れや欠落により、取りこぼしや誤判定が含まれる可能性があります。</p>
</article>"""
    write(SITE / "methodology.html", page("集計方法 | TopSSCS", body, 0))


def main():
    papers = json.loads((ROOT / "data" / "papers.json").read_text(encoding="utf-8"))
    papers = [p for p in papers if p["year"] in YEARS]
    if SITE.exists():
        shutil.rmtree(SITE)
    (SITE / "assets").mkdir(parents=True)
    shutil.copy(ROOT / "src" / "style.css", SITE / "assets" / "style.css")
    ry = reflected_years(papers)
    rows, per_conf = build_index(papers, ry)
    for c in CONFERENCES:
        if c["id"] in ry:
            build_conf(papers, ry, c["id"])
    for r in rows:
        build_univ(papers, r["slug"], r, per_conf)
    build_methodology(ry)
    print(f"built {len(rows)} universities into {SITE}")


if __name__ == "__main__":
    main()
