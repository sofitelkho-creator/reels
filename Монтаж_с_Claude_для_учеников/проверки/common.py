"""Общие функции для проверок: звук через ffmpeg, огибающая громкости, распознавание речи.
Распознавание: на Mac с Apple Silicon — mlx-whisper (быстро), иначе — faster-whisper (Windows, Linux, Intel-Mac).
Модель можно сменить переменной окружения WHISPER_MODEL (по умолчанию large-v3-turbo)."""
import os, re, shutil, subprocess, json
import numpy as np

FF = shutil.which("ffmpeg") or os.path.expanduser("~/bin/ffmpeg")
FP = shutil.which("ffprobe") or os.path.expanduser("~/bin/ffprobe")
SR = 16000
HOP = 0.01   # шаг огибающей — 10 мс

# То, что Whisper «слышит» в тишине и шуме (галлюцинации). Такие куски не брать.
HALLUCINATIONS = ["продолжение следует", "спасибо за просмотр", "субтитры", "редактор субтитров", "подписывайтесь на канал",
                  "ставьте лайки", "до новых встреч", "благодарю за внимание", "dimatorzok", "amara.org"]


def need_ffmpeg():
    if not (os.path.exists(FF) or shutil.which("ffmpeg")):
        raise SystemExit("Нет ffmpeg. Поставьте его (ffmpeg.org) и добавьте в PATH.")


def duration(path):
    out = subprocess.run([FP, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], capture_output=True, text=True).stdout
    return float(out.strip())


