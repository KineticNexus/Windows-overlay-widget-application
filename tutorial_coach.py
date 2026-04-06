"""
AI Tutorial Coach para Ancianos — v2
=====================================
El usuario escribe en el chat qué quiere aprender.
El asistente observa la pantalla, los clicks del mouse y lo que se escribe,
y va dando instrucciones paso a paso en lenguaje simple.

Instalación:
    pip install anthropic mss Pillow PyQt5 pynput

Uso:
    1. Configura la variable de entorno ANTHROPIC_API_KEY
    2. python tutorial_coach.py
    3. Escribe en el chat qué quieres aprender (ej: "quiero mandar un mensaje a mi hijo")
    4. Sigue las instrucciones en pantalla

NOTA: La aplicación captura clicks del mouse y texto escrito para ayudar
      al asistente a entender qué está haciendo el usuario.
"""

import sys
import base64
import threading
import time
from io import BytesIO
from collections import deque

try:
    import mss
    from PIL import Image
    import anthropic
    from pynput import mouse as pmouse, keyboard as pkeyboard
    from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
    from PyQt5.QtGui import QFont, QTextCursor
    from PyQt5.QtWidgets import (
        QApplication, QLabel, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QTextEdit, QLineEdit, QFrame, QSizePolicy,
        QScrollArea,
    )
except ImportError as e:
    print(f"\nFalta una dependencia: {e}")
    print("Instala con:  pip install anthropic mss Pillow PyQt5 pynput\n")
    sys.exit(1)


# ───────────────────────────────────────────────────────────
#  Constantes
# ───────────────────────────────────────────────────────────
DEBOUNCE_SECONDS = 2.5      # segundos de inactividad antes de analizar
MAX_EVENTS = 15             # eventos recientes a enviar a la IA
MAX_HISTORY = 24            # mensajes máximos en historial de conversación

SYSTEM_PROMPT = """Eres un asistente muy amable, paciente y claro que ayuda a personas mayores \
a usar internet en su computadora.

Tienes acceso a:
1. Una captura de la pantalla actual del usuario
2. Lo que el usuario te escribió en el chat (su objetivo)
3. Los eventos recientes: clicks del mouse y texto que escribió en la pantalla

Tu tarea es dar UNA sola instrucción concreta y simple sobre qué hacer a continuación.

Reglas estrictas:
- Una sola acción por respuesta. Nunca des dos pasos a la vez.
- Lenguaje muy simple. Evita tecnicismos. Di "presiona" en vez de "haz clic". \
Di "la barra de arriba donde dice la dirección" en vez de "URL". \
Di "el botón verde grande" en vez de "botón de confirmación".
- Describe exactamente DÓNDE está el elemento: color, posición, texto que muestra.
- Si el usuario ya hizo lo que pediste (lo ves en los eventos o en la pantalla), \
reconócelo con entusiasmo antes de dar el siguiente paso.
- Si ves que el usuario cometió un error, dile cómo corregirlo amablemente.
- Tono cálido y motivador. Usa "¡Muy bien!", "¡Perfecto!", "¡Casi listo!".
- Máximo 3 oraciones cortas.

Responde ÚNICAMENTE con la instrucción. Sin numeración, sin títulos, sin texto extra."""


# ───────────────────────────────────────────────────────────
#  Señales Qt (comunicación entre hilos → UI)
# ───────────────────────────────────────────────────────────
class Signals(QObject):
    instruction_ready   = pyqtSignal(str)   # nueva instrucción de la IA
    status_changed      = pyqtSignal(str)   # texto de estado pequeño
    activity_logged     = pyqtSignal(str)   # evento de mouse/teclado
    chat_reply          = pyqtSignal(str)   # mensaje IA en el chat


