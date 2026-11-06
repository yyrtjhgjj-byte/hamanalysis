"""メモの書き手とハムちゃんずの性格類似度。

キャラのセリフはデータに無いので、13 項目を 0〜5 で手採点して比べる。
- 書き手: メモ本文の証拠から採点（コメント参照）
- キャラ: 作中の基本設定 + メモでの描写から採点
採点は計算前に固定した。主観なので、採点ノイズと項目の選び方で結果が揺らぐかも確かめる。
"""
from __future__ import annotations

import numpy as np

TRAITS = [
    "物知り・うんちく", "ものづくり", "ツッコミ", "ボケ・ギャグ", "関西弁",
    "好奇心・探検", "記録・観察", "仲間への愛着", "恋愛脳", "マイペース・省エネ",
    "辛口", "心配性", "筋を通す・正直",
]

# 書き手（メモから）
ME = [
    5,  # ばてれん・ジャンガリアンの D・声優の兼役まで調べる
    3,  # 記法・分冊・年表を作るが、手を動かす工作ではない
    5,  # ツッコミ表現が 1000 字あたり 3.5〜4.6 回、画面に話しかけ続ける
    3,  # 「一行(大嘘)」「草」など自虐ボケはあるが主軸はツッコミ
    3,  # ほんま・やん・ウソつけへん。標準語ベースに混ざる程度
    4,  # 知識への好奇心は最大、新キャラには保守的
    5,  # 296 話の採点・タイムスタンプ付き作画ミス報告
    1,  # 本人申告「同じ人間に執着し続けられない、飽きる」（メモ上の点呼はハムちゃんず限定）
    1,  # 恋愛は筋が通っているかだけ気にする（「この組み合わせはどうでも...」）
    3,  # 完走はするが 2 倍速解禁・まとめ書き
    4,  # 「本当にゴミ」「燃やしたくなる」。矛先は作り手
    3,  # 予告で怖がり、本編で「杞憂」
    5,  # 「ワイは自分にウソつけへん」「忖度はしません」★の撤回
]

CHARS = {
    #                 物知 工作 ツッ ボケ 関西 好奇 記録 愛着 恋愛 マイ 辛口 心配 筋
    "ハム太郎":       [1, 1, 1, 3, 0, 5, 1, 5, 1, 1, 1, 1, 4],  # 好奇心旺盛・仲間思い・恋に鈍感
    "リボンちゃん":   [1, 1, 2, 2, 0, 3, 1, 3, 5, 2, 1, 2, 3],  # ハム太郎一筋・「お花畑」
    "タイショーくん": [1, 2, 3, 3, 0, 3, 1, 4, 5, 1, 3, 2, 3],  # 地下ハウスの親分・リボン一筋・空回り
    "こうしくん":     [1, 1, 1, 2, 0, 1, 1, 3, 5, 2, 1, 5, 3],  # 臆病・じゃじゃハム一筋
    "トンガリくん":   [4, 3, 1, 2, 0, 5, 4, 2, 1, 3, 1, 1, 3],  # 旅と地図の情報屋・唐突に現れる
    "まいどくん":     [2, 1, 2, 5, 5, 2, 1, 3, 3, 2, 1, 2, 3],  # 関西弁・滑るギャグ・マフラー狙い
    "めがねくん":     [2, 1, 3, 1, 0, 2, 2, 3, 3, 3, 3, 2, 3],  # 「急に冷笑というかマジレス」
    "のっぽくん":     [5, 3, 2, 1, 0, 3, 4, 3, 1, 3, 1, 2, 4],  # 物知りのブレイン・運動もできる
    "パンダくん":     [2, 5, 2, 2, 0, 3, 2, 3, 1, 2, 1, 2, 3],  # 工作の天才・大工志望
    "ちび丸ちゃん":   [0, 0, 0, 2, 0, 3, 0, 3, 0, 2, 0, 1, 2],  # 赤ちゃん・すぐいなくなる
    "マフラーちゃん": [1, 1, 0, 1, 0, 2, 1, 3, 1, 3, 0, 4, 3],  # 泣き虫・甘えん坊
    "ねてるくん":     [1, 1, 0, 1, 0, 1, 1, 4, 1, 5, 0, 1, 3],  # いつも寝ている・タイショーを迎える
    "かぶるくん":     [0, 1, 1, 2, 0, 1, 1, 3, 1, 3, 0, 4, 3],  # 恥ずかしがり・「かぶ！」
    "トラハムくん":   [1, 1, 0, 4, 0, 3, 1, 2, 4, 1, 1, 1, 2],  # マラカス・オチ担当・「碌でもない」
    "トラハムちゃん": [2, 1, 5, 1, 0, 2, 2, 3, 1, 2, 3, 1, 4],  # 兄へのツッコミ役・しっかり者
    "ラピスちゃん":   [2, 1, 4, 1, 0, 2, 3, 3, 2, 2, 2, 2, 4],  # 「常識的」
    "ラズリーちゃん": [3, 5, 1, 3, 0, 4, 1, 3, 1, 1, 1, 1, 3],  # 発明・素直で明るい
}

