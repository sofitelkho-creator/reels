"""Шаг 5. Безопасная зона Instagram Reels: кадры ролика с наложенным интерфейсом — видно, что закроют кнопки, ник и подпись.
  python 5_безопасная_зона.py ГОТОВЫЙ.mp4 --at 1.5 4 8.2     (или --every 3 — кадр каждые 3 с)
Пишет ГОТОВЫЙ_зона_<время>.png. Claude открывает их и проверяет: текст, логотипы и картинки не заходят в красное.
Замер сделан по настоящему экрану iPhone (видео 1080×1920). Для TikTok и Shorts колонка кнопок и подпись примерно там же,
но точнее замерьте по своему скриншоту: поправьте ZONES ниже."""
import sys, os, argparse, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import FF, need_ffmpeg, duration

ZONES = [  # (x0, y0, x1, y1, что)
    (0, 0, 1080, 117, "статус-бар"),
    (0, 0, 57, 1920, "срез слева"), (1023, 0, 1080, 1920, "срез справа"),
    (110, 160, 170, 225, "стрелка «назад»"), (920, 155, 1000, 228, "камера"),
    (915, 1040, 1005, 1835, "кнопки: лайк, комментарии, репост, сохранить"),
    (75, 1465, 265, 1675, "«Отметьте друга»"),
    (75, 1690, 760, 1860, "ник и подпись"),
]
ap = argparse.ArgumentParser(); ap.add_argument("video"); ap.add_argument("--at", type=float, nargs="*", default=[]); ap.add_argument("--every", type=float)
A = ap.parse_args(); need_ffmpeg()
ts = A.at or [round(t, 2) for t in [x * (A.every or 3) + 0.5 for x in range(int(duration(A.video) / (A.every or 3)))]]
boxes = ",".join(f"drawbox=x={x0}:y={y0}:w={x1 - x0}:h={y1 - y0}:color=red@0.33:t=fill" for x0, y0, x1, y1, _ in ZONES)
guide = "drawbox=x=80:y=240:w=920:h=1400:color=lime@0.9:t=3"   # зелёная рамка — где текст точно виден
base = os.path.splitext(A.video)[0]
for t in ts:
    out = f"{base}_зона_{t:.1f}.png"
    subprocess.run([FF, "-v", "error", "-y", "-ss", str(t), "-i", A.video, "-frames:v", "1", "-vf", f"scale=1080:1920,{boxes},{guide}", out], check=True)
    print(out)
print("""
Правила (проверено на iPhone):
  • от боковых краёв — не ближе 80 px (по 57 px Instagram просто срезает);
  • сверху в углах — не выше 240 px (стрелка и камера), по центру можно с 140 px;
  • справа ниже 1040 px правый край текста — не дальше 900 px (кнопки);
  • низ текста — не ниже ~1640 px; слева ниже 1460 px — ничего («Отметьте друга»).
Зелёная рамка — зона, где текст виден всегда.""")
