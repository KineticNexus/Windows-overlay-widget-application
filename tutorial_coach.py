"""
AI Tutorial Coach — Guiado Visual con Flechas
==============================================
Guía a personas mayores paso a paso usando flechas y anotaciones
en pantalla generadas por inteligencia artificial.

Instalación:
    pip install anthropic mss Pillow PyQt5 pynput pyinstaller

Generar ejecutable:
    pyinstaller --onefile --windowed --icon=icon.ico --name "AsistenteTutorial" tutorial_coach.py
"""

import sys
import json
import math
import base64
import threading
from io import BytesIO

# ── Verificar dependencias ────────────────────────────────────────────────────
try:
    import mss
    from PIL import Image
    import anthropic
    from pynput import mouse as pmouse
    from PyQt5.QtCore import (Qt, QTimer, QPoint, QRect, QPointF,
                               pyqtSignal, QObject)
    from PyQt5.QtGui import (QPainter, QColor, QPen, QBrush, QFont,
                              QPolygonF, QPainterPath, QLinearGradient)
    from PyQt5.QtWidgets import (QApplication, QDialog, QLabel, QWidget,
                                  QVBoxLayout, QHBoxLayout, QPushButton,
                                  QLineEdit, QTextEdit, QFrame, QSizePolicy,
                                  QStackedWidget, QGraphicsDropShadowEffect)
except ImportError as e:
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk(); root.withdraw()
    messagebox.showerror("Dependencia faltante",
        f"{e}\n\nInstala con:\npip install anthropic mss Pillow PyQt5 pynput")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
#  Constantes y prompts
# ═══════════════════════════════════════════════════════════════════════════════
CLICK_RADIUS   = 90    # píxeles de tolerancia para auto-avance
ANIM_INTERVAL  = 40    # ms entre frames de animación (~25fps)

PLAN_SYSTEM = """Eres un asistente experto en usabilidad que ayuda a personas mayores a usar la computadora.
Analizas capturas de pantalla y generas planes paso a paso muy claros y simples."""

PLAN_USER = """Analiza esta captura de pantalla (resolución real: {w}x{h} px) y crea un plan
paso a paso para que una persona mayor pueda: {goal}

Responde ÚNICAMENTE con JSON válido, sin texto antes ni después, con este formato exacto:
{{
  "title": "Título corto del plan",
  "steps": [
    {{
      "n": 1,
      "instruction": "Instrucción simple de máximo 12 palabras",
      "target_x": 640,
      "target_y": 360
    }}
  ]
}}

Reglas CRÍTICAS:
- Instrucciones en español, simples, sin tecnicismos. Di "presiona" no "haz clic".
  Di "la barra de arriba donde dice la dirección web" no "URL bar".
- Una sola acción por paso.
- target_x y target_y son coordenadas del CENTRO del elemento en la pantalla REAL ({w}x{h}).
- Si la pantalla no muestra lo necesario, el primer paso indica cómo llegar ahí.
- Máximo 8 pasos."""


# ═══════════════════════════════════════════════════════════════════════════════
#  Señales Qt (comunicación entre hilos y widgets)
# ═══════════════════════════════════════════════════════════════════════════════
class Signals(QObject):
    plan_ready     = pyqtSignal(dict)   # plan JSON de la IA
    step_completed = pyqtSignal()       # click cerca del target → avanzar
    error_occurred = pyqtSignal(str)
    status_changed = pyqtSignal(str)


