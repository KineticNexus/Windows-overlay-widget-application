"""
AI Tutorial Coach para Ancianos
================================
Captura la pantalla en tiempo real, se la manda a Claude con visión,
y muestra instrucciones paso a paso en un overlay grande y claro.

Uso:
    1. Configura ANTHROPIC_API_KEY en variables de entorno
    2. Abre el programa que quieres aprender (ej: WhatsApp Web en el navegador)
    3. Ejecuta: python tutorial_coach.py
    4. El asistente te guiará paso a paso

Dependencias:
    pip install anthropic mss Pillow PyQt5
"""

import sys
import base64
import threading
from io import BytesIO

try:
    import mss
    from PIL import Image
    import anthropic
    from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
    from PyQt5.QtGui import QFont, QColor, QPainter, QPen, QBrush
    from PyQt5.QtWidgets import (
        QApplication, QLabel, QWidget, QVBoxLayout,
        QPushButton, QHBoxLayout, QComboBox, QSizePolicy
    )
except ImportError as e:
    print(f"\nFalta una dependencia: {e}")
    print("Instala con:  pip install anthropic mss Pillow PyQt5\n")
    sys.exit(1)


# ─────────────────────────────────────────────
#  Herramientas disponibles para enseñar
# ─────────────────────────────────────────────
TOOLS = {
    "WhatsApp Web": "WhatsApp Web (mensajería por navegador)",
    "Gmail": "Gmail (correo electrónico en el navegador)",
    "YouTube": "YouTube (ver videos en el navegador)",
    "Google Maps": "Google Maps (buscar lugares y rutas)",
    "Zoom": "Zoom (videollamadas)",
}

SYSTEM_PROMPT_TEMPLATE = """Eres un asistente muy amable y paciente que ayuda a personas mayores a aprender a usar {tool}.

Estás viendo una captura de pantalla de su computadora. Tu tarea es dar UNA sola instrucción, muy simple y concreta, sobre qué hacer a continuación.

Reglas estrictas:
- Da SOLO UN paso a la vez
- Usa palabras simples, sin tecnicismos. Nada de "hacer clic" → di "presionar". Nada de "URL" → di "la barra de dirección arriba".
- Describe con precisión DÓNDE está el elemento: color, posición en pantalla, texto que dice
- Si el usuario ya completó el paso anterior, avanza al siguiente paso
- Máximo 2 oraciones cortas por instrucción
- Tono muy amable y alentador. Usa frases como "¡Muy bien!", "¡Excelente!", "Ahora..."
- Si la pantalla no muestra {tool}, indica primero cómo llegar ahí

Responde ÚNICAMENTE con la instrucción. Sin títulos, sin numeración, sin explicaciones extra."""


# ─────────────────────────────────────────────
#  Señales Qt para comunicación entre hilos
# ─────────────────────────────────────────────
class Signals(QObject):
    instruction_ready = pyqtSignal(str)
    status_changed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)


