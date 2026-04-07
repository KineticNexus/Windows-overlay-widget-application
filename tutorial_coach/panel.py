"""Panel de control flotante — UI limpia inspirada en Material Design."""
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QTextCursor, QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QFrame, QStackedWidget, QSizePolicy,
    QApplication, QCheckBox, QSlider, QGraphicsDropShadowEffect,
)

from tutorial_coach.config import load_profile, save_profile

# Fuente base del sistema
FONT = "Segoe UI"

# ── Stylesheet — limpio, claro, Material-like ─────────────────────────────────
STYLE = """
QWidget#panel {
    background: rgba(255, 255, 255, 200);
    border: 1px solid rgba(226, 226, 226, 160);
    border-radius: 14px;
}
QWidget         { background: transparent; }
QLabel          { background: transparent; color: #3c4043; }
QLabel#title    { color: #1a73e8; }
QLabel#step     { color: #1a73e8; }
QLabel#instr    { color: #202124; }
QLabel#status   { color: #9aa0a6; }
QLabel#hint     { color: #9aa0a6; }
QTextEdit {
    background: rgba(248, 249, 250, 160); color: #3c4043;
    border: 1px solid rgba(218, 220, 224, 120);
    border-radius: 8px; padding: 8px;
    selection-background-color: rgba(26,115,232,0.2);
}
QLineEdit {
    background: rgba(248, 249, 250, 180); color: #202124;
    border: 1px solid rgba(218, 220, 224, 150);
    border-radius: 24px; padding: 10px 16px;
}
QLineEdit:focus {
    border: 2px solid #1a73e8;
    background: rgba(255, 255, 255, 220);
}
QPushButton#primary {
    background: rgba(26, 115, 232, 230); color: white;
    border: none; border-radius: 20px; padding: 10px 20px;
}
QPushButton#primary:hover { background: rgba(21, 87, 176, 240); }
QPushButton#primary:disabled { background: rgba(218, 220, 224, 180); color: #9aa0a6; }
QPushButton#sec {
    background: rgba(255,255,255,100); color: #5f6368;
    border: 1px solid rgba(218, 220, 224, 140);
    border-radius: 20px; padding: 8px 16px;
}
QPushButton#sec:hover { background: rgba(241, 243, 244, 180); }
QPushButton#close_btn {
    background: transparent; color: #9aa0a6;
    border: none; border-radius: 12px; padding: 2px;
    font-size: 14px;
}
QPushButton#close_btn:hover { background: rgba(234, 67, 53, 30); color: #d93025; }
QPushButton#mic {
    background: rgba(234, 67, 53, 210); color: white;
    border: none; border-radius: 18px;
}
QPushButton#mic:hover { background: rgba(197, 34, 31, 230); }
QPushButton#tab_btn {
    background: transparent; color: #5f6368;
    border: none; border-radius: 0; padding: 8px 12px;
    border-bottom: 2px solid transparent;
}
QPushButton#tab_btn:hover { color: #1a73e8; }
QFrame#line { background: rgba(232, 234, 237, 140); }
QCheckBox { color: #3c4043; background: transparent; }
QSlider::groove:horizontal {
    background: rgba(218, 220, 224, 180); height: 4px; border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #1a73e8; width: 16px; height: 16px;
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
        self.setFixedWidth(400)
        self.setStyleSheet(STYLE)
        self._drag_pos = None
        self._profile = load_profile()
        self._tab_btns = []
        self._build_ui()
        self._place()

    # ── Build UI ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        panel = QWidget(self); panel.setObjectName("panel")

        # Sombra sutil
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 40))
        panel.setGraphicsEffect(shadow)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.addWidget(panel)

        m = QVBoxLayout(panel)
        m.setContentsMargins(20, 14, 20, 14)
        m.setSpacing(8)

        # ── Header ────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        icon = QLabel("◉")
        icon.setFont(QFont(FONT, 16))
        icon.setStyleSheet("color: #1a73e8; background: transparent;")
        hdr.addWidget(icon)
        t = QLabel("Tortuga")
        t.setObjectName("title"); t.setFont(QFont(FONT, 14, QFont.DemiBold))
        hdr.addWidget(t)
        hdr.addStretch()

        self.help_btn = QPushButton("?")
        self.help_btn.setObjectName("sec")
        self.help_btn.setToolTip("¿Dónde estoy? (F1)")
        self.help_btn.setFixedSize(30, 30)
        self.help_btn.setFont(QFont(FONT, 11, QFont.Bold))
        self.help_btn.clicked.connect(self.help_clicked.emit)
        hdr.addWidget(self.help_btn)

        self.status_lbl = QLabel("Listo")
        self.status_lbl.setObjectName("status")
        self.status_lbl.setFont(QFont(FONT, 9))
        hdr.addWidget(self.status_lbl)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("close_btn")
        close_btn.setFixedSize(28, 28)
        close_btn.setFont(QFont(FONT, 14))
        close_btn.setToolTip("Cerrar")
        close_btn.clicked.connect(self.close_clicked.emit)
        hdr.addWidget(close_btn)
        m.addLayout(hdr)

        ln = QFrame(); ln.setObjectName("line")
        ln.setFrameShape(QFrame.HLine); ln.setFixedHeight(1)
        m.addWidget(ln)

        # ── Tabs ──────────────────────────────────────────────────────────
        tabs = QHBoxLayout()
        tabs.setSpacing(0)
        for label, idx in [("Chat", 0), ("Guía", 1), ("Historial", 2), ("Config", 3)]:
            btn = QPushButton(label)
            btn.setObjectName("tab_btn")
            btn.setFont(QFont(FONT, 10))
            btn.clicked.connect(lambda _, x=idx: self._select_tab(x))
            tabs.addWidget(btn)
            self._tab_btns.append(btn)
        m.addLayout(tabs)

        # Thin line under tabs
        ln2 = QFrame(); ln2.setObjectName("line")
        ln2.setFrameShape(QFrame.HLine); ln2.setFixedHeight(1)
        m.addWidget(ln2)

        # ── Stack ─────────────────────────────────────────────────────────
        self._stack = QStackedWidget()
        m.addWidget(self._stack)
        self._stack.addWidget(self._page_chat())     # 0
        self._stack.addWidget(self._page_guide())    # 1
        self._stack.addWidget(self._page_history())  # 2
        self._stack.addWidget(self._page_config())   # 3

        self._select_tab(0)

    def _select_tab(self, idx):
        self._stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._tab_btns):
            if i == idx:
                btn.setStyleSheet("border-bottom: 2px solid #1a73e8; color: #1a73e8;")
            else:
                btn.setStyleSheet("border-bottom: 2px solid transparent; color: #5f6368;")
        self.adjustSize()

    # ── Chat ──────────────────────────────────────────────────────────────────
    def _page_chat(self):
        p = QWidget(); l = QVBoxLayout(p)
        l.setContentsMargins(0, 8, 0, 0); l.setSpacing(10)

        lbl = QLabel("¿Qué querés hacer?")
        lbl.setFont(QFont(FONT, 13, QFont.DemiBold)); l.addWidget(lbl)

        self.chat_log = QTextEdit()
        self.chat_log.setReadOnly(True)
        self.chat_log.setFont(QFont(FONT, 11))
        self.chat_log.setFixedHeight(90)
        l.addWidget(self.chat_log)

        row = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Escribe o habla...")
        self.chat_input.setFont(QFont(FONT, 12))
        self.chat_input.returnPressed.connect(self._on_send)
        row.addWidget(self.chat_input)

        self.mic_btn = QPushButton("🎤")
        self.mic_btn.setObjectName("mic")
        self.mic_btn.setFixedSize(36, 36)
        self.mic_btn.setToolTip("Hablar")
        self.mic_btn.clicked.connect(self.mic_clicked.emit)
        row.addWidget(self.mic_btn)
        l.addLayout(row)

        self.send_btn = QPushButton("Comenzar")
        self.send_btn.setObjectName("primary")
        self.send_btn.setFont(QFont(FONT, 12, QFont.DemiBold))
        self.send_btn.clicked.connect(self._on_send)
        l.addWidget(self.send_btn)
        return p

    # ── Guía ──────────────────────────────────────────────────────────────────
    def _page_guide(self):
        p = QWidget(); l = QVBoxLayout(p)
        l.setContentsMargins(0, 8, 0, 0); l.setSpacing(6)

        self.step_lbl = QLabel("Paso 1 de 1")
        self.step_lbl.setObjectName("step")
        self.step_lbl.setFont(QFont(FONT, 10, QFont.DemiBold))
        l.addWidget(self.step_lbl)

        self.instr_lbl = QLabel("")
        self.instr_lbl.setObjectName("instr")
        self.instr_lbl.setFont(QFont(FONT, 16, QFont.DemiBold))
        self.instr_lbl.setWordWrap(True)
        self.instr_lbl.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.instr_lbl.setMinimumHeight(60)
        self.instr_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        l.addWidget(self.instr_lbl)

        self.feedback_lbl = QLabel("")
        self.feedback_lbl.setFont(QFont(FONT, 11))
        self.feedback_lbl.setStyleSheet("color: #188038; background: transparent;")
        self.feedback_lbl.setWordWrap(True)
        l.addWidget(self.feedback_lbl)

        hint = QLabel("Presiona el elemento indicado para avanzar.")
        hint.setObjectName("hint")
        hint.setFont(QFont(FONT, 9)); hint.setWordWrap(True)
        l.addWidget(hint)

        row = QHBoxLayout()
        self.reset_btn = QPushButton("Nueva")
        self.reset_btn.setObjectName("sec")
        self.reset_btn.setFont(QFont(FONT, 10))
        self.reset_btn.clicked.connect(self.reset_clicked.emit)
        row.addWidget(self.reset_btn)

        self.prev_btn = QPushButton("◀")
        self.prev_btn.setObjectName("sec"); self.prev_btn.setFixedWidth(40)
        self.prev_btn.clicked.connect(self.prev_clicked.emit)
        row.addWidget(self.prev_btn)

        self.next_btn = QPushButton("Siguiente")
        self.next_btn.setObjectName("primary")
        self.next_btn.setFont(QFont(FONT, 11, QFont.DemiBold))
        self.next_btn.setFixedWidth(120)
        self.next_btn.clicked.connect(self.next_clicked.emit)
        row.addWidget(self.next_btn)
        l.addLayout(row)
        return p

    # ── Historial ─────────────────────────────────────────────────────────────
    def _page_history(self):
        p = QWidget(); l = QVBoxLayout(p)
        l.setContentsMargins(0, 8, 0, 0); l.setSpacing(6)
        lbl = QLabel("Sesiones anteriores")
        lbl.setFont(QFont(FONT, 12, QFont.DemiBold)); l.addWidget(lbl)
        self.history_log = QTextEdit()
        self.history_log.setReadOnly(True)
        self.history_log.setFont(QFont(FONT, 11))
        self.history_log.setMinimumHeight(140)
        l.addWidget(self.history_log)
        return p

    # ── Config ────────────────────────────────────────────────────────────────
    def _page_config(self):
        p = QWidget(); l = QVBoxLayout(p)
        l.setContentsMargins(0, 8, 0, 0); l.setSpacing(10)
        lbl = QLabel("Configuración")
        lbl.setFont(QFont(FONT, 12, QFont.DemiBold)); l.addWidget(lbl)

        self.voice_chk = QCheckBox("Leer instrucciones en voz alta")
        self.voice_chk.setFont(QFont(FONT, 11))
        self.voice_chk.setChecked(self._profile.get("voice_enabled", True))
        l.addWidget(self.voice_chk)

        self.verify_chk = QCheckBox("Verificar cada paso con IA")
        self.verify_chk.setFont(QFont(FONT, 11))
        self.verify_chk.setChecked(self._profile.get("auto_verify", True))
        l.addWidget(self.verify_chk)

        row = QHBoxLayout()
        row.addWidget(QLabel("Texto:"))
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
        self.set_status("Guardado")

    # ── Dragging ──────────────────────────────────────────────────────────────
    def _place(self):
        screen = QApplication.primaryScreen().geometry()
        self.adjustSize()
        self.move(screen.width() - self.width() - 24, 24)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() == Qt.LeftButton:
            self.move(e.globalPos() - self._drag_pos)

    def mouseReleaseEvent(self, _):
        self._drag_pos = None

    # ── API pública ───────────────────────────────────────────────────────────
    def get_profile(self) -> dict:
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
        self.instr_lbl.setText("Completaste todos los pasos.")
        self.feedback_lbl.setText("")
        self.next_btn.setEnabled(False)
        self.adjustSize()

    def set_status(self, text: str):
        self.status_lbl.setText(text)

    def append_chat(self, who: str, text: str, color: str):
        self.chat_log.append(
            f'<span style="color:{color};font-weight:600">{who}:</span> '
            f'<span style="color:#3c4043">{text}</span>')
        self.chat_log.moveCursor(QTextCursor.End)

    def set_busy(self, busy: bool):
        self.send_btn.setEnabled(not busy)
        self.send_btn.setText("Analizando…" if busy else "Comenzar")

    def set_mic_state(self, state: str):
        if state == "recording":
            self.mic_btn.setText("■")
            self.mic_btn.setStyleSheet(
                "background: #d93025; color: white; border-radius: 18px;")
        else:
            self.mic_btn.setText("🎤")
            self.mic_btn.setStyleSheet("")

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
        self.append_chat("Tú", text, "#1a73e8")
        self.chat_input.clear()
        self.set_busy(True)
        self.goal_submitted.emit(text)

    def get_rect(self):
        p = self.pos(); s = self.size()
        return p.x(), p.y(), s.width(), s.height()