# ═══════════════════════════════════════════════════════════════════════════════
#  Diálogo inicial: API Key
# ═══════════════════════════════════════════════════════════════════════════════
class APIKeyDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Asistente Tutorial — Configuración")
        self.setFixedSize(480, 260)
        self.setStyleSheet("""
            QDialog   { background:#111827; }
            QLabel    { color:#f9fafb; background:transparent; }
            QLineEdit {
                background:#1f2937; color:#f9fafb;
                border:2px solid #374151; border-radius:8px; padding:10px;
                font-size:14px;
            }
            QLineEdit:focus { border-color:#22c55e; }
            QPushButton {
                background:#22c55e; color:#111827; border:none;
                border-radius:8px; padding:12px; font-size:15px; font-weight:bold;
            }
            QPushButton:hover { background:#16a34a; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(14)

        title = QLabel("🧭  Asistente Tutorial")
        title.setFont(QFont("Arial", 18, QFont.Bold))
        title.setStyleSheet("color:#22c55e; background:transparent;")
        layout.addWidget(title)

        sub = QLabel("Ingresa tu clave de Anthropic para comenzar:")
        sub.setFont(QFont("Arial", 12))
        layout.addWidget(sub)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("sk-ant-api03-...")
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.returnPressed.connect(self.accept)
        layout.addWidget(self.key_input)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color:#f87171; background:transparent;")
        self.error_label.setFont(QFont("Arial", 11))
        layout.addWidget(self.error_label)

        btn = QPushButton("Continuar  ▶")
        btn.clicked.connect(self._on_continue)
        layout.addWidget(btn)

    def _on_continue(self):
        if len(self.key_input.text().strip()) < 20:
            self.error_label.setText("⚠  La clave parece muy corta. Verifica e intenta de nuevo.")
            return
        self.accept()

    def get_key(self) -> str:
        return self.key_input.text().strip()


# ═══════════════════════════════════════════════════════════════════════════════
#  Overlay full-screen transparente con anotaciones animadas
# ═══════════════════════════════════════════════════════════════════════════════
class AnnotationOverlay(QWidget):
    """
    Ventana full-screen, completamente transparente al input.
    Dibuja flechas y burbujas animadas encima de todo.
    """
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint |
            Qt.Tool | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)

        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)

        self.step      = None   # dict con n, instruction, target_x, target_y
        self.total     = 0
        self._phase    = 0.0    # animación (0..2π)
        self._screen_w = screen.width()
        self._screen_h = screen.height()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(ANIM_INTERVAL)

    def set_step(self, step: dict, total: int):
        self.step  = step
        self.total = total
        self.update()

    def clear(self):
        self.step = None
        self.update()

    # ── Animación ─────────────────────────────────────────────────────────────
    def _tick(self):
        if self.step:
            self._phase = (self._phase + 0.08) % (2 * math.pi)
            self.update()

    # ── Dibujo ────────────────────────────────────────────────────────────────
    def paintEvent(self, _):
        if not self.step:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)

        tx = self.step["target_x"]
        ty = self.step["target_y"]
        instruction = self.step["instruction"]
        step_n = self.step["n"]
        pulse  = 0.75 + 0.25 * math.sin(self._phase)       # 0.75 – 1.0
        bounce = int(6  * math.sin(self._phase * 1.3))     # rebote suave

        # ── 1. Anillo pulsante alrededor del target ────────────────────────
        for r, alpha in [(55, 60), (38, 100), (22, 180)]:
            r = int(r * pulse)
            p.setPen(QPen(QColor(74, 222, 128, alpha), 2))
            p.setBrush(QBrush(QColor(74, 222, 128, max(0, alpha - 130))))
            p.drawEllipse(QPoint(tx, ty), r, r)

        # ── 2. Cruz central ────────────────────────────────────────────────
        p.setPen(QPen(QColor(250, 204, 21), 3, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(tx - 10, ty, tx + 10, ty)
        p.drawLine(tx, ty - 10, tx, ty + 10)

        # ── 3. Burbuja de texto ────────────────────────────────────────────
        bw, bh = 320, 110
        bx, by = self._bubble_pos(tx, ty, bw, bh)
        by += bounce

        self._draw_bubble(p, bx, by, bw, bh, step_n, self.total, instruction)

        # ── 4. Flecha burbuja → target ─────────────────────────────────────
        arrow_start_x = bx + bw // 2
        arrow_start_y = by + bh // 2
        self._draw_arrow(p, arrow_start_x, arrow_start_y, tx, ty)

        p.end()

    def _bubble_pos(self, tx: int, ty: int, bw: int, bh: int):
        """Elige posición de la burbuja para no salirse de pantalla ni tapar el target."""
        margin = 80
        candidates = [
            (tx - bw - margin, ty - bh // 2),           # izquierda
            (tx + margin,       ty - bh // 2),           # derecha
            (tx - bw // 2,      ty - bh - margin),       # arriba
            (tx - bw // 2,      ty + margin),            # abajo
        ]
        for bx, by in candidates:
            if (0 <= bx and bx + bw <= self._screen_w and
                    0 <= by and by + bh <= self._screen_h):
                return bx, by
        # Fallback: esquina superior izquierda
        return 20, 20

    def _draw_bubble(self, p: QPainter, bx, by, bw, bh,
                     step_n: int, total: int, text: str):
        rect = QRect(bx, by, bw, bh)

        # Fondo con gradiente oscuro semitransparente
        grad = QLinearGradient(bx, by, bx, by + bh)
        grad.setColorAt(0, QColor(17, 24, 39, 230))
        grad.setColorAt(1, QColor(31, 41, 55, 230))
        p.setBrush(QBrush(grad))
        p.setPen(QPen(QColor(74, 222, 128), 2))
        path = QPainterPath()
        path.addRoundedRect(bx, by, bw, bh, 14, 14)
        p.drawPath(path)

        # Etiqueta de paso
        p.setFont(QFont("Arial", 10, QFont.Bold))
        p.setPen(QColor(74, 222, 128))
        p.drawText(rect.adjusted(14, 10, -14, 0),
                   Qt.AlignTop | Qt.AlignLeft,
                   f"PASO {step_n} DE {total}")

        # Texto de instrucción
        p.setFont(QFont("Arial", 14, QFont.Bold))
        p.setPen(QColor(249, 250, 251))
        p.drawText(rect.adjusted(14, 28, -14, -10),
                   Qt.AlignVCenter | Qt.AlignLeft | Qt.TextWordWrap,
                   text)

    def _draw_arrow(self, p: QPainter,
                    x1: int, y1: int, x2: int, y2: int):
        """Flecha amarilla desde (x1,y1) hacia (x2,y2), con punta en destino."""
        dx, dy  = x2 - x1, y2 - y1
        length  = math.hypot(dx, dy)
        if length < 30:
            return

        # Acortar para que no toque el anillo
        short = 30
        ex = x2 - int(dx / length * short)
        ey = y2 - int(dy / length * short)

        # Línea con contorno
        for color, width in [(QColor(0, 0, 0, 160), 6), (QColor(250, 204, 21), 3)]:
            p.setPen(QPen(color, width, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(x1, y1, ex, ey)

        # Cabeza de flecha
        angle = math.atan2(ey - y1, ex - x1)
        head  = 16
        pts   = QPolygonF([
            QPointF(ex, ey),
            QPointF(ex - head * math.cos(angle - 0.45),
                    ey - head * math.sin(angle - 0.45)),
            QPointF(ex - head * math.cos(angle + 0.45),
                    ey - head * math.sin(angle + 0.45)),
        ])
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(250, 204, 21)))
        p.drawPolygon(pts)


# ═══════════════════════════════════════════════════════════════════════════════
#  Panel de control flotante (chat + guía)
# ═══════════════════════════════════════════════════════════════════════════════
class ControlPanel(QWidget):
    goal_submitted = pyqtSignal(str)
    prev_clicked   = pyqtSignal()
    next_clicked   = pyqtSignal()
    reset_clicked  = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setFixedWidth(420)
        self.setStyleSheet(self._stylesheet())
        self._drag_pos = None

        self._build_ui()
        self._place()

    # ── Estilos ───────────────────────────────────────────────────────────────
    def _stylesheet(self):
        return """
        QWidget#panel {
            background:#111827;
            border:2px solid #22c55e;
            border-radius:16px;
        }
        QLabel { background:transparent; }
        QLabel#title_lbl  { color:#22c55e; }
        QLabel#step_lbl   { color:#86efac; }
        QLabel#instr_lbl  { color:#f9fafb; }
        QLabel#status_lbl { color:#6b7280; }
        QTextEdit {
            background:#1f2937; color:#d1d5db;
            border:1px solid #374151; border-radius:8px; padding:6px;
        }
        QLineEdit {
            background:#1f2937; color:#f9fafb;
            border:2px solid #374151; border-radius:8px; padding:10px;
            font-size:14px;
        }
        QLineEdit:focus { border-color:#22c55e; }
        QPushButton {
            background:#22c55e; color:#111827; border:none;
            border-radius:8px; padding:10px 16px; font-weight:bold;
        }
        QPushButton:hover    { background:#16a34a; }
        QPushButton:disabled { background:#374151; color:#6b7280; }
        QPushButton#btn_sec {
            background:#374151; color:#d1d5db;
        }
        QPushButton#btn_sec:hover { background:#4b5563; }
        """

    # ── Construcción de UI ────────────────────────────────────────────────────
    def _build_ui(self):
        panel = QWidget(self)
        panel.setObjectName("panel")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(panel)

        self._main = QVBoxLayout(panel)
        self._main.setContentsMargins(20, 16, 20, 16)
        self._main.setSpacing(10)

        # Cabecera (draggable, siempre visible)
        hdr = QHBoxLayout()
        title = QLabel("🧭  Asistente Tutorial")
        title.setObjectName("title_lbl")
        title.setFont(QFont("Arial", 13, QFont.Bold))
        hdr.addWidget(title)
        hdr.addStretch()
        self.status_lbl = QLabel("Listo")
        self.status_lbl.setObjectName("status_lbl")
        self.status_lbl.setFont(QFont("Arial", 10))
        hdr.addWidget(self.status_lbl)
        self._main.addLayout(hdr)

        line = QFrame(); line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background:#374151;"); line.setFixedHeight(1)
        self._main.addWidget(line)

        # Stacked: modo CHAT y modo GUÍA
        self._stack = QStackedWidget()
        self._main.addWidget(self._stack)
        self._stack.addWidget(self._build_chat_page())   # índice 0
        self._stack.addWidget(self._build_guide_page())  # índice 1

    def _build_chat_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        prompt = QLabel("¿Qué quieres aprender o hacer?")
        prompt.setFont(QFont("Arial", 13, QFont.Bold))
        prompt.setStyleSheet("color:#d1d5db; background:transparent;")
        lay.addWidget(prompt)

        self.chat_log = QTextEdit()
        self.chat_log.setReadOnly(True)
        self.chat_log.setFont(QFont("Arial", 12))
        self.chat_log.setFixedHeight(100)
        lay.addWidget(self.chat_log)

        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText(
            "Ej: quiero mandar un mensaje a mi hijo por WhatsApp…")
        self.chat_input.setFont(QFont("Arial", 13))
        self.chat_input.returnPressed.connect(self._on_send)
        lay.addWidget(self.chat_input)

        self.send_btn = QPushButton("Analizar pantalla y comenzar  ▶")
        self.send_btn.setFont(QFont("Arial", 13, QFont.Bold))
        self.send_btn.clicked.connect(self._on_send)
        lay.addWidget(self.send_btn)
        return page

    def _build_guide_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self.step_lbl = QLabel("Paso 1 de 1")
        self.step_lbl.setObjectName("step_lbl")
        self.step_lbl.setFont(QFont("Arial", 11, QFont.Bold))
        lay.addWidget(self.step_lbl)

        self.instr_lbl = QLabel("")
        self.instr_lbl.setObjectName("instr_lbl")
        self.instr_lbl.setFont(QFont("Arial", 18, QFont.Bold))
        self.instr_lbl.setWordWrap(True)
        self.instr_lbl.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.instr_lbl.setMinimumHeight(80)
        self.instr_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        lay.addWidget(self.instr_lbl)

        hint = QLabel("💡 El asistente avanza solo cuando presionas el elemento indicado.")
        hint.setFont(QFont("Arial", 10))
        hint.setStyleSheet("color:#6b7280; background:transparent;")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        btn_row = QHBoxLayout()
        self.reset_btn = QPushButton("↺ Nueva consulta")
        self.reset_btn.setObjectName("btn_sec")
        self.reset_btn.setFont(QFont("Arial", 11))
        self.reset_btn.clicked.connect(self.reset_clicked.emit)
        btn_row.addWidget(self.reset_btn)

        self.prev_btn = QPushButton("◀")
        self.prev_btn.setObjectName("btn_sec")
        self.prev_btn.setFont(QFont("Arial", 12, QFont.Bold))
        self.prev_btn.setFixedWidth(50)
        self.prev_btn.clicked.connect(self.prev_clicked.emit)
        btn_row.addWidget(self.prev_btn)

        self.next_btn = QPushButton("Siguiente  ▶")
        self.next_btn.setFont(QFont("Arial", 12, QFont.Bold))
        self.next_btn.setFixedWidth(140)
        self.next_btn.clicked.connect(self.next_clicked.emit)
        btn_row.addWidget(self.next_btn)
        lay.addLayout(btn_row)
        return page

    # ── Posición y dragging ───────────────────────────────────────────────────
    def _place(self):
        screen = QApplication.primaryScreen().geometry()
        self.adjustSize()
        self.move(screen.width() - self.width() - 20, 20)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() == Qt.LeftButton:
            self.move(e.globalPos() - self._drag_pos)

    def mouseReleaseEvent(self, _):
        self._drag_pos = None

    # ── API pública ───────────────────────────────────────────────────────────
    def show_chat_mode(self):
        self._stack.setCurrentIndex(0)
        self.chat_input.setFocus()
        self.adjustSize()

    def show_guide_mode(self, step: dict, total: int):
        self.step_lbl.setText(f"Paso {step['n']} de {total}")
        self.instr_lbl.setText(step["instruction"])
        self._stack.setCurrentIndex(1)
        self.prev_btn.setEnabled(step["n"] > 1)
        self.next_btn.setEnabled(step["n"] < total)
        self.adjustSize()

    def show_finished(self):
        self.instr_lbl.setText("¡Lo lograste! 🎉\nCompletaste todos los pasos.")
        self.next_btn.setEnabled(False)
        self.adjustSize()

    def set_status(self, text: str):
        self.status_lbl.setText(text)

    def append_chat(self, who: str, text: str, color: str):
        self.chat_log.append(
            f'<span style="color:{color};font-weight:bold">{who}:</span> '
            f'<span style="color:#e5e7eb">{text}</span>')

    def set_busy(self, busy: bool):
        self.send_btn.setEnabled(not busy)
        self.send_btn.setText(
            "Analizando pantalla…" if busy else "Analizar pantalla y comenzar  ▶")

    # ── Handlers ─────────────────────────────────────────────────────────────
    def _on_send(self):
        text = self.chat_input.text().strip()
        if not text:
            return
        self.append_chat("Tú", text, "#86efac")
        self.chat_input.clear()
        self.set_busy(True)
        self.goal_submitted.emit(text)


# ═══════════════════════════════════════════════════════════════════════════════
#  Coach de IA
# ═══════════════════════════════════════════════════════════════════════════════
class AICoach:
    def __init__(self, api_key: str, signals: Signals):
        self.client  = anthropic.Anthropic(api_key=api_key)
        self.signals = signals
        self._busy   = False
        self._lock   = threading.Lock()

    def _capture(self) -> tuple[str, int, int]:
        """Captura pantalla completa, devuelve (base64_jpeg, width, height)."""
        with mss.mss() as sct:
            mon = sct.monitors[1]
            w, h = mon["width"], mon["height"]
            shot = sct.grab(mon)
            img  = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
            # Reducir a máx 1600px para ahorrar tokens, pero mantener aspecto
            img.thumbnail((1600, 1600), Image.LANCZOS)
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=80)
            return base64.b64encode(buf.getvalue()).decode(), w, h

    def generate_plan(self, goal: str):
        """Genera el plan paso a paso. No bloquea."""
        with self._lock:
            if self._busy:
                return
            self._busy = True

        def _run():
            try:
                self.signals.status_changed.emit("Analizando pantalla…")
                img_b64, w, h = self._capture()

                response = self.client.messages.create(
                    model="claude-opus-4-6",
                    max_tokens=800,
                    system=PLAN_SYSTEM,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "image",
                             "source": {"type": "base64",
                                        "media_type": "image/jpeg",
                                        "data": img_b64}},
                            {"type": "text",
                             "text": PLAN_USER.format(goal=goal, w=w, h=h)},
                        ],
                    }],
                )
                raw = response.content[0].text.strip()

                # Limpiar posible texto extra antes/después del JSON
                start = raw.find("{")
                end   = raw.rfind("}") + 1
                plan  = json.loads(raw[start:end])

                if "steps" not in plan or not plan["steps"]:
                    raise ValueError("El plan no contiene pasos.")

                self.signals.plan_ready.emit(plan)
                self.signals.status_changed.emit("Plan listo")

            except anthropic.AuthenticationError:
                self.signals.error_occurred.emit(
                    "API key inválida. Reinicia el programa e ingresa una clave correcta.")
            except json.JSONDecodeError as e:
                self.signals.error_occurred.emit(f"Error procesando respuesta de IA: {e}")
            except Exception as e:
                self.signals.error_occurred.emit(f"Error inesperado: {e}")
            finally:
                with self._lock:
                    self._busy = False

        threading.Thread(target=_run, daemon=True).start()


# ═══════════════════════════════════════════════════════════════════════════════
#  Monitor de clicks para auto-avance
# ═══════════════════════════════════════════════════════════════════════════════
class ClickMonitor:
    """Escucha clicks del mouse y avisa si el usuario clickeó cerca del target."""

    def __init__(self, on_hit):
        self._on_hit  = on_hit        # callback al acertar
        self._target  = None          # (x, y) o None
        self._panel_rect = None       # (x, y, w, h) del panel
        self._listener = None

    def start(self):
        self._listener = pmouse.Listener(on_click=self._check)
        self._listener.daemon = True
        self._listener.start()

    def stop(self):
        if self._listener:
            self._listener.stop()

    def set_target(self, x: int, y: int):
        self._target = (x, y)

    def clear_target(self):
        self._target = None

    def set_panel_rect(self, x, y, w, h):
        self._panel_rect = (x, y, w, h)

    def _in_panel(self, x, y) -> bool:
        if not self._panel_rect:
            return False
        px, py, pw, ph = self._panel_rect
        return px <= x <= px + pw and py <= y <= py + ph

    def _check(self, x, y, button, pressed):
        if not pressed or not self._target or self._in_panel(x, y):
            return
        tx, ty = self._target
        if math.hypot(x - tx, y - ty) <= CLICK_RADIUS:
            self._on_hit()


# ═══════════════════════════════════════════════════════════════════════════════
#  Orquestador principal
# ═══════════════════════════════════════════════════════════════════════════════
class TutorialApp:
    def __init__(self, api_key: str):
        self.signals  = Signals()
        self.coach    = AICoach(api_key, self.signals)
        self.overlay  = AnnotationOverlay()
        self.panel    = ControlPanel()
        self.monitor  = ClickMonitor(on_hit=self._auto_advance)

        self._steps:  list = []
        self._current: int = 0   # índice 0-based

        self._connect()
        self._update_panel_rect()

    def _connect(self):
        self.signals.plan_ready.connect(self._on_plan)
        self.signals.error_occurred.connect(self._on_error)
        self.signals.status_changed.connect(self.panel.set_status)

        self.panel.goal_submitted.connect(self._on_goal)
        self.panel.prev_clicked.connect(self._go_prev)
        self.panel.next_clicked.connect(self._go_next)
        self.panel.reset_clicked.connect(self._reset)

    def _update_panel_rect(self):
        pos  = self.panel.pos()
        size = self.panel.size()
        self.monitor.set_panel_rect(pos.x(), pos.y(), size.width(), size.height())

    # ── Handlers de señales ───────────────────────────────────────────────────
    def _on_goal(self, text: str):
        self._steps   = []
        self._current = 0
        self.overlay.clear()
        self.coach.generate_plan(text)

    def _on_plan(self, plan: dict):
        self._steps   = plan.get("steps", [])
        self._current = 0
        self.panel.set_busy(False)
        if self._steps:
            self.panel.append_chat(
                "Asistente",
                f"Plan listo: «{plan.get('title', '')}» — {len(self._steps)} pasos.",
                "#60a5fa")
            self._show_step(0)

    def _on_error(self, msg: str):
        self.panel.set_busy(False)
        self.panel.append_chat("⚠ Error", msg, "#f87171")
        self.panel.set_status("Error")

    # ── Navegación de pasos ───────────────────────────────────────────────────
    def _show_step(self, idx: int):
        step = self._steps[idx]
        total = len(self._steps)

        self.overlay.set_step(step, total)
        self.panel.show_guide_mode(step, total)
        self.monitor.set_target(step["target_x"], step["target_y"])
        self._update_panel_rect()
        self.panel.set_status(f"Paso {step['n']} de {total}  •  activo")

    def _auto_advance(self):
        """Llamado desde pynput (hilo de fondo) → usamos QTimer para ir al hilo Qt."""
        QTimer.singleShot(0, self._go_next)

    def _go_next(self):
        if self._current < len(self._steps) - 1:
            self._current += 1
            self._show_step(self._current)
        else:
            self.overlay.clear()
            self.monitor.clear_target()
            self.panel.show_finished()
            self.panel.set_status("¡Completado!")

    def _go_prev(self):
        if self._current > 0:
            self._current -= 1
            self._show_step(self._current)

    def _reset(self):
        self._steps   = []
        self._current = 0
        self.overlay.clear()
        self.monitor.clear_target()
        self.panel.show_chat_mode()
        self.panel.set_status("Listo")

    def run(self):
        self.overlay.showFullScreen()
        self.panel.show()
        self.monitor.start()


# ═══════════════════════════════════════════════════════════════════════════════
#  Punto de entrada
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Asistente Tutorial")

    # 1. Pedir API key
    dialog = APIKeyDialog()
    if dialog.exec_() != QDialog.Accepted:
        sys.exit(0)
    api_key = dialog.get_key()

    # 2. Lanzar la aplicación principal
    tutorial = TutorialApp(api_key)
    tutorial.run()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
