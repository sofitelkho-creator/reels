"""Шаг 6. Громкость: музыка на 18 дБ тише голоса («слышно, но не мешает»), итог — −14 LUFS, пик не выше −1 дБ.
  python 6_громкость.py РОЛИК.mp4                          — измерить голос и итог
  python 6_громкость.py РОЛИК.mp4 --music трек.mp3 [--start 0] [--below 18] --out РОЛИК_с_музыкой.mp4
Музыка подрезается по длине ролика, в конце затухает за 1,5 с. Видео не перекодируется.
Голос и все звуки внутри ролика не меняются — сдвигается только громкость музыки."""
import sys, os, re, argparse, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import FF, need_ffmpeg, duration

def lufs(args):
    r = subprocess.run([FF, "-hide_banner", "-nostats"] + args + ["-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    i = re.findall(r"I:\s+(-?[\d.]+) LUFS", r); p = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", r)
    return float(i[-1]), (float(p[-1]) if p else None)

ap = argparse.ArgumentParser(); ap.add_argument("video"); ap.add_argument("--music"); ap.add_argument("--start", type=float, default=0)
ap.add_argument("--below", type=float, default=18, help="на сколько дБ музыка тише голоса"); ap.add_argument("--out")
A = ap.parse_args(); need_ffmpeg()
D = duration(A.video); V, Vp = lufs(["-i", A.video])
print(f"голос (весь ролик): {V:.1f} LUFS, пик {Vp} дБ")
if not A.music:
    print("для рилса итог −14 LUFS: " + ("нормально" if abs(V + 14) <= 1.5 else f"поправьте на {-14 - V:+.1f} дБ") + (", пик выше −1 дБ — снизьте" if Vp and Vp > -1 else ""))
    sys.exit(0)
M, _ = lufs(["-ss", str(A.start), "-t", str(D), "-i", A.music])
gain = (V - A.below) - M
print(f"музыка на этом участке: {M:.1f} LUFS → нужно {gain:+.1f} дБ, чтобы стать {V - A.below:.1f} LUFS (на {A.below:g} дБ тише голоса)")
if A.out:
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        mix = os.path.join(td, "mix.wav")
        fc = (f"[1:a]atrim=0:{D:.3f},asetpts=PTS-STARTPTS,volume={gain:.2f}dB,afade=t=out:st={max(0, D - 1.5):.3f}:d=1.5[m];"
              f"[0:a][m]amix=inputs=2:duration=first:normalize=0[a]")
        subprocess.run([FF, "-v", "error", "-y", "-i", A.video, "-ss", str(A.start), "-i", A.music, "-filter_complex", fc, "-map", "[a]", "-ar", "48000", mix], check=True)
        L, _ = lufs(["-i", mix]); g2 = -14 - L   # итог ровно −14 LUFS, пик ограничен −1 дБ
        subprocess.run([FF, "-v", "error", "-y", "-i", A.video, "-i", mix, "-filter_complex", f"[1:a]volume={g2:.2f}dB,alimiter=limit=0.89:level=false[a]",
                        "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", A.out], check=True)
    F, Fp = lufs(["-i", A.out]); print(f"готово: {A.out} — итог {F:.1f} LUFS, пик {Fp} дБ")
