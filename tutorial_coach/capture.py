"""
Captura de pantalla.

Arquitectura matemática:
  1. mss captura en píxeles FÍSICOS del hardware.
  2. La imagen se redimensiona a píxeles LÓGICOS (Qt / pynput) ANTES del grid.
  3. El grid se dibuja en coordenadas lógicas.
  4. Claude lee coordenadas lógicas del grid y las devuelve.
  5. El overlay dibuja en esas mismas coordenadas lógicas.
  → Cero conversión de coordenadas. Alineación perfecta garantizada.
"""
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
        w.show()


def _logical_size():
    """Devuelve (width, height) en píxeles lógicos de Qt."""
    from PyQt5.QtWidgets import QApplication
    geo = QApplication.primaryScreen().geometry()
    return geo.width(), geo.height()


def _draw_grid(img: Image.Image, lw: int, lh: int, step: int = GRID_STEP):
    """
    Dibuja cuadrícula con etiquetas en coordenadas LÓGICAS.
    La imagen ya está redimensionada a (lw × lh) antes de llamar esta función.
    """
    draw = ImageDraw.Draw(img, "RGBA")

    try:
        font_big = ImageFont.truetype("arial.ttf", 20)
        font_sm  = ImageFont.truetype("arial.ttf", 14)
    except OSError:
        font_big = ImageFont.load_default()
        font_sm  = font_big

    RED    = (220, 50, 50, 200)
    BG_LBL = (255, 255, 255, 210)

    # Líneas verticales
    for x in range(0, lw, step):
        draw.line([(x, 0), (x, lh)], fill=(220, 50, 50, 70), width=1)
        lbl = str(x)
        tw  = len(lbl) * 12
        # Etiqueta arriba
        draw.rectangle([x + 2, 2, x + 2 + tw, 26], fill=BG_LBL)
        draw.text((x + 4, 4), lbl, fill=RED, font=font_big)
        # Etiqueta abajo
        draw.rectangle([x + 2, lh - 26, x + 2 + tw, lh - 2], fill=BG_LBL)
        draw.text((x + 4, lh - 24), lbl, fill=RED, font=font_sm)

    # Líneas horizontales
    for y in range(0, lh, step):
        draw.line([(0, y), (lw, y)], fill=(220, 50, 50, 70), width=1)
        lbl = str(y)
        tw  = len(lbl) * 12
        # Etiqueta izquierda
        draw.rectangle([2, y + 2, 2 + tw, y + 26], fill=BG_LBL)
        draw.text((4, y + 4), lbl, fill=RED, font=font_big)
        # Etiqueta derecha
        draw.rectangle([lw - 2 - tw, y + 2, lw - 2, y + 26], fill=BG_LBL)
        draw.text((lw - tw, y + 4), lbl, fill=RED, font=font_sm)


def capture_screen(with_grid: bool = True) -> tuple:
    """
    Captura, redimensiona a lógico, dibuja grid, codifica.

    Returns:
        (base64_jpeg, logical_width, logical_height)
        Las coordenadas del grid SON coordenadas lógicas — sin conversión.
    """
    lw, lh = _logical_size()

    _hide_widgets()
    try:
        with mss.mss() as sct:
            mon  = sct.monitors[1]
            shot = sct.grab(mon)
            img  = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    finally:
        _show_widgets()

    # Paso crítico: redimensionar a lógico ANTES del grid
    # Ahora cada pixel de la imagen = 1 pixel lógico Qt = 1 unidad pynput
    if img.size != (lw, lh):
        img = img.resize((lw, lh), Image.LANCZOS)

    if with_grid:
        _draw_grid(img, lw, lh)

    # Si la resolución lógica supera 1920 (pantallas muy grandes),
    # reducir para limitar tokens de API pero escalar las coordenadas
    # proporcionalmente (pasamos lw/lh al prompt, no las dimensiones de imagen)
    if lw > 1920:
        scale = 1920 / lw
        img = img.resize((1920, int(lh * scale)), Image.LANCZOS)
        # NOTA: lw/lh devueltos siguen siendo los lógicos reales
        # El prompt incluye lw/lh para que Claude dé coords en ese espacio

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode(), lw, lh
