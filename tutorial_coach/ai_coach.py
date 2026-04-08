"""Motor de IA: genera planes, verifica pasos, responde preguntas libres.

Threading:
  - capture_screen() corre en hilo principal (Qt).
  - Solo la llamada a Claude va al hilo de fondo.
  - Signals PyQt5 cross-thread son thread-safe (queued connections).
"""
import json
import threading

import anthropic

from tutorial_coach.config import (
    MODEL, PLAN_SYSTEM, PLAN_USER, VERIFY_PROMPT,
    FREEQ_PROMPT, WHERE_PROMPT,
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
                     max_tokens: int = 1024) -> str:
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
        """Extrae JSON robusto: intenta múltiples estrategias antes de fallar."""
        # Estrategia 1: texto directo
        try:
            return json.loads(raw.strip())
        except json.JSONDecodeError:
            pass

        # Estrategia 2: primer { hasta último }
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(raw[start:end])
            except json.JSONDecodeError:
                pass

        # Estrategia 3: seguir llaves correctamente (ignora truncaciones)
        if start != -1:
            depth     = 0
            in_str    = False
            escaped   = False
            for i, c in enumerate(raw[start:], start):
                if escaped:
                    escaped = False
                    continue
                if c == "\\" and in_str:
                    escaped = True
                    continue
                if c == '"':
                    in_str = not in_str
                    continue
                if not in_str:
                    if c == "{":
                        depth += 1
                    elif c == "}":
                        depth -= 1
                        if depth == 0:
                            try:
                                return json.loads(raw[start:i + 1])
                            except json.JSONDecodeError:
                                break

        raise ValueError(f"Respuesta de IA no contiene JSON válido: {raw[:200]}")

    def _bg(self, fn):
        threading.Thread(target=fn, daemon=True).start()

    # ── Generar plan ───────────────────────────────────────────────────────────
    def generate_plan(self, goal: str):
        if self._is_busy():
            return
        self.goal = goal

        # Captura en hilo principal
        try:
            self.signals.status_changed.emit("Capturando pantalla…")
            img, pw, ph = capture_screen(with_grid=True)
        except Exception as e:
            self._release()
            self.signals.error_occurred.emit(f"Error capturando pantalla: {e}")
            return

        def _run():
            try:
                self.signals.status_changed.emit("Tortuga está pensando…")
                prompt = PLAN_USER.format(goal=goal)
                # 2000 tokens — suficiente para 6 pasos con room to spare
                raw  = self._call_claude(PLAN_SYSTEM, prompt, img, max_tokens=2000)
                plan = self._parse_json(raw)

                if "steps" not in plan or not plan["steps"]:
                    raise ValueError("El plan no tiene pasos.")

                for s in plan["steps"]:
                    s.setdefault("region_w", 0.08)   # 8% del ancho
                    s.setdefault("region_h", 0.04)   # 4% del alto
                    s.setdefault("element", "")

                self.signals.plan_ready.emit(plan)
                self.signals.status_changed.emit("Listo")

            except anthropic.AuthenticationError:
                self.signals.error_occurred.emit(
                    "API key inválida. Reinicia Tortuga con la clave correcta.")
            except json.JSONDecodeError as e:
                self.signals.error_occurred.emit(f"Error de formato IA: {e}")
            except Exception as e:
                self.signals.error_occurred.emit(f"Error: {e}")
            finally:
                self._release()

        self._bg(_run)

    # ── Verificar paso ─────────────────────────────────────────────────────────
    def verify_step(self, step: dict):
        if self._is_busy():
            return

        try:
            img, pw, ph = capture_screen(with_grid=False)
        except Exception:
            self._release()
            self.signals.verify_result.emit({"completed": True, "feedback": ""})
            return

        def _run():
            try:
                self.signals.status_changed.emit("Verificando…")
                prompt = VERIFY_PROMPT.format(
                    goal=self.goal,
                    n=step["n"],
                    instruction=step["instruction"],
                    element=step.get("element", ""),
                )
                raw    = self._call_claude(PLAN_SYSTEM, prompt, img, max_tokens=256)
                result = self._parse_json(raw)
                result.setdefault("completed", False)
                result.setdefault("feedback", "")
                self.signals.verify_result.emit(result)
            except Exception:
                self.signals.verify_result.emit({"completed": True, "feedback": ""})
            finally:
                self._release()

        self._bg(_run)

    # ── Pregunta libre ─────────────────────────────────────────────────────────
    def ask_free(self, question: str, mouse_x: int = 0, mouse_y: int = 0):
        if self._is_busy():
            return

        try:
            img, _, _ = capture_screen(with_grid=False)
        except Exception as e:
            self._release()
            self.signals.error_occurred.emit(f"Error capturando: {e}")
            return

        def _run():
            try:
                self.signals.status_changed.emit("Pensando…")
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
        if self._is_busy():
            return

        try:
            img, _, _ = capture_screen(with_grid=False)
        except Exception as e:
            self._release()
            self.signals.error_occurred.emit(f"Error capturando: {e}")
            return

        def _run():
            try:
                self.signals.status_changed.emit("Mirando tu pantalla…")
                answer = self._call_claude(PLAN_SYSTEM, WHERE_PROMPT, img, 300)
                self.signals.free_answer.emit(answer)
                self.signals.status_changed.emit("Listo")
            except Exception as e:
                self.signals.error_occurred.emit(f"Error: {e}")
            finally:
                self._release()

        self._bg(_run)
