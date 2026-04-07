"""
Overlay full-screen — paleta tropical Tortuga.

Colores:
  #1A535C  ocean deep    — texto oscuro
  #4ECDC4  turquoise     — anillos, borde de tarjeta
  #FF6B6B  coral warm    — flecha, punto central
  #FFE66D  sand yellow   — número de paso
  #F7FFF7  sea foam      — fondo tarjeta
"""
import math

from PyQt5.QtCore    import Qt, QTimer, QPoint, QPointF, QRect, QRectF
from PyQt5.QtGui     import (
    QPainter, QColor, QPen, QBrush, QFont,
    QPainterPath, QLinearGradient, QPolygonF, QRadialGradient,
)
from PyQt5.QtWidgets import QApplication, QWidget

from tutorial_coach.config import ANIM_INTERVAL

# ── Paleta ────────────────────────────────────────────────────────────────────
_DEEP   = QColor( 26,  83,  92)   # #1A535C
_TEAL   = QColor( 78, 205, 196)   # #4ECDC4
_TEAL2  = QColor( 38, 166, 154)   # #26A69A  gradiente
_CORAL  = QColor(255, 107, 107)   # #FF6B6B
_CORAL2 = QColor(255,  70,  70)   # más vivo para borde
_SAND   = QColor(255, 230, 109)   # #FFE66D
_FOAM   = QColor(247, 255, 247)   # #F7FFF7  fondo tarjeta
_WHITE  = QColor(255, 255, 255)
_SHADOW = QColor(  0,   0,   0)


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

        self.step   = None
        self.total  = 0
        self._phase = 0.0
        self._sw    = screen.width()
        self._sh    = screen.height()

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
            self._phase = (self._phase + 0.050) % (2 * math.pi)
            self.update()

    # ── Paint ─────────────────────────────────────────────────────────────────
    def paintEvent(self, _):
        if not self.step:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)

        tx    = self.step["target_x"]
        ty    = self.step["target_y"]
        rw    = max(self.step.get("region_w", 120), 50)
        rh    = max(self.step.get("region_h",  44), 24)
        text  = self.step["instruction"]
        n     = self.step["n"]
        pulse = 0.60 + 0.40 * math.sin(self._phase)

        # 1 — Anillos concéntricos pulsantes en el target
        self._draw_rings(p, tx, ty, rw, rh, pulse)

        # 2 — Tarjeta flotante
        bw, bh = 330, 112
        bx, by = self._card_pos(tx, ty, bw, bh)
        self._draw_card(p, bx, by, bw, bh, n, self.total, text)

        # 3 — Flecha curva coral del borde de tarjeta al target
        ox, oy = self._edge_point(bx, by, bw, bh, tx, ty)
        self._draw_curved_arrow(p, ox, oy, tx, ty)

        p.end()

    # ── Anillos pulsantes ─────────────────────────────────────────────────────
    def _draw_rings(self, p, tx, ty, rw, rh, pulse):
        # 3 anillos expandiéndose hacia afuera
        for i, (alpha_base, pad_base) in enumerate([(50, 28), (80, 16), (110, 6)]):
            r_alpha = int(alpha_base * pulse)
            pad     = int(pad_base  * pulse) + 2
            hw      = rw // 2 + pad
            hh      = rh // 2 + pad

            # Relleno sutil
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(QColor(78, 205, 196, r_alpha // 4)))
            p.drawRoundedRect(tx - hw, ty - hh, hw * 2, hh * 2, 10, 10)

            # Borde
            ring_color = _TEAL if i < 2 else _CORAL
            pen = QPen(ring_color, 2 - i * 0.5)
            pen.setColor(QColor(ring_color.red(), ring_color.green(),
                                ring_color.blue(), r_alpha))
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(tx - hw, ty - hh, hw * 2, hh * 2, 10, 10)

        # Punto central: círculo blanco con borde coral grueso
        p.setPen(QPen(_CORAL, 3))
        p.setBrush(QBrush(_WHITE))
        p.drawEllipse(QPoint(tx, ty), 8, 8)
        # Punto coral interior
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(_CORAL))
        p.drawEllipse(QPoint(tx, ty), 3, 3)

    # ── Posición de tarjeta ───────────────────────────────────────────────────
    def _card_pos(self, tx, ty, bw, bh):
        M = 80
        candidates = [
            (tx - bw // 2,  ty - bh - M),   # arriba
            (tx - bw - M,   ty - bh // 2),   # izquierda
            (tx + M,        ty - bh // 2),   # derecha
            (tx - bw // 2,  ty + M),         # abajo
        ]
        for bx, by in candidates:
            if 8 <= bx and bx + bw <= self._sw - 8 and \
               8 <= by and by + bh <= self._sh - 8:
                return bx, by
        bx = max(8, min(tx - bw // 2, self._sw - bw - 8))
        by = max(8, min(ty - bh - M,  self._sh - bh - 8))
        return bx, by

    def _edge_point(self, bx, by, bw, bh, tx, ty):
        """Punto en el borde de la tarjeta más cercano al target."""
        cx, cy = bx + bw // 2, by + bh // 2
        edges  = [
            (bx + bw // 2, by),
            (bx + bw // 2, by + bh),
            (bx,           by + bh // 2),
            (bx + bw,      by + bh // 2),
        ]
        return min(edges, key=lambda e: math.hypot(e[0]-tx, e[1]-ty))

    # ── Tarjeta ───────────────────────────────────────────────────────────────
    def _draw_card(self, p, bx, by, bw, bh, n, total, text):
        HDR = 32

        # Sombra suave — 5 capas con desplazamiento progresivo
        for off, a in [(12, 2), (9, 5), (6, 9), (3, 15), (1, 22)]:
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(QColor(0, 0, 0, a)))
            sh = QPainterPath()
            sh.addRoundedRect(bx + off, by + off, bw, bh, 8, 8)
            p.drawPath(sh)

        # Cuerpo — sea foam white
        body = QPainterPath()
        body.addRoundedRect(bx, by, bw, bh, 8, 8)
        p.setBrush(QBrush(QColor(247, 255, 247, 250)))
        p.setPen(QPen(QColor(78, 205, 196, 100), 1.5))
        p.drawPath(body)

        # Header — gradiente ocean deep → teal
        grad = QLinearGradient(bx, by, bx + bw, by + HDR)
        grad.setColorAt(0.0, QColor( 26,  83,  92))   # deep
        grad.setColorAt(0.6, QColor( 38, 130, 120))   # mid
        grad.setColorAt(1.0, QColor( 78, 205, 196))   # teal

        hdr = QPainterPath()
        hdr.addRoundedRect(bx, by, bw, HDR, 8, 8)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(grad))
        p.drawPath(hdr)
        p.drawRect(bx, by + HDR // 2, bw, HDR // 2)   # cuadrar esquinas inf

        # Número de paso (sand/amarillo brillante)
        p.setFont(QFont("Segoe UI", 10, QFont.Bold))
        p.setPen(_SAND)
        p.drawText(QRect(bx + 12, by, 80, HDR), Qt.AlignVCenter | Qt.AlignLeft,
                   f"Paso {n} de {total}")

        # Ícono tortuga — pequeño en header derecho
        p.setFont(QFont("Segoe UI", 14))
        p.setPen(QColor(78, 205, 196, 180))
        p.drawText(QRect(bx, by, bw - 10, HDR),
                   Qt.AlignVCenter | Qt.AlignRight, "🐢")

        # Línea separadora teal bajo el header
        p.setPen(QPen(QColor(78, 205, 196, 60), 1))
        p.drawLine(bx + 12, by + HDR, bx + bw - 12, by + HDR)

        # Instrucción — Segoe UI SemiBold, color deep ocean
        p.setFont(QFont("Segoe UI", 13, QFont.DemiBold))
        p.setPen(_DEEP)
        inner = QRect(bx + 14, by + HDR + 6, bw - 28, bh - HDR - 12)
        p.drawText(inner, Qt.AlignVCenter | Qt.AlignLeft | Qt.TextWordWrap, text)

    # ── Flecha curva coral ────────────────────────────────────────────────────
    def _draw_curved_arrow(self, p, x1, y1, x2, y2):
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if length < 30:
            return

        # Control points para curva de Bézier cuadrática
        # El punto de control se desplaza perpendicularmente a la línea
        perp_x = -dy / length * min(length * 0.35, 80)
        perp_y =  dx / length * min(length * 0.35, 80)
        cx1 = (x1 + x2) / 2 + perp_x
        cy1 = (y1 + y2) / 2 + perp_y

        # Calcular punto de inicio de la cabeza (20px antes del destino)
        # usando la tangente de la curva en t=1
        tx_tan = x2 - cx1
        ty_tan = y2 - cy1
        t_len  = math.hypot(tx_tan, ty_tan)
        if t_len < 1:
            return
        ux, uy = tx_tan / t_len, ty_tan / t_len
        STOP   = 22
        ex, ey = x2 - ux * STOP, y2 - uy * STOP

        # ── Sombra de la curva ─────────────────────────────────────────────
        shadow_path = QPainterPath()
        shadow_path.moveTo(x1 + 3, y1 + 3)
        shadow_path.quadTo(cx1 + 3, cy1 + 3, ex + 3, ey + 3)
        p.setPen(QPen(QColor(0, 0, 0, 35), 10,
                      Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        p.drawPath(shadow_path)

        # ── Curva principal — coral ────────────────────────────────────────
        path = QPainterPath()
        path.moveTo(x1, y1)
        path.quadTo(cx1, cy1, ex, ey)

        p.setPen(QPen(_CORAL, 6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)

        # Punto de salida — pequeño círculo turquesa
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(_TEAL))
        p.drawEllipse(QPointF(x1, y1), 5, 5)

        # ── Cabeza de flecha — triángulo coral ─────────────────────────────
        angle = math.atan2(ey - cy1, ex - cx1)
        HEAD  = 20
        WING  = 0.42

        tip = QPointF(x2, y2)
        lft = QPointF(x2 - HEAD * math.cos(angle - WING),
                      y2 - HEAD * math.sin(angle - WING))
        rgt = QPointF(x2 - HEAD * math.cos(angle + WING),
                      y2 - HEAD * math.sin(angle + WING))

        # Sombra de cabeza
        p.setBrush(QBrush(QColor(0, 0, 0, 30)))
        p.drawPolygon(QPolygonF([
            QPointF(tip.x()+3, tip.y()+3),
            QPointF(lft.x()+3, lft.y()+3),
            QPointF(rgt.x()+3, rgt.y()+3),
        ]))

        # Cabeza rellena
        p.setBrush(QBrush(_CORAL))
        p.setPen(QPen(_WHITE, 1.5))
        p.drawPolygon(QPolygonF([tip, lft, rgt]))
