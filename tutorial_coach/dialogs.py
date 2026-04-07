"""Diálogos: API Keys (Anthropic + Deepgram opcional) con estilo Material Design."""
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QGraphicsDropShadowEffect,
)

from tutorial_coach.config import load_profile, save_profile


_STYLE = """
QDialog {
    background: #ffffff;
}
QLabel {
    background: transparent;
    color: #202124;
    font-family: 'Segoe UI', Arial, sans-serif;
}
QLineEdit {
    background: #f8f9fa;
    color: #202124;
    border: 1px solid #dadce0;
    border-radius: 8px;
    padding: 12px 14px;
    font-size: 14px;
    font-family: 'Segoe UI', Arial, sans-serif;
}
QLineEdit:focus {
    border: 2px solid #1a73e8;
    background: #ffffff;
    padding: 11px 13px;
}
QPushButton#primary {
    background: #1a73e8;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 12px 28px;
    font-size: 14px;
    font-weight: bold;
    font-family: 'Segoe UI', Arial, sans-serif;
}
QPushButton#primary:hover  { background: #1557b0; }
QPushButton#primary:pressed { background: #0d47a1; }
"""


class APIKeyDialog(QDialog):
    def __init__(self):
        super().__init__(None, Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle("Asistente Tutorial — Configuración")
        self.setFixedWidth(460)
        self.setStyleSheet(_STYLE)

        profile = load_profile()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 36, 40, 36)
        layout.setSpacing(0)

        # ── Logo + título ──────────────────────────────────────────────────
        logo_row = QHBoxLayout()
        badge = QLabel("A")
        badge.setFixedSize(38, 38)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            "background:#1a73e8; color:white; border-radius:8px;"
            "font-size:18px; font-weight:bold; font-family:'Segoe UI',Arial;")
        title_lbl = QLabel("Asistente Tutorial")
        title_lbl.setFont(QFont("Segoe UI", 17, QFont.Bold))
        title_lbl.setStyleSheet("color:#202124;")
        logo_row.addWidget(badge)
        logo_row.addSpacing(12)
        logo_row.addWidget(title_lbl)
        logo_row.addStretch()
        layout.addLayout(logo_row)
        layout.addSpacing(6)

        sub = QLabel("Ingresa tus claves de API para comenzar")
        sub.setFont(QFont("Segoe UI", 11))
        sub.setStyleSheet("color:#5f6368;")
        layout.addWidget(sub)
        layout.addSpacing(28)

        # ── Clave Anthropic ────────────────────────────────────────────────
        lbl1 = QLabel("Clave Anthropic  *")
        lbl1.setFont(QFont("Segoe UI", 11, QFont.Bold))
        layout.addWidget(lbl1)
        layout.addSpacing(6)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("sk-ant-api03-...")
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.setText(profile.get("anthropic_key", ""))
        self.key_input.returnPressed.connect(self._validate)
        layout.addWidget(self.key_input)
        layout.addSpacing(20)

        # ── Clave Deepgram ─────────────────────────────────────────────────
        lbl2 = QLabel("Clave Deepgram  (opcional — mejora voz notablemente)")
        lbl2.setFont(QFont("Segoe UI", 11))
        lbl2.setStyleSheet("color:#5f6368;")
        layout.addWidget(lbl2)
        layout.addSpacing(6)

        self.deepgram_input = QLineEdit()
        self.deepgram_input.setPlaceholderText("Token de Deepgram...")
        self.deepgram_input.setEchoMode(QLineEdit.Password)
        self.deepgram_input.setText(profile.get("deepgram_key", ""))
        self.deepgram_input.returnPressed.connect(self._validate)
        layout.addWidget(self.deepgram_input)
        layout.addSpacing(10)

        # ── Error ──────────────────────────────────────────────────────────
        self.error_lbl = QLabel("")
        self.error_lbl.setFont(QFont("Segoe UI", 10))
        self.error_lbl.setStyleSheet("color:#d93025;")
        layout.addWidget(self.error_lbl)
        layout.addSpacing(24)

        # ── Botón ──────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.ok_btn = QPushButton("Continuar →")
        self.ok_btn.setObjectName("primary")
        self.ok_btn.setFixedHeight(46)
        self.ok_btn.setMinimumWidth(150)
        self.ok_btn.clicked.connect(self._validate)
        btn_row.addWidget(self.ok_btn)
        layout.addLayout(btn_row)

    def _validate(self):
        key = self.key_input.text().strip()
        if len(key) < 20:
            self.error_lbl.setText("⚠  La clave Anthropic parece incorrecta.")
            self.key_input.setFocus()
            return
        self.error_lbl.setText("")

        # Guardar claves en perfil para la próxima sesión
        profile = load_profile()
        profile["anthropic_key"] = key
        dg = self.deepgram_input.text().strip()
        if dg:
            profile["deepgram_key"] = dg
        save_profile(profile)

        self.accept()

    def get_key(self) -> str:
        return self.key_input.text().strip()

    def get_deepgram_key(self) -> str:
        return self.deepgram_input.text().strip()
