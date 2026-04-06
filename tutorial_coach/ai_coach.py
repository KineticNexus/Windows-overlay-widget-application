"""Motor de IA: genera planes, verifica pasos, responde preguntas libres."""
import json
import threading

import anthropic

from tutorial_coach.config import (
    MODEL, PLAN_SYSTEM, PLAN_USER, VERIFY_PROMPT,
    FREEQ_PROMPT, WHERE_PROMPT, GRID_STEP,
)
from tutorial_coach.capture import capture_screen
from tutorial_coach.signals import Signals


class AICoach:
    def __init__(self, api_key: str, signals: Signals):
        self.client  = anthropic.Anthropic(api_key=api_key)
        self.signals = signals
        self.goal    = ""
        self._busy   = False
        self._lock   = threading.Lock()

    # ── Utilidades ─────────────────────────────────────────────────────────────
    def _is_busy(self) -> bool:
        with self._lock:
            if self._busy:
                return True
            self._busy = True
            return False

    def _release(self):
        with self._lock:
            self._busy = False

    def _call_claude(self, system: str, user_text: str,
                     image_b64: str | None = None,
                     max_tokens: int = 600) -> str:
        """Llamada síncrona a Claude. Devuelve el texto de respuesta."""
        content = []
        if image_b64:
            content.append({
                "type": "image",
                "source": {"type": "base64",
                           "media_type": "image/jpeg",
                           "data": image_b64},
            })
        content.append({"type": "text", "text": user_text})

        resp = self.client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": content}],
        )
        return resp.content[0].text.strip()

    def _parse_json(self, raw: str) -> dict:
        """Extrae JSON de una respuesta que puede tener texto extra."""
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError(f"No se encontró JSON en la respuesta: {raw[:100]}")
        return json.loads(raw[start:end])

    def _bg(self, fn):
        """Ejecuta fn en un hilo daemon."""
        threading.Thread(target=fn, daemon=True).start()

    # ── Generar plan ───────────────────────────────────────────────────────────
    def generate_plan(self, goal: str):
        """Captura pantalla, genera plan paso a paso. No bloquea."""
        if self._is_busy():
            return
        self.goal = goal

        def _run():
            try:
                self.signals.status_changed.emit("Analizando pantalla…")
                img, w, h, _ = capture_screen(with_grid=True)
                prompt = PLAN_USER.format(goal=goal, w=w, h=h, grid=GRID_STEP)
                raw    = self._call_claude(PLAN_SYSTEM, prompt, img, max_tokens=800)
                plan   = self._parse_json(raw)

                if "steps" not in plan or not plan["steps"]:
                    raise ValueError("El plan no contiene pasos.")

                # Asegurar campos opcionales con defaults
                for s in plan["steps"]:
                    s.setdefault("region_w", 100)
                    s.setdefault("region_h", 40)
                    s.setdefault("element", "")

                self.signals.plan_ready.emit(plan)
                self.signals.status_changed.emit("Plan listo")

            except anthropic.AuthenticationError:
                self.signals.error_occurred.emit(
                    "API key inválida. Reinicia el programa con una clave correcta.")
            except json.JSONDecodeError as e:
                self.signals.error_occurred.emit(
                    f"Error leyendo respuesta de IA: {e}")
            except Exception as e:
                self.signals.error_occurred.emit(f"Error: {e}")
            finally:
                self._release()

        self._bg(_run)

    # ── Verificar paso completado ──────────────────────────────────────────────
    def verify_step(self, step: dict):
        """Re-captura la pantalla y pregunta a Claude si el paso se completó."""
        if self._is_busy():
            return

        def _run():
            try:
                self.signals.status_changed.emit("Verificando…")
                img, w, h, _ = capture_screen(with_grid=False)
                prompt = VERIFY_PROMPT.format(
                    goal=self.goal,
                    n=step["n"],
                    instruction=step["instruction"],
                    element=step.get("element", ""),
                )
                raw    = self._call_claude(PLAN_SYSTEM, prompt, img, max_tokens=200)
                result = self._parse_json(raw)
                result.setdefault("completed", False)
                result.setdefault("feedback", "")
                self.signals.verify_result.emit(result)
            except Exception as e:
                self.signals.verify_result.emit({
                    "completed": True,
                    "feedback": "",
                })
            finally:
                self._release()

        self._bg(_run)

    # ── Pregunta libre ─────────────────────────────────────────────────────────
    def ask_free(self, question: str, mouse_x: int = 0, mouse_y: int = 0):
        """Responde una pregunta del usuario sobre la pantalla actual."""
        if self._is_busy():
            return

        def _run():
            try:
                self.signals.status_changed.emit("Pensando…")
                img, _, _, _ = capture_screen(with_grid=False)
                prompt = FREEQ_PROMPT.format(
                    question=question, mx=mouse_x, my=mouse_y)
                answer = self._call_claude(PLAN_SYSTEM, prompt, img, max_tokens=300)
                self.signals.free_answer.emit(answer)
                self.signals.status_changed.emit("Listo")
            except Exception as e:
                self.signals.error_occurred.emit(f"Error: {e}")
            finally:
                self._release()

        self._bg(_run)

    # ── ¿Dónde estoy? ─────────────────────────────────────────────────────────
    def where_am_i(self):
        """Explica qué hay en pantalla ahora mismo."""
        if self._is_busy():
            return

        def _run():
            try:
                self.signals.status_changed.emit("Mirando tu pantalla…")
                img, _, _, _ = capture_screen(with_grid=False)
                answer = self._call_claude(PLAN_SYSTEM, WHERE_PROMPT, img, 250)
                self.signals.free_answer.emit(answer)
                self.signals.status_changed.emit("Listo")
            except Exception as e:
                self.signals.error_occurred.emit(f"Error: {e}")
            finally:
                self._release()

        self._bg(_run)
