"""Captura de pantalla con cuadrícula de coordenadas para Claude."""
import base64
import time
from io import BytesIO

import mss
from PIL import Image, ImageDraw, ImageFont

from tutorial_coach.config import GRID_STEP

# Referencia a los widgets para ocultarlos durante la captura
_widgets_to_hide = []


def register_widgets(*widgets):
    """Registra widgets que deben ocultarse antes de capturar."""
    _widgets_to_hide.clear()
    _widgets_to_hide.extend(widgets)


def _hide_widgets():
    """Oculta widgets antes de capturar. LLAMAR SOLO DESDE HILO PRINCIPAL."""
    from PyQt5.QtWidgets import QApplication
    for w in _widgets_to_hide:
        w.hide()
    QApplication.processEvents()   # procesar repintado antes de capturar
    time.sleep(0.08)               # Windows necesita tiempo extra para recomponer


def _show_widgets():
    """Restaura widgets después de capturar. LLAMAR SOLO DESDE HILO PRINCIPAL."""
    for w in _widgets_to_hide:
        if hasattr(w, "showFullScreen"):
            w.showFullScreen()
        else:
            w.show()


def _draw_grid(img: Image.Image, w: int, h: int, step: int = GRID_STEP):
    """Dibuja cuadrícula roja sutil con etiquetas de coordenadas reales."""
    draw = ImageDraw.Draw(img, "RGBA")
    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except OSError:
        font = ImageFont.load_default()

    for x in range(0, w, step):
        draw.line([(x, 0), (x, h)], fill=(255, 60, 60, 50), width=1)
        draw.text((x + 3, 3),      str(x), fill=(255, 60, 60, 210), font=font)
        draw.text((x + 3, h - 18), str(x), fill=(255, 60, 60, 160), font=font)

    for y in range(0, h, step):
        draw.line([(0, y), (w, y)], fill=(255, 60, 60, 50), width=1)
        draw.text((3, y + 3),      str(y), fill=(255, 60, 60, 210), font=font)
        draw.text((w - 50, y + 3), str(y), fill=(255, 60, 60, 160), font=font)


def capture_screen(with_grid: bool = True) -> tuple:
    """
    Oculta widgets, captura la pantalla, restaura widgets.

    Returns:
        (base64_jpeg, physical_width, physical_height)
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

    if pw > 1920:
        img.thumbnail((1920, 1920), Image.LANCZOS)

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode(), pw, ph
