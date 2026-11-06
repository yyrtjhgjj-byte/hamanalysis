"""analyze.py の後に実行。検定・回帰・特徴語を stats.json に追記する。"""
from __future__ import annotations

import json
import math
import random
import re
from collections import Counter
from pathlib import Path
from statistics import mean

import numpy as np
from janome.tokenizer import Tokenizer

OUT = Path(__file__).resolve().parent / "out"
E = json.loads((OUT / "episodes.json").read_text(encoding="utf-8"))
stats = json.loads((OUT / "stats.json").read_text(encoding="utf-8"))
rated = [e for e in E if e["rating"] is not None]
random.seed(0)

from labels import DANGER, DREAM, SAKUGA_BAD, SAKUGA_GOOD  # noqa: E402

# ---- 自己申告の採点式に対応する特徴 ----------------------------------------
# 6.txt「今まで付けてた点数の基本の算出方法が分かった」
#   基礎点3 / かわいいキャラがメイン +1 / かわいくないキャラがメイン ±0,-1
#   目新しい展開 +1,2 / 夢回・劇中劇 -1 / 作画が良い +0.5
REG_FEATURES = [
    ("夢回・劇中劇", DREAM, "-1"),
    ("作画が良い", SAKUGA_GOOD, "+0.5"),
    ("「かわいい」と書いた", r"かわいい|可愛い", "+1"),
    ("「かわいくない」と書いた", r"かわいくな|可愛くな", "±0〜-1"),
    ("目新しさ(初めて/珍しい/新鮮)", r"初めて|珍しい|新鮮|新しい|斬新|見たことない", "+1〜2"),
    ("ハムちゃんず全員", r"ハムちゃんず全員|全員(?:出|集合|いる|喋|ちゃんと)|みんな出|フルメンバー|ちゃんと全員", "甘くなりがち"),
    ("死にかける回", DANGER, "（申告なし）"),
    ("じゃじゃハム", r"じゃじゃ", "（申告なし）"),
]


def hit(feat, e):
    return e["label"] in feat if isinstance(feat, set) else bool(re.search(feat, e["memo"]))


def perm_test(y, mask, n_iter=20000):
    """mask=True 群と False 群の平均差の両側並べ替え検定。"""
    y = np.asarray(y, float)
    mask = np.asarray(mask, bool)
    k = mask.sum()
    if k == 0 or k == len(y):
        return None, None
    obs = y[mask].mean() - y[~mask].mean()
    rng = np.random.default_rng(0)
    cnt = 0
    for _ in range(n_iter):
        p = rng.permutation(len(y))[:k]
        m = np.zeros(len(y), bool)
        m[p] = True
        d = y[m].mean() - y[~m].mean()
        if abs(d) >= abs(obs) - 1e-12:
            cnt += 1
    return float(obs), (cnt + 1) / (n_iter + 1)


y_raw = [e["rating"] for e in rated]
y_star = [1.0 if e["star"] else 0.0 for e in rated]
tests = []
X_cols = []
for name, pat, claim in REG_FEATURES:
    mask = [hit(pat, e) for e in rated]
    d, p = perm_test(y_raw, mask)
    ds, ps = perm_test(y_star, mask)
    tests.append({
        "feature": name, "claim": claim, "n": int(sum(mask)),
        "mean_with": round(mean(r for r, m in zip(y_raw, mask) if m), 3),
        "mean_without": round(mean(r for r, m in zip(y_raw, mask) if not m), 3),
        "diff": round(d, 3), "p": round(p, 4),
        "star_with": round(mean(s for s, m in zip(y_star, mask) if m), 3),
        "star_without": round(mean(s for s, m in zip(y_star, mask) if not m), 3),
        "star_diff": round(ds, 3), "star_p": round(ps, 4),
    })
    X_cols.append(mask)
stats["tests"] = tests

