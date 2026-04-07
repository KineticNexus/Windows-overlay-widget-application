"""Overlay full-screen transparente — estilo Material Design / Google."""
import math

from PyQt5.QtCore import Qt, QTimer, QPoint, QRect, QPointF, QRectF
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont,
    QPolygonF, QPainterPath, QLinearGradient, QRadialGradient,
)
from PyQt5.QtWidgets import QApplication, QWidget

from tutorial_coach.config import ANIM_INTERVAL

# Paleta Material / Google
_BLUE      = QColor(26, 115, 232)        # #1a73e8
_BLUE_LITE = QColor(66, 133, 244, 60)    # highlight fill
_WHITE     = QColor(255, 255, 255)
_DARK      = QColor(32, 33, 36)          # texto oscuro
_GREY      = QColor(95, 99, 104)         # texto secundario
_BORDER    = QColor(218, 220, 224)


class AnnotationOverlay(QWidget):
    """Ventana full-screen transparente al input. Dibuja anotaciones tipo Google."""

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
            self._phase = (self._phase + 0.06) % (2 * math.pi)
            self.update()

    # ── Dibujo principal ──────────────────────────────────────────────────────
    def paintEvent(self, _):
        if not self.step:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)

        tx    = self.step["target_x"]
        ty    = self.step["target_y"]
        rw    = self.step.get("region_w", 120)
        rh    = self.step.get("region_h", 44)
        text  = self.step["instruction"]
        n     = self.step["n"]
        pulse = 0.70 + 0.30 * math.sin(self._phase)

        # 1 — Highlight del elemento objetivo
        self._draw_highlight(p, tx, ty, rw, rh, pulse)

        # 2 — Punto central pulsante
        self._draw_dot(p, tx, ty, pulse)

        # 3 — Burbuja de instrucción (Material card)
        bw, bh = 360, 108
        bx, by = self._bubble_pos(tx, ty, bw, bh)
        self._draw_card(p, bx, by, bw, bh, n, self.total, text)

        # 4 — Flecha estilo Google
        self._draw_arrow(p, bx + bw // 2, by + bh, tx, ty)

        p.end()

    # ── Highlight ─────────────────────────────────────────────────────────────
    def _draw_highlight(self, p, tx, ty, rw, rh, pulse):
        hw = int(rw / 2 * pulse) + 8
        hh = int(rh / 2 * pulse) + 6

        # Relleno interior azul muy sutil
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(_BLUE_LITE))
        p.drawRoundedRect(tx - hw, ty - hh, hw * 2, hh * 2, 6, 6)

        # Borde azul sólido
        pen = QPen(_BLUE, 2, Qt.SolidLine)
        pen.setCosmetic(True)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(tx - hw, ty - hh, hw * 2, hh * 2, 6, 6)

        # Esquinas de acento (pequeños cuadrados azules en las esquinas)
        sz = 7
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(_BLUE))
        for cx, cy in [
            (tx - hw, ty - hh), (tx + hw - sz, ty - hh),
            (tx - hw, ty + hh - sz), (tx + hw - sz, ty + hh - sz),
        ]:
            p.drawRect(cx, cy, sz, sz)

    # ── Punto central ─────────────────────────────────────────────────────────
    def _draw_dot(self, p, tx, ty, pulse):
        r_outer = int(14 * pulse)
        # Halo exterior
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(26, 115, 232, int(60 * pulse))))
        p.drawEllipse(QPoint(tx, ty), r_outer, r_outer)
        # Punto blanco con borde azul
        p.setPen(QPen(_BLUE, 2))
        p.setBrush(QBrush(_WHITE))
        p.drawEllipse(QPoint(tx, ty), 6, 6)

    # ── Posición de burbuja ───────────────────────────────────────────────────
    def _bubble_pos(self, tx, ty, bw, bh):
        margin = 80
        # Preferir arriba → izquierda → derecha → abajo
        candidates = [
            (tx - bw // 2,      ty - bh - margin),   # arriba
            (tx - bw - margin,  ty - bh // 2),        # izquierda
            (tx + margin,       ty - bh // 2),        # derecha
            (tx - bw // 2,      ty + margin),         # abajo
        ]
        for bx, by in candidates:
            if (bx >= 0 and bx + bw <= self._screen_w and
                    by >= 0 and by + bh <= self._screen_h):
                return bx, by
        # Fallback: anclado arriba-izquierda
        bx = max(0, min(tx - bw // 2, self._screen_w - bw))
        by = max(0, min(ty - bh - margin, self._screen_h - bh))
        return bx, by

    # ── Material card ─────────────────────────────────────────────────────────
    def _draw_card(self, p, bx, by, bw, bh, n, total, text):
        # Sombra acumulada (Material elevation 4)
        for offset, alpha in [(8, 3), (6, 6), (4, 10), (2, 16)]:
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(QColor(0, 0, 0, alpha)))
            sh = QPainterPath()
            sh.addRoundedRect(bx + offset, by + offset, bw, bh, 6, 6)
            p.drawPath(sh)

        # Fondo blanco
        card = QPainterPath()
        card.addRoundedRect(bx, by, bw, bh, 6, 6)
        p.setBrush(QBrush(QColor(255, 255, 255, 252)))
        p.setPen(QPen(_BORDER, 1))
        p.drawPath(card)

        # Franja azul superior (header)
        header = QPainterPath()
        header.addRoundedRect(bx, by, bw, 30, 6, 6)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(_BLUE))
        p.drawPath(header)
        # Rectángulo extra para cuadrar la mitad inferior del header
        p.drawRect(bx, by + 15, bw, 15)

        # Texto del paso en la franja
        p.setFont(QFont("Segoe UI", 10, QFont.Bold))
        p.setPen(_WHITE)
        p.drawText(QRect(bx, by, bw, 30), Qt.AlignCenter,
                   f"PASO {n} DE {total}")

        # Instrucción
        p.setFont(QFont("Segoe UI", 13, QFont.DemiBold))
        p.setPen(_DARK)
        p.drawText(
            QRect(bx + 14, by + 36, bw - 28, bh - 46),
            Qt.AlignVCenter | Qt.AlignLeft | Qt.TextWordWrap,
            text,
        )

    # ── Flecha estilo Google ──────────────────────────────────────────────────
    def _draw_arrow(self, p, x1, y1, x2, y2):
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if length < 50:
            return

        ux, uy = dx / length, dy / length
        stop = 22   # distancia desde punta al extremo de la línea
        ex   = x2 - ux * stop
        ey   = y2 - uy * stop

        # ── Línea principal ────────────────────────────────────────────────
        # Sombra de línea
        p.setPen(QPen(QColor(0, 0, 0, 35), 6,
                      Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawLine(x1 + 2, y1 + 2, int(ex) + 2, int(ey) + 2)

        # Línea azul Google
        p.setPen(QPen(_BLUE, 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawLine(x1, y1, int(ex), int(ey))

        # ── Cabeza de flecha (chevron relleno) ─────────────────────────────
        angle = math.atan2(ey - y1, ex - x1)
        head  = 18
        wing  = 0.42   # rad — ángulo de las alas (~24°)

        tip = QPointF(x2, y2)
        lft = QPointF(
            x2 - head * math.cos(angle - wing),
            y2 - head * math.sin(angle - wing),
        )
        rgt = QPointF(
            x2 - head * math.cos(angle + wing),
            y2 - head * math.sin(angle + wing),
        )

        # Sombra de cabeza
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(0, 0, 0, 30)))
        p.drawPolygon(QPolygonF([
            QPointF(tip.x() + 2, tip.y() + 2),
            QPointF(lft.x() + 2, lft.y() + 2),
            QPointF(rgt.x() + 2, rgt.y() + 2),
        ]))

        # Cabeza azul
        p.setBrush(QBrush(_BLUE))
        p.drawPolygon(QPolygonF([tip, lft, rgt]))
