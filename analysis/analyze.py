"""parse.py の出力を集計して analysis/out/stats.json を作る。"""
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

OUT = Path(__file__).resolve().parent / "out"
E = json.loads((OUT / "episodes.json").read_text(encoding="utf-8"))
METAS = json.loads((OUT / "meta_notes.json").read_text(encoding="utf-8"))

SERIES_ORDER = ["1期前半(1-80)", "1期後半(81-193)", "2期すいぱら編(194-244)", "2期ハムハーの木編(245-296)", "劇場版・OVA"]

# 採点値：★は 5.5 として扱う（★付き 5 と無印 5 の差を残すため）。素点も別に出す。
def score(e):
    if e["rating"] is None:
        return None
    return 5.5 if e["star"] else float(e["rating"])


# ---- キャラ辞書 -------------------------------------------------------------
# (表示名, グループ, 正規表現)
CHARS = [
    ("ハム太郎", "ハムちゃんず", r"(?<!とっとこ)(?<!とっとこ )ハム太郎(?![0-9２-４]| ハムちゃんず大集合| ラブラブ| にじいろ)"),
    ("リボンちゃん", "ハムちゃんず", r"リボン(?!ちゃん危機一髪)"),
    ("タイショーくん", "ハムちゃんず", r"タイショー"),
    ("こうしくん", "ハムちゃんず", r"こうし(?!て|た|よう|ろ|ま)"),
    ("トンガリくん", "ハムちゃんず", r"トンガリ"),
    ("まいどくん", "ハムちゃんず", r"まいど"),
    ("めがねくん", "ハムちゃんず", r"めがね"),
    ("のっぽくん", "ハムちゃんず", r"のっぽ"),
    ("パンダくん", "ハムちゃんず", r"パンダ"),
    ("ちび丸ちゃん", "ハムちゃんず", r"ちび丸"),
    ("マフラーちゃん", "ハムちゃんず", r"マフラー"),
    ("ねてるくん", "ハムちゃんず", r"ねてる"),
    ("かぶるくん", "ハムちゃんず", r"かぶる"),
    ("トラハムくん", "ハムちゃんず", r"トラハム(?:くん|兄(?!妹))"),
    ("トラハムちゃん", "ハムちゃんず", r"トラハム(?:ちゃん|妹)"),
    ("長老ハム", "準レギュラー", r"長老"),
    ("じゃじゃハムちゃん", "準レギュラー", r"じゃじゃ"),
    ("くるりんちゃん", "準レギュラー", r"くるりん"),
    ("おしゃれちゃん", "準レギュラー", r"おしゃれ"),
    ("ナースちゃん", "準レギュラー", r"ナース"),
    ("ぬけないくん", "準レギュラー", r"ぬけない"),
    ("トン吉", "準レギュラー", r"トン吉"),
    ("サブさん", "準レギュラー", r"サブ(?!タイ)"),
    ("デビハムくん", "2期以降", r"デビハム"),
    ("ラピスちゃん", "2期以降", r"ラピス|ラピラズ"),
    ("ラズリーちゃん", "2期以降", r"ラズリー|ラピラズ"),
    ("おとめ・ズー", "2期以降", r"おとめ"),
    ("ニンハム", "2期以降", r"ニンハム"),
    ("マジカル", "2期以降", r"マジカル"),
    ("ミステリー", "2期以降", r"ミステリー"),
    ("そらハム", "2期以降", r"そらハム"),
    ("ロコちゃん", "人間", r"ロコ(?!モ)"),
    ("木村くん", "人間", r"木村|キムラ"),
    ("ロベルト", "人間", r"ロベルト"),
]

LAUGH = r"w+(?![a-zA-Z])|ｗ+|草"


def per_k(n, chars):
    return round(n / chars * 1000, 2) if chars else 0.0


