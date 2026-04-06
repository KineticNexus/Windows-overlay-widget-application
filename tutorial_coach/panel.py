"""Panel de control flotante: chat, guía, historial, voz, configuración."""
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QTextCursor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QFrame, QStackedWidget, QSizePolicy,
    QApplication, QComboBox, QCheckBox, QSlider,
)

from tutorial_coach.config import ACCENT_HEX, load_profile, save_profile


# ── Stylesheet ─────────────────────────────────────────────────────────────────
STYLE = """
QWidget#panel {
    background: rgba(8, 12, 28, 218);
    border: 1px solid rgba(56, 220, 180, 140);
    border-radius: 18px;
}
QWidget         { background: transparent; }
QLabel          { background: transparent; color: #c8d8e8; }
QLabel#title    { color: rgba(56, 220, 180, 255); }
QLabel#step     { color: rgba(130, 230, 200, 255); }
QLabel#instr    { color: #f0f4ff; }
QLabel#status   { color: rgba(140, 150, 170, 200); }
QTextEdit {
    background: rgba(255,255,255,14); color: #c8d0e0;
    border: 1px solid rgba(255,255,255,20); border-radius: 8px; padding: 6px;
    selection-background-color: rgba(56,220,180,80);
}
QLineEdit {
    background: rgba(255,255,255,14); color: #f0f4ff;
    border: 1px solid rgba(56,220,180,80); border-radius: 8px; padding: 10px;
}
QLineEdit:focus { border: 1px solid rgba(56,220,180,255); }
QPushButton {
    background: rgba(56,220,180,200); color: #080c1c;
    border: none; border-radius: 8px; padding: 9px 16px; font-weight: bold;
}
QPushButton:hover    { background: rgba(56,220,180,255); }
QPushButton:disabled { background: rgba(255,255,255,25); color: rgba(180,180,180,100); }
QPushButton#sec      { background: rgba(255,255,255,25); color: #c0c8d8; }
QPushButton#sec:hover { background: rgba(255,255,255,40); }
QPushButton#mic      { background: rgba(255,80,80,180); color: white; border-radius: 18px; }
QPushButton#mic:hover { background: rgba(255,80,80,255); }
QFrame#line { background: rgba(255,255,255,15); }
QCheckBox { color: #c8d0e0; background: transparent; }
QComboBox {
    background: rgba(255,255,255,14); color: #f0f4ff;
    border: 1px solid rgba(255,255,255,25); border-radius: 6px; padding: 6px;
}
QComboBox QAbstractItemView {
    background: #0f172a; color: white;
    selection-background-color: rgba(56,220,180,120);
}
"""


