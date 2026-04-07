"""
Overlay full-screen transparente.
Paleta Tortuga: turquesa #00BCD4, coral #FF5722, verde-mar #26A69A.
"""
import math

from PyQt5.QtCore  import Qt, QTimer, QPoint, QRect, QPointF
from PyQt5.QtGui   import (
    QPainter, QColor, QPen, QBrush, QFont,
    QPolygonF, QPainterPath, QLinearGradient,
)
from PyQt5.QtWidgets import QApplication, QWidget

from tutorial_coach.config import ANIM_INTERVAL

# ── Paleta ────────────────────────────────────────────────────────────────────
_TEAL   = QColor(0,   188, 212)   # #00BCD4  cabecera de tarjeta
_TEAL2  = QColor(0,   131, 143)   # #00838F  gradiente más oscuro
_CORAL  = QColor(255,  87,  34)   # #FF5722  flecha / acento
_WHITE  = QColor(255, 255, 255)
_DARK   = QColor(  0,  77,  64)   # #004D40  texto principal
_GREY   = QColor( 80, 130, 120)   # texto secundario
_RING   = QColor(  0, 188, 212, 90)   # halo del target


class AnnotationOverlay(QWidget):
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
        self._sw       = screen.width()
        self._sh       = screen.height()

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
            self._phase = (self._phase + 0.055) % (2 * math.pi)
            self.update()

    # ── Paint ─────────────────────────────────────────────────────────────────
    def paintEvent(self, _):
        if not self.step:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)

        tx     = self.step["target_x"]
        ty     = self.step["target_y"]
        rw     = max(self.step.get("region_w", 120), 60)
        rh     = max(self.step.get("region_h", 44),  28)
        text   = self.step["instruction"]
        n      = self.step["n"]
        pulse  = 0.65 + 0.35 * math.sin(self._phase)

        # 1) Anillo pulsante en el target
        self._draw_ring(p, tx, ty, rw, rh, pulse)

        # 2) Tarjeta de instrucción
        bw, bh = 320, 104
        bx, by = self._card_pos(tx, ty, bw, bh)
        self._draw_card(p, bx, by, bw, bh, n, self.total, text)

        # 3) Flecha coral — del borde de la tarjeta al target
        tip_x, tip_y = self._arrow_root(bx, by, bw, bh, tx, ty)
        self._draw_arrow(p, tip_x, tip_y, tx, ty)

        p.end()

    # ── Anillo pulsante ───────────────────────────────────────────────────────
    def _draw_ring(self, p, tx, ty, rw, rh, pulse):
        hw = int(rw / 2 * pulse) + 12
        hh = int(rh / 2 * pulse) + 8

        # Relleno interior muy sutil
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(0, 188, 212, int(30 * pulse))))
        p.drawRoundedRect(tx - hw, ty - hh, hw * 2, hh * 2, 8, 8)

        # Borde teal sólido, 3px
        p.setPen(QPen(_TEAL, 3, Qt.SolidLine))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(tx - hw, ty - hh, hw * 2, hh * 2, 8, 8)

        # Punto central blanco con borde coral
        p.setPen(QPen(_CORAL, 3))
        p.setBrush(QBrush(_WHITE))
        p.drawEllipse(QPoint(tx, ty), 7, 7)

    # ── Posición de la tarjeta ────────────────────────────────────────────────
    def _card_pos(self, tx, ty, bw, bh):
        margin = 70
        candidates = [
            (tx - bw // 2,  ty - bh - margin),   # arriba
            (tx - bw - margin, ty - bh // 2),     # izquierda
            (tx + margin,   ty - bh // 2),        # derecha
            (tx - bw // 2,  ty + margin),         # abajo
        ]
        for bx, by in candidates:
            if bx >= 4 and bx + bw <= self._sw - 4 and \
               by >= 4 and by + bh <= self._sh - 4:
                return bx, by
        # fallback
        bx = max(4, min(tx - bw // 2, self._sw - bw - 4))
        by = max(4, min(ty - bh - margin, self._sh - bh - 4))
        return bx, by

    # ── Punto de inicio de la flecha (borde de tarjeta más cercano al target) ─
    def _arrow_root(self, bx, by, bw, bh, tx, ty):
        cx = bx + bw // 2
        cy = by + bh // 2
        # Centro de cada borde
        edges = [
            (bx + bw // 2, by),           # arriba
            (bx + bw // 2, by + bh),      # abajo
            (bx,           by + bh // 2), # izquierda
            (bx + bw,      by + bh // 2), # derecha
        ]
        best = min(edges, key=lambda e: math.hypot(e[0] - tx, e[1] - ty))
        return best

    # ── Tarjeta ───────────────────────────────────────────────────────────────
    def _draw_card(self, p, bx, by, bw, bh, n, total, text):
        HDR = 30   # altura del header

        # Sombra realista (4 capas)
        for off, a in [(10, 2), (7, 5), (4, 10), (2, 18)]:
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(QColor(0, 0, 0, a)))
            sh = QPainterPath()
            sh.addRoundedRect(bx + off, by + off, bw, bh, 6, 6)
            p.drawPath(sh)

        # Cuerpo blanco
        card = QPainterPath()
        card.addRoundedRect(bx, by, bw, bh, 6, 6)
        p.setBrush(QBrush(QColor(255, 255, 255, 252)))
        p.setPen(QPen(QColor(0, 188, 212, 80), 1))
        p.drawPath(card)

        # Header con gradiente teal
        grad = QLinearGradient(bx, by, bx + bw, by)
        grad.setColorAt(0.0, _TEAL)
        grad.setColorAt(1.0, _TEAL2)

        hdr_path = QPainterPath()
        hdr_path.addRoundedRect(bx, by, bw, HDR, 6, 6)
        # Rectángulo extra para cuadrar la mitad inferior del header
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(grad))
        p.drawPath(hdr_path)
        p.drawRect(bx, by + HDR // 2, bw, HDR // 2)

        # Texto del paso
        p.setFont(QFont("Segoe UI", 10, QFont.Bold))
        p.setPen(_WHITE)
        p.drawText(QRect(bx, by, bw, HDR),
                   Qt.AlignCenter, f"Paso {n} de {total}")

        # Instrucción
        p.setFont(QFont("Segoe UI", 13, QFont.DemiBold))
        p.setPen(_DARK)
        inner = QRect(bx + 14, by + HDR + 8, bw - 28, bh - HDR - 16)
        p.drawText(inner,
                   Qt.AlignVCenter | Qt.AlignLeft | Qt.TextWordWrap,
                   text)

    # ── Flecha coral ─────────────────────────────────────────────────────────
    def _draw_arrow(self, p, x1, y1, x2, y2):
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if length < 30:
            return

        ux, uy = dx / length, dy / length
        STOP  = 20        # distancia punta → fin de línea
        ex    = x2 - ux * STOP
        ey    = y2 - uy * STOP

        # Sombra de línea
        p.setPen(QPen(QColor(0, 0, 0, 40), 9,
                      Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawLine(x1, y1, int(ex), int(ey))

        # Línea coral, 6px
        p.setPen(QPen(_CORAL, 6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawLine(x1, y1, int(ex), int(ey))

        # Cabeza de flecha (triángulo relleno)
        angle = math.atan2(ey - y1, ex - x1)
        HEAD  = 22
        WING  = 0.44   # ~25°

        tip = QPointF(x2, y2)
        lft = QPointF(x2 - HEAD * math.cos(angle - WING),
                      y2 - HEAD * math.sin(angle - WING))
        rgt = QPointF(x2 - HEAD * math.cos(angle + WING),
                      y2 - HEAD * math.sin(angle + WING))

        # Sombra de cabeza
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(0, 0, 0, 35)))
        p.drawPolygon(QPolygonF([
            QPointF(tip.x() + 3, tip.y() + 3),
            QPointF(lft.x() + 3, lft.y() + 3),
            QPointF(rgt.x() + 3, rgt.y() + 3),
        ]))

        # Cabeza coral
        p.setBrush(QBrush(_CORAL))
        p.drawPolygon(QPolygonF([tip, lft, rgt]))

        # Borde blanco en la punta para contraste
        p.setPen(QPen(_WHITE, 1.5))
        p.drawPolygon(QPolygonF([tip, lft, rgt]))