def main():
    for e in E:
        e["score"] = score(e)
    rated = [e for e in E if e["score"] is not None]
    tv_rated = [e for e in rated if e["kind"] == "tv"]

    stats: dict = {}

    # 1. 評価の分布
    dist = Counter("★" if e["star"] else str(e["rating"]) for e in rated)
    stats["dist"] = {k: dist.get(k, 0) for k in ["★", "5", "4", "3", "2", "1"]}
    stats["n_entries"] = len(E)
    stats["n_rated"] = len(rated)

    # 2. シリーズ別
    by_series = []
    for s in SERIES_ORDER:
        es = [e for e in E if e["series"] == s]
        rs = [e for e in es if e["score"] is not None]
        chars = sum(e["memo_chars"] for e in es)
        by_series.append({
            "series": s,
            "n": len(es),
            "mean_raw": round(mean(e["rating"] for e in rs), 3),
            "star_rate": round(sum(e["star"] for e in rs) / len(rs), 3),
            "le3_rate": round(sum(e["rating"] <= 3 for e in rs) / len(rs), 3),
            "dist": {k: sum(1 for e in rs if ("★" if e["star"] else str(e["rating"])) == k) for k in ["★", "5", "4", "3", "2", "1"]},
            "chars_per_entry": round(chars / len(es)),
        })
    stats["by_series"] = by_series

    # 3. 視聴順の推移（エピソード単位）
    timeline = []
    for e in E:
        timeline.append({
            "order": e["order"], "label": e["label"], "kind": e["kind"], "series": e["series"],
            "rating": e["rating"], "star": e["star"], "score": e["score"], "chars": e["memo_chars"],
            "laugh": len(re.findall(LAUGH, e["memo"])),
        })
    stats["timeline"] = timeline

    # 4. キャラ言及
    char_rows = []
    for name, group, pat in CHARS:
        rx = re.compile(pat)
        per_series = {}
        for s in SERIES_ORDER[:4]:
            es = [e for e in E if e["series"] == s]
            hits = sum(1 for e in es if rx.search(e["memo"]))
            per_series[s] = round(hits / len(es), 3)
        with_ = [e for e in rated if rx.search(e["memo"])]
        without = [e for e in rated if not rx.search(e["memo"])]
        total = sum(len(rx.findall(e["memo"])) for e in E)
        char_rows.append({
            "name": name, "group": group, "mentions": total, "episodes": len(with_),
            "share_by_series": per_series,
            "mean_with": round(mean(e["rating"] for e in with_), 3) if with_ else None,
            "star_with": round(sum(e["star"] for e in with_) / len(with_), 3) if with_ else None,
            "mean_without": round(mean(e["rating"] for e in without), 3),
            "first_seen": next((e["label"] for e in E if rx.search(e["memo"])), None),
        })
    stats["chars"] = char_rows

    base_mean = mean(e["rating"] for e in rated)
    base_star = sum(e["star"] for e in rated) / len(rated)
    stats["base"] = {"mean": round(base_mean, 3), "star": round(base_star, 3)}

    # 6. 落差バイアス：直前の評価ごとの次回評価
    seq = [e for e in E if e["score"] is not None]
    trans = defaultdict(list)
    for a, b in zip(seq, seq[1:]):
        key = "★" if a["star"] else ("5" if a["rating"] == 5 else ("4" if a["rating"] == 4 else "≤3"))
        trans[key].append(b)
    stats["after"] = {
        k: {"n": len(v), "mean_next": round(mean(x["rating"] for x in v), 3),
            "star_next": round(sum(x["star"] for x in v) / len(v), 3)}
        for k, v in trans.items()
    }
    # ラグ1 自己相関（score）
    xs = [e["score"] for e in seq]
    mu = mean(xs)
    num = sum((a - mu) * (b - mu) for a, b in zip(xs, xs[1:]))
    den = sum((a - mu) ** 2 for a in xs)
    stats["autocorr_lag1"] = round(num / den, 3)

    # 最長連続★・最長連続 4 点以下
    def longest(pred):
        best, cur, best_end = 0, 0, None
        for e in seq:
            cur = cur + 1 if pred(e) else 0
            if cur > best:
                best, best_end = cur, e["label"]
        return best, best_end
    stats["streaks"] = {
        "star": longest(lambda e: e["star"]),
        "five_or_star": longest(lambda e: e["rating"] == 5),
        "four_or_less": longest(lambda e: e["rating"] <= 4),
    }

    # 7. 文体統計（シリーズ別、1000 字あたり）
    STYLE = [
        ("笑い(w/草)", LAUGH),
        ("関西弁(やん/やろ/やな/ほんま/ええ/あかん/なんや)", r"やん(?!ちゃ)|やろ|やな(?!い)|ほんま|ええ(?!と)|あかん|なんや"),
        ("ツッコミ(だろ/かよ/なんだよ/やめろ)", r"だろ|かよ|なんだよ|なんだコレ|なんだこれ|やめろ|おかしい"),
        ("「流石に」", r"流石に|さすがに"),
        ("「かわいい」", r"かわいい|可愛い"),
        ("「マジ/ガチ」", r"マジ|ガチ"),
        ("「？」", r"[？?]"),
        ("「...」", r"\.\.\.|…"),
    ]
    style_rows = []
    for name, pat in STYLE:
        row = {"style": name}
        for s in SERIES_ORDER[:4]:
            es = [e for e in E if e["series"] == s]
            txt = "".join(e["memo"] for e in es)
            row[s] = per_k(len(re.findall(pat, txt)), len(txt))
        style_rows.append(row)
    stats["style"] = style_rows

    # 8. 記録系
    longest_memo = sorted(E, key=lambda e: -e["memo_chars"])[:5]
    stats["longest"] = [{"label": e["label"], "chars": e["memo_chars"], "rating": e["rating"], "star": e["star"]} for e in longest_memo]
    shortest = sorted([e for e in E if e["kind"] == "tv"], key=lambda e: e["memo_chars"])[:5]
    stats["shortest"] = [{"label": e["label"], "chars": e["memo_chars"], "memo": e["memo"]} for e in shortest]
    laughiest = sorted(E, key=lambda e: -len(re.findall(LAUGH, e["memo"])))[:5]
    stats["laughiest"] = [{"label": e["label"], "laugh": len(re.findall(LAUGH, e["memo"])), "rating": e["rating"], "star": e["star"]} for e in laughiest]
    stats["low"] = [{"label": e["label"], "rating": e["rating"], "memo": e["memo"]} for e in rated if e["rating"] <= 3]

    # 文字数と評価の相関
    ys = [e["score"] for e in rated]
    cs = [e["memo_chars"] for e in rated]
    my, mc = mean(ys), mean(cs)
    cov = sum((a - my) * (b - mc) for a, b in zip(ys, cs))
    r = cov / math.sqrt(sum((a - my) ** 2 for a in ys) * sum((b - mc) ** 2 for b in cs))
    stats["corr_chars_score"] = round(r, 3)
    stats["chars_by_rating"] = {
        k: round(mean(e["memo_chars"] for e in rated if ("★" if e["star"] else str(e["rating"])) == k))
        for k in ["★", "5", "4", "3"]
    }

    (OUT / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- コンソール要約 ----
    print("dist", stats["dist"], "base", stats["base"])
    for s in by_series:
        print(s)
    print("after", stats["after"], "acf1", stats["autocorr_lag1"])
    print("streaks", stats["streaks"])
    print("corr chars-score", stats["corr_chars_score"], stats["chars_by_rating"])
    print("--- chars")
    for c in sorted(char_rows, key=lambda c: -c["mentions"]):
        print(c)
    print("--- style")
    for s in style_rows:
        print(s)
    print("longest", stats["longest"])
    print("laughiest", stats["laughiest"])
    print("shortest", stats["shortest"])


if __name__ == "__main__":
    main()
