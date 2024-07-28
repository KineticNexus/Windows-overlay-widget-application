import sys
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication, QLabel, QWidget, QInputDialog, QVBoxLayout, QPushButton


class OverlayWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setFont(QFont('Arial', 100, QFont.Bold))
        self.label.setStyleSheet("color: red;")
        self.layout.addWidget(self.label)

        self.input_button = QPushButton("Set Word and Coordinates", self)
        self.input_button.clicked.connect(self.get_input)
        self.layout.addWidget(self.input_button)

    def get_input(self):
        word, ok = QInputDialog.getText(self, "Input Dialog", "Enter the word:")
        if ok and word:
            x, ok = QInputDialog.getInt(self, "Input Dialog", "Enter X coordinate:", min=0, max=1920)
            if ok:
                y, ok = QInputDialog.getInt(self, "Input Dialog", "Enter Y coordinate:", min=0, max=1080)
                if ok:
                    self.show_word(word, x, y)

    def show_word(self, word, x, y):
        self.label.setText(word)
        self.setGeometry(x, y, 800, 200)  # Adjust the size as needed
        self.show()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    overlay = OverlayWidget()
    overlay.get_input()
    sys.exit(app.exec_())