def load_audio(path, ss=None, to=None, sr=SR):
    """Моно float32. ss/to — секунды исходника (необязательно)."""
    cmd = [FF, "-v", "error"]
    if ss is not None: cmd += ["-ss", f"{max(0, ss):.3f}"]
    if to is not None: cmd += ["-to", f"{to:.3f}"]
    cmd += ["-i", path, "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    return np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.float32).copy()


def env_db(x, sr=SR, hop=HOP):
    """Громкость (дБ) каждые 10 мс."""
    n = int(sr * hop); k = len(x) // n
    if k == 0: return np.array([-100.0])
    f = x[:k * n].reshape(k, n)
    return 20 * np.log10(np.sqrt((f ** 2).mean(1)) + 1e-9)


def band_db(x, lo, hi, sr=SR, hop=HOP, win=0.03):
    """Громкость в полосе частот lo–hi Гц каждые 10 мс (для гласных — 200–2500, для шипящих — 3500–8000)."""
    n, w = int(sr * hop), int(sr * win)
    if len(x) < w: return np.array([-100.0])
    freqs = np.fft.rfftfreq(w, 1 / sr); m = (freqs >= lo) & (freqs < hi); win_f = np.hanning(w)
    out = []
    for i in range(0, len(x) - w, n):
        s = np.abs(np.fft.rfft(x[i:i + w] * win_f)) ** 2
        out.append(10 * np.log10(s[m].sum() / w + 1e-12))
    return np.array(out)


def levels(e):
    """Пол (тишина) и уровень речи по огибающей."""
    return float(np.percentile(e, 12)), float(np.percentile(e, 95))


def norm(w):
    w = w.lower().replace("ё", "е")
    return re.sub(r"[^\w%]+", "", w)


def is_hallucination(text, dur):
    t = norm_text(text)
    if any(h.replace(" ", "") in t.replace(" ", "") for h in HALLUCINATIONS): return True
    return dur < 1.0 and t in ("спасибо", "спасибо спасибо", "угу", "ага")   # короткое «Спасибо.» в тишине — частая выдумка Whisper


def norm_text(text):
    return " ".join(norm(w) for w in text.split() if norm(w))


_model = {}
def transcribe(path, lang="ru", prompt=None, words=True):
    """[{w, s, e}] — слова с временем (секунды файла). Сначала пробует mlx-whisper, потом faster-whisper."""
    name = os.environ.get("WHISPER_MODEL", "large-v3-turbo")
    try:
        import mlx_whisper
        repo = name if "/" in name else f"mlx-community/whisper-{name}"
        r = mlx_whisper.transcribe(path, path_or_hf_repo=repo, language=lang, word_timestamps=words, initial_prompt=prompt,
                                   condition_on_previous_text=False)
        return [{"w": w["word"].strip(), "s": round(w["start"], 3), "e": round(w["end"], 3)} for sg in r["segments"] for w in sg.get("words", [])]
    except ImportError:
        pass
    # whisper.cpp (pywhispercpp) — если в папке «модели» лежит файл ggml-*.bin (когда сайт моделей недоступен)
    import glob
    ggml = os.environ.get("WHISPER_CPP_MODEL") or next(iter(sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "модели", "ggml-*.bin")))), None)
    if ggml:
        try:
            from pywhispercpp.model import Model
        except ImportError:
            ggml = None
    if ggml:
        if ggml not in _model:
            _model[ggml] = Model(ggml, n_threads=os.cpu_count() or 4, print_progress=False, print_realtime=False, redirect_whispercpp_logs_to=None)
        audio = load_audio(path)
        kw = dict(language=lang, token_timestamps=words, split_on_word=True, max_len=1 if words else 0)
        if prompt:
            kw["initial_prompt"] = prompt
        segs = _model[ggml].transcribe(audio, **kw)
        return [{"w": sg.text.strip(), "s": round(sg.t0 / 100, 3), "e": round(sg.t1 / 100, 3)} for sg in segs if sg.text.strip()]
    # sherpa-onnx (GigaAM, русский) — если задана папка SHERPA_MODEL (когда huggingface.co недоступен; модель лежит в релизах GitHub k2-fsa/sherpa-onnx)
    sherpa = os.environ.get("SHERPA_MODEL")
    if sherpa:
        return _transcribe_sherpa(path, sherpa)
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise SystemExit("Нет распознавания речи: pip install faster-whisper  (на Mac с M-чипом лучше: pip install mlx-whisper)")
    if name not in _model:
        _model[name] = WhisperModel(name, device="auto", compute_type="int8")
    audio = load_audio(path)   # звук читаем сами через ffmpeg: встроенный декодер faster-whisper ломается на части версий PyAV
    segs, _ = _model[name].transcribe(audio, language=lang, word_timestamps=words, initial_prompt=prompt, condition_on_previous_text=False, vad_filter=False)
    return [{"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)} for sg in segs for w in (sg.words or [])]


def _transcribe_sherpa(path, d):
    """GigaAM через sherpa-onnx: модель выдаёт буквы со временем, из них собираем слова. Без пунктуации и цифр."""
    import sherpa_onnx
    if d not in _model:
        _model[d] = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=os.path.join(d, "encoder.int8.onnx"), decoder=os.path.join(d, "decoder.onnx"), joiner=os.path.join(d, "joiner.onnx"),
            tokens=os.path.join(d, "tokens.txt"), model_type="nemo_transducer", num_threads=os.cpu_count() or 4)
    audio = load_audio(path)
    st = _model[d].create_stream(); st.accept_waveform(SR, audio); _model[d].decode_stream(st)
    r = st.result
    words, cur = [], None
    for tok, t in zip(r.tokens, r.timestamps):
        if tok.strip() == "":
            cur = None; continue
        if cur is None:
            cur = {"w": "", "s": t, "e": t}; words.append(cur)
        cur["w"] += tok; cur["e"] = t
    # время буквы — её начало; конец слова — плюс одна буква (~0,08 с)
    end = len(audio) / SR
    return [{"w": w["w"], "s": round(w["s"], 3), "e": round(min(end, w["e"] + 0.08), 3)} for w in words]


def save(obj, path):
    json.dump(obj, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def load(path):
    return json.load(open(path, encoding="utf-8"))
