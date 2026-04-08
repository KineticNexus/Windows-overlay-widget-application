"""Grabador de tutoriales: captura acciones del usuario para crear guías reutilizables."""
import time
import json
from dataclasses import dataclass, asdict, field

from pynput import mouse as pmouse

from tutorial_coach.capture import capture_screen
from tutorial_coach.memory import save_tutorial


@dataclass
class RecordedStep:
    n: int
    instruction: str = ""
    target_x: int = 0
    target_y: int = 0
    region_w: int = 100
    region_h: int = 40
    element: str = ""
    timestamp: float = 0.0


class TutorialRecorder:
    """Graba clicks del mouse como pasos de un tutorial."""

    def __init__(self, on_step_recorded=None):
        self._on_step  = on_step_recorded   # callback(step_dict)
        self._steps    = []
        self._listener = None
        self._active   = False
        self._counter  = 0

    @property
    def is_recording(self) -> bool:
        return self._active

    @property
    def steps(self) -> list[dict]:
        return [asdict(s) for s in self._steps]

    def start(self):
        """Inicia grabación."""
        self._steps   = []
        self._counter = 0
        self._active  = True
        self._listener = pmouse.Listener(on_click=self._on_click)
        self._listener.daemon = True
        self._listener.start()

    def stop(self) -> list[dict]:
        """Detiene grabación y devuelve los pasos."""
        self._active = False
        if self._listener:
            self._listener.stop()
            self._listener = None
        return self.steps

    def save(self, name: str) -> int:
        """Guarda el tutorial en la base de datos."""
        return save_tutorial(name, self.steps)

    def set_instruction(self, step_idx: int, text: str):
        """Agrega instrucción a un paso grabado."""
        if 0 <= step_idx < len(self._steps):
            self._steps[step_idx].instruction = text

    def _on_click(self, x, y, button, pressed):
        if not pressed or not self._active:
            return

        self._counter += 1
        step = RecordedStep(
            n=self._counter,
            target_x=int(x),
            target_y=int(y),
            instruction=f"Paso {self._counter}: presiona aquí",
            timestamp=time.time(),
        )
        self._steps.append(step)

        if self._on_step:
            self._on_step(asdict(step))
