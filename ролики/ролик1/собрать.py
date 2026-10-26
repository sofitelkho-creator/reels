"""Оформление ролика по РЕГЛАМЕНТ.md:
  слово за словом сверху по центру (Soyuz Grotesk #EAFC00), призыв в конце — Mediocre Cartoon крупнее с обводкой,
  чёрно-белая вставка в середине, засветка перед призывом, плашка профиля в финале, без зума, без водяного знака.
  python собрать.py ролик1.edl.json оформление.mp4"""
import sys, os, json, subprocess

edl = json.load(open(sys.argv[1], encoding="utf-8")); out = sys.argv[2]
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
FONT = os.path.join(ROOT, "шрифты", "SoyuzGrotesk-Bold.ttf")
FONT_CTA = os.path.join(ROOT, "шрифты", "MediocreCartoon-Regular.ttf")
PLATE = os.path.join(ROOT, "картинки", "профиль.png")
COLOR, SIZE, SIZE_CTA = "0xEAFC00", 64, 84
# Текст сверху по центру, над головой — на уровне глаз зрителя
X, Y = 540, 380
# Стена светлая — под жёлтым текстом мягкая тёмная тень, иначе не читается
SHADOW = "shadowcolor=black@0.55:shadowx=3:shadowy=3:borderw=2:bordercolor=black@0.35"
SHADOW_CTA = "shadowcolor=black@0.5:shadowx=4:shadowy=4:borderw=6:bordercolor=0x1a1a1a"

# Что показать вместо распознанных слов: (слова по порядку) → (текст, сколько слов заменить)
# Числа — цифрами; ошибки распознавания — правильным словом
FIX = {
    ("во", "первых"): ("во-первых", 2),
    ("три", "года"): ("3", 1),
    ("сто", "восьмидесяти", "трех"): ("183", 3),
    ("двадцати", "четырех", "процентов"): ("24%", 3),
    ("три", "тысячи"): ("3 000", 2),
    ("семьсот", "двадцать"): ("720", 2),
    ("восьмидесяти",): ("80", 1),
    ("трехста",): ("300", 1),
    ("пятиста",): ("500", 1),
    ("это", "не", "все"): ("это не всё", 3),
    ("зарабатывайте",): ("зарабатываете", 1),
    ("аутунома",): ("автонома", 1),
    ("виз",): ("виза", 1),
    ("приезду",): ("переезду", 1),
    ("стресс",): ("стресса", 1),
    ("номен",): ("номад", 1),
    ("ее",): ("её", 1),
    ("идет",): ("идёт", 1),
    ("растет",): ("растёт", 1),
    ("испании",): ("Испании", 1),
    ("европе",): ("Европе", 1),
}

words = edl["words"]; dur = edl["duration"]
seg_starts = [s["out_start"] for s in edl["segments"]]
cuts = seg_starts + [dur]
shown, i = [], 0
while i < len(words):
    for seq, (txt, n) in sorted(FIX.items(), key=lambda kv: -len(kv[0])):
        if tuple(w["w"] for w in words[i:i + len(seq)]) == seq:
            if txt == "это не всё":
                for w in words[i:i + 3]:
                    shown.append(("всё" if w["w"] == "все" else w["w"], w["s"], w["e"]))
            else:
                shown.append((txt, words[i]["s"], words[i + n - 1]["e"]))
            i += n
            break
    else:
        shown.append((words[i]["w"], words[i]["s"], words[i]["e"])); i += 1

# Призыв — последняя склейка («пиши слово … подписаться»)
CTA = seg_starts[-1]
# Чёрно-белая вставка — смысловой блок про налоги: от «налог на ваш…» до «…отдать государству»
BW = next(w["s"] for w in words if w["w"] == "налог")
BW_END = next(c for c in cuts if c > next(w["e"] for w in words if w["w"] == "государству" and w["s"] > BW))
# Плашка профиля — на «не забудь подписаться»
PLATE_FROM = next(w["s"] for w in words if w["s"] >= CTA and w["w"] == "не")

# слово держится до начала следующего, но не дольше склейки
items = []
for k, (w, s, e) in enumerate(shown):
    nxt = shown[k + 1][1] if k + 1 < len(shown) else dur
    cut = next(c for c in cuts if c > s + 1e-3)
    items.append((w, s, min(max(e, nxt), cut)))

vf = ["[0:v]delogo=x=770:y=1825:w=290:h=75",
      f"hue=s=0:enable='between(t,{BW:.3f},{BW_END - 0.001:.3f})'"]
# Засветка перед призывом: кадр уходит в светло-голубой и возвращается (по 0,3 с в каждую сторону)
for a, b, al in [(-0.3, -0.2, 0.35), (-0.2, -0.1, 0.65), (-0.1, 0.1, 0.9), (0.1, 0.2, 0.65), (0.2, 0.3, 0.35)]:
    vf.append(f"drawbox=x=0:y=0:w=iw:h=ih:color=0xCFF6FF@{al}:t=fill:enable='between(t,{CTA + a:.3f},{CTA + b:.3f})'")
for w, s, e in items:
    t = w.replace("\\", "\\\\").replace("'", "’").replace(":", "\\:")
    cta = s >= CTA - 1e-3
    font, size, sh = (FONT_CTA, SIZE_CTA, SHADOW_CTA) if cta else (FONT, SIZE, SHADOW)
    y = 440 if cta and s >= PLATE_FROM - 1e-3 else Y
    vf.append(f"drawtext=fontfile='{font}':expansion=none:text='{t}':fontsize={size}:fontcolor={COLOR}:x={X}-text_w/2:y={y}:{sh}"
              f":enable='between(t,{s:.3f},{e - 0.001:.3f})'")
fc = ",".join(vf) + "[v];"
# Плашка профиля сверху по центру, над текстом призыва, 600 px шириной
fc += f"[1:v]scale=600:-1[p];[v][p]overlay=x=(W-w)/2:y=150:enable='between(t,{PLATE_FROM:.3f},{dur:.3f})'[vo]"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", edl["cut"], "-loop", "1", "-i", PLATE, "-filter_complex", fc, "-map", "[vo]", "-map", "0:a",
                "-shortest", "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "copy", out], check=True)
print(f"слов на экране: {len(items)}; ч/б {BW:.1f}–{BW_END:.1f} с; засветка у {CTA:.1f} с; плашка с {PLATE_FROM:.1f} с → {out}")
