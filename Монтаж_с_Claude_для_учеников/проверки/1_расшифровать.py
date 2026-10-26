"""Шаг 1. Расшифровка исходника по кускам между паузами, с временем каждого слова.
  python 1_расшифровать.py ИСХОДНИК.MOV [--lang ru] [--prompt "текст сценария"]
Пишет ИСХОДНИК.chunks.json и печатает пронумерованные куски: по ним видно все дубли.
Куски, которые Whisper «услышал» в тишине («Продолжение следует», «Спасибо.»), помечены «галлюцинация» — их не брать."""
import sys, os, argparse, tempfile, subprocess, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import FF, need_ffmpeg, transcribe, is_hallucination, save

ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("--lang", default="ru"); ap.add_argument("--prompt")
ap.add_argument("--silence-db", type=float, default=-38, help="порог тишины, дБ"); ap.add_argument("--silence-min", type=float, default=0.25, help="минимальная пауза, с")
A = ap.parse_args(); need_ffmpeg()
log = subprocess.run([FF, "-hide_banner", "-i", A.src, "-af", f"silencedetect=noise={A.silence_db}dB:d={A.silence_min}", "-f", "null", "-"],
                     capture_output=True, text=True).stderr
h, m, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", log).groups(); dur = int(h) * 3600 + int(m) * 60 + float(s)
ss = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", log)]; se = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
spans, t = [], 0.0
for a, b in zip(ss, se + [dur] * (len(ss) - len(se))):
    if a - t > 0.2: spans.append((round(t, 2), round(a, 2)))
    t = b
if dur - t > 0.2: spans.append((round(t, 2), round(dur, 2)))
chunks = []
with tempfile.TemporaryDirectory() as td:
    for a, b in spans:
        wav = os.path.join(td, "c.wav"); s0 = max(0, a - 0.15)
        subprocess.run([FF, "-v", "error", "-y", "-ss", str(s0), "-t", str(b - s0 + 0.15), "-i", A.src, "-ac", "1", "-ar", "16000", wav], check=True)
        words = [dict(w, s=round(s0 + w["s"], 2), e=round(s0 + w["e"], 2)) for w in transcribe(wav, A.lang, A.prompt)]
        text = " ".join(w["w"] for w in words).strip()
        if not text: continue
        chunks.append({"n": len(chunks) + 1, "a": a, "b": b, "text": text, "words": words, "halluc": is_hallucination(text, b - a)})
out = os.path.splitext(A.src)[0] + ".chunks.json"; save(chunks, out)
for c in chunks:
    print(f"{c['n']:3}  {c['a']:7.2f}–{c['b']:7.2f}  {c['text']}" + ("   ← галлюцинация, не брать" if c["halluc"] else ""))
print(f"\nкусков: {len(chunks)} → {out}\nДальше: python 2_выбрать_дубли.py {out}")