# ---- 重回帰（OLS）: 素点 ~ 特徴 -------------------------------------------
X = np.column_stack([np.ones(len(rated))] + [np.asarray(c, float) for c in X_cols])
yv = np.asarray(y_raw, float)
beta, *_ = np.linalg.lstsq(X, yv, rcond=None)
resid = yv - X @ beta
n, k = X.shape
sigma2 = resid @ resid / (n - k)
se = np.sqrt(np.diag(sigma2 * np.linalg.inv(X.T @ X)))
r2 = 1 - (resid @ resid) / ((yv - yv.mean()) @ (yv - yv.mean()))
stats["ols"] = {
    "r2": round(float(r2), 3),
    "n": n,
    "coef": [{"term": "切片(基礎点)", "beta": round(float(beta[0]), 3), "se": round(float(se[0]), 3), "claim": "3"}]
    + [{"term": f[0], "beta": round(float(b), 3), "se": round(float(s), 3), "claim": f[2]}
       for f, b, s in zip(REG_FEATURES, beta[1:], se[1:])],
}

# ---- 落差バイアス：自己相関の並べ替え検定 ---------------------------------
seq = [5.5 if e["star"] else float(e["rating"]) for e in E if e["rating"] is not None]
def acf1(xs):
    xs = np.asarray(xs)
    mu = xs.mean()
    return float(((xs[:-1] - mu) * (xs[1:] - mu)).sum() / ((xs - mu) ** 2).sum())
obs = acf1(seq)
rng = np.random.default_rng(1)
null = [acf1(rng.permutation(seq)) for _ in range(20000)]
stats["acf_test"] = {"acf1": round(obs, 3), "p_two_sided": round((sum(abs(v) >= abs(obs) for v in null) + 1) / 20001, 4)}

# 直前 3 話の平均が低い（≤4.34）ときと高いときで次回の評価を比較
roll = []
for i in range(3, len(seq)):
    roll.append((mean(seq[i - 3:i]), seq[i]))
low = [b for a, b in roll if a <= 4.5]
high = [b for a, b in roll if a >= 5.5 - 1e-9]
stats["contrast"] = {
    "after_low3": {"n": len(low), "mean_next": round(mean(low), 3), "star_next": round(mean(1 if v == 5.5 else 0 for v in low), 3)},
    "after_star3": {"n": len(high), "mean_next": round(mean(high), 3), "star_next": round(mean(1 if v == 5.5 else 0 for v in high), 3)},
    "overall_star": round(mean(1 if v == 5.5 else 0 for v in seq), 3),
}

# ---- 10 話ビン ------------------------------------------------------------
bins = []
tv = [e for e in E if e["kind"] == "tv" and e["rating"] is not None]
for lo in range(1, 297, 20):
    hi = lo + 19
    es = [e for e in tv if lo <= e["ep"] <= hi]
    if not es:
        continue
    bins.append({
        "range": f"{lo}-{min(hi, 296)}",
        "n": len(es),
        "mean": round(mean(e["rating"] for e in es), 3),
        "star": round(mean(e["star"] for e in es), 3),
        "chars": round(mean(e["memo_chars"] for e in es)),
    })
stats["bins20"] = bins

# ---- 特徴語（★回 vs 4 点以下の回）: 情報量付きディリクレ事前の log-odds ----
tok = Tokenizer()
STOP = set("する いる ある なる れる られる てる 思う 言う いう こと もの よう それ これ あれ そう ない くん ちゃん さん の ん 回 話 感じ 今回 気 方 中 時 人 さ 的 系 化 一 二 何 的 ここ そこ みたい やつ 奴 自分 すぎる 出る 来る くる 見る 行く やる くれる しまう ちゃう てる 為".split())


def words(text):
    out = []
    for t in tok.tokenize(text):
        pos = t.part_of_speech.split(",")
        base = t.base_form if t.base_form != "*" else t.surface
        if pos[0] in ("名詞", "形容詞", "動詞") and pos[1] not in ("非自立", "数", "代名詞", "接尾"):
            if len(base) >= 2 and base not in STOP and not re.fullmatch(r"[0-9a-zA-Z０-９ｗw…・、。！？!?\.\-〜ー]+", base):
                out.append(base)
    return out


grp_a = Counter()  # ★
grp_b = Counter()  # ≤4
for e in rated:
    ws = set(words(e["memo"]))  # 文書頻度ベース（1 話で連呼しても 1 回）
    if e["star"]:
        grp_a.update(ws)
    elif e["rating"] <= 4:
        grp_b.update(ws)
