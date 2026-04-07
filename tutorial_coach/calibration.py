"""
Calibración visual de pantalla.

Muestra 500 columnas y 500 filas numeradas, luego mueve el mouse
automáticamente a 5 posiciones y mide en qué columna/fila cayó.
Calcula el factor de corrección de coordenadas.
"""
import math
import time

from PyQt5.QtCore  import Qt, QTimer, QRect, QPoint
from PyQt5.QtGui   import (
    QPainter, QColor, QPen, QBrush, QFont, QLinearGradient, QPainterPath,
)
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QApplication,
)

# ── Paleta ───────────────────────────────────────────────────────────────────
_DEEP   = QColor( 26,  83,  92)   # #1A535C fondo oscuro
_TEAL   = QColor( 78, 205, 196)   # #4ECDC4 líneas columna
_CORAL  = QColor(255, 107, 107)   # #FF6B6B líneas fila / acento
_SAND   = QColor(255, 230, 109)   # #FFE66D highlight
_WHITE  = QColor(255, 255, 255)


def _col_for(x, lw):
    """Columna (0-499) para posición x lógica."""
    return max(0, min(499, int(x * 500 / lw)))


def _row_for(y, lh):
    """Fila (0-499) para posición y lógica."""
    return max(0, min(499, int(y * 500 / lh)))


