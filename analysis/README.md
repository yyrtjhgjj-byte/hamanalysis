# ハム太郎感想メモの分析

`docs/1.txt`〜`9.txt`（初見の各話メモ）をパースして集計・検定したコード一式です。

結果のレポート: `out/report.html`（全296話のメモ閲覧・検索つき）

## 実行

```sh
pip install -r analysis/requirements.txt
python3 analysis/parse.py       # docs → out/episodes.csv / episodes.json / meta_notes.json
python3 analysis/analyze.py     # 分布・シリーズ別・キャラ言及・文体 → out/stats.json
python3 analysis/deep.py        # 並べ替え検定・重回帰・特徴語を stats.json に追記
python3 analysis/build_page.py  # out/report.html を生成
```

## ファイル

| ファイル | 中身 |
|---|---|
| `parse.py` | 「・話数［評価］★」見出しでエントリを切り出す。見出しでない「・」行はメタ考察として分離 |
| `labels.py` | 夢回・死にかける回・作画の良し悪しの手動ラベル（該当行を目視で確定） |
| `analyze.py` | 基本集計 |
| `deep.py` | 自己申告の採点式の答え合わせ（並べ替え検定 20,000 回、OLS）、落差バイアス、作画ジンクス、特徴語 |
| `build_page.py` / `report_template.html` | レポート HTML の生成 |
| `out/episodes.csv` | 1 エントリ 1 行の表（Excel でそのまま開ける UTF-8 BOM 付き） |

## 主な結果

- 評価: ★91 / 5点114 / 4点66 / 3点15 / 2点2 / 1点1（空欄2）。平均4.63
- 夢回・劇中劇の減点は自己申告（−1）より重く、重回帰で −1.68。3点以下18回のうち10回が夢回
- 「ハムちゃんず全員が出ると甘くなりがち」は外れ（全員回の平均4.53、それ以外4.64）
- 申告にない減点要素: じゃじゃハム（−0.82、p=0.004）。加点要素: 死にかける回（★率53% vs 30%）
- 「面白い時に限って作画がゴミ」は外れ（122話以降の★率: 作画ほめ41% / けなし26% / 言及なし15%）
- ハムハーの木編（245〜296話）で★率10%、メモ1件94字、「マジ・ガチ」は1期前半の4.7倍
