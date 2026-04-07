"""Calibración de pantalla: mapeo entre píxeles físicos (mss/Claude) y lógicos (Qt/overlay)."""
import mss


def calibrate(qt_app) -> dict:
    """
    Compara la resolución física (lo que mss captura y Claude ve)
    contra la resolución lógica (lo que Qt usa para posicionar widgets).

    Returns dict con scale_x, scale_y, y las resoluciones.
    """
    # Resolución física (mss siempre captura a nivel de hardware)
    with mss.mss() as sct:
        mon = sct.monitors[1]
        phys_w = mon["width"]
        phys_h = mon["height"]

    # Resolución lógica (Qt usa esta para posicionar)
    screen = qt_app.primaryScreen()
    geo = screen.geometry()
    logical_w = geo.width()
    logical_h = geo.height()

    scale_x = phys_w / logical_w if logical_w > 0 else 1.0
    scale_y = phys_h / logical_h if logical_h > 0 else 1.0

    result = {
        "physical_w": phys_w,
        "physical_h": phys_h,
        "logical_w":  logical_w,
        "logical_h":  logical_h,
        "scale_x":    round(scale_x, 4),
        "scale_y":    round(scale_y, 4),
    }
    return result
