"""Diálogos: API Keys (Anthropic + Deepgram opcional) con estilo Material Design."""
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QGraphicsDropShadowEffect, QWidget
)


def _shadow(blur=20, alpha=40):
    fx = QGraphicsDropShadowEffect()
    fx.setBlurRadius(blur)
    fx.setOffset(0, 2)
    fx.setColor(QColor(0, 0, 0, alpha))
    return fx


_STYLE = """
QDialog {
    background: #ffffff;
    border-radius: 12px;
}
QLabel {
    background: transparent;
    color: #202124;
}
QLabel#hint {
    color: #5f6368;
    font-size: 12px;
}
QLabel#error {
    color: #d93025;
    font-size: 12px;
}
QLineEdit {
    background: #ffffff;
    color: #202124;
    border: 1px solid #dadce0;
    border-radius: 8px;
    padding: 11px 14px;
    font-size: 14px;
    font-family: 'Segoe UI', Arial, sans-serif;
}
QLineEdit:focus {
    border: 2px solid #1a73e8;
    padding: 10px 13px;
}
QPushButton#primary {
    background: #1a73e8;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 12px 24px;
    font-size: 14px;
    font-weight: bold;
    font-family: 'Segoe UI', Arial, sans-serif;
}
QPushButton#primary:hover {
    background: #1557b0;
}
QPushButton#primary:pressed {
    background: #0d47a1;
}
"""


class APIKeyDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Asistente Tutorial")
        self.setFixedSize(480, 380)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet(_STYLE)
        self.setGraphicsEffect(_shadow(blur=32, alpha=60))

        # Card container
        card = QWidget(self)
        card.setGeometry(0, 0, 480, 380)
        card.setStyleSheet("""
            QWidget {
                background: #ffffff;
                border-radius: 12px;
            }
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(40, 36, 40, 36)
        layout.setSpacing(0)

        # Logo + title
        logo_row = QHBoxLayout()
        logo_lbl = QLabel("G")
        logo_lbl.setFixedSize(36, 36)
        logo_lbl.setAlignment(Qt.AlignCenter)
        logo_lbl.setStyleSheet("""
            background: #1a73e8;
            color: white;
            border-radius: 8px;
            font-size: 18px;
            font-weight: bold;
            font-family: 'Segoe UI', Arial;
        """)
        title_lbl = QLabel("Asistente Tutorial")
        title_lbl.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title_lbl.setStyleSheet("color: #202124; background: transparent;")
        logo_row.addWidget(logo_lbl)
        logo_row.addSpacing(12)
        logo_row.addWidget(title_lbl)
        logo_row.addStretch()
        layout.addLayout(logo_row)
        layout.addSpacing(8)

        sub = QLabel("Ingresa tus claves de API para comenzar")
        sub.setObjectName("hint")
        layout.addWidget(sub)
        layout.addSpacing(24)

        # Anthropic key
        ant_lbl = QLabel("Clave Anthropic *")
        ant_lbl.setFont(QFont("Segoe UI", 12, QFont.Bold))
        layout.addWidget(ant_lbl)
        layout.addSpacing(6)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("sk-ant-api03-...")
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.returnPressed.connect(self._validate)
        layout.addWidget(self.key_input)
        layout.addSpacing(16)

        # Deepgram key
        dg_lbl = QLabel("Clave Deepgram (opcional — mejora voz)")
        dg_lbl.setObjectName("hint")
        dg_lbl.setFont(QFont("Segoe UI", 11))
        layout.addWidget(dg_lbl)
        layout.addSpacing(6)

        self.deepgram_input = QLineEdit()
        self.deepgram_input.setPlaceholderText("Token Deepgram...")
        self.deepgram_input.setEchoMode(QLineEdit.Password)
        self.deepgram_input.returnPressed.connect(self._validate)
        layout.addWidget(self.deepgram_input)
        layout.addSpacing(8)

        self.error_label = QLabel("")
        self.error_label.setObjectName("error")
        layout.addWidget(self.error_label)
        layout.addStretch()

        # Button row
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn = QPushButton("Continuar")
        btn.setObjectName("primary")
        btn.setFixedHeight(44)
        btn.setMinimumWidth(140)
        btn.clicked.connect(self._validate)
        btn_row.addWidget(btn)
        layout.addLayout(btn_row)

    def _validate(self):
        key = self.key_input.text().strip()
        if len(key) < 20:
            self.error_label.setText("La clave Anthropic parece incorrecta.")
            return
        self.accept()

    def get_key(self) -> str:
        return self.key_input.text().strip()

    def get_deepgram_key(self) -> str:
        return self.deepgram_input.text().strip()
