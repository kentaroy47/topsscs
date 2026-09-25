# TopSSCS

固体回路系トップ国際会議・論文誌（ISSCC・VLSI Symposium・JSSC・CICC・A-SSCC・ESSCIRC/ESSERC）の論文数をもとに、日本の大学と企業・研究機関をランキングする静的サイトです。[TopCsUniv](https://topcsuniv.org/japan/) の集計方式（F1式ポイントによる総合ランキング）を固体回路分野に当てはめた非公式版です。

公開先: https://kentaroy47.github.io/topsscs/

## 集計の概要

- **版**: 2022–2026 LIVE（最新5年、前回比較つき）と 2021–2025 確定版
- **対象**: 大学 / 企業・研究機関（海外企業は日本拠点のみ）
- **カウント方式**（ページ上で切替）: フルカウント / 筆頭著者 / 著者按分
- **Tier と重み**（`scripts/conferences.py` の `TIER_WEIGHT`）: Tier 1（×1.0）ISSCC, VLSI, JSSC / Tier 2（×0.5）CICC, A-SSCC, ESSERC
- **回路系のみ**: VLSI（2022年〜）と ESSERC（2024年〜）は技術・デバイス系の論文を除外。分類は `data/track_labels.tsv`（LLM によるタイトル分類、C/T/U）。未分類の論文はキーワードで暫定判定
- **著者の名寄せ**: ORCID が一致する表記を同一人物として統合

## 仕組み

1. `scripts/fetch_crossref.py` — Crossref から論文と著者所属（IEEE Xplore のメタデータ）を取得し `data/raw/` に保存
2. `scripts/fill_openalex.py` — Crossref に所属がない著者（主に2021年）を OpenAlex で補完し `data/openalex.json` に保存
3. `scripts/build_data.py` — 論文以外の項目を除外し、所属を大学（`scripts/universities.py`）と企業・研究機関（`scripts/organizations.py`）に対応付けて `data/papers.json` を生成
4. `scripts/build_site.py` — `site/` に静的 HTML を生成（CSS/JS は `src/`）

```sh
python scripts/fetch_crossref.py   # 数分かかる
python scripts/fill_openalex.py
python scripts/build_data.py
python scripts/build_site.py       # site/index.html を開く
```

外部ライブラリは不要です（Python 3.9+ 標準ライブラリのみ）。

## デプロイ

`main` への push で GitHub Actions がビルドして GitHub Pages にデプロイします。毎週月曜（JST）と手動実行時は Crossref / OpenAlex から再取得し、更新されたデータをコミットします。

## メンテナンス

- 所属が拾えていない大学・企業は `scripts/universities.py` / `scripts/organizations.py` にパターンを追加してください。
- VLSI・ESSERC の新しい年の論文は、`data/track_labels.tsv` に `DOI<TAB>C|T|U` を追記すると暫定判定より優先されます。
