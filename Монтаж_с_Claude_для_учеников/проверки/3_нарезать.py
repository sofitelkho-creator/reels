"""Шаг 3. Нарезка по РЕАЛЬНОЙ тишине в звуке (не по таймингам Whisper — они неточные и съедают начала и концы слов).
  python 3_нарезать.py ИСХОДНИК.MOV ИСХОДНИК.chunks.json ИСХОДНИК.keep.json [--speed 1.2] [--out нарезка.mp4]
Из каждого взятого куска берётся речь от первого звука до затухания последнего слова (с запасом), длинные паузы внутри
(больше 0,35 с) укорачиваются до ~0,25 с. Потом всё склеивается и ускоряется (по умолчанию ×1,2 — как в рилсах).
Пишет нарезку и ИСХОДНИК.edl.json (куски и слова со временем в нарезке) — его читает шаг 4."""
import sys, os, argparse, subprocess
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import FF, HOP, need_ffmpeg, load_audio, env_db, levels, load, save, norm, transcribe

ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("chunks"); ap.add_argument("keep")
ap.add_argument("--speed", type=float, default=1.2); ap.add_argument("--out")
ap.add_argument("--pause", type=float, default=0.35, help="паузы длиннее этого внутри куска укорачиваются")
ap.add_argument("--keep-pause", type=float, default=0.12, help="сколько тишины оставить с каждой стороны вырезанной паузы")
A = ap.parse_args(); need_ffmpeg()
C = sorted(load(A.chunks), key=lambda c: c["a"]); K = load(A.keep)
keep = [round(x, 2) for x in K["keep"]]; trim = {round(float(k), 2): v for k, v in K.get("trim", {}).items()}
x = load_audio(A.src); e = env_db(x); fl, sp = levels(e); R = sp - fl
LO, HI = fl + 0.22 * R, fl + 0.50 * R   # мягкий порог (тут уже есть звук) и строгий (тут точно речь)
QUIET = max(LO, sp - 20)                # для пауз внутри куска: вдох и шум на 20 дБ тише речи — тоже пауза
es = np.convolve(e, np.ones(5) / 5, mode="same")   # для пауз — сглаженная громкость (вдох «дрожит» вокруг порога)
fr = lambda t: int(round(t / HOP)); tm = lambda i: round(i * HOP, 3)
segs = []
for i, c in enumerate(C):
    if round(c["a"], 2) not in keep: continue
    lo = max(c["a"] - 0.4, (C[i - 1]["b"] + 0.06) if i > 0 else 0)            # не залезать в соседний кусок (там может быть брошенный дубль)
    hi = min(c["b"] + 0.4, (C[i + 1]["a"] - 0.06) if i + 1 < len(C) else c["b"] + 0.4, (len(e) - 1) * HOP)   # не дальше конца файла
    t0, t1 = trim.get(round(c["a"], 2), [None, None])
    if t0 is not None: lo = max(lo, t0)
    if t1 is not None: hi = min(hi, t1)
    i0, i1 = fr(lo), min(len(e), fr(hi)); v = np.where(e[i0:i1] > HI)[0]
    if not len(v): print(f"!! кусок {c['n']} ({c['a']:.2f}): не нашёл речь — проверьте trim"); continue
    s, k = i0 + v[0], 0
    while s > i0 and e[s - 1] > LO and k < 25: s -= 1; k += 1            # назад — пока ещё звучит (начало слова тише середины)
    t_end, k = i0 + v[-1], 0
    while t_end < i1 - 1 and (e[t_end:t_end + 8] > LO + 3).any() and k < 25: t_end += 1; k += 1   # вперёд — пока затухает гласная
    start, end = max(lo, tm(s) - 0.05), min(hi, tm(t_end) + 0.06)
    # длинные паузы внутри куска — укоротить
    cur, j = start, fr(start)
    jmax = min(fr(end), len(es))
    while j < jmax:
        if es[j] < QUIET:
            k = j
            while k < jmax and es[k] < QUIET: k += 1
            if (k - j) * HOP > A.pause:
                segs.append([cur, tm(j) + A.keep_pause]); cur = tm(k) - A.keep_pause
            j = k
        else: j += 1
    segs.append([cur, end])
segs = [s for s in segs if s[1] - s[0] > 0.12]
merged = []
for s in segs:
    if merged and s[0] <= merged[-1][1] + 0.03: merged[-1][1] = max(merged[-1][1], s[1])
    else: merged.append(list(s))
# слова → время в нарезке
words, t, out_segs = [], 0.0, []
# у обрезанных кусков (trim) время слов из расшифровки неточное (Whisper растягивает слово на вырезанный фальстарт) — распознаём заново
import tempfile
for c in C:
    tr_ = trim.get(round(c["a"], 2))
    if round(c["a"], 2) in keep and tr_ and any(v is not None for v in tr_):
        t0_, t1_ = (tr_[0] if tr_[0] is not None else c["a"] - 0.15), (tr_[1] if tr_[1] is not None else c["b"] + 0.15)
        with tempfile.TemporaryDirectory() as td:
            wav = os.path.join(td, "t.wav")
            subprocess.run([FF, "-v", "error", "-y", "-ss", f"{t0_:.3f}", "-to", f"{t1_:.3f}", "-i", A.src, "-ac", "1", "-ar", "16000", wav], check=True)
            c["words"] = [dict(w, s=round(t0_ + w["s"], 3), e=round(t0_ + w["e"], 3)) for w in transcribe(wav)]
        print(f"кусок {c['n']}: после trim распознан заново — {' '.join(w['w'] for w in c['words'])}")
allw = [w for c in C if round(c["a"], 2) in keep for w in c["words"]]
for a, b in merged:
    out_segs.append({"src_in": round(a, 3), "src_out": round(b, 3), "out_start": round(t / A.speed, 3)})
    for w in allw:
        m = (w["s"] + w["e"]) / 2
        if a <= m <= b: words.append({"w": w["w"], "s": round((t + max(0, w["s"] - a)) / A.speed, 3), "e": round((t + min(b, w["e"]) - a) / A.speed, 3)})
    t += b - a
out = A.out or os.path.splitext(A.src)[0] + "_нарезка.mp4"
# каждый кусок — отдельный вход с точной перемоткой: trim по одному входу копит в памяти все кадры между кусками
f, inputs = [], []
for i, (a, b) in enumerate(merged):
    d = b - a
    inputs += ["-ss", f"{a:.3f}", "-t", f"{d:.3f}", "-i", A.src]
    f.append(f"[{i}:v]trim=duration={d:.3f},setpts=PTS-STARTPTS[v{i}];"
             f"[{i}:a]atrim=duration={d:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.005,afade=t=out:st={max(0, d - 0.006):.3f}:d=0.006[a{i}];")
f.append("".join(f"[v{i}][a{i}]" for i in range(len(merged))) + f"concat=n={len(merged)}:v=1:a=1[v][a];[v]setpts=PTS/{A.speed},fps=30[vo];[a]atempo={A.speed}[ao]")
subprocess.run([FF, "-v", "error", "-y"] + inputs + ["-filter_complex", "".join(f), "-map", "[vo]", "-map", "[ao]",
                "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", out], check=True)
edl = os.path.splitext(A.src)[0] + ".edl.json"
save({"source": os.path.abspath(A.src), "cut": os.path.abspath(out), "speed": A.speed, "segments": out_segs, "words": words, "duration": round(t / A.speed, 3)}, edl)
print(f"кусков склейки: {len(merged)}, длительность {t / A.speed:.1f} с (×{A.speed}) → {out}\nДальше: python 4_проверить.py {edl}")