# ───────────────────────────────────────────────────────────
#  Monitor de eventos (mouse + teclado) con pynput
# ───────────────────────────────────────────────────────────
class EventMonitor:
    """Escucha mouse y teclado en background y acumula eventos en un buffer."""

    def __init__(self, signals: Signals, on_activity):
        self.signals = signals
        self.on_activity = on_activity          # callback al detectar actividad
        self.events: deque = deque(maxlen=MAX_EVENTS)
        self._typed: list  = []                  # buffer de texto en curso
        self._overlay_rect = None                # (x, y, w, h) del overlay
        self._mouse_listener    = None
        self._keyboard_listener = None
        self._ignore_keyboard   = False          # True cuando el chat tiene foco

    # ── Ciclo de vida ──────────────────────────────────────
    def start(self):
        self._mouse_listener = pmouse.Listener(on_click=self._on_click)
        self._keyboard_listener = pkeyboard.Listener(on_press=self._on_key)
        self._mouse_listener.daemon = True
        self._keyboard_listener.daemon = True
        self._mouse_listener.start()
        self._keyboard_listener.start()

    def stop(self):
        if self._mouse_listener:
            self._mouse_listener.stop()
        if self._keyboard_listener:
            self._keyboard_listener.stop()

    def set_overlay_rect(self, x: int, y: int, w: int, h: int):
        self._overlay_rect = (x, y, w, h)

    def set_ignore_keyboard(self, ignore: bool):
        self._ignore_keyboard = ignore

    # ── Handlers de eventos ───────────────────────────────
    def _in_overlay(self, x: int, y: int) -> bool:
        if not self._overlay_rect:
            return False
        ox, oy, ow, oh = self._overlay_rect
        return ox <= x <= ox + ow and oy <= y <= oy + oh

    def _flush_typed(self):
        if self._typed:
            text = "".join(self._typed).strip()
            if text:
                evt = f'Escribió: "{text[:60]}"'
                self.events.append(evt)
                self.signals.activity_logged.emit(f"⌨  {evt}")
            self._typed.clear()

    def _on_click(self, x, y, button, pressed):
        if not pressed or self._in_overlay(x, y):
            return
        self._flush_typed()
        evt = f"Click del mouse en posición ({x}, {y})"
        self.events.append(evt)
        self.signals.activity_logged.emit(f"🖱  ({x}, {y})")
        self.on_activity()

    def _on_key(self, key):
        if self._ignore_keyboard:
            return
        try:
            char = key.char
            if char and char.isprintable():
                self._typed.append(char)
                self.on_activity()
        except AttributeError:
            if key == pkeyboard.Key.backspace:
                if self._typed:
                    self._typed.pop()
            elif key == pkeyboard.Key.enter:
                self._flush_typed()
                self.events.append("Presionó Enter")
                self.signals.activity_logged.emit("↵  Enter")
                self.on_activity()
            elif key == pkeyboard.Key.space:
                self._typed.append(" ")

    # ── API pública ───────────────────────────────────────
    def get_summary(self) -> str:
        self._flush_typed()
        if not self.events:
            return "Sin actividad de mouse o teclado desde la última consulta."
        return "\n".join(f"- {e}" for e in self.events)

    def clear(self):
        self.events.clear()
        self._typed.clear()


# ───────────────────────────────────────────────────────────
#  Timer de debounce simple (cancela y reinicia)
# ───────────────────────────────────────────────────────────
class DebounceTimer:
    def __init__(self, delay: float, callback):
        self.delay = delay
        self.callback = callback
        self._timer = None
        self._lock = threading.Lock()

    def trigger(self):
        with self._lock:
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(self.delay, self.callback)
            self._timer.daemon = True
            self._timer.start()

    def cancel(self):
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None