names = list(CHARS)
M = np.array([CHARS[n] for n in names], float)
me = np.array(ME, float)


def score(M, me, w=None):
    """類似度 = 100 × (1 − 重み付き平均絶対差 / 5)。"""
    w = np.ones(len(me)) if w is None else w
    mad = (np.abs(M - me) * w).sum(axis=1) / w.sum()
    return 100 * (1 - mad / 5)


def pearson(M, me):
    a = me - me.mean()
    B = M - M.mean(axis=1, keepdims=True)
    return (B @ a) / (np.linalg.norm(B, axis=1) * np.linalg.norm(a))


s = score(M, me)
r = pearson(M, me)
order = np.argsort(-s)
print("rank name score pearson")
for i, k in enumerate(order, 1):
    print(i, names[k], f"{s[k]:.1f}", f"{r[k]:+.2f}")

# 共通点と相違点（上位 3 人）
for k in order[:3]:
    d = np.abs(M[k] - me)
    same = [TRAITS[j] for j in np.argsort(d)[:4]]
    diff = [f"{TRAITS[j]}({int(M[k][j])} vs {int(me[j])})" for j in np.argsort(-d)[:3]]
    print(names[k], "近い:", same, "遠い:", diff)

rng = np.random.default_rng(0)
N = 20000

# 1) 項目の選び方：13 項目から復元抽出して 1 位を数える
top_boot = np.zeros(len(names))
for _ in range(N):
    idx = rng.integers(0, len(me), len(me))
    top_boot[np.argmax(score(M[:, idx], me[idx]))] += 1

# 2) 採点のブレ：キャラの全採点に −1/0/+1 のノイズ
top_noise = np.zeros(len(names))
for _ in range(N):
    Mn = np.clip(M + rng.integers(-1, 2, M.shape), 0, 5)
    top_noise[np.argmax(score(Mn, me))] += 1

# 3) 1 項目ずつ抜いたときの 1 位
loo = [names[np.argmax(score(np.delete(M, j, 1), np.delete(me, j)))] for j in range(len(me))]

print("\nbootstrap(項目) 1位率:", {names[k]: round(top_boot[k] / N, 3) for k in np.argsort(-top_boot)[:5]})
print("noise(採点) 1位率:", {names[k]: round(top_noise[k] / N, 3) for k in np.argsort(-top_noise)[:5]})
print("leave-one-out 1位:", dict(zip(TRAITS, loo)))

# 4) 逆転条件：ある項目の重みを何倍にすると、そのキャラが 1 位になるか
print("\n逆転条件（単一項目の重みを上げて 1 位になる最小倍率）")
for k in order[1:8]:
    best = None
    for j in range(len(me)):
        for mult in np.arange(1, 30.01, 0.25):
            w = np.ones(len(me))
            w[j] = mult
            if np.argmax(score(M, me, w)) == k:
                if best is None or mult < best[1]:
                    best = (TRAITS[j], mult)
                break
    print(names[k], best)
