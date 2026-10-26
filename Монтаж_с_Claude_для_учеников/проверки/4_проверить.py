"""Шаг 4. Ворота нарезки: пока здесь не «ПРОЙДЕНО», дальше (текст, графика, музыка) не идём.
  python 4_проверить.py ИСХОДНИК.edl.json
Проверяет готовую нарезку (файл из шага 3):
  1. повторы и брошенные дубли по тексту (слово дважды, фраза дважды рядом, два куска подряд с одного начала);
  2. срезанные концы и начала слов на каждой склейке — по звуку исходника (гласные 200–2500 Гц, шипящие 3,5–8 кГц);
  3. длинные паузы (> 0,35 с) и огрызки (кусок короче 0,5 с — даёт «вспышку» картинки);
  4. прослушка: нарезка распознаётся заново БЕЗ подсказок и сравнивается с ожидаемым текстом — лишние слова (фальстарт, дубль)
     и пропавшие слова (срезано).
Ложное «!!» отменить рассуждением нельзя: проверьте место напрямую (распознайте отдельно этот кусок, посмотрите громкость) и
допишите строку «время: что проверено и чем» в ИСХОДНИК.proof.txt — ворота примут столько «!!», сколько строк доказательств."""
import sys, os, difflib
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import HOP, need_ffmpeg, load_audio, env_db, band_db, levels, load, norm, transcribe

need_ffmpeg()
E = load(sys.argv[1]); SRC, CUT, SP = E["source"], E["cut"], E["speed"]; S = E["segments"]; W = E["words"]
issues = []   # (время в нарезке, текст)
def add(t, msg): issues.append((round(t, 2), msg))
src_t = lambda t: next((s["src_in"] + (t - s["out_start"]) * SP for s in reversed(S) if s["out_start"] <= t + 1e-6), 0)

# 1. текст
nw = [(norm(w["w"]), w) for w in W if norm(w["w"])]
for i in range(1, len(nw)):
    if nw[i][0] == nw[i - 1][0] and len(nw[i][0]) > 2: add(nw[i][1]["s"], f"слово «{nw[i][1]['w']}» два раза подряд")
for n in (3, 2):
    for i in range(len(nw) - n):
        for j in range(i + 1, min(i + 9, len(nw) - n + 1)):
            if [x[0] for x in nw[i:i + n]] == [x[0] for x in nw[j:j + n]] and all(len(x[0]) > 1 for x in nw[i:i + n]):
                add(nw[j][1]["s"], f"фраза «{' '.join(x[1]['w'] for x in nw[i:i + n])}» повторяется рядом — сценарий или дубль?")
seg_words = [[w for w in nw if s["out_start"] <= w[1]["s"] < (S[k + 1]["out_start"] if k + 1 < len(S) else 1e9)] for k, s in enumerate(S)]
for k in range(len(S) - 1):
    if abs(S[k + 1]["src_in"] - S[k]["src_out"]) < 0.05: continue
    a, b = [x[0] for x in seg_words[k][:2]], [x[0] for x in seg_words[k + 1][:2]]
    if len(a) == 2 and a == b: add(S[k + 1]["out_start"], f"два куска подряд начинаются одинаково «{' '.join(x[1]['w'] for x in seg_words[k][:2])}» — брошенный дубль?")

# 2. края кусков — по исходнику
x = load_audio(SRC)
vb, hf = band_db(x, 200, 2500), band_db(x, 3500, 8000)
fv, _ = levels(vb); fh, _ = levels(hf)
eb = env_db(x); _, spb = levels(eb)   # общая громкость: вдох на 20 дБ тише речи — не шипящий
fr = lambda t: int(round(t / HOP))
mean = lambda a, i, j: float(np.mean(a[max(0, i):max(i + 1, j)]))
for k, s in enumerate(S):
    nxt_contig = k + 1 < len(S) and abs(S[k + 1]["src_in"] - s["src_out"]) < 0.05
    prv_contig = k > 0 and abs(s["src_in"] - S[k - 1]["src_out"]) < 0.05
    t_out_end = (S[k + 1]["out_start"] if k + 1 < len(S) else E["duration"])
    if not nxt_contig:
        i = fr(s["src_out"])
        if mean(vb, i - 4, i) > fv + 22 and mean(vb, i, i + 6) > mean(vb, i - 4, i) - 6:   # до склейки — голос (не вдох), и после не затих
            add(t_out_end, f"конец слова срезан на {s['src_out']:.2f} с исходника (после склейки голос ещё звучит) — дотянуть конец")
        elif mean(hf, i - 4, i) > fh + 18 and mean(hf, i, i + 6) > mean(hf, i - 4, i) - 6 and mean(eb, i - 4, i) > spb - 20:   # шипящий звучал ДО склейки и не затих после (вдох после тишины — не в счёт)
            add(t_out_end, f"шипящий на конце срезан на {s['src_out']:.2f} с исходника (с, ш, ч, ц, ф, х) — дотянуть конец")
    if not prv_contig:
        i = fr(s["src_in"])
        if mean(vb, i - 6, i) > fv + 22 and mean(vb, i - 6, i) > mean(vb, i, i + 4) - 6:   # перед началом куска уже звучал голос
            add(s["out_start"], f"начало слова срезано на {s['src_in']:.2f} с исходника — начать раньше")
    if (s["src_out"] - s["src_in"]) / SP < 0.5 and not (nxt_contig or prv_contig):
        add(s["out_start"], f"огрызок {(s['src_out'] - s['src_in']) / SP:.2f} с — картинка мелькнёт; склеить с соседом или убрать")