# ───────────────────────────────────────────────────────────
#  Lógica de IA (Claude con visión)
# ───────────────────────────────────────────────────────────
class AICoach:
    def __init__(self, signals: Signals):
        self.signals  = signals
        self.client   = anthropic.Anthropic()
        self.history  = []          # conversación texto (sin imágenes)
        self.goal     = ""          # objetivo del usuario
        self._busy    = False
        self._lock    = threading.Lock()

    # ── Captura de pantalla ───────────────────────────────
    def _capture(self) -> str:
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            shot = sct.grab(monitor)
            img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
            img.thumbnail((1280, 720), Image.LANCZOS)
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=82)
            return base64.b64encode(buf.getvalue()).decode()

    # ── Consulta a la IA ──────────────────────────────────
    def analyze(self, events_summary: str, user_message: str = ""):
        """Llama a Claude en un hilo separado. No bloquea."""
        with self._lock:
            if self._busy:
                return
            self._busy = True

        def _run():
            try:
                self.signals.status_changed.emit("Analizando pantalla y actividad...")
                image_b64 = self._capture()

                # Construir el texto de contexto para este turno
                parts = []
                if self.goal:
                    parts.append(f"Objetivo del usuario: {self.goal}")
                if events_summary and "Sin actividad" not in events_summary:
                    parts.append(f"Actividad reciente:\n{events_summary}")
                if user_message:
                    parts.append(f"El usuario dice: {user_message}")
                parts.append("Esta es la pantalla ahora mismo. ¿Cuál es el siguiente paso?")
                context_text = "\n\n".join(parts)

                # Mensajes: historial texto + imagen actual
                messages = list(self.history) + [{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_b64,
                            },
                        },
                        {"type": "text", "text": context_text},
                    ],
                }]

                response = self.client.messages.create(
                    model="claude-opus-4-6",
                    max_tokens=250,
                    system=SYSTEM_PROMPT,
                    messages=messages,
                )
                instruction = response.content[0].text.strip()

                # Guardar en historial solo texto (imágenes se descartan)
                summary = context_text.replace(image_b64, "")[:200]
                self.history.append({"role": "user",      "content": summary})
                self.history.append({"role": "assistant", "content": instruction})
                if len(self.history) > MAX_HISTORY:
                    self.history = self.history[-MAX_HISTORY:]

                self.signals.instruction_ready.emit(instruction)
                self.signals.chat_reply.emit(instruction)
                self.signals.status_changed.emit("Listo  •  activo")

            except anthropic.AuthenticationError:
                msg = "Error de API: verifica tu ANTHROPIC_API_KEY."
                self.signals.instruction_ready.emit(f"⚠  {msg}")
                self.signals.status_changed.emit("Error de autenticación")
            except Exception as exc:
                msg = f"Error inesperado: {exc}"
                self.signals.instruction_ready.emit(f"⚠  {msg}")
                self.signals.status_changed.emit("Error")
            finally:
                with self._lock:
                    self._busy = False

        threading.Thread(target=_run, daemon=True).start()

    def reset(self):
        self.history.clear()
        self.goal = ""


# ───────────────────────────────────────────────────────────
#  Overlay PyQt5
# ───────────────────────────────────────────────────────────
STYLE = """
QWidget#root {
    background-color: #111827;
    border: 2px solid #22c55e;
    border-radius: 16px;
}
QLabel#header_label {
    color: #22c55e;
    background: transparent;
}
QLabel#instruction_label {
    color: #f9fafb;
    background: transparent;
}
QLabel#status_label {
    color: #6b7280;
    background: transparent;
}
QTextEdit#chat_log {
    background-color: #1f2937;
    color: #d1d5db;
    border: 1px solid #374151;
    border-radius: 8px;
    padding: 6px;
}
QLineEdit#chat_input {
    background-color: #1f2937;
    color: #f9fafb;
    border: 2px solid #374151;
    border-radius: 8px;
    padding: 8px 12px;
}
QLineEdit#chat_input:focus {
    border-color: #22c55e;
}
QPushButton {
    background-color: #22c55e;
    color: #111827;
    border: none;
    border-radius: 8px;
    padding: 9px 18px;
    font-weight: bold;
}
QPushButton:hover    { background-color: #16a34a; }
QPushButton:disabled { background-color: #374151; color: #6b7280; }
QPushButton#reset_btn {
    background-color: #374151;
    color: #9ca3af;
}
QPushButton#reset_btn:hover { background-color: #4b5563; }
QFrame#divider {
    color: #374151;
    background-color: #374151;
}
"""


