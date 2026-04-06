"""Overlay full-screen transparente con anotaciones animadas."""
import math

from PyQt5.QtCore import Qt, QTimer, QPoint, QRect, QPointF
from PyQt5.QtGui import (QPainter, QColor, QPen, QBrush, QFont,
                          QPolygonF, QPainterPath, QLinearGradient)
from PyQt5.QtWidgets import QApplication, QWidget

from tutorial_coach.config import ANIM_INTERVAL


class AnnotationOverlay(QWidget):
    """Ventana full-screen transparente al input. Dibuja flechas y glow."""

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

        self.step      = None
        self.total     = 0
        self._phase    = 0.0
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

    def _tick(self):
        if self.step:
            self._phase = (self._phase + 0.07) % (2 * math.pi)
            self.update()

    # ── Dibujo principal ──────────────────────────────────────────────────────
    def paintEvent(self, _):
        if not self.step:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)

        tx = self.step["target_x"]
        ty = self.step["target_y"]
        rw = self.step.get("region_w", 100)
        rh = self.step.get("region_h", 40)
        instruction = self.step["instruction"]
        step_n = self.step["n"]
        pulse  = 0.75 + 0.25 * math.sin(self._phase)
        bounce = int(5 * math.sin(self._phase * 1.2))

        # ── 1. Highlight de región (rectángulo pulsante) ──────────────────
        hw = int(rw * pulse / 2) + 10
        hh = int(rh * pulse / 2) + 6
        for alpha, pad in [(20, 14), (40, 8), (70, 2)]:
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(QColor(56, 220, 180, alpha)))
            p.drawRoundedRect(
                tx - hw - pad, ty - hh - pad,
                (hw + pad) * 2, (hh + pad) * 2, 8, 8)

        # Borde nítido
        p.setPen(QPen(QColor(56, 220, 180, 200), 2))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(tx - hw, ty - hh, hw * 2, hh * 2, 6, 6)

        # ── 2. Punto central ──────────────────────────────────────────────
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(255, 255, 255, 220)))
        p.drawEllipse(QPoint(tx, ty), 4, 4)

        # ── 3. Burbuja ────────────────────────────────────────────────────
        bw, bh = 340, 115
        bx, by = self._bubble_pos(tx, ty, bw, bh)
        by += bounce
        self._draw_bubble(p, bx, by, bw, bh, step_n, self.total, instruction)

        # ── 4. Flecha ─────────────────────────────────────────────────────
        self._draw_arrow(p, bx + bw // 2, by + bh // 2, tx, ty)

        p.end()

    # ── Posición de burbuja ───────────────────────────────────────────────────
    def _bubble_pos(self, tx, ty, bw, bh):
        margin = 90
        for bx, by in [
            (tx - bw - margin, ty - bh // 2),
            (tx + margin,       ty - bh // 2),
            (tx - bw // 2,      ty - bh - margin),
            (tx - bw // 2,      ty + margin),
        ]:
            if 0 <= bx and bx + bw <= self._screen_w and \
               0 <= by and by + bh <= self._screen_h:
                return bx, by
        return 20, 20

    # ── Burbuja glassmorphism ─────────────────────────────────────────────────
    def _draw_bubble(self, p, bx, by, bw, bh, step_n, total, text):
        rect = QRect(bx, by, bw, bh)

        # Sombra
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(0, 0, 0, 50)))
        sh = QPainterPath()
        sh.addRoundedRect(bx + 3, by + 3, bw, bh, 16, 16)
        p.drawPath(sh)

        # Fondo
        grad = QLinearGradient(bx, by, bx, by + bh)
        grad.setColorAt(0, QColor(8,  14, 32, 225))
        grad.setColorAt(1, QColor(14, 22, 48, 215))
        p.setBrush(QBrush(grad))
        p.setPen(QPen(QColor(56, 220, 180, 160), 1))
        bg = QPainterPath()
        bg.addRoundedRect(bx, by, bw, bh, 16, 16)
        p.drawPath(bg)

        # Línea acento
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(56, 220, 180, 100)))
        p.drawRoundedRect(bx + 1, by + 1, bw - 2, 3, 2, 2)

        # Paso
        p.setFont(QFont("Arial", 9, QFont.Bold))
        p.setPen(QColor(56, 220, 180, 200))
        p.drawText(rect.adjusted(14, 8, -14, 0),
                   Qt.AlignTop | Qt.AlignLeft,
                   f"PASO {step_n} DE {total}")

        # Instrucción
        p.setFont(QFont("Arial", 14, QFont.Bold))
        p.setPen(QColor(235, 240, 255))
        p.drawText(rect.adjusted(14, 26, -14, -10),
                   Qt.AlignVCenter | Qt.AlignLeft | Qt.TextWordWrap,
                   text)

    # ── Flecha teal ───────────────────────────────────────────────────────────
    def _draw_arrow(self, p, x1, y1, x2, y2):
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if length < 40:
            return

        short = 35
        ex = x2 - int(dx / length * short)
        ey = y2 - int(dy / length * short)

        # Sombra
        p.setPen(QPen(QColor(0, 0, 0, 70), 5, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(x1 + 2, y1 + 2, ex + 2, ey + 2)
        # Línea
        p.setPen(QPen(QColor(56, 220, 180, 190), 3, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(x1, y1, ex, ey)

        # Cabeza
        angle = math.atan2(ey - y1, ex - x1)
        head = 13
        pts = QPolygonF([
            QPointF(ex, ey),
            QPointF(ex - head * math.cos(angle - 0.4),
                    ey - head * math.sin(angle - 0.4)),
            QPointF(ex - head * math.cos(angle + 0.4),
                    ey - head * math.sin(angle + 0.4)),
        ])
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(56, 220, 180, 230)))
        p.drawPolygon(pts)
