"""Вырезает спикера из кадров (MediaPipe selfie multiclass): PNG-кадры с прозрачным фоном, чтобы ставить надписи «за человеком».
  python вырезать_спикера.py НАРЕЗКА.mp4 ПАПКА [от до] [от до] ...
Кадры пишутся только для заданных отрезков (секунды нарезки), имя — номер кадра при 30 к/с: 00042.webp.
Модель: /home/user/models/mp/selfie_multiclass.tflite (или переменная MP_MODEL)."""
import sys, os, subprocess
import numpy as np
from PIL import Image, ImageFilter
import mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions

src, out = sys.argv[1], sys.argv[2]
spans = [(float(a), float(b)) for a, b in zip(sys.argv[3::2], sys.argv[4::2])]
os.makedirs(out, exist_ok=True)
model = os.environ.get("MP_MODEL", "/home/user/models/mp/selfie_multiclass.tflite")
seg = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(
    base_options=BaseOptions(model_asset_path=model), output_confidence_masks=True))
W, H, FPS = 1080, 1920, 30
need = lambda i: any(a - 0.4 <= i / FPS <= b + 0.4 for a, b in spans)
p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", src, "-vf", f"scale={W}:{H},fps={FPS}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                     stdout=subprocess.PIPE)
i = n = 0
while True:
    buf = p.stdout.read(W * H * 3)
    if len(buf) < W * H * 3: break
    if need(i):
        rgb = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
        r = seg.segment(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb)))
        # канал 0 — фон; всё остальное (волосы, тело, лицо, одежда) — человек
        alpha = 1.0 - np.squeeze(r.confidence_masks[0].numpy_view())
        # резче край: полупрозрачные «призраки» фона (лампа) убираем, волосы остаются
        alpha = (alpha - 0.5) * 3 + 0.5
        m = Image.fromarray((np.clip(alpha, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2))
        im = Image.fromarray(rgb).convert("RGBA"); im.putalpha(m)
        im.save(os.path.join(out, f"{i:05d}.webp"), quality=88, method=2); n += 1
    i += 1
p.wait()
print(f"кадров с вырезанным спикером: {n} → {out}")
