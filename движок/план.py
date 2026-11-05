"""План сцены из нарезки и сценария оформления.
  python план.py НАРЕЗКА.edl.json ОФОРМЛЕНИЕ.json план.json
ОФОРМЛЕНИЕ.json: fix — замены слов {"распознанное": "как показать"}, heads — крупные фразы, screens — экраны-инфографика,
intro — [от, до] флаг-шапки, flag — картинка шапки. Время в оформлении — секунды нарезки."""
import sys, os, json

edl, spec, out = sys.argv[1:4]
E = json.load(open(edl, encoding="utf-8")); S = json.load(open(spec, encoding="utf-8"))
base = os.path.dirname(os.path.abspath(spec))
url = lambda p: "file://" + os.path.abspath(os.path.join(base, p))
fix = S.get("fix", {})
cuts = [s["out_start"] for s in E["segments"]] + [E["duration"]]
ws = E["words"]
# fixSeq — замена нескольких слов подряд одним: [[["две", "тысячи", "двадцать", "пятый"], "2025"], ...]
for seq, txt in S.get("fixSeq", []):
    i = 0
    while i + len(seq) <= len(ws):
        if [w["w"] for w in ws[i:i + len(seq)]] == seq:
            ws = ws[:i] + [{"w": txt, "s": ws[i]["s"], "e": ws[i + len(seq) - 1]["e"]}] + ws[i + len(seq):]
        i += 1
words = []
for k, w in enumerate(ws):
    nxt = ws[k + 1]["s"] if k + 1 < len(ws) else E["duration"]
    cut = next(c for c in cuts if c > w["s"] + 1e-3)
    # слово держится до начала следующего, но не дольше склейки
    words.append({"w": fix.get(w["w"], w["w"]), "s": w["s"], "e": min(max(w["e"], nxt), cut)})
words = [w for w in words if w["w"]]
if "phrases" in S:
    words = [{"w": t, "s": a, "e": b} for a, b, t in S["phrases"]]
for s in S.get("screens", []):
    for it in s["items"]:
        if "img" in it: it["img"] = url(it["img"])
    for b in s.get("bgs", []):
        b["img"] = url(b["img"])
plan = {"words": words, "heads": S.get("heads", []), "screens": S.get("screens", []), "intro": S.get("intro", [0, 0]),
        "flag": url(S["flag"]) if S.get("flag") else None,
        "wordPos": S.get("wordPos", [300, 1320]), "accent": S.get("accent"), "stroke": S.get("stroke", False), "headMargin": S.get("headMargin", 60), "captionWidth": S.get("captionWidth"), "wordPosScreen": S.get("wordPosScreen", [540, 790])}
json.dump(plan, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"слов: {len(words)}, фраз: {len(plan['heads'])}, экранов: {len(plan['screens'])} → {out}")