# 3. паузы в готовой нарезке
y = load_audio(CUT); ec = env_db(y); fl, sp = levels(ec); lo = max(fl + 0.22 * (sp - fl), sp - 20)   # вдох на 20 дБ тише речи — тоже пауза
ecs = np.convolve(ec, np.ones(5) / 5, mode="same")   # сглаженная громкость — как в нарезке
i, n = int(0.3 / HOP), len(ec) - int(0.3 / HOP)
while i < n:
    if ecs[i] < lo:
        j = i
        while j < n and ecs[j] < lo: j += 1
        if (j - i) * HOP > 0.35: add(i * HOP, f"пауза {(j - i) * HOP:.2f} с (у {src_t(i * HOP):.2f} с исходника) — длинновато для рилса")
        i = j
    else: i += 1

# 4. прослушка
heard = transcribe(CUT)
hw = [(norm(w["w"]), w) for w in heard if norm(w["w"])]
exp = [x[0] for x in nw]; got = [x[0] for x in hw]
for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, exp, got, autojunk=False).get_opcodes():
    extra = (j2 - j1) - (i2 - i1)
    if op == "insert" and j2 - j1 >= 2 or op == "replace" and extra >= 2:
        add(hw[j1][1]["s"], f"слышно лишнее «{' '.join(x[1]['w'] for x in hw[j1:j2])}» — фальстарт или брошенный дубль?")
    if op == "delete" and any(len(x) > 2 for x in exp[i1:i2]):
        add(nw[i1][1]["s"], f"пропало «{' '.join(x[1]['w'] for x in nw[i1:i2])}» — срезано или проглочено?")
for n in (2, 3):
    for i in range(len(got) - n):
        for j in range(i + n, min(i + n + 4, len(got) - n + 1)):
            if got[i:i + n] == got[j:j + n] and " ".join(got[i:i + n]) not in " ".join(exp):
                add(hw[j][1]["s"], f"на слух «{' '.join(x[1]['w'] for x in hw[i:i + n])}» звучит дважды — повтор?")

# 4б. Запинки, которые Whisper в целом ролике «склеивает» в одно слово («ровно 60… ровно 60 лет» → «ровно 60 лет»).
# Главный способ: на каждой микропаузе внутри речи кусок ДО и кусок ПОСЛЕ распознаются ОТДЕЛЬНО; конец первого = начало второго — повтор.
import tempfile, subprocess
from common import FF
def rec(t0, t1):
    with tempfile.TemporaryDirectory() as td:
        f = os.path.join(td, "c.wav")
        subprocess.run([FF, "-v", "error", "-y", "-ss", f"{max(0, t0):.3f}", "-to", f"{t1:.3f}", "-i", CUT, "-ac", "1", "-ar", "16000", f], check=True)
        return [x for x in (norm(w["w"]) for w in transcribe(f)) if x]
ws = [(w["s"], w["e"], w["w"]) for _, w in hw]
thr = float(np.percentile(ec, 50)) - 8          # «звучит речь»: не тише медианы больше чем на 8 дБ
vm = ec > thr
k = 0
while k < len(vm):                               # щелчки короче 40 мс паузу не разрывают
    if vm[k]:
        j = k
        while j < len(vm) and vm[j]: j += 1
        if j - k < 4: vm[k:j] = False
        k = j
    else: k += 1
