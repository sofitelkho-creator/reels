"""Оформление пробы по РЕГЛАМЕНТ.md: слово за словом сверху по центру, Soyuz Grotesk #EAFC00, без зума, без водяного знака.
  python собрать.py проба.edl.json оформление.mp4"""
import sys, os, json, subprocess

edl = json.load(open(sys.argv[1], encoding="utf-8")); out = sys.argv[2]
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
FONT = os.path.join(ROOT, "шрифты", "SoyuzGrotesk-Bold.otf")
COLOR, SIZE = "0xEAFC00", 64
# Текст сверху по центру, над головой — на уровне глаз зрителя
X, Y = 540, 380
# Стена светлая — под жёлтым текстом мягкая тёмная тень, иначе не читается
SHADOW = "shadowcolor=black@0.55:shadowx=3:shadowy=3:borderw=2:bordercolor=black@0.35"
# Числа — цифрами: (слова по порядку) → (что показать, сколько слов это число занимает)
NUMBERS = {("три", "года"): ("3", 1), ("сто", "восьмидесяти", "трех"): ("183", 3)}

words = edl["words"]; cuts = [s["out_start"] for s in edl["segments"]] + [edl["duration"]]
shown, i = [], 0
while i < len(words):
    for seq, (num, n) in NUMBERS.items():
        if tuple(w["w"] for w in words[i:i + len(seq)]) == seq:
            shown.append((num, words[i]["s"], words[i + n - 1]["e"])); i += n
            break
    else:
        shown.append((words[i]["w"], words[i]["s"], words[i]["e"])); i += 1
# слово держится до начала следующего, но не дольше склейки
items = []
for k, (w, s, e) in enumerate(shown):
    nxt = shown[k + 1][1] if k + 1 < len(shown) else edl["duration"]
    cut = next(c for c in cuts if c > s + 1e-3)
    items.append((w, s, min(max(e, nxt), cut)))

vf = ["delogo=x=770:y=1825:w=290:h=75"]
for w, s, e in items:
    t = w.replace("'", "’").replace(":", "\\:")
    vf.append(f"drawtext=fontfile='{FONT}':text='{t}':fontsize={SIZE}:fontcolor={COLOR}:x={X}-text_w/2:y={Y}:{SHADOW}:enable='between(t,{s:.3f},{e - 0.001:.3f})'")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", edl["cut"], "-vf", ",".join(vf), "-c:v", "libx264", "-crf", "18", "-preset", "medium",
                "-pix_fmt", "yuv420p", "-c:a", "copy", out], check=True)
print(f"слов на экране: {len(items)} → {out}")
