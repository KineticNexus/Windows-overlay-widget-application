"""Motor de voz: TTS (pyttsx3) + STT (speech_recognition con Google)."""
import threading

from tutorial_coach.signals import Signals

# ── TTS (text-to-speech) ───────────────────────────────────────────────────────
_tts_engine = None
_tts_lock   = threading.Lock()


def _get_tts():
    global _tts_engine
    if _tts_engine is None:
        import pyttsx3
        _tts_engine = pyttsx3.init()
        _tts_engine.setProperty("rate", 160)
        # Buscar voz en español si existe
        for voice in _tts_engine.getProperty("voices"):
            if "spanish" in voice.name.lower() or "es" in voice.id.lower():
                _tts_engine.setProperty("voice", voice.id)
                break
    return _tts_engine


def speak(text: str):
    """Lee texto en voz alta. No bloquea."""
    def _run():
        with _tts_lock:
            try:
                engine = _get_tts()
                engine.say(text)
                engine.runAndWait()
            except Exception:
                pass  # fallo silencioso si TTS no funciona
    threading.Thread(target=_run, daemon=True).start()


def set_rate(wpm: int):
    """Cambia velocidad de voz (palabras por minuto)."""
    try:
        engine = _get_tts()
        engine.setProperty("rate", wpm)
    except Exception:
        pass


# ── STT (speech-to-text) ──────────────────────────────────────────────────────
_stt_thread = None


def listen(signals: Signals, timeout: int = 8):
    """
    Graba audio del micrófono y lo convierte a texto.
    Emite voice_text_ready con el texto, o voice_status con errores.
    """
    global _stt_thread

    def _run():
        try:
            import speech_recognition as sr
        except ImportError:
            signals.voice_status.emit("error:instala SpeechRecognition y pyaudio")
            return

        signals.voice_status.emit("recording")
        recognizer = sr.Recognizer()
        recognizer.energy_threshold = 300
        recognizer.dynamic_energy_threshold = True

        try:
            with sr.Microphone() as mic:
                recognizer.adjust_for_ambient_noise(mic, duration=0.5)
                signals.voice_status.emit("recording")
                audio = recognizer.listen(mic, timeout=timeout, phrase_time_limit=15)

            signals.voice_status.emit("processing")
            text = recognizer.recognize_google(audio, language="es-ES")
            signals.voice_text_ready.emit(text)
            signals.voice_status.emit("idle")

        except Exception as e:
            err = str(e)
            if "timed out" in err.lower():
                signals.voice_status.emit("No escuché nada. Intenta de nuevo.")
            elif "no microphone" in err.lower() or "pyaudio" in err.lower():
                signals.voice_status.emit("error:No se detectó micrófono")
            else:
                signals.voice_status.emit(f"error:{err[:80]}")

    _stt_thread = threading.Thread(target=_run, daemon=True)
    _stt_thread.start()
