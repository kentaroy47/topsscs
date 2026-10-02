# TopSSCS

固体回路系トップ国際会議・論文誌（ISSCC・VLSI Symposium・JSSC・CICC・A-SSCC・ESSCIRC/ESSERC）の論文数をもとに、各国・全世界の大学と企業・研究機関をランキングする静的サイトです。[TopCsUniv](https://topcsuniv.org/japan/) の集計方式（F1式ポイントによる総合ランキング）を固体回路分野に当てはめた非公式版です。

公開先: https://kentaroy47.github.io/topsscs/

## 集計の概要

- **版**: 2022–2026 LIVE（最新5年、前回比較つき）と 2021–2025 確定版
- **地域**: 日本（初期表示）・アメリカ・中国・韓国・台湾・全世界。世界ランキングには、この5か国以外の機関も含みます
- **対象**: 大学 / 企業・研究機関。国別に順位・総合ポイントを再計算し、世界ランキングでは全機関で計算します
- **言語**: 右上の EN / 日本語ボタンで切替。設定はブラウザに保存し、`?lang=en` / `?lang=ja` で直接指定もできます
- **カウント方式**（ページ上で切替）: フルカウント / 筆頭著者 / 著者按分
- **Tier と重み**（`scripts/conferences.py` の `TIER_WEIGHT`）: Tier 1（×1.0）ISSCC, VLSI, JSSC / Tier 2（×0.5）CICC, A-SSCC, ESSERC
- **回路系のみ**: VLSI（2022年〜）と ESSERC（2024年〜）は技術・デバイス系の論文を除外。分類は `data/track_labels.tsv`（LLM によるタイトル分類、C/T/U）。未分類の論文はキーワードで暫定判定
- **著者の名寄せ**: ORCID が一致する表記を同一人物として統合

## 仕組み

1. `scripts/fetch_crossref.py` — Crossref から論文と著者所属（IEEE Xplore のメタデータ）を取得し `data/raw/` に保存
2. `scripts/fill_openalex.py` — 全論文の OpenAlex 著者所属・機関IDを `data/openalex.json` に、機関の親子関係を `data/openalex_institutions.json` に保存
3. `scripts/build_data.py` — 論文以外の項目を除外。日本の所属は大学・企業の独自辞書、海外は OpenAlex の国・機関種別と `scripts/global_orgs.py` のグループ統合で対応付け、`data/papers.json` と `data/institutions.json` を生成。日本ランキングで海外企業を数えるのは日本拠点の所属のみです
4. `scripts/build_site.py` — `site/` に静的 HTML を生成（CSS/JS は `src/`）

```sh
python scripts/fetch_crossref.py   # 数分かかる
python scripts/fill_openalex.py
python scripts/build_data.py
python scripts/build_site.py       # site/index.html を開く
```

外部ライブラリは不要です（Python 3.9+ 標準ライブラリのみ）。

国・機関種別・会議・版を切り替えても他の選択を保持します。各ランキングは上位100件まで表示します。海外所属の判定は OpenAlex の収録状況に依存するため、未収録・所属欠落による取りこぼしがあります。

検証（言語切り替えのテストには Node.js が必要）:

```sh
python -m unittest discover -s tests
node --test tests/site.test.js
```

## デプロイ

`main` への push で GitHub Actions がビルドして GitHub Pages にデプロイします。毎週月曜（JST）と手動実行時は Crossref / OpenAlex から再取得し、更新されたデータをコミットします。

## メンテナンス

- 所属が拾えていない大学・企業は `scripts/universities.py` / `scripts/organizations.py` にパターンを追加してください。
- VLSI・ESSERC の新しい年の論文は、`data/track_labels.tsv` に `DOI<TAB>C|T|U` を追記すると暫定判定より優先されます。
