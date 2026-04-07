"""Panel de control flotante — paleta tropical Tortuga."""
from PyQt5.QtCore    import Qt, pyqtSignal
from PyQt5.QtGui     import QFont, QTextCursor, QColor, QLinearGradient, QPainter
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QFrame, QStackedWidget, QSizePolicy,
    QApplication, QCheckBox, QSlider, QGraphicsDropShadowEffect,
)
from tutorial_coach.config import load_profile, save_profile

FONT = "Segoe UI"

# Paleta tropical
_DEEP  = "#1A535C"   # ocean deep
_TEAL  = "#4ECDC4"   # turquoise
_CORAL = "#FF6B6B"   # warm coral
_SAND  = "#FFE66D"   # sandy yellow
_FOAM  = "#F7FFF7"   # sea foam (fondo claro)
_DARK  = "#2D3748"   # texto oscuro
_MID   = "#4A5568"   # texto secundario
_GREY  = "#9AA0A6"   # texto hint

STYLE = """
/* ── Panel base ─────────────────────────────────────────────── */
QWidget#panel {
    background: rgba(247, 255, 247, 215);
    border: 1.5px solid rgba(78, 205, 196, 140);
    border-radius: 2px;
}
QWidget         { background: transparent; }
QLabel          { background: transparent; color: #2D3748; }
QLabel#title    { color: #1A535C; }
QLabel#step     { color: #1A535C; }
QLabel#instr    { color: #1A535C; }
QLabel#status   { color: #9AA0A6; }
QLabel#hint     { color: #9AA0A6; }

/* ── Texto ────────────────────────────────────────────────────── */
QTextEdit {
    background: rgba(255, 255, 255, 150);
    color: #2D3748;
    border: 1px solid rgba(78, 205, 196, 90);
    border-radius: 2px;
    padding: 8px;
    font-family: 'Segoe UI';
    font-size: 12px;
}
QLineEdit {
    background: rgba(255, 255, 255, 180);
    color: #1A535C;
    border: 1.5px solid rgba(78, 205, 196, 120);
    border-radius: 2px;
    padding: 10px 14px;
    font-family: 'Segoe UI';
    font-size: 13px;
}
QLineEdit:focus {
    border: 2px solid #4ECDC4;
    background: rgba(255, 255, 255, 220);
}

/* ── Botones primarios ───────────────────────────────────────── */
QPushButton#primary {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #26A69A, stop:1 #4ECDC4);
    color: #F7FFF7;
    border: none;
    border-radius: 2px;
    padding: 10px 20px;
    font-family: 'Segoe UI';
    font-size: 13px;
    font-weight: bold;
}
QPushButton#primary:hover    {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #1A535C, stop:1 #26A69A);
}
QPushButton#primary:disabled {
    background: rgba(78, 205, 196, 50);
    color: rgba(26, 83, 92, 100);
}

/* ── Botones secundarios ─────────────────────────────────────── */
QPushButton#sec {
    background: rgba(255, 255, 255, 120);
    color: #1A535C;
    border: 1.5px solid rgba(78, 205, 196, 110);
    border-radius: 2px;
    padding: 8px 16px;
    font-family: 'Segoe UI';
    font-size: 12px;
}
QPushButton#sec:hover { background: rgba(78, 205, 196, 35); }

/* ── Cierre ──────────────────────────────────────────────────── */
QPushButton#close_btn {
    background: transparent;
    color: #9AA0A6;
    border: none;
    border-radius: 2px;
    font-size: 14px;
}
QPushButton#close_btn:hover {
    background: rgba(255, 107, 107, 20);
    color: #FF6B6B;
}

/* ── Micrófono ───────────────────────────────────────────────── */
QPushButton#mic {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #4ECDC4, stop:1 #26A69A);
    color: white;
    border: none;
    border-radius: 2px;
}
QPushButton#mic:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #26A69A, stop:1 #1A535C);
}
QPushButton#mic_rec {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #FF6B6B, stop:1 #E53E3E);
    color: white;
    border: none;
    border-radius: 2px;
}

/* ── Tabs ────────────────────────────────────────────────────── */
QPushButton#tab_btn {
    background: transparent;
    color: #9AA0A6;
    border: none;
    border-radius: 0;
    padding: 8px 10px;
    border-bottom: 2px solid transparent;
    font-family: 'Segoe UI';
    font-size: 11px;
}
QPushButton#tab_btn:hover { color: #4ECDC4; }

/* ── Separadores / otros ─────────────────────────────────────── */
QFrame#line { background: rgba(78, 205, 196, 80); }
QCheckBox   { color: #2D3748; background: transparent;
              font-family: 'Segoe UI'; font-size: 12px; }
QSlider::groove:horizontal {
    background: rgba(78, 205, 196, 60); height: 4px; border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #4ECDC4; width: 16px; height: 16px;
    margin: -6px 0; border-radius: 8px;
}
"""


