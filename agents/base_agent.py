"""
BaseAgent — classe base para todos os agentes do pipeline.
Gerencia chamadas ao Gemini API com retry/backoff e logging.
"""
from __future__ import annotations

import logging
import threading
import time

from google import genai
from google.genai import types
from google.api_core import exceptions as google_exceptions

logger = logging.getLogger(__name__)


class BaseAgent:
    def __init__(
        self,
        name: str,
        api_key: str | None = None,
        model: str = "gemini-flash-latest",
        sleep_between_calls: float = 1.0,
        client=None,  # compat com testes antigos (MagicMock)
    ) -> None:
        self.name = name
        self.model = model
        self.sleep_between_calls = sleep_between_calls
        self._api_key = api_key
        # client não-None = configurado (suporta MagicMock nos testes)
        self.client = api_key or client
        self._gemini: genai.Client | None = None
        if api_key:
            self._gemini = genai.Client(api_key=api_key)
        self._logger = logging.getLogger(f"agents.{name}")

    def log(self, msg: str, level: str = "INFO") -> None:
        getattr(self._logger, level.lower())(msg)

    def _call_claude(
        self,
        messages: list[dict],
        system: str,
        max_tokens: int = 2048,
        retries: int = 3,
    ) -> str:
        """Chama Gemini API com retry exponencial. Mantém nome _call_claude por compat interna."""
        if not self.client:
            raise RuntimeError(f"Agent '{self.name}' requer GEMINI_API_KEY configurada")

        # Caminho de compat para mocks nos testes (MagicMock com .messages)
        if hasattr(self.client, "messages"):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
            )
            return response.content[0].text

        API_TIMEOUT = 30  # segundos por chamada antes de desistir

        last_exc: Exception | None = None
        for attempt in range(retries):
            try:
                if attempt > 0:
                    wait = 2 ** attempt
                    self.log(f"Retry {attempt}/{retries}, aguardando {wait}s...", "WARNING")
                    time.sleep(wait)

                prompt = messages[-1]["content"]
                gemini = self._gemini
                result_box: list = []
                error_box: list = []

                def _call():
                    try:
                        result_box.append(gemini.models.generate_content(
                            model=self.model,
                            contents=prompt,
                            config=types.GenerateContentConfig(
                                system_instruction=system,
                                max_output_tokens=max_tokens,
                                thinking_config=types.ThinkingConfig(thinking_budget=0),
                            ),
                        ))
                    except Exception as e:
                        error_box.append(e)

                # daemon=True: thread é abandonada se travar (não bloqueia o processo)
                t = threading.Thread(target=_call, daemon=True)
                t.start()
                t.join(timeout=API_TIMEOUT)

                if t.is_alive():
                    raise RuntimeError(f"Gemini não respondeu em {API_TIMEOUT}s")
                if error_box:
                    raise error_box[0]

                response = result_box[0]
                time.sleep(self.sleep_between_calls)
                self.log(f"Gemini: {len(prompt)} chars → {len(response.text)} chars")
                return response.text

            except google_exceptions.ResourceExhausted as exc:
                wait_rl = min(15 * (attempt + 1), 30)
                self.log(f"Rate limit — aguardando {wait_rl}s: {exc}", "WARNING")
                time.sleep(wait_rl)
                last_exc = exc
            except Exception as exc:
                self.log(f"API error (tentativa {attempt+1}): {exc}", "ERROR")
                last_exc = exc

        raise RuntimeError(f"Gemini API falhou após {retries} tentativas: {last_exc}")
