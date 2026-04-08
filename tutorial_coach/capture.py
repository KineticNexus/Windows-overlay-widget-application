"""
Captura de pantalla.

Arquitectura matemática:
  1. mss captura en píxeles FÍSICOS del hardware.
  2. La imagen se redimensiona a píxeles LÓGICOS (Qt / pynput) ANTES del grid.
  3. El grid muestra etiquetas de PORCENTAJE (0%, 25%, 50%, 75%, 100%).
  4. Claude devuelve coordenadas NORMALIZADAS (fracciones 0.000–1.000).
  5. app.py multiplica por las dimensiones lógicas para dibujar el overlay.
  → Invariante a DPI, resolución y versión de Windows. Alineación perfecta.
"""
import base64
import time
from io import BytesIO

import mss
from PIL import Image, ImageDraw, ImageFont

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


def _draw_grid(img: Image.Image, lw: int, lh: int):
    """
    Dibuja cuadrícula con etiquetas de PORCENTAJE.
    Líneas principales en 0%, 25%, 50%, 75%, 100%.
    Líneas secundarias en 10%, 20%, 30%, 40%, 60%, 70%, 80%, 90%.
    La imagen ya está redimensionada a (lw × lh) antes de llamar esta función.
    """
    draw = ImageDraw.Draw(img, "RGBA")

    try:
        font_big = ImageFont.truetype("arial.ttf", 20)
        font_sm  = ImageFont.truetype("arial.ttf", 13)
    except OSError:
        font_big = ImageFont.load_default()
        font_sm  = font_big

    RED_MAIN = (220, 50,  50, 200)
    RED_SUB  = (220, 50,  50, 110)
    BG_LBL   = (255, 255, 255, 220)

    MAJOR = {0, 25, 50, 75, 100}
    MINOR = {10, 20, 30, 40, 60, 70, 80, 90}

    # ── Líneas verticales ──────────────────────────────────────────────────────
    for pct in sorted(MAJOR | MINOR):
        x   = int(pct * lw / 100)
        lbl = f"{pct}%"
        tw  = len(lbl) * 10

        if pct in MAJOR:
            draw.line([(x, 0), (x, lh)], fill=(220, 50, 50, 130), width=2)
            # Etiqueta arriba
            draw.rectangle([x + 2, 2, x + 2 + tw, 26], fill=BG_LBL)
            draw.text((x + 4, 4), lbl, fill=RED_MAIN, font=font_big)
            # Etiqueta abajo
            draw.rectangle([x + 2, lh - 26, x + 2 + tw, lh - 2], fill=BG_LBL)
            draw.text((x + 4, lh - 24), lbl, fill=RED_MAIN, font=font_sm)
        else:
            draw.line([(x, 0), (x, lh)], fill=(220, 50, 50, 50), width=1)
            draw.rectangle([x + 2, 2, x + 2 + tw, 20], fill=BG_LBL)
            draw.text((x + 4, 3), lbl, fill=RED_SUB, font=font_sm)

    # ── Líneas horizontales ────────────────────────────────────────────────────
    for pct in sorted(MAJOR | MINOR):
        y   = int(pct * lh / 100)
        lbl = f"{pct}%"
        tw  = len(lbl) * 10

        if pct in MAJOR:
            draw.line([(0, y), (lw, y)], fill=(220, 50, 50, 130), width=2)
            # Etiqueta izquierda
            draw.rectangle([2, y + 2, 2 + tw, y + 26], fill=BG_LBL)
            draw.text((4, y + 4), lbl, fill=RED_MAIN, font=font_big)
            # Etiqueta derecha
            draw.rectangle([lw - 2 - tw, y + 2, lw - 2, y + 26], fill=BG_LBL)
            draw.text((lw - tw, y + 4), lbl, fill=RED_MAIN, font=font_sm)
        else:
            draw.line([(0, y), (lw, y)], fill=(220, 50, 50, 50), width=1)
            draw.rectangle([2, y + 2, 2 + tw, y + 20], fill=BG_LBL)
            draw.text((4, y + 3), lbl, fill=RED_SUB, font=font_sm)


def capture_screen(with_grid: bool = True) -> tuple:
    """
    Captura, redimensiona a lógico, dibuja grid de porcentajes, codifica.

    Returns:
        (base64_jpeg, logical_width, logical_height)
        Las coordenadas del grid son PORCENTAJES → Claude devuelve fracciones 0.0–1.0.
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
    if img.size != (lw, lh):
        img = img.resize((lw, lh), Image.LANCZOS)

    if with_grid:
        _draw_grid(img, lw, lh)

    # Si la resolución lógica supera 1920, reducir para limitar tokens de API.
    # lw/lh devueltos siguen siendo los lógicos reales — Claude dará fracciones
    # que se multiplican por lw/lh en app.py.
    if lw > 1920:
        scale = 1920 / lw
        img = img.resize((1920, int(lh * scale)), Image.LANCZOS)

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode(), lw, lh
