"""Шаг 2. Подсказка, какие дубли брать: из нескольких попыток одной фразы — последняя полная.
  python 2_выбрать_дубли.py ИСХОДНИК.chunks.json
Пишет ИСХОДНИК.keep.json — список кусков для нарезки — и печатает группы дублей (✓ — взят, ✗ — отброшен и почему).
Это ПОДСКАЗКА: Claude и вы проверяете её глазами. Сценарные повторы («Весь мир… Весь мир…») группой не считаются, если между ними другие фразы.
Фальстарт ВНУТРИ одного куска («ровно 60… ровно 60 лет назад») расшифровка часто не видит — его ловит шаг 4 (прослушка)."""
import sys, os, difflib, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load, save, norm

MAT = re.compile(r"\b(бля\w*|сук[аи]|ху[йяе]\w*|пизд\w*|еба\w*|ёба\w*|нахуй|охуе\w*)\b", re.I)
path = sys.argv[1]; C = load(path)
words = lambda c: [norm(w["w"]) for w in c["words"] if norm(w["w"])]
complete = lambda c: c["text"].rstrip().endswith((".", "!", "?", "»")) and not c["text"].rstrip().endswith("...") and not c["text"].rstrip().endswith("…")
FILLER = {"в", "и", "а", "но", "ну", "вот", "так", "да", "это"}
def head(c, k):   # первые слова без служебного в начале («В 8 лет…» = «8 лет…»)
    w = words(c)
    while w and w[0] in FILLER and len(w) > 1: w = w[1:]
    return w[:k]
def _eq(u, v):   # слово совпадает или оборвано («глав» = «главное», «на работ» = «наработки»)
    return u == v or (min(len(u), len(v)) >= 3 and (u.startswith(v) or v.startswith(u)))
def _alike(a, b):
    if not (a and b) or not _eq(a[0], b[0]): return False
    n = min(len(a), len(b))
    if all(_eq(a[i], b[i]) for i in range(n)): return True      # одно — начало другого: оборванный дубль
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.6
def same_start(x, y, k=3):   # начала совпадают — как есть или без служебного слова в начале
    return _alike(words(x)[:k], words(y)[:k]) or _alike(head(x, k), head(y, k))

groups, skipped = [], []
MIC = {"раз", "раздва", "раздватри", "разраз", "проверка", "тест", "алло"}
for c in C:
    if c.get("halluc"): skipped.append((c, "галлюцинация Whisper в тишине")); continue
    if "".join(words(c)) in MIC: skipped.append((c, "проверка микрофона")); continue
    if c["b"] - c["a"] < 0.6 and len(words(c)) <= 1 and not complete(c): skipped.append((c, "обрывок")); continue
    if MAT.search(c["text"]): skipped.append((c, "мат — оговорка, вырезать")); continue
    if groups and any(same_start(c, g) for g in groups[-1]): groups[-1].append(c)
    elif len(groups) >= 2 and any(same_start(c, g) for g in groups[-2]):   # между дублями один исковерканный («Значит, то же завтра»)
        last = groups.pop(); groups[-1].extend(last + [c])
    else: groups.append([c])
keep = []
for gi, g in enumerate(groups):
    longest = max(len(words(c)) for c in g)
    good = [c for c in g if complete(c) and len(words(c)) >= 0.75 * longest]
    pick = good[-1] if good else max(g, key=lambda c: (len(words(c)), c["a"]))
    # поздний дубль, записанный двумя кусками: короче полного, но его продолжение — следующий кусок → берём поздний (последний дубль — лучший)
    last_ok = [c for c in g if complete(c)]
    if last_ok and last_ok[-1] is not pick and last_ok[-1]["a"] > pick["a"] and gi + 1 < len(groups):
        full, short, nxt = words(max(g, key=lambda c: len(words(c)))), words(last_ok[-1]), words(groups[gi + 1][0])
        rest = full[len(short):] if len(full) > len(short) else []
        if rest and difflib.SequenceMatcher(None, rest, nxt).ratio() >= 0.6: pick = last_ok[-1]
    keep.append(pick["a"])
    if len(g) > 1:
        print("дубли:")
        for c in g:
            why = "" if c is pick else ("  ← оборван" if not complete(c) else ("  ← короче полного" if len(words(c)) < 0.75 * longest and c["a"] < pick["a"] else "  ← есть дубль позже"))
            print(f"   {'✓' if c is pick else '✗'} {c['n']:3} {c['a']:7.2f}  {c['text']}{why}")
    else:
        print(f"   ✓ {g[0]['n']:3} {g[0]['a']:7.2f}  {g[0]['text']}")
for c, why in skipped:
    print(f"   ✗ {c['n']:3} {c['a']:7.2f}  {c['text']}  ← {why}")
out = path.replace(".chunks.json", ".keep.json")
save({"keep": keep, "trim": {}, "_как_править": "keep — начала (a) нужных кусков. trim: {\"a\": [от, до]} — взять из куска только часть (вырезать фальстарт в начале или лишнее в конце), время в секундах исходника; null — без ограничения"}, out)
print(f"\nвзято кусков: {len(keep)} → {out}\nДальше: python 3_нарезать.py ИСХОДНИК {path} {out}")