voiced = lambda a_, b_: float(vm[int(a_ / HOP):int(b_ / HOP)].sum()) * HOP
found = []
k = 0
while k < len(vm):
    if not vm[k]:
        j = k
        while j < len(vm) and not vm[j]: j += 1
        if j - k >= 6 and vm[max(0, k - 15):k].sum() >= 12 and vm[j:j + 15].sum() >= 12:   # пауза ≥ 60 мс посреди речи
            p0, p1 = k * HOP, j * HOP
            L, Rr = rec(p0 - 1.0, p0 + 0.02), rec(p1 - 0.02, p1 + 1.0)
            hit = None
            if L and Rr:
                for n_ in (3, 2, 1):
                    # одно короткое слово — только при паузе от 0,1 с: внутри «что» (ч…то) есть своя микропауза 40–80 мс, это не повтор
                    if len(L) >= n_ and len(Rr) >= n_ and L[-n_:] == Rr[:n_] and (n_ >= 2 or (len(L[-1]) >= 3 and p1 - p0 >= 0.10)): hit = " ".join(L[-n_:]); break
                if not hit and len(L[-1]) >= 3 and any(x != L[-1] and x.startswith(L[-1]) for x in Rr[:2]): hit = L[-1] + "… " + next(x for x in Rr[:2] if x.startswith(L[-1]))
                # обрыв посреди слова: Whisper дописывает в конец огрызок («прошло ш…» перед «прошло 60 лет») — смотрим два последних слова
                if not hit and len(L) >= 2 and len(L[-2]) >= 3 and len(L[-1]) <= 2 and L[-2] in Rr[:2]: hit = L[-2] + " " + L[-1] + "…"
            if hit:
                found.append(p0); add(p0, f"запинка: перед паузой и после неё звучит «{hit}» (у {src_t(p0):.2f} с исходника) — вырезать первый вариант")
        k = j
    else: k += 1
# 4в. Слово дольше, чем положено по буквам, — распознать отдельно (вместе с предыдущим): два раза одно слово — повтор
for i, (s0, e0, w0) in enumerate(ws):
    nm = norm(w0)
    if not nm or e0 - s0 < 0.42 or e0 - s0 < 1.9 * (0.12 + 0.07 * len(nm)) or voiced(s0, e0) < 0.25: continue
    if any(abs(f_ - s0) < 0.8 for f_ in found): continue
    ps0 = ws[i - 1][0] if i > 0 else s0
    t4 = rec(ps0 - 0.05, e0 + 0.1); prev = norm(ws[i - 1][2]) if i > 0 else ""
    if (prev and t4.count(prev) >= 2) or t4.count(nm) >= 2:
        found.append(s0); add(s0, f"в растянутом слове «{w0}» отдельно слышно «{' '.join(t4)}» — повтор, вырезать")
# 4г. Звучит речь, которой нет среди слов (в паузе между словами или внутри растянутого слова)
for (s0, e0, w0), (s1, e1, w1) in zip(ws, ws[1:]):
    if s1 - e0 > 0.45 and voiced(e0, s1) > 0.35 and not any(e0 - 0.3 < f_ < s1 + 0.3 for f_ in found):
        add(e0, f"между «{w0}» и «{w1}» звучит речь ({voiced(e0, s1):.1f} с), которой нет в словах — оговорка/повтор? послушайте")

issues = sorted(set(issues))
merged_ = []   # тревоги в одном месте (ближе 0,6 с) — одной строкой
for t, m in issues:
    if merged_ and t - merged_[-1][0] < 0.6 and m not in merged_[-1][1]: merged_[-1] = (merged_[-1][0], merged_[-1][1] + " | " + m)
    elif not (merged_ and t - merged_[-1][0] < 0.6): merged_.append((t, m))
issues = merged_
proof = os.path.splitext(sys.argv[1])[0].replace(".edl", "") + ".proof.txt"
n_proof = sum(1 for l in open(proof, encoding="utf-8") if l.strip()) if os.path.exists(proof) else 0
print(f"нарезка {E['duration']:.1f} с, кусков {len(S)}")
for t, m in issues: print(f"!! {t:6.2f} с  {m}")
if len(issues) <= n_proof: print(f"\nНАРЕЗКА ПРОЙДЕНА: замечаний {len(issues)}, доказательств {n_proof}")
else:
    print(f"\nНЕ ПРОЙДЕНА: замечаний {len(issues)}, доказательств {n_proof}. Исправьте нарезку (keep/trim → шаг 3) или докажите ложное прямой проверкой в {os.path.basename(proof)}")
    sys.exit(1)
