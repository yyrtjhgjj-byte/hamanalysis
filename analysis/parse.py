"""docs/*.txt の感想メモを 1 エントリ = 1 行の表に変換する。

エントリ見出しは `・<話数 or タイトル>［<評価>］★?` の形。
見出しでない `・` 行が出てきたら、次の見出しまでは「メタ考察」として別扱いにする。
4.txt には見出しが前の行の末尾にくっついている箇所があるので、行頭に限定せず探す。
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
OUT = Path(__file__).resolve().parent / "out"

HEADER = re.compile(r"・(?P<label>[^・\n［]*?)\s*［(?P<rating>[1-5]?)］[ 　]*(?P<star>★)?")

# 劇場版・OVA のラベル判定（タイトルの一部で判定）
SPECIALS = [
    ("(OVA)ハム太郎のおたんじょうび", "OVA1"),
    ("ハムちゃんずの宝さがし大作戦", "OVA2"),
    ("ハムちゃんずと虹の国の王子さま", "OVA3"),
    ("ハムちゃんずのめざせ! ハムハム金メダル", "OVA4"),
    ("劇場版 とっとこハム太郎 ハムハムランド大冒険", "劇場版1"),
    ("劇場版 とっとこハム太郎 ハムハムハムージャ", "劇場版2"),
    ("劇場版 とっとこハム太郎 ハムハムグランプリン", "劇場版3"),
    ("劇場版 とっとこハム太郎 はむはむぱらだいちゅ", "劇場版4"),
]


def series_of(ep: int | None, kind: str) -> str:
    if kind != "tv" or ep is None:
        return "劇場版・OVA"
    if ep <= 80:
        return "1期前半(1-80)"
    if ep <= 193:
        return "1期後半(81-193)"
    if ep <= 244:
        return "2期すいぱら編(194-244)"
    return "2期ハムハーの木編(245-296)"


def classify(label: str):
    label = label.strip()
    m = re.fullmatch(r"(\d+)(?:〜(\d+))?", label)
    if m:
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else start
        return "tv", start, end, label
    for key, short in SPECIALS:
        if label.startswith(key):
            return ("movie" if short.startswith("劇場版") else "ova"), None, None, short
    raise ValueError(f"unknown label: {label!r}")


def parse_file(path: Path, vol: str):
    text = path.read_text(encoding="utf-8")
    matches = list(HEADER.finditer(text))
    entries, metas = [], []
    for i, m in enumerate(matches):
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.end():body_end]
        # 見出しでない `・` 行以降はメタ考察として切り出す
        memo_lines, meta_lines, in_meta = [], [], False
        for line in body.split("\n"):
            if line.startswith("・"):
                in_meta = True
            (meta_lines if in_meta else memo_lines).append(line)
        memo = "\n".join(l for l in memo_lines if l.strip()).strip()
        meta = "\n".join(l for l in meta_lines if l.strip()).strip()
        kind, start, end, short = classify(m.group("label"))
        entries.append({
            "vol": vol,
            "kind": kind,
            "label": short,
            "ep": start,
            "ep_end": end,
            "rating": int(m.group("rating")) if m.group("rating") else None,
            "star": bool(m.group("star")),
            "memo": memo,
            "memo_chars": len(memo.replace("\n", "")),
            "memo_lines": memo.count("\n") + 1 if memo else 0,
        })
        if meta:
            metas.append({"vol": vol, "after": short, "text": meta})
    # 最初の見出しより前（前書き）もメタ扱い
    head = text[: matches[0].start()].strip() if matches else text.strip()
    if head:
        metas.insert(0, {"vol": vol, "after": None, "text": head})
    return entries, metas


def main():
    OUT.mkdir(exist_ok=True)
    vols = [str(i) for i in range(1, 10)]
    entries, metas = [], []
    for vol in vols:
        e, mt = parse_file(DOCS / f"{vol}.txt", vol)
        entries += e
        metas += mt
    for i, e in enumerate(entries):
        e["order"] = i  # 視聴順（劇場版・OVA はメモ上の挿入位置）
        e["series"] = series_of(e["ep"], e["kind"])

    ex_text = (DOCS / "EX.txt").read_text(encoding="utf-8")

    cols = ["order", "vol", "kind", "label", "ep", "ep_end", "series", "rating", "star",
            "memo_chars", "memo_lines", "memo"]
    with open(OUT / "episodes.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for e in entries:
            w.writerow({k: e[k] for k in cols})
    (OUT / "episodes.json").write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "meta_notes.json").write_text(json.dumps(metas, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "ex.txt").write_text(ex_text, encoding="utf-8")

    tv = [e for e in entries if e["kind"] == "tv"]
    covered = sorted({n for e in tv for n in range(e["ep"], e["ep_end"] + 1)})
    missing = sorted(set(range(1, 297)) - set(covered))
    print(f"entries={len(entries)} tv={len(tv)} specials={len(entries)-len(tv)} metas={len(metas)}")
    print(f"tv episodes covered={len(covered)} missing={missing}")
    print("unrated:", [e["label"] for e in entries if e["rating"] is None])


if __name__ == "__main__":
    main()