# ─────────────────────────────────────────────
#  Lógica de IA: captura pantalla + llama Claude
# ─────────────────────────────────────────────
class AICoach:
    def __init__(self, signals: Signals):
        self.signals = signals
        self.client = anthropic.Anthropic()
        self.text_history = []   # historial solo texto (sin imágenes) para contexto
        self.tool_name = list(TOOLS.keys())[0]
        self._busy = False
        self._lock = threading.Lock()

    def set_tool(self, tool_name: str):
        self.tool_name = tool_name
        self.text_history = []   # reinicia historial al cambiar herramienta

    def _capture_screen(self) -> str:
        """Captura la pantalla principal y devuelve JPEG en base64."""
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            screenshot = sct.grab(monitor)
            img = Image.frombytes(
                "RGB", screenshot.size, screenshot.bgra, "raw", "BGRX"
            )
            # Reducir tamaño para ahorrar tokens (max 1280px ancho)
            img.thumbnail((1280, 720), Image.LANCZOS)
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=82)
            return base64.b64encode(buf.getvalue()).decode("utf-8")

    def get_instruction(self):
        """Analiza la pantalla y emite la siguiente instrucción. No bloquea."""
        with self._lock:
            if self._busy:
                return
            self._busy = True

        def _run():
            try:
                self.signals.status_changed.emit("Analizando tu pantalla...")

                image_b64 = self._capture_screen()
                system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
                    tool=TOOLS[self.tool_name]
                )

                # Construcción del mensaje: historial texto + imagen actual
                messages = list(self.text_history)
                messages.append({
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
                        {
                            "type": "text",
                            "text": "Esta es mi pantalla ahora mismo. ¿Qué debo hacer?",
                        },
                    ],
                })

                response = self.client.messages.create(
                    model="claude-opus-4-6",
                    max_tokens=220,
                    system=system_prompt,
                    messages=messages,
                )

                instruction = response.content[0].text.strip()

                # Guardar en historial solo texto (las imágenes se descartan)
                self.text_history.append({
                    "role": "user",
                    "content": "El usuario está mirando la pantalla.",
                })
                self.text_history.append({
                    "role": "assistant",
                    "content": instruction,
                })

                # Mantener últimas 10 exchanges (20 mensajes)
                if len(self.text_history) > 20:
                    self.text_history = self.text_history[-20:]

                self.signals.instruction_ready.emit(instruction)
                self.signals.status_changed.emit("Listo  •  se actualiza cada 10 s")

            except anthropic.AuthenticationError:
                self.signals.error_occurred.emit(
                    "Error: ANTHROPIC_API_KEY inválida o no configurada."
                )
            except Exception as exc:
                self.signals.error_occurred.emit(f"Error inesperado: {exc}")
            finally:
                with self._lock:
                    self._busy = False

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()


# ─────────────────────────────────────────────
#  Overlay visual — panel de instrucciones
# ─────────────────────────────────────────────
class TutorialOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool
        )
        # Fondo sólido oscuro (no translúcido para mejor legibilidad)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self._build_ui()
        self._position_bottom_center()

    # ── Construcción de la UI ──────────────────
    def _build_ui(self):
        self.setStyleSheet("""
            QWidget#panel {
                background-color: #1a1a2e;
                border: 2px solid #4ade80;
                border-radius: 14px;
            }
            QLabel#header {
                color: #4ade80;
                background: transparent;
            }
            QLabel#instruction {
                color: #ffffff;
                background: transparent;
            }
            QLabel#status {
                color: #888888;
                background: transparent;
            }
            QPushButton {
                background-color: #4ade80;
                color: #1a1a2e;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #22c55e; }
            QPushButton:disabled { background-color: #374151; color: #6b7280; }
            QComboBox {
                background-color: #374151;
                color: white;
                border: 1px solid #4b5563;
                border-radius: 6px;
                padding: 6px 10px;
            }
            QComboBox QAbstractItemView {
                background-color: #1f2937;
                color: white;
                selection-background-color: #4ade80;
                selection-color: #1a1a2e;
            }
        """)

        # Panel contenedor
        panel = QWidget(self)
        panel.setObjectName("panel")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(panel)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(10)

        # — Fila superior: título + selector de herramienta —
        top_row = QHBoxLayout()

        header = QLabel("🧭  Asistente paso a paso")
        header.setObjectName("header")
        header.setFont(QFont("Arial", 13, QFont.Bold))
        top_row.addWidget(header)

        top_row.addStretch()

        self.tool_selector = QComboBox()
        self.tool_selector.setFont(QFont("Arial", 12))
        for name in TOOLS:
            self.tool_selector.addItem(name)
        top_row.addWidget(self.tool_selector)

        layout.addLayout(top_row)

        # — Instrucción principal (texto grande) —
        self.instruction_label = QLabel("Presiona el botón para comenzar.")
        self.instruction_label.setObjectName("instruction")
        self.instruction_label.setFont(QFont("Arial", 22, QFont.Bold))
        self.instruction_label.setWordWrap(True)
        self.instruction_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.instruction_label.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Minimum
        )
        layout.addWidget(self.instruction_label)

        # — Fila inferior: estado + botones —
        bottom_row = QHBoxLayout()

        self.status_label = QLabel("Listo para empezar")
        self.status_label.setObjectName("status")
        self.status_label.setFont(QFont("Arial", 11))
        bottom_row.addWidget(self.status_label)

        bottom_row.addStretch()

        self.restart_btn = QPushButton("↺  Reiniciar")
        self.restart_btn.setFont(QFont("Arial", 12))
        self.restart_btn.setFixedWidth(130)
        bottom_row.addWidget(self.restart_btn)

        self.analyze_btn = QPushButton("▶  Siguiente paso")
        self.analyze_btn.setFont(QFont("Arial", 13, QFont.Bold))
        self.analyze_btn.setFixedWidth(180)
        bottom_row.addWidget(self.analyze_btn)

        layout.addLayout(bottom_row)

    # ── Posición: parte inferior centrada ─────
    def _position_bottom_center(self):
        screen = QApplication.primaryScreen().geometry()
        w = min(820, screen.width() - 60)
        # Altura mínima — Qt la expandirá si el texto es largo
        self.setFixedWidth(w)
        x = (screen.width() - w) // 2
        y = screen.height() - 260
        self.move(x, y)

    # ── Slots públicos ─────────────────────────
    def show_instruction(self, text: str):
        self.instruction_label.setText(text)
        self.analyze_btn.setEnabled(True)
        self.adjustSize()

    def show_status(self, text: str):
        self.status_label.setText(text)

    def show_error(self, text: str):
        self.instruction_label.setText(f"⚠  {text}")
        self.status_label.setText("Ocurrió un error")
        self.analyze_btn.setEnabled(True)

    def set_busy(self):
        self.analyze_btn.setEnabled(False)
        self.status_label.setText("Analizando pantalla...")


