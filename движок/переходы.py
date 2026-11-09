"""Переходы-засветки и звуковые эффекты поверх готового ролика (регламент: засветка — «экран», ~65 %, звуки на 12–15 дБ тише голоса).
  python переходы.py РОЛИК.mp4 ПЕРЕХОДЫ.json ИТОГ.mp4
ПЕРЕХОДЫ.json: {"leaks": [[время, "переходы/переход1.mov"], ...], "sounds": [[время, "звуки/pop_длинный.wav", -14], ...]}
Время засветки — момент склейки: клип ставится так, что его середина приходится на склейку. Пути — от корня проекта."""
import sys, os, json, subprocess

video, spec, out = sys.argv[1:4]
S = json.load(open(spec, encoding="utf-8"))
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
dur = lambda p: float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                                     capture_output=True, text=True).stdout)
OPACITY = S.get("opacity", 0.65)
cmd = ["ffmpeg", "-v", "error", "-y", "-i", video]; fc = []; v = "0:v"; n = 1
fc.append("[0:v]format=gbrp[b0]"); v = "b0"
for i, (t, clip) in enumerate(S.get("leaks", [])):
    p = os.path.join(ROOT, clip); start = max(0, t - dur(p) / 2)
    cmd += ["-i", p]
    # засветка той же длины, что ролик: до и после — чёрное, а чёрное в режиме «экран» ничего не меняет
    fc.append(f"[{n}:v]scale=1080:1920,fps=30,format=gbrp,setpts=PTS-STARTPTS+{start:.3f}/TB,"
              f"tpad=start_duration={start:.3f}:stop_duration=600:color=black[l{i}]")
    fc.append(f"[{v}][l{i}]blend=all_mode=screen:all_opacity={OPACITY}:shortest=1[b{i + 1}]"); v = f"b{i + 1}"; n += 1
fc.append(f"[{v}]format=yuv420p[vo]")
a = ["[0:a]"]
for j, (t, snd, db) in enumerate(S.get("sounds", [])):
    cmd += ["-i", os.path.join(ROOT, snd)]
    ms = int(t * 1000)
    fc.append(f"[{n}:a]volume={db}dB,adelay={ms}|{ms}[s{j}]"); a.append(f"[s{j}]"); n += 1
fc.append("".join(a) + f"amix=inputs={len(a)}:normalize=0:duration=first[ao]")
cmd += ["-filter_complex", ";".join(fc), "-map", "[vo]", "-map", "[ao]", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
        "-c:a", "aac", "-b:a", "192k", out]
subprocess.run(cmd, check=True)
print(f"засветок: {len(S.get('leaks', []))}, звуков: {len(S.get('sounds', []))} → {out}")
