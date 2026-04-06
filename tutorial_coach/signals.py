"""Señales Qt para comunicación thread-safe entre componentes."""
from PyQt5.QtCore import pyqtSignal, QObject


class Signals(QObject):
    # ── IA ─────────────────────────────────────────────────────────────────────
    plan_ready       = pyqtSignal(dict)    # plan JSON de la IA
    verify_result    = pyqtSignal(dict)    # {"completed": bool, "feedback": str}
    free_answer      = pyqtSignal(str)     # respuesta a pregunta libre / "dónde estoy"
    error_occurred   = pyqtSignal(str)     # error de la IA o sistema
    status_changed   = pyqtSignal(str)     # texto de estado del panel

    # ── Eventos de usuario ─────────────────────────────────────────────────────
    target_clicked   = pyqtSignal()        # click cerca del target actual
    hotkey_pressed   = pyqtSignal(str)     # hotkey global presionada (ej: "f1")

    # ── Voz ────────────────────────────────────────────────────────────────────
    voice_text_ready = pyqtSignal(str)     # STT terminó: texto reconocido
    voice_status     = pyqtSignal(str)     # "recording", "processing", "idle"

    # ── Recorder ───────────────────────────────────────────────────────────────
    recording_step   = pyqtSignal(dict)    # nuevo paso grabado