# ─────────────────────────────────────────────
#  Aplicación principal
# ─────────────────────────────────────────────
class TutorialApp:
    def __init__(self):
        self.qt_app = QApplication(sys.argv)
        self.qt_app.setApplicationName("Asistente Tutorial")

        self.signals = Signals()
        self.coach = AICoach(self.signals)
        self.overlay = TutorialOverlay()

        self._connect_signals()
        self._setup_timer()

    def _connect_signals(self):
        # Señales de la IA → overlay
        self.signals.instruction_ready.connect(self.overlay.show_instruction)
        self.signals.status_changed.connect(self.overlay.show_status)
        self.signals.error_occurred.connect(self.overlay.show_error)

        # Botones del overlay
        self.overlay.analyze_btn.clicked.connect(self._on_analyze)
        self.overlay.restart_btn.clicked.connect(self._on_restart)
        self.overlay.tool_selector.currentTextChanged.connect(self._on_tool_changed)

    def _setup_timer(self):
        """Analiza automáticamente cada 10 segundos."""
        self.timer = QTimer()
        self.timer.timeout.connect(self._on_analyze)
        self.timer.start(10_000)

    # ── Handlers ──────────────────────────────
    def _on_analyze(self):
        self.overlay.set_busy()
        self.coach.get_instruction()

    def _on_restart(self):
        self.coach.text_history = []
        self.overlay.show_instruction("Historial borrado. Presiona 'Siguiente paso' para empezar de nuevo.")
        self.overlay.show_status("Reiniciado")

    def _on_tool_changed(self, name: str):
        self.coach.set_tool(name)
        self.overlay.show_instruction(
            f"Ahora te enseñaré a usar {name}. Presiona 'Siguiente paso' cuando estés listo."
        )
        self.overlay.show_status("Herramienta cambiada — historial borrado")

    def run(self):
        self.overlay.show()
        sys.exit(self.qt_app.exec_())


# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("  AI Tutorial Coach para Ancianos")
    print("  Asegúrate de tener ANTHROPIC_API_KEY configurada")
    print("=" * 55)
    app = TutorialApp()
    app.run()