class TutorialOverlay(QWidget):
    chat_submitted = pyqtSignal(str)      # usuario envió mensaje en el chat
    chat_focus_changed = pyqtSignal(bool) # True = input tiene foco

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self._build_ui()
        self._place_on_screen()

    # ── Construcción de UI ────────────────────────────────
    def _build_ui(self):
        self.setStyleSheet(STYLE)

        root = QWidget(self)
        root.setObjectName("root")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(22, 16, 22, 16)
        layout.setSpacing(10)

        # ── Cabecera ─────────────────────────────────────
        header_row = QHBoxLayout()
        header = QLabel("🧭  Asistente paso a paso")
        header.setObjectName("header_label")
        header.setFont(QFont("Arial", 13, QFont.Bold))
        header_row.addWidget(header)
        header_row.addStretch()

        self.status_label = QLabel("Listo para comenzar")
        self.status_label.setObjectName("status_label")
        self.status_label.setFont(QFont("Arial", 11))
        header_row.addWidget(self.status_label)

        reset_btn = QPushButton("↺ Reiniciar")
        reset_btn.setObjectName("reset_btn")
        reset_btn.setObjectName("reset_btn")
        reset_btn.setFont(QFont("Arial", 11))
        reset_btn.setFixedWidth(110)
        reset_btn.clicked.connect(self._on_reset_clicked)
        header_row.addWidget(reset_btn)
        layout.addLayout(header_row)

        # ── Instrucción grande ────────────────────────────
        self.instruction_label = QLabel("Escríbeme en el chat qué quieres aprender.")
        self.instruction_label.setObjectName("instruction_label")
        self.instruction_label.setFont(QFont("Arial", 21, QFont.Bold))
        self.instruction_label.setWordWrap(True)
        self.instruction_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.instruction_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.instruction_label.setMinimumHeight(80)
        layout.addWidget(self.instruction_label)

        # ── Divisor ───────────────────────────────────────
        line = QFrame()
        line.setObjectName("divider")
        line.setFrameShape(QFrame.HLine)
        line.setFixedHeight(1)
        layout.addWidget(line)

        # ── Log de actividad (pequeño, colapsable) ────────
        activity_row = QHBoxLayout()
        act_title = QLabel("Actividad reciente:")
        act_title.setFont(QFont("Arial", 10))
        act_title.setStyleSheet("color: #6b7280; background: transparent;")
        activity_row.addWidget(act_title)
        activity_row.addStretch()
        layout.addLayout(activity_row)

        self.activity_log = QTextEdit()
        self.activity_log.setObjectName("chat_log")
        self.activity_log.setReadOnly(True)
        self.activity_log.setFont(QFont("Consolas", 10))
        self.activity_log.setFixedHeight(60)
        layout.addWidget(self.activity_log)

        # ── Chat ──────────────────────────────────────────
        chat_title = QLabel("Chat — escribe qué quieres hacer:")
        chat_title.setFont(QFont("Arial", 11, QFont.Bold))
        chat_title.setStyleSheet("color: #d1d5db; background: transparent;")
        layout.addWidget(chat_title)

        self.chat_log = QTextEdit()
        self.chat_log.setObjectName("chat_log")
        self.chat_log.setReadOnly(True)
        self.chat_log.setFont(QFont("Arial", 12))
        self.chat_log.setFixedHeight(110)
        layout.addWidget(self.chat_log)

        # ── Entrada de chat ───────────────────────────────
        input_row = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setObjectName("chat_input")
        self.chat_input.setFont(QFont("Arial", 14))
        self.chat_input.setPlaceholderText(
            "Ej: quiero mandar un mensaje a mi hijo por WhatsApp..."
        )
        self.chat_input.returnPressed.connect(self._on_send)
        self.chat_input.focusInEvent  = self._input_focus_in
        self.chat_input.focusOutEvent = self._input_focus_out
        input_row.addWidget(self.chat_input)

        send_btn = QPushButton("Enviar  ▶")
        send_btn.setFont(QFont("Arial", 13, QFont.Bold))
        send_btn.setFixedWidth(120)
        send_btn.clicked.connect(self._on_send)
        input_row.addWidget(send_btn)
        layout.addLayout(input_row)

    # ── Posición ──────────────────────────────────────────
    def _place_on_screen(self):
        screen = QApplication.primaryScreen().geometry()
        w = min(860, screen.width() - 40)
        self.setFixedWidth(w)
        self.adjustSize()
        x = (screen.width() - w) // 2
        y = screen.height() - self.sizeHint().height() - 30
        self.move(x, y)

    # ── Handlers internos ─────────────────────────────────
    def _on_send(self):
        text = self.chat_input.text().strip()
        if not text:
            return
        self.chat_input.clear()
        self._append_chat("Tú", text, "#86efac")
        self.chat_submitted.emit(text)

    def _on_reset_clicked(self):
        self.chat_log.clear()
        self.activity_log.clear()
        self.instruction_label.setText("Historial borrado. ¿Qué quieres aprender ahora?")
        self.status_label.setText("Reiniciado")
        # Emitir vacío para que el app resetee el coach
        self.chat_submitted.emit("")

    def _input_focus_in(self, event):
        self.chat_focus_changed.emit(True)
        QLineEdit.focusInEvent(self.chat_input, event)

    def _input_focus_out(self, event):
        self.chat_focus_changed.emit(False)
        QLineEdit.focusOutEvent(self.chat_input, event)

    # ── API pública ───────────────────────────────────────
    def show_instruction(self, text: str):
        self.instruction_label.setText(text)
        self.adjustSize()
        # Reposicionar por si cambió el alto
        screen = QApplication.primaryScreen().geometry()
        y = screen.height() - self.height() - 30
        self.move(self.x(), y)

    def show_status(self, text: str):
        self.status_label.setText(text)

    def log_activity(self, text: str):
        self.activity_log.append(text)
        self.activity_log.moveCursor(QTextCursor.End)

    def _append_chat(self, who: str, text: str, color: str):
        self.chat_log.append(
            f'<span style="color:{color};font-weight:bold">{who}:</span> '
            f'<span style="color:#f3f4f6">{text}</span>'
        )
        self.chat_log.moveCursor(QTextCursor.End)

    def show_ai_reply(self, text: str):
        self._append_chat("Asistente", text, "#60a5fa")

    def get_overlay_rect(self):
        pos = self.pos()
        size = self.size()
        return pos.x(), pos.y(), size.width(), size.height()


