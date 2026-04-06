"""Captura de pantalla con cuadrícula de coordenadas para Claude."""
import base64
from io import BytesIO

import mss
from PIL import Image, ImageDraw, ImageFont

from tutorial_coach.config import GRID_STEP


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


def get_dpi_scale() -> float:
    """Devuelve el factor de escala DPI del monitor primario."""
    try:
        from PyQt5.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            return screen.devicePixelRatio()
    except Exception:
        pass
    return 1.0


def capture_screen(with_grid: bool = True) -> tuple:
    """
    Captura la pantalla principal.

    Returns:
        (base64_jpeg, physical_width, physical_height, dpi_scale)
    """
    with mss.mss() as sct:
        mon = sct.monitors[1]
        pw, ph = mon["width"], mon["height"]
        shot = sct.grab(mon)
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

    if with_grid:
        _draw_grid(img, pw, ph)

    # Solo escalar si supera 1920px (reducir tokens, mantener legibilidad)
    if pw > 1920:
        img.thumbnail((1920, 1920), Image.LANCZOS)

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode(), pw, ph, get_dpi_scale()
