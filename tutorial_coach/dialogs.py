"""Diálogos: API Key y splash."""
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton


class APIKeyDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Asistente Tutorial")
        self.setFixedSize(500, 280)
        self.setStyleSheet("""
            QDialog   { background: #080c1c; }
            QLabel    { color: #f0f4ff; background: transparent; }
            QLineEdit {
                background: rgba(255,255,255,10); color: #f0f4ff;
                border: 1px solid rgba(56,220,180,80);
                border-radius: 10px; padding: 12px; font-size: 14px;
            }
            QLineEdit:focus { border: 1px solid rgba(56,220,180,255); }
            QPushButton {
                background: rgba(56,220,180,200); color: #080c1c;
                border: none; border-radius: 10px;
                padding: 13px; font-size: 15px; font-weight: bold;
            }
            QPushButton:hover { background: rgba(56,220,180,255); }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 30, 36, 30)
        layout.setSpacing(14)

        title = QLabel("🧭  Asistente Tutorial")
        title.setFont(QFont("Arial", 20, QFont.Bold))
        title.setStyleSheet("color: rgba(56,220,180,255); background: transparent;")
        layout.addWidget(title)

        sub = QLabel("Ingresa tu clave de Anthropic para comenzar:")
        sub.setFont(QFont("Arial", 12))
        layout.addWidget(sub)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("sk-ant-api03-...")
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.returnPressed.connect(self._validate)
        layout.addWidget(self.key_input)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #f87171; background: transparent;")
        self.error_label.setFont(QFont("Arial", 11))
        layout.addWidget(self.error_label)

        btn = QPushButton("Continuar  ▶")
        btn.clicked.connect(self._validate)
        layout.addWidget(btn)

    def _validate(self):
        key = self.key_input.text().strip()
        if len(key) < 20:
            self.error_label.setText("⚠  La clave parece muy corta.")
            return
        self.accept()

    def get_key(self) -> str:
        return self.key_input.text().strip()