class _Grid(QDialog):
    """Ventana de calibración: grid de 500 cols × 500 filas + pruebas."""

    # Secuencia de movimientos desde el centro: (dx, dy, etiqueta)
    _TESTS = [
        (   0,    0, "Centro"),
        (  25,    0, "+25 px →"),
        (  50,    0, "+50 px →"),
        ( 200,    0, "+200 px →"),
        ( 350,    0, "+350 px →"),
        (   0,   25, "+25 px ↓"),
        (   0,  200, "+200 px ↓"),
    ]

    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)

        self._lw   = screen.width()
        self._lh   = screen.height()
        self._step = 0
        self._res  = []          # (label, px, py, col, row, ok)
        self._dot  = None        # posición actual del mouse (QPoint)
        self._done = False

        self._build_panel()

    # ── Panel de resultados (flotante sobre el grid) ─────────────────────────
    def _build_panel(self):
        self._panel = QFrame(self)
        self._panel.setObjectName("panel")
        self._panel.setStyleSheet("""
            QFrame#panel {
                background: rgba(26, 83, 92, 235);
                border: 2px solid rgba(78, 205, 196, 180);
                border-radius: 4px;
            }
            QLabel { color: #F7FFF7; font-family: 'Segoe UI'; background: transparent; }
        """)
        pw, ph = 480, 420
        self._panel.setGeometry(
            (self._lw - pw) // 2,
            (self._lh - ph) // 2,
            pw, ph,
        )

        lay = QVBoxLayout(self._panel)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(8)

        title = QLabel("🐢  Calibración de pantalla")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #4ECDC4;")
        lay.addWidget(title)

        sub = QLabel("Moviendo mouse y verificando coordenadas...")
        sub.setFont(QFont("Segoe UI", 11))
        sub.setStyleSheet("color: #FFE66D;")
        lay.addWidget(sub)
        lay.addSpacing(8)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background: rgba(78,205,196,80); min-height:1px;")
        lay.addWidget(sep)
        lay.addSpacing(4)

        self._rows_lbl = []
        for _ in self._TESTS:
            lbl = QLabel("⏳  Esperando...")
            lbl.setFont(QFont("Segoe UI", 11))
            lay.addWidget(lbl)
            self._rows_lbl.append(lbl)

        lay.addSpacing(4)
        sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("background: rgba(78,205,196,80); min-height:1px;")
        lay.addWidget(sep2)
        lay.addSpacing(4)

        self._factor_lbl = QLabel("")
        self._factor_lbl.setFont(QFont("Segoe UI", 11, QFont.Bold))
        lay.addWidget(self._factor_lbl)

        lay.addStretch()

        self._ok_btn = QPushButton("Continuar  →")
        self._ok_btn.setEnabled(False)
        self._ok_btn.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self._ok_btn.setFixedHeight(44)
        self._ok_btn.setStyleSheet("""
            QPushButton {
                background: #4ECDC4; color: #1A535C;
                border: none; border-radius: 2px;
            }
            QPushButton:hover    { background: #45B8B0; }
            QPushButton:disabled { background: rgba(78,205,196,60); color: rgba(247,255,247,80); }
        """)
        self._ok_btn.clicked.connect(self.accept)
        lay.addWidget(self._ok_btn)

        # Iniciar secuencia automática
        QTimer.singleShot(800, self._run_step)

    # ── Secuencia de prueba ───────────────────────────────────────────────────
    def _run_step(self):
        if self._step >= len(self._TESTS):
            self._finish()
            return

        from pynput.mouse import Controller
        mouse = Controller()

        cx = self._lw // 2
        cy = self._lh // 2

        dx, dy, label = self._TESTS[self._step]
        tx = cx + dx
        ty = cy + dy

        mouse.position = (tx, ty)
        time.sleep(0.25)
        rx, ry = mouse.position

        col = _col_for(rx, self._lw)
        row = _row_for(ry, self._lh)
        ec  = _col_for(tx, self._lw)
        er  = _row_for(ty, self._lh)
        ok  = abs(col - ec) <= 2 and abs(row - er) <= 2

        self._res.append((label, rx, ry, col, row, ok))
        self._dot = QPoint(rx, ry)

        icon = "✅" if ok else "⚠️"
        self._rows_lbl[self._step].setText(
            f"{icon}  {label:12s}  →  col {col:3d}  fila {row:3d}"
            + ("" if ok else f"  (esperado {ec},{er})")
        )
        if not ok:
            self._rows_lbl[self._step].setStyleSheet("color: #FF6B6B;")
        else:
            self._rows_lbl[self._step].setStyleSheet("color: #4ECDC4;")

        self.update()
        self._step += 1
        QTimer.singleShot(350, self._run_step)

    def _finish(self):
        self._done = True
        # Calcular factor de corrección: comparar movimiento real vs esperado
        # Test +200px horizontal (index 3)
        if len(self._res) >= 4:
            _, rx, _, _, _, _ = self._res[3]   # +200 horizontal
            cx = self._lw // 2
            actual_move = rx - cx
            expected_move = 200
            factor_x = actual_move / expected_move if expected_move else 1.0
        else:
            factor_x = 1.0

        if len(self._res) >= 7:
            _, _, ry, _, _, _ = self._res[6]   # +200 vertical
            cy = self._lh // 2
            actual_move = ry - cy
            factor_y = actual_move / 200 if 200 else 1.0
        else:
            factor_y = 1.0

        self._factor_x = factor_x
        self._factor_y = factor_y

        all_ok = all(r[5] for r in self._res)
        if all_ok:
            self._factor_lbl.setText(
                f"✅  Calibración perfecta — factor X={factor_x:.3f} Y={factor_y:.3f}")
            self._factor_lbl.setStyleSheet(
                "color: #FFE66D; font-family: 'Segoe UI'; background: transparent;")
        else:
            self._factor_lbl.setText(
                f"⚠  Factor corrección X={factor_x:.3f} Y={factor_y:.3f}  "
                f"(aplicado automáticamente)")
            self._factor_lbl.setStyleSheet(
                "color: #FF6B6B; font-family: 'Segoe UI'; background: transparent;")

        self._ok_btn.setEnabled(True)
        self.update()

    # ── Dibujo del grid ───────────────────────────────────────────────────────
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # Fondo oscuro semitransparente
        p.fillRect(self.rect(), QColor(10, 20, 30, 210))

        lw, lh = self._lw, self._lh

        # 500 columnas — líneas turquesa
        for i in range(501):
            x = int(i * lw / 500)
            if i % 100 == 0:
                p.setPen(QPen(_TEAL, 2))
                p.setFont(QFont("Segoe UI", 9, QFont.Bold))
                p.setPen(QPen(_TEAL, 2))
                p.drawLine(x, 0, x, lh)
                p.setPen(QPen(_SAND, 1))
                p.drawText(x + 3, 14, str(i))
            elif i % 50 == 0:
                p.setPen(QPen(QColor(78, 205, 196, 100), 1))
                p.drawLine(x, 0, x, lh)
            else:
                p.setPen(QPen(QColor(78, 205, 196, 28), 1))
                p.drawLine(x, 0, x, lh)

        # 500 filas — líneas coral
        for i in range(501):
            y = int(i * lh / 500)
            if i % 100 == 0:
                p.setPen(QPen(_CORAL, 2))
                p.drawLine(0, y, lw, y)
                p.setPen(QPen(_SAND, 1))
                p.setFont(QFont("Segoe UI", 9, QFont.Bold))
                p.drawText(3, y + 13, str(i))
            elif i % 50 == 0:
                p.setPen(QPen(QColor(255, 107, 107, 90), 1))
                p.drawLine(0, y, lw, y)
            else:
                p.setPen(QPen(QColor(255, 107, 107, 22), 1))
                p.drawLine(0, y, lw, y)

        # Punto del mouse en la última posición medida
        if self._dot:
            dx, dy = self._dot.x(), self._dot.y()
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(QColor(255, 230, 109, 80)))
            p.drawEllipse(QPoint(dx, dy), 20, 20)
            p.setBrush(QBrush(_CORAL))
            p.drawEllipse(QPoint(dx, dy), 7, 7)

        p.end()

    def result(self) -> dict:
        fx = getattr(self, "_factor_x", 1.0)
        fy = getattr(self, "_factor_y", 1.0)
        return {
            "scale_x": 1.0,
            "scale_y": 1.0,
            "factor_x": round(fx, 4),
            "factor_y": round(fy, 4),
            "logical_w": self._lw,
            "logical_h": self._lh,
            "ok": all(r[5] for r in self._res),
        }


def calibrate(qt_app) -> dict:
    """Muestra el diálogo visual de calibración y retorna el resultado."""
    dlg = _Grid()
    dlg.exec_()
    return dlg.result()
