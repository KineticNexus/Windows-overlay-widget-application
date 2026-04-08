"""Motor de voz: TTS + STT via Deepgram API, con fallback local."""
import io
import os
import wave
import threading
import tempfile

from tutorial_coach.signals import Signals

_tts_lock = threading.Lock()
_deepgram_key = ""


def set_deepgram_key(key: str):
    global _deepgram_key
    _deepgram_key = key.strip()


# ═══════════════════════════════════════════════════════════════════════════════
#  TTS — Deepgram Aura → WAV → winsound (fallback: pyttsx3)
# ═══════════════════════════════════════════════════════════════════════════════
def speak(text: str):
    """Lee texto en voz alta. No bloquea."""
    if not text or not text.strip():
        return
    threading.Thread(target=lambda: _speak_sync(text), daemon=True).start()


def _speak_sync(text: str):
    with _tts_lock:
        if _deepgram_key:
            try:
                _speak_deepgram(text)
                return
            except Exception:
                pass
        _speak_pyttsx3(text)


def _speak_deepgram(text: str):
    """TTS via Deepgram Aura API → WAV → winsound."""
    import httpx

    resp = httpx.post(
        "https://api.deepgram.com/v1/speak",
        params={"model": "aura-asteria-en", "encoding": "linear16",
                "sample_rate": "24000", "container": "wav"},
        headers={"Authorization": f"Token {_deepgram_key}",
                 "Content-Type": "application/json"},
        json={"text": text},
        timeout=15,
    )
    resp.raise_for_status()

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.write(resp.content)
    tmp.close()
    try:
        import winsound
        winsound.PlaySound(tmp.name, winsound.SND_FILENAME)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def _speak_pyttsx3(text: str):
    """Fallback TTS local con pyttsx3."""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", 160)
        voices = engine.getProperty("voices") or []
        for v in voices:
            name = getattr(v, "name", "") or ""
            vid  = getattr(v, "id", "")  or ""
            if "spanish" in name.lower() or "es" in vid.lower():
                engine.setProperty("voice", vid)
                break
        engine.say(text)
        engine.runAndWait()
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
#  STT — Deepgram Nova-2 (fallback: Google via speech_recognition)
# ═══════════════════════════════════════════════════════════════════════════════
def listen(signals: Signals, timeout: int = 8):
    """Graba micrófono y transcribe. Emite voice_text_ready o voice_status."""
    threading.Thread(target=lambda: _listen_sync(signals, timeout),
                     daemon=True).start()


def _listen_sync(signals: Signals, timeout: int):
    signals.voice_status.emit("recording")

    try:
        audio_wav = _record_mic(timeout)
    except Exception as e:
        signals.voice_status.emit(f"error:Micrófono no disponible: {e}")
        return

    signals.voice_status.emit("processing")

    # Intentar Deepgram primero
    if _deepgram_key:
        try:
            text = _stt_deepgram(audio_wav)
            if text and text.strip():
                signals.voice_text_ready.emit(text.strip())
                signals.voice_status.emit("idle")
                return
        except Exception:
            pass

    # Fallback Google
    try:
        text = _stt_google(audio_wav)
        if text and text.strip():
            signals.voice_text_ready.emit(text.strip())
            signals.voice_status.emit("idle")
        else:
            signals.voice_status.emit("error:No escuché nada. Intenta de nuevo.")
    except Exception as e:
        signals.voice_status.emit(f"error:{str(e)[:80]}")


def _record_mic(duration: int = 8) -> bytes:
    """Graba audio del micrófono y devuelve bytes WAV."""
    import pyaudio

    RATE     = 16000
    CHUNK    = 1024
    FORMAT   = pyaudio.paInt16
    CHANNELS = 1

    p = pyaudio.PyAudio()
    # Obtener sample size ANTES de terminate()
    sample_width = p.get_sample_size(FORMAT)

    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                    input=True, frames_per_buffer=CHUNK)
    frames = []
    try:
        for _ in range(int(RATE / CHUNK * duration)):
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

    buf = io.BytesIO()
    wf = wave.open(buf, "wb")
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(sample_width)
    wf.setframerate(RATE)
    wf.writeframes(b"".join(frames))
    wf.close()
    return buf.getvalue()


def _stt_deepgram(audio_wav: bytes) -> str:
    """STT via Deepgram Nova-2 API."""
    import httpx

    resp = httpx.post(
        "https://api.deepgram.com/v1/listen",
        params={"language": "es", "model": "nova-2", "smart_format": "true"},
        headers={"Authorization": f"Token {_deepgram_key}",
                 "Content-Type": "audio/wav"},
        content=audio_wav,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    # Acceso seguro a la estructura de respuesta
    try:
        transcript = (data.get("results", {})
                          .get("channels", [{}])[0]
                          .get("alternatives", [{}])[0]
                          .get("transcript", ""))
        return transcript
    except (IndexError, AttributeError, TypeError):
        return ""


def _stt_google(audio_wav: bytes) -> str:
    """Fallback STT con Google via speech_recognition."""
    import speech_recognition as sr

    recognizer = sr.Recognizer()
    # WAV estándar: header de 44 bytes, mono 16-bit 16kHz
    audio = sr.AudioData(audio_wav[44:], 16000, 2)
    return recognizer.recognize_google(audio, language="es-ES")
