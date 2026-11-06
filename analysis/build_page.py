"""stats.json と episodes.json をレポート HTML に埋め込む。

使い方: python3 analysis/build_page.py [出力パス]
（parse.py → analyze.py → deep.py の後に実行）
"""
from __future__ import annotations

import html as htmllib
import json
import re
import sys
from pathlib import Path

from labels import DANGER, DREAM, SAKUGA_BAD, SAKUGA_GOOD

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
DOCS = HERE.parent / "docs"
E = json.loads((OUT / "episodes.json").read_text(encoding="utf-8"))
S = json.loads((OUT / "stats.json").read_text(encoding="utf-8"))
METAS = json.loads((OUT / "meta_notes.json").read_text(encoding="utf-8"))

SERIES = ["1期前半(1-80)", "1期後半(81-193)", "2期すいぱら編(194-244)", "2期ハムハーの木編(245-296)", "劇場版・OVA"]
SERIES_SHORT = ["1期前半", "1期後半", "すいぱら編", "ハムハーの木編", "劇場版・OVA"]
SERIES_RANGE = ["1〜80話", "81〜193話", "194〜244話", "245〜296話", "8本"]

# 出番監視：いつも出ない組の「いない／喋らない」チェック
WATCH = {
    "パンダくん": r"パンダ.{0,25}(出番|いない|いねえ|映ら|セリフ|台詞|喋|出てこな|離脱)|(出番|セリフ).{0,10}パンダ",
    "トラハムくん": r"トラハム.{0,25}(出番|いない|いねえ|映ら|セリフ|台詞|喋|声帯|出てこな|霊圧|離脱)|(出番|セリフ).{0,10}トラハム",
    "かぶるくん": r"かぶる.{0,25}(出番|いない|いねえ|セリフ|台詞|喋|消え)|(出番|セリフ).{0,10}かぶる",
}

QUOTES = [
    ("26", "夢の中の話。これいる？"),
    ("78", "夢回はまあ着衣ハムがかわいいのでギリ許せなくも...？←ウソや！ワイは自分にウソつけへん！"),
    ("23", "やっぱり死にかける回は面白い。"),
    ("100", "パンダくんの出番多いけど別に忖度はしません、普通に4です。"),
    ("260", "パンダくんがめちゃくちゃ喋ったのでおまけ５点"),
    ("168", "話面白い時に限って作画がゴミになるのほんまやめろ"),
    ("233", "夢回に限って作画いいのほんま腹立つ"),
    ("178", "どうしよう、久々に全員出てて嬉しいけど気持ち的には4.5点"),
    ("180", "相変わらずトラハムくんは声帯が奪われてマラカスの音しかしない"),
    ("劇場版3", "劇場版、再生ボタンを押すまでに腰が重すぎる。見るか.........みたいになる→再生するまでに2時間かかりました"),
    ("195", "➡︎「劇中劇が嫌い」で済む話をこの文字数"),
    ("261", "夢回じゃないのに３点は相当やで"),
]


def main(out_path: Path):
    by_label = {e["label"]: e for e in E}
    entries = []
    watch_eps = {k: set() for k in WATCH}
    for e in E:
        flags = []
        if e["label"] in DREAM:
            flags.append("dream")
        if e["label"] in DANGER:
            flags.append("danger")
        if e["label"] in SAKUGA_GOOD:
            flags.append("sg")
        if e["label"] in SAKUGA_BAD:
            flags.append("sb")
        if "じゃじゃ" in e["memo"]:
            flags.append("jaja")
        for who, pat in WATCH.items():
            if any(re.search(pat, line) for line in e["memo"].split("\n")):
                watch_eps[who].add(e["label"])
                if "watch" not in flags:
                    flags.append("watch")
        entries.append({
            "o": e["order"], "v": e["vol"], "l": e["label"], "k": e["kind"], "ep": e["ep"], "ee": e["ep_end"],
            "s": SERIES.index(e["series"]), "r": e["rating"], "st": e["star"], "c": e["memo_chars"],
            "m": e["memo"], "f": flags,
        })

    quotes = []
    for label, text in QUOTES:
        e = by_label[label]
        assert text in e["memo"], f"quote not found verbatim in {label}: {text}"
        quotes.append({"l": label, "t": text, "r": e["rating"], "st": e["star"]})

    total_chars = sum(len(p.read_text(encoding="utf-8")) for p in sorted(DOCS.glob("*.txt")))
    late = [e for e in E if e["kind"] == "tv" and e["ep"] >= 122 and e["rating"] is not None]

    data = {
        "entries": entries,
        "series": [{"name": n, "short": s, "range": r} for n, s, r in zip(SERIES, SERIES_SHORT, SERIES_RANGE)],
        "dist": S["dist"],
        "base": S["base"],
        "n_rated": S["n_rated"],
        "by_series": S["by_series"],
        "tests": S["tests"],
        "ols": S["ols"],
        "sakuga": S["sakuga"],
        "late_star": round(sum(e["star"] for e in late) / len(late), 3),
        "contrast": S["contrast"],
        "acf": S["acf_test"],
        "chars": [c for c in S["chars"] if c["episodes"] >= 9],
        "heat": [c for c in S["chars"] if c["group"] in ("ハムちゃんず",) or c["name"] in ("ラピスちゃん", "ラズリーちゃん")],
        "style": S["style"],
        "streaks": S["streaks"],
        "longest": S["longest"],
        "shortest": S["shortest"][:3],
        "words_star": S["words_star"][:8],
        "words_low": S["words_low"][:8],
        "le3": S["le3_breakdown"],
        "watch": {k: len(v) for k, v in watch_eps.items()},
        "quotes": quotes,
        "total_chars": total_chars,
        "n_meta": len(METAS),
        "chars_by_rating": S["chars_by_rating"],
    }
    tpl = (HERE / "report_template.html").read_text(encoding="utf-8")
    check_essay_quotes(tpl, by_label)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = tpl.replace("/*__DATA__*/null", payload)
    out_path.write_text(html, encoding="utf-8")
    print(f"wrote {out_path} ({len(html)/1024:.0f} KB)", "watch:", data["watch"], "late_star:", data["late_star"])


def check_essay_quotes(tpl: str, by_label: dict):
    """「読んだ感想」の引用が原文と一字一句一致するかを確かめる。"""
    raw = "\n".join(p.read_text(encoding="utf-8") for p in sorted(DOCS.glob("*.txt")))
    sec = tpl[tpl.index('<section id="essay">'):tpl.index("<footer>")]
    quotes = re.findall(r'<(?:q|span class="eq")>(.*?)</(?:q|span)>', sec)
    bad = [q for q in quotes if htmllib.unescape(q) not in raw]
    assert not bad, f"引用が原文に見つからない: {bad}"
    # 話数つきの引用は、その話のメモにあるかまで確かめる
    for q, src in re.findall(r'<span class="eq">(.*?)</span><small>(\d+話|劇場版\d)', sec):
        label = src.removesuffix("話")
        assert htmllib.unescape(q) in by_label[label]["memo"], f"{src} のメモに見つからない: {q}"
    print(f"essay quotes ok: {len(quotes)}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else OUT / "report.html")