class ControlPanel(QWidget):
    goal_submitted = pyqtSignal(str)
    prev_clicked   = pyqtSignal()
    next_clicked   = pyqtSignal()
    reset_clicked  = pyqtSignal()
    mic_clicked    = pyqtSignal()
    help_clicked   = pyqtSignal()       # "¿dónde estoy?"
    profile_saved  = pyqtSignal(dict)   # perfil actualizado

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(440)
        self.setStyleSheet(STYLE)
        self._drag_pos = None
        self._profile = load_profile()
        self._build_ui()
        self._place()

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        panel = QWidget(self); panel.setObjectName("panel")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(panel)

        m = QVBoxLayout(panel)
        m.setContentsMargins(20, 14, 20, 14)
        m.setSpacing(8)

        # Cabecera
        hdr = QHBoxLayout()
        t = QLabel("🧭  Asistente Tutorial")
        t.setObjectName("title"); t.setFont(QFont("Arial", 13, QFont.Bold))
        hdr.addWidget(t); hdr.addStretch()

        self.help_btn = QPushButton("❓")
        self.help_btn.setObjectName("sec")
        self.help_btn.setToolTip("¿Dónde estoy?")
        self.help_btn.setFixedSize(32, 32)
        self.help_btn.clicked.connect(self.help_clicked.emit)
        hdr.addWidget(self.help_btn)

        self.status_lbl = QLabel("Listo")
        self.status_lbl.setObjectName("status")
        self.status_lbl.setFont(QFont("Arial", 10))
        hdr.addWidget(self.status_lbl)
        m.addLayout(hdr)

        ln = QFrame(); ln.setObjectName("line")
        ln.setFrameShape(QFrame.HLine); ln.setFixedHeight(1)
        m.addWidget(ln)

        # Stack: chat | guía | historial | config
        self._stack = QStackedWidget()
        m.addWidget(self._stack)
        self._stack.addWidget(self._page_chat())     # 0
        self._stack.addWidget(self._page_guide())    # 1
        self._stack.addWidget(self._page_history())  # 2
        self._stack.addWidget(self._page_config())   # 3

        # Tabs inferiores
        tabs = QHBoxLayout()
        for i, (label, idx) in enumerate([("Chat", 0), ("Guía", 1),
                                           ("Historial", 2), ("Config", 3)]):
            btn = QPushButton(label)
            btn.setObjectName("sec"); btn.setFont(QFont("Arial", 10))
            btn.clicked.connect(lambda _, x=idx: self._stack.setCurrentIndex(x))
            tabs.addWidget(btn)
        m.addLayout(tabs)

    # ── Página: Chat ──────────────────────────────────────────────────────────
    def _page_chat(self):
        p = QWidget(); l = QVBoxLayout(p)
        l.setContentsMargins(0, 4, 0, 0); l.setSpacing(8)

        lbl = QLabel("¿Qué quieres aprender o hacer?")
        lbl.setFont(QFont("Arial", 12, QFont.Bold)); l.addWidget(lbl)

        self.chat_log = QTextEdit()
        self.chat_log.setReadOnly(True)
        self.chat_log.setFont(QFont("Arial", 11))
        self.chat_log.setFixedHeight(100)
        l.addWidget(self.chat_log)

        row = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Ej: quiero mandar un mensaje por WhatsApp…")
        self.chat_input.setFont(QFont("Arial", 13))
        self.chat_input.returnPressed.connect(self._on_send)
        row.addWidget(self.chat_input)

        self.mic_btn = QPushButton("🎤")
        self.mic_btn.setObjectName("mic")
        self.mic_btn.setFixedSize(36, 36)
        self.mic_btn.setToolTip("Hablar")
        self.mic_btn.clicked.connect(self.mic_clicked.emit)
        row.addWidget(self.mic_btn)
        l.addLayout(row)

        self.send_btn = QPushButton("Analizar pantalla y comenzar  ▶")
        self.send_btn.setFont(QFont("Arial", 12, QFont.Bold))
        self.send_btn.clicked.connect(self._on_send)
        l.addWidget(self.send_btn)
        return p

    # ── Página: Guía ──────────────────────────────────────────────────────────
    def _page_guide(self):
        p = QWidget(); l = QVBoxLayout(p)
        l.setContentsMargins(0, 4, 0, 0); l.setSpacing(6)

        self.step_lbl = QLabel("Paso 1 de 1")
        self.step_lbl.setObjectName("step")
        self.step_lbl.setFont(QFont("Arial", 11, QFont.Bold))
        l.addWidget(self.step_lbl)

        self.instr_lbl = QLabel("")
        self.instr_lbl.setObjectName("instr")
        self.instr_lbl.setFont(QFont("Arial", 17, QFont.Bold))
        self.instr_lbl.setWordWrap(True)
        self.instr_lbl.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.instr_lbl.setMinimumHeight(70)
        self.instr_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        l.addWidget(self.instr_lbl)

        self.feedback_lbl = QLabel("")
        self.feedback_lbl.setFont(QFont("Arial", 11))
        self.feedback_lbl.setStyleSheet("color: #86efac; background: transparent;")
        self.feedback_lbl.setWordWrap(True)
        l.addWidget(self.feedback_lbl)

        hint = QLabel("💡 Presiona el elemento indicado para avanzar, o usa los botones.")
        hint.setFont(QFont("Arial", 9))
        hint.setStyleSheet("color: rgba(140,150,170,180); background: transparent;")
        hint.setWordWrap(True)
        l.addWidget(hint)

        row = QHBoxLayout()
        self.reset_btn = QPushButton("↺ Nueva")
        self.reset_btn.setObjectName("sec")
        self.reset_btn.setFont(QFont("Arial", 10))
        self.reset_btn.clicked.connect(self.reset_clicked.emit)
        row.addWidget(self.reset_btn)

        self.prev_btn = QPushButton("◀")
        self.prev_btn.setObjectName("sec"); self.prev_btn.setFixedWidth(42)
        self.prev_btn.clicked.connect(self.prev_clicked.emit)
        row.addWidget(self.prev_btn)

        self.next_btn = QPushButton("Siguiente ▶")
        self.next_btn.setFont(QFont("Arial", 11, QFont.Bold))
        self.next_btn.setFixedWidth(130)
        self.next_btn.clicked.connect(self.next_clicked.emit)
        row.addWidget(self.next_btn)
        l.addLayout(row)
        return p

    # ── Página: Historial ─────────────────────────────────────────────────────
    def _page_history(self):
        p = QWidget(); l = QVBoxLayout(p)
        l.setContentsMargins(0, 4, 0, 0); l.setSpacing(6)
        lbl = QLabel("Sesiones anteriores")
        lbl.setFont(QFont("Arial", 12, QFont.Bold)); l.addWidget(lbl)
        self.history_log = QTextEdit()
        self.history_log.setReadOnly(True)
        self.history_log.setFont(QFont("Arial", 11))
        self.history_log.setMinimumHeight(160)
        l.addWidget(self.history_log)
        return p

    # ── Página: Configuración ─────────────────────────────────────────────────
    def _page_config(self):
        p = QWidget(); l = QVBoxLayout(p)
        l.setContentsMargins(0, 4, 0, 0); l.setSpacing(8)
        lbl = QLabel("Configuración"); lbl.setFont(QFont("Arial", 12, QFont.Bold))
        l.addWidget(lbl)

        self.voice_chk = QCheckBox("Leer instrucciones en voz alta")
        self.voice_chk.setFont(QFont("Arial", 11))
        self.voice_chk.setChecked(self._profile.get("voice_enabled", True))
        self.voice_chk.toggled.connect(self._on_config_changed)
        l.addWidget(self.voice_chk)

        self.verify_chk = QCheckBox("Verificar cada paso con IA")
        self.verify_chk.setFont(QFont("Arial", 11))
        self.verify_chk.setChecked(self._profile.get("auto_verify", True))
        self.verify_chk.toggled.connect(self._on_config_changed)
        l.addWidget(self.verify_chk)

        row = QHBoxLayout()
        row.addWidget(QLabel("Tamaño de texto:"))
        self.font_slider = QSlider(Qt.Horizontal)
        self.font_slider.setRange(12, 24)
        self.font_slider.setValue(self._profile.get("font_size", 14))
        self.font_slider.valueChanged.connect(self._on_config_changed)
        row.addWidget(self.font_slider)
        self.font_val = QLabel(str(self.font_slider.value()))
        self.font_val.setFixedWidth(24)
        row.addWidget(self.font_val)
        l.addLayout(row)

        save_btn = QPushButton("Guardar configuración")
        save_btn.setFont(QFont("Arial", 11))
        save_btn.clicked.connect(self._save_config)
        l.addWidget(save_btn)
        l.addStretch()
        return p

    def _on_config_changed(self, _=None):
        self.font_val.setText(str(self.font_slider.value()))

    def _save_config(self):
        self._profile["voice_enabled"] = self.voice_chk.isChecked()
        self._profile["auto_verify"]   = self.verify_chk.isChecked()
        self._profile["font_size"]     = self.font_slider.value()
        save_profile(self._profile)
        self.profile_saved.emit(self._profile)
        self.set_status("Configuración guardada")

    # ── Dragging ──────────────────────────────────────────────────────────────
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
    def get_profile(self) -> dict:
        return dict(self._profile)

    def show_chat_mode(self):
        self._stack.setCurrentIndex(0)
        self.chat_input.setFocus()
        self.adjustSize()

    def show_guide_mode(self, step: dict, total: int):
        self.step_lbl.setText(f"Paso {step['n']} de {total}")
        self.instr_lbl.setText(step["instruction"])
        self.feedback_lbl.setText("")
        self._stack.setCurrentIndex(1)
        self.prev_btn.setEnabled(step["n"] > 1)
        self.next_btn.setEnabled(step["n"] < total)
        self.adjustSize()

    def show_feedback(self, text: str):
        self.feedback_lbl.setText(text)

    def show_finished(self):
        self.instr_lbl.setText("¡Lo lograste! Completaste todos los pasos.")
        self.feedback_lbl.setText("")
        self.next_btn.setEnabled(False)
        self.adjustSize()

    def set_status(self, text: str):
        self.status_lbl.setText(text)

    def append_chat(self, who: str, text: str, color: str):
        self.chat_log.append(
            f'<span style="color:{color};font-weight:bold">{who}:</span> '
            f'<span style="color:#e0e4f0">{text}</span>')
        self.chat_log.moveCursor(QTextCursor.End)

    def set_busy(self, busy: bool):
        self.send_btn.setEnabled(not busy)
        self.send_btn.setText(
            "Analizando…" if busy else "Analizar pantalla y comenzar  ▶")

    def set_mic_state(self, state: str):
        if state == "recording":
            self.mic_btn.setText("⏹")
            self.mic_btn.setStyleSheet(
                "background: rgba(255,40,40,220); color: white; border-radius: 18px;")
        else:
            self.mic_btn.setText("🎤")
            self.mic_btn.setStyleSheet("")

    def set_history(self, sessions: list):
        self.history_log.clear()
        for s in sessions:
            icon = "✅" if s.get("completed") else "⏸"
            self.history_log.append(
                f'{icon} <b>{s["goal"]}</b> — {s.get("created_at", "")}')

    def _on_send(self):
        text = self.chat_input.text().strip()
        if not text:
            return
        self.append_chat("Tú", text, "#86efac")
        self.chat_input.clear()
        self.set_busy(True)
        self.goal_submitted.emit(text)

    def get_rect(self):
        p = self.pos(); s = self.size()
        return p.x(), p.y(), s.width(), s.height()
