"""Captura de pantalla con cuadrícula de coordenadas para Claude."""
import base64
import time
from io import BytesIO

import mss
from PIL import Image, ImageDraw, ImageFont

from tutorial_coach.config import GRID_STEP

_widgets_to_hide = []


def register_widgets(*widgets):
    _widgets_to_hide.clear()
    _widgets_to_hide.extend(widgets)


def _hide_widgets():
    """SOLO llamar desde el hilo principal."""
    from PyQt5.QtWidgets import QApplication
    for w in _widgets_to_hide:
        w.hide()
    QApplication.processEvents()
    time.sleep(0.10)


def _show_widgets():
    """SOLO llamar desde el hilo principal."""
    for w in _widgets_to_hide:
        w.show()          # show() — la geometría ya está fijada en __init__


def _draw_grid(img: Image.Image, w: int, h: int, step: int = GRID_STEP):
    """Cuadrícula con etiquetas grandes y legibles para Claude."""
    draw = ImageDraw.Draw(img, "RGBA")

    # Fuente grande para que Claude lea los números con claridad
    try:
        font_big  = ImageFont.truetype("arial.ttf", 22)
        font_small = ImageFont.truetype("arial.ttf", 16)
    except OSError:
        font_big  = ImageFont.load_default()
        font_small = font_big

    # Líneas verticales
    for x in range(0, w, step):
        draw.line([(x, 0), (x, h)], fill=(220, 50, 50, 80), width=1)
        # Fondo blanco detrás del número para legibilidad
        label = str(x)
        draw.rectangle([x + 2, 0, x + 2 + len(label) * 14, 26],
                       fill=(255, 255, 255, 180))
        draw.text((x + 4, 2), label, fill=(200, 30, 30, 255), font=font_big)

    # Líneas horizontales
    for y in range(0, h, step):
        draw.line([(0, y), (w, y)], fill=(220, 50, 50, 80), width=1)
        label = str(y)
        draw.rectangle([2, y + 2, 2 + len(label) * 14, y + 26],
                       fill=(255, 255, 255, 180))
        draw.text((4, y + 3), label, fill=(200, 30, 30, 255), font=font_big)


def capture_screen(with_grid: bool = True) -> tuple:
    """
    Oculta widgets, captura pantalla, restaura widgets.
    Returns: (base64_jpeg, physical_width, physical_height)
    """
    _hide_widgets()
    try:
        with mss.mss() as sct:
            mon = sct.monitors[1]
            pw, ph = mon["width"], mon["height"]
            shot = sct.grab(mon)
            img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    finally:
        _show_widgets()

    if with_grid:
        _draw_grid(img, pw, ph)

    # Limitar a 1920px de ancho para reducir tokens y coste
    if pw > 1920:
        img.thumbnail((1920, 1080), Image.LANCZOS)

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=82)
    return base64.b64encode(buf.getvalue()).decode(), pw, ph