# ───────────────────────────────────────────────────────────
#  Orquestador principal
# ───────────────────────────────────────────────────────────
class TutorialApp:
    def __init__(self):
        self.qt_app = QApplication(sys.argv)
        self.qt_app.setApplicationName("Asistente Tutorial")

        self.signals  = Signals()
        self.coach    = AICoach(self.signals)
        self.overlay  = TutorialOverlay()
        self.monitor  = EventMonitor(self.signals, on_activity=self._on_user_activity)
        self.debounce = DebounceTimer(DEBOUNCE_SECONDS, self._trigger_analysis)

        self._connect()
        self._update_overlay_rect()

    def _connect(self):
        # Señales IA → overlay
        self.signals.instruction_ready.connect(self.overlay.show_instruction)
        self.signals.status_changed.connect(self.overlay.show_status)
        self.signals.activity_logged.connect(self.overlay.log_activity)
        self.signals.chat_reply.connect(self.overlay.show_ai_reply)

        # Eventos del overlay → lógica
        self.overlay.chat_submitted.connect(self._on_chat_message)
        self.overlay.chat_focus_changed.connect(self.monitor.set_ignore_keyboard)

    def _update_overlay_rect(self):
        """Le dice al monitor qué área ignorar (el propio overlay)."""
        rect = self.overlay.get_overlay_rect()
        self.monitor.set_overlay_rect(*rect)

    # ── Handlers ─────────────────────────────────────────
    def _on_chat_message(self, text: str):
        if not text:
            self.coach.reset()
            return
        self.coach.goal = text
        self.debounce.cancel()
        self.coach.analyze(
            events_summary=self.monitor.get_summary(),
            user_message=text
        )
        self.monitor.clear()

    def _on_user_activity(self):
        """Llamado cada vez que hay un click o tecla. Inicia debounce."""
        self.debounce.trigger()

    def _trigger_analysis(self):
        """Disparado por el debounce tras inactividad."""
        if not self.coach.goal:
            return   # no analizar si aún no hay objetivo
        summary = self.monitor.get_summary()
        self.monitor.clear()
        self.coach.analyze(events_summary=summary)

    def run(self):
        self.overlay.show()
        self._update_overlay_rect()
        self.monitor.start()
        sys.exit(self.qt_app.exec_())


# ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  AI Tutorial Coach para Ancianos  —  v2")
    print("  Requiere: ANTHROPIC_API_KEY en variables de entorno")
    print("=" * 60)
    TutorialApp().run()
