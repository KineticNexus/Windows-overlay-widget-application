"""
Calibración empírica de pantalla por movimiento de mouse.

Procedimiento:
1. Registrar resolución física (mss) y lógica (Qt).
2. Mover el mouse 200 unidades pynput en X y en Y.
3. Medir cuántos pixels lógicos se desplazó realmente.
4. Calcular escala física→lógica con corrección empírica.
5. Si el mouse no llegó al lugar esperado, retornar ok=False.
"""
import time

import mss
from pynput.mouse import Controller


def calibrate(qt_app) -> dict:
    """Retorna dict con scale_x, scale_y y campo 'ok'."""

    # ── 1. Resoluciones ──────────────────────────────────────────────────────
    with mss.mss() as sct:
        mon       = sct.monitors[1]
        phys_w    = mon["width"]
        phys_h    = mon["height"]

    screen    = qt_app.primaryScreen()
    logical_w = screen.geometry().width()
    logical_h = screen.geometry().height()

    base_sx = phys_w / logical_w if logical_w > 0 else 1.0
    base_sy = phys_h / logical_h if logical_h > 0 else 1.0

    # ── 2. Mover mouse y medir desplazamiento real ───────────────────────────
    mouse     = Controller()
    MOVE      = 200     # unidades pynput a mover
    TOLERANCE = 10      # error aceptable en pixels

    cx = logical_w // 2
    cy = logical_h // 2

    # Horizontal
    mouse.position = (cx, cy)
    time.sleep(0.25)
    x0, _ = mouse.position
    mouse.move(MOVE, 0)
    time.sleep(0.25)
    x1, _ = mouse.position
    delta_x = x1 - x0

    # Vertical
    mouse.position = (cx, cy)
    time.sleep(0.25)
    _, y0 = mouse.position
    mouse.move(0, MOVE)
    time.sleep(0.25)
    _, y1 = mouse.position
    delta_y = y1 - y0

    # Volver al centro
    mouse.position = (cx, cy)

    # ── 3. Calcular escala real ───────────────────────────────────────────────
    # Si pynput move(200,0) produjo menos de 200 pixels lógicos,
    # hay una corrección necesaria (DPI fraccional, multi-monitor, etc.)
    corr_x  = MOVE / delta_x if delta_x > 0 else 1.0
    corr_y  = MOVE / delta_y if delta_y > 0 else 1.0

    scale_x = round(base_sx * corr_x, 4)
    scale_y = round(base_sy * corr_y, 4)

    ok = (abs(delta_x - MOVE) <= TOLERANCE and
          abs(delta_y - MOVE) <= TOLERANCE)

    return {
        "scale_x":    scale_x,
        "scale_y":    scale_y,
        "physical_w": phys_w,
        "physical_h": phys_h,
        "logical_w":  logical_w,
        "logical_h":  logical_h,
        "ok":         ok,
        "delta_x":    delta_x,
        "delta_y":    delta_y,
        "expected":   MOVE,
    }