prior = grp_a + grp_b
a0 = sum(prior.values())
na, nb = sum(grp_a.values()), sum(grp_b.values())
scores = []
for w, pw in prior.items():
    if pw < 4:
        continue
    ya, yb = grp_a[w], grp_b[w]
    aw = pw * 0.5  # 事前の強さ
    a0s = a0 * 0.5
    la = math.log((ya + aw) / (na + a0s - ya - aw))
    lb = math.log((yb + aw) / (nb + a0s - yb - aw))
    var = 1 / (ya + aw) + 1 / (yb + aw)
    scores.append((w, (la - lb) / math.sqrt(var), ya, yb))
scores.sort(key=lambda x: -x[1])
stats["words_star"] = [{"w": w, "z": round(z, 2), "star_eps": a, "le4_eps": b} for w, z, a, b in scores[:20]]
stats["words_low"] = [{"w": w, "z": round(z, 2), "star_eps": a, "le4_eps": b} for w, z, a, b in scores[::-1][:20]]
stats["group_sizes"] = {"star": sum(1 for e in rated if e["star"]), "le4": sum(1 for e in rated if e["rating"] <= 4)}

# ---- 作画 × 評価（122 話以降の TV 回） -------------------------------------
late = [e for e in rated if e["kind"] == "tv" and e["ep"] >= 122]
def summarize(es):
    return {"n": len(es), "mean": round(mean(e["rating"] for e in es), 3),
            "star": round(mean(e["star"] for e in es), 3),
            "le4": round(mean(e["rating"] <= 4 for e in es), 3)}
g = [e for e in late if e["label"] in SAKUGA_GOOD]
b = [e for e in late if e["label"] in SAKUGA_BAD]
o = [e for e in late if e["label"] not in SAKUGA_GOOD | SAKUGA_BAD]
mask_b = [e["label"] in SAKUGA_BAD for e in g + b]
_, p_star_gb = perm_test([1.0 if e["star"] else 0.0 for e in g + b], mask_b)
_, p_mean_gb = perm_test([e["rating"] for e in g + b], mask_b)
dream_good = sum(1 for e in E if e["label"] in DREAM and e["label"] in SAKUGA_GOOD)
dream_late = [e for e in E if e["label"] in DREAM and e["kind"] == "tv" and e["ep"] >= 122]
nondream_late = [e for e in E if e["label"] not in DREAM and e["kind"] == "tv" and e["ep"] >= 122]
stats["sakuga"] = {
    "good": summarize(g), "bad": summarize(b), "none": summarize(o),
    "p_star_good_vs_bad": round(p_star_gb, 4), "p_mean_good_vs_bad": round(p_mean_gb, 4),
    "dream_late_n": len(dream_late),
    "dream_late_good": sum(e["label"] in SAKUGA_GOOD for e in dream_late),
    "nondream_late_good_rate": round(mean(e["label"] in SAKUGA_GOOD for e in nondream_late), 3),
    "dream_late_bad": sum(e["label"] in SAKUGA_BAD for e in dream_late),
    "nondream_late_bad_rate": round(mean(e["label"] in SAKUGA_BAD for e in nondream_late), 3),
}
stats["dream_eps"] = [{"label": e["label"], "rating": e["rating"], "star": e["star"]} for e in E if e["label"] in DREAM]
stats["danger_eps"] = [{"label": e["label"], "rating": e["rating"], "star": e["star"]} for e in E if e["label"] in DANGER]
le3 = [e for e in rated if e["rating"] <= 3]
stats["le3_breakdown"] = {"total": len(le3), "dream": sum(e["label"] in DREAM for e in le3)}

(OUT / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")

print("sakuga", stats["sakuga"])
print("le3", stats["le3_breakdown"])
for t in tests:
    print(t)
print("OLS r2", stats["ols"]["r2"])
for c in stats["ols"]["coef"]:
    print(c)
print("acf", stats["acf_test"], "contrast", stats["contrast"])
print("bins", bins)
print("★ words", [(d["w"], d["z"], d["star_eps"], d["le4_eps"]) for d in stats["words_star"]])
print("≤4 words", [(d["w"], d["z"], d["star_eps"], d["le4_eps"]) for d in stats["words_low"]])