class ControlPanel(QWidget):
    goal_submitted = pyqtSignal(str)
    prev_clicked   = pyqtSignal()
    next_clicked   = pyqtSignal()
    reset_clicked  = pyqtSignal()
    mic_clicked    = pyqtSignal()
    help_clicked   = pyqtSignal()
    close_clicked  = pyqtSignal()
    profile_saved  = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(380)
        self.setStyleSheet(STYLE)
        self._drag_pos = None
        self._profile  = load_profile()
        self._tab_btns = []
        self._build_ui()
        self._place()

    # ── Build UI ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        panel = QWidget(self)
        panel.setObjectName("panel")

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(26, 83, 92, 55))
        panel.setGraphicsEffect(shadow)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.addWidget(panel)

        m = QVBoxLayout(panel)
        m.setContentsMargins(0, 0, 0, 0)
        m.setSpacing(0)

        # ── Header con gradiente ───────────────────────────────────────────
        hdr_widget = _GradientHeader()
        hdr_widget.setFixedHeight(50)
        m.addWidget(hdr_widget)

        hdr_inner = QHBoxLayout(hdr_widget)
        hdr_inner.setContentsMargins(16, 0, 12, 0)
        hdr_inner.setSpacing(8)

        logo = QLabel("🐢")
        logo.setFont(QFont(FONT, 18))
        hdr_inner.addWidget(logo)

        title = QLabel("Tortuga")
        title.setFont(QFont(FONT, 15, QFont.Bold))
        title.setStyleSheet("color: #F7FFF7; background: transparent;")
        hdr_inner.addWidget(title)
        hdr_inner.addStretch()

        self.status_lbl = QLabel("Listo")
        self.status_lbl.setFont(QFont(FONT, 9))
        self.status_lbl.setStyleSheet("color: rgba(247,255,247,150); background: transparent;")
        hdr_inner.addWidget(self.status_lbl)

        help_btn = QPushButton("?")
        help_btn.setObjectName("sec")
        help_btn.setFixedSize(26, 26)
        help_btn.setFont(QFont(FONT, 10, QFont.Bold))
        help_btn.setToolTip("¿Dónde estoy? (F1)")
        help_btn.setStyleSheet("""
            QPushButton { background: rgba(247,255,247,25); color: #F7FFF7;
                border: 1px solid rgba(247,255,247,50); border-radius: 2px; }
            QPushButton:hover { background: rgba(78,205,196,60); }
        """)
        help_btn.clicked.connect(self.help_clicked.emit)
        hdr_inner.addWidget(help_btn)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("close_btn")
        close_btn.setFixedSize(26, 26)
        close_btn.setFont(QFont(FONT, 13))
        close_btn.setToolTip("Cerrar Tortuga")
        close_btn.setStyleSheet("""
            QPushButton { background: transparent; color: rgba(247,255,247,140);
                border: none; border-radius: 2px; }
            QPushButton:hover { background: rgba(255,107,107,50); color: #FF6B6B; }
        """)
        close_btn.clicked.connect(self.close_clicked.emit)
        hdr_inner.addWidget(close_btn)

        # ── Tabs ──────────────────────────────────────────────────────────
        tab_widget = QWidget()
        tab_widget.setStyleSheet("background: rgba(26,83,92,15);")
        tab_lay = QHBoxLayout(tab_widget)
        tab_lay.setContentsMargins(4, 0, 4, 0)
        tab_lay.setSpacing(0)

        for label, idx in [("Chat", 0), ("Guía", 1), ("Historial", 2), ("Config", 3)]:
            btn = QPushButton(label)
            btn.setObjectName("tab_btn")
            btn.setFont(QFont(FONT, 11))
            btn.clicked.connect(lambda _, x=idx: self._select_tab(x))
            tab_lay.addWidget(btn)
            self._tab_btns.append(btn)

        m.addWidget(tab_widget)

        sep = QFrame(); sep.setObjectName("line")
        sep.setFrameShape(QFrame.HLine); sep.setFixedHeight(1)
        m.addWidget(sep)

        # ── Stack ─────────────────────────────────────────────────────────
        self._stack = QStackedWidget()
        self._stack.setContentsMargins(0, 0, 0, 0)
        m.addWidget(self._stack)
        self._stack.addWidget(self._page_chat())
        self._stack.addWidget(self._page_guide())
        self._stack.addWidget(self._page_history())
        self._stack.addWidget(self._page_config())

        self._select_tab(0)

    def _select_tab(self, idx):
        self._stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._tab_btns):
            if i == idx:
                btn.setStyleSheet(
                    "border-bottom: 2.5px solid #4ECDC4; color: #1A535C; "
                    "font-weight: bold;")
            else:
                btn.setStyleSheet(
                    "border-bottom: 2px solid transparent; color: #9AA0A6;")
        self.adjustSize()

    # ── Chat ──────────────────────────────────────────────────────────────────
    def _page_chat(self):
        p = QWidget()
        l = QVBoxLayout(p)
        l.setContentsMargins(16, 12, 16, 16)
        l.setSpacing(10)

        lbl = QLabel("¿Qué querés hacer?")
        lbl.setFont(QFont(FONT, 13, QFont.DemiBold))
        lbl.setStyleSheet("color: #1A535C;")
        l.addWidget(lbl)

        self.chat_log = QTextEdit()
        self.chat_log.setReadOnly(True)
        self.chat_log.setFont(QFont(FONT, 11))
        self.chat_log.setFixedHeight(86)
        l.addWidget(self.chat_log)

        row = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Escribí o hablá tu consulta...")
        self.chat_input.setFont(QFont(FONT, 12))
        self.chat_input.returnPressed.connect(self._on_send)
        row.addWidget(self.chat_input)

        self.mic_btn = QPushButton("\uE720")
        self.mic_btn.setObjectName("mic")
        self.mic_btn.setFixedSize(40, 40)
        self.mic_btn.setFont(QFont("Segoe MDL2 Assets", 15))
        self.mic_btn.setToolTip("Hablar")
        self.mic_btn.clicked.connect(self.mic_clicked.emit)
        row.addWidget(self.mic_btn)
        l.addLayout(row)

        self.send_btn = QPushButton("Comenzar  →")
        self.send_btn.setObjectName("primary")
        self.send_btn.setFont(QFont(FONT, 12, QFont.DemiBold))
        self.send_btn.clicked.connect(self._on_send)
        l.addWidget(self.send_btn)
        return p

    # ── Guía ──────────────────────────────────────────────────────────────────
    def _page_guide(self):
        p = QWidget()
        l = QVBoxLayout(p)
        l.setContentsMargins(16, 12, 16, 16)
        l.setSpacing(6)

        self.step_lbl = QLabel("Paso 1 de 1")
        self.step_lbl.setObjectName("step")
        self.step_lbl.setFont(QFont(FONT, 10, QFont.Bold))
        self.step_lbl.setStyleSheet("color: #4ECDC4; letter-spacing: 1px;")
        l.addWidget(self.step_lbl)

        self.instr_lbl = QLabel("")
        self.instr_lbl.setObjectName("instr")
        self.instr_lbl.setFont(QFont(FONT, 14, QFont.DemiBold))
        self.instr_lbl.setStyleSheet("color: #1A535C;")
        self.instr_lbl.setWordWrap(True)
        self.instr_lbl.setMinimumHeight(56)
        self.instr_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        l.addWidget(self.instr_lbl)

        self.feedback_lbl = QLabel("")
        self.feedback_lbl.setFont(QFont(FONT, 11))
        self.feedback_lbl.setStyleSheet("color: #26A69A;")
        self.feedback_lbl.setWordWrap(True)
        l.addWidget(self.feedback_lbl)

        hint = QLabel("Presioná el elemento indicado para avanzar")
        hint.setObjectName("hint")
        hint.setFont(QFont(FONT, 9))
        hint.setWordWrap(True)
        l.addWidget(hint)

        row = QHBoxLayout()
        self.reset_btn = QPushButton("Nueva")
        self.reset_btn.setObjectName("sec")
        self.reset_btn.setFont(QFont(FONT, 10))
        self.reset_btn.clicked.connect(self.reset_clicked.emit)
        row.addWidget(self.reset_btn)

        self.prev_btn = QPushButton("◀")
        self.prev_btn.setObjectName("sec")
        self.prev_btn.setFixedWidth(38)
        self.prev_btn.clicked.connect(self.prev_clicked.emit)
        row.addWidget(self.prev_btn)

        self.next_btn = QPushButton("Siguiente  →")
        self.next_btn.setObjectName("primary")
        self.next_btn.setFont(QFont(FONT, 11, QFont.DemiBold))
        self.next_btn.setFixedWidth(130)
        self.next_btn.clicked.connect(self.next_clicked.emit)
        row.addWidget(self.next_btn)
        l.addLayout(row)
        return p

    # ── Historial ─────────────────────────────────────────────────────────────
    def _page_history(self):
        p = QWidget()
        l = QVBoxLayout(p)
        l.setContentsMargins(16, 12, 16, 16)
        l.setSpacing(6)
        lbl = QLabel("Sesiones anteriores")
        lbl.setFont(QFont(FONT, 12, QFont.DemiBold))
        lbl.setStyleSheet("color: #1A535C;")
        l.addWidget(lbl)
        self.history_log = QTextEdit()
        self.history_log.setReadOnly(True)
        self.history_log.setFont(QFont(FONT, 11))
        self.history_log.setMinimumHeight(130)
        l.addWidget(self.history_log)
        return p

    # ── Config ────────────────────────────────────────────────────────────────
    def _page_config(self):
        p = QWidget()
        l = QVBoxLayout(p)
        l.setContentsMargins(16, 12, 16, 16)
        l.setSpacing(12)
        lbl = QLabel("Configuración")
        lbl.setFont(QFont(FONT, 12, QFont.DemiBold))
        lbl.setStyleSheet("color: #1A535C;")
        l.addWidget(lbl)

        self.voice_chk = QCheckBox("Leer instrucciones en voz alta")
        self.voice_chk.setFont(QFont(FONT, 11))
        self.voice_chk.setChecked(self._profile.get("voice_enabled", True))
        l.addWidget(self.voice_chk)

        self.verify_chk = QCheckBox("Verificar cada paso con IA")
        self.verify_chk.setFont(QFont(FONT, 11))
        self.verify_chk.setChecked(self._profile.get("auto_verify", True))
        l.addWidget(self.verify_chk)

        row = QHBoxLayout()
        sz_lbl = QLabel("Texto:")
        sz_lbl.setFont(QFont(FONT, 11))
        row.addWidget(sz_lbl)
        self.font_slider = QSlider(Qt.Horizontal)
        self.font_slider.setRange(12, 24)
        self.font_slider.setValue(self._profile.get("font_size", 14))
        self.font_slider.valueChanged.connect(
            lambda v: self.font_val.setText(str(v)))
        row.addWidget(self.font_slider)
        self.font_val = QLabel(str(self.font_slider.value()))
        self.font_val.setFixedWidth(24)
        row.addWidget(self.font_val)
        l.addLayout(row)

        save_btn = QPushButton("Guardar")
        save_btn.setObjectName("primary")
        save_btn.setFont(QFont(FONT, 11))
        save_btn.clicked.connect(self._save_config)
        l.addWidget(save_btn)
        l.addStretch()
        return p

    def _save_config(self):
        self._profile["voice_enabled"] = self.voice_chk.isChecked()
        self._profile["auto_verify"]   = self.verify_chk.isChecked()
        self._profile["font_size"]     = self.font_slider.value()
        save_profile(self._profile)
        self.profile_saved.emit(self._profile)
        self.set_status("Guardado ✓")

    # ── Drag ──────────────────────────────────────────────────────────────────
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
    def get_profile(self):
        return dict(self._profile)

    def show_chat_mode(self):
        self._select_tab(0)
        self.chat_input.setFocus()

    def show_guide_mode(self, step: dict, total: int):
        self.step_lbl.setText(f"Paso {step['n']} de {total}")
        self.instr_lbl.setText(step["instruction"])
        self.feedback_lbl.setText("")
        self._select_tab(1)
        self.prev_btn.setEnabled(step["n"] > 1)
        self.next_btn.setEnabled(step["n"] < total)

    def show_feedback(self, text: str):
        self.feedback_lbl.setText(text)

    def show_finished(self):
        self.instr_lbl.setText("¡Completaste todos los pasos! 🎉")
        self.feedback_lbl.setText("")
        self.next_btn.setEnabled(False)
        self.adjustSize()

    def set_status(self, text: str):
        self.status_lbl.setText(text)

    def append_chat(self, who: str, text: str, color: str):
        self.chat_log.append(
            f'<span style="color:{color};font-weight:700">{who}:</span> '
            f'<span style="color:#2D3748">{text}</span>')
        self.chat_log.moveCursor(QTextCursor.End)

    def set_busy(self, busy: bool):
        self.send_btn.setEnabled(not busy)
        self.send_btn.setText("Analizando..." if busy else "Comenzar  →")

    def set_mic_state(self, state: str):
        if state == "recording":
            self.mic_btn.setObjectName("mic_rec")
            self.mic_btn.setText("\uE73E")
            self.mic_btn.setFont(QFont("Segoe MDL2 Assets", 13))
        else:
            self.mic_btn.setObjectName("mic")
            self.mic_btn.setText("\uE720")
            self.mic_btn.setFont(QFont("Segoe MDL2 Assets", 15))
        self.mic_btn.style().unpolish(self.mic_btn)
        self.mic_btn.style().polish(self.mic_btn)

    def set_history(self, sessions: list):
        self.history_log.clear()
        for s in sessions:
            icon = "✓" if s.get("completed") else "○"
            self.history_log.append(
                f'{icon}  <b>{s["goal"]}</b>  —  {s.get("created_at", "")}')

    def _on_send(self):
        text = self.chat_input.text().strip()
        if not text:
            return
        self.append_chat("Vos", text, _TEAL)
        self.chat_input.clear()
        self.set_busy(True)
        self.goal_submitted.emit(text)

    def get_rect(self):
        p = self.pos(); s = self.size()
        return p.x(), p.y(), s.width(), s.height()


# ── Widget auxiliar: header con gradiente pintado ─────────────────────────────
class _GradientHeader(QWidget):
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        grad = QLinearGradient(0, 0, self.width(), 0)
        grad.setColorAt(0.0, QColor(26,  83,  92))   # deep ocean
        grad.setColorAt(0.5, QColor(38, 130, 120))   # mid teal
        grad.setColorAt(1.0, QColor(78, 205, 196))   # turquoise
        p.fillRect(self.rect(), grad)
        p.end()
