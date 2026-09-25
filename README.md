# TopSSCS

固体回路系トップ国際会議・論文誌（ISSCC・VLSI Symposium・JSSC・CICC・A-SSCC・ESSCIRC/ESSERC）の論文数をもとに、日本の大学をランキングする静的サイトです。[TopCsUniv](https://topcsuniv.org/japan/) の集計方式（フルカウント、F1式ポイントによる総合ランキング）を固体回路分野に当てはめた非公式版です。

## Tier と重み

総合ランキングでは、F1式の配点に Tier ごとの重みを掛けます（`scripts/conferences.py` の `TIER_WEIGHT`）。

- Tier 1（×1.0）: ISSCC, VLSI, JSSC
- Tier 2（×0.5）: CICC, A-SSCC, ESSERC

## 仕組み

1. `scripts/fetch_crossref.py` — Crossref から各会議の論文と著者所属（IEEE Xplore のメタデータ）を取得し、`data/raw/` に保存
2. `scripts/build_data.py` — 論文以外の項目を除外し、所属文字列を `scripts/universities.py` の辞書で日本の大学に対応付けて `data/papers.json` を生成
3. `scripts/build_site.py` — `site/` に静的 HTML を生成

```sh
python scripts/fetch_crossref.py   # 数分かかる
python scripts/build_data.py
python scripts/build_site.py       # site/index.html を開く
```

外部ライブラリは不要です（Python 3.9+ 標準ライブラリのみ）。

## デプロイ

`main` への push で GitHub Actions がビルドして GitHub Pages にデプロイします。毎週月曜（JST）と手動実行時は Crossref から再取得し、更新されたデータをコミットします。

## 大学の追加・表記揺れ

所属が拾えていない大学は `scripts/universities.py` にパターンを追加してください。
