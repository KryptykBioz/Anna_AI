# Filename: BASE/core/cognitive_filter.py
"""
Cognitive Response Filter
==========================
Independent AI layer that validates generated responses before delivery.

Discards responses that are:
1. Completely unrelated to the current thought chain context
2. Written in a language other than English or Japanese
3. Near-identical duplicates of the previous response (non-trivial length only)

Fail-open: on Ollama timeout/error, the response is approved to avoid silencing
the agent due to infrastructure issues.
"""
import re
import requests
from typing import Tuple, Optional, List

_FEW_WORD_THRESHOLD = 8  # responses at or below this word count are exempt from duplicate filtering


class CognitiveFilter:
    """
    Validates responses via a single low-latency Ollama call before delivery.
    Maintains last-response state for duplicate detection.
    Both autonomous and user-triggered response paths share one instance.
    """

    __slots__ = (
        'config', 'controls', 'logger', '_last_response', '_last_response_words', '_filter_model'
    )

    def __init__(self, config, controls, logger):
        self.config = config
        self.controls = controls
        self.logger = logger
        self._last_response: str = ""
        self._last_response_words: int = 0
        self._filter_model: str = (
            getattr(config, 'filter_model', None)
            or getattr(config, 'thought_model', 'llama3.2:3b')
        )

    def _is_enabled(self) -> bool:
        return getattr(self.controls, 'COGNITIVE_FILTER', True)

    # ========================================================================
    # PUBLIC API
    # ========================================================================

    def check_response(
        self,
        response: str,
        thought_chain: List,
        context_parts: Optional[List[str]] = None
    ) -> Tuple[bool, str]:
        """
        Validate response against all three filter criteria.

        Args:
            response: Cleaned, finalized response text.
            thought_chain: Recent thought objects (stringified internally).
            context_parts: Additional context strings passed to the prompt builder.

        Returns:
            (approved, reason)
            approved=True  → response passes, deliver normally
            approved=False → response is discarded silently
        """
        if not response or not response.strip():
            return False, "empty_response"

        if not self._is_enabled():
            return True, "filter_disabled"
        
        return True, "filter_unavailable" # TEMP: always approve, skip Ollama call during early testing

        response_words = len(response.split())
        prev_words = self._last_response_words
        is_trivial = response_words <= _FEW_WORD_THRESHOLD
        prev_trivial = prev_words <= _FEW_WORD_THRESHOLD

        # Fast local duplicate check — skip Ollama for obvious exact matches
        if not is_trivial and not prev_trivial and self._last_response:
            if self._normalize(response) == self._normalize(self._last_response):
                self.logger.filter("[CognitiveFilter] BLOCKED: exact duplicate")
                return False, "duplicate"

        thought_summary = self._summarize_context(thought_chain, context_parts)
        prompt = self._build_prompt(response, thought_summary, is_trivial, prev_trivial)
        raw = self._call_ollama(prompt)

        if not raw:
            # Fail-open: infrastructure issue should not silence the agent
            self.logger.filter("[CognitiveFilter] Ollama unavailable — approving response")
            return True, "filter_unavailable"

        approved, reason = self._parse_result(raw)

        if not approved:
            self.logger.filter(f"[CognitiveFilter] BLOCKED: {reason}")

        return approved, reason

    def update_last_response(self, response: str):
        """
        Record an approved, delivered response for future duplicate detection.
        Must be called immediately after check_response returns True.
        """
        self._last_response = response
        self._last_response_words = len(response.split()) if response else 0

    # ========================================================================
    # INTERNAL
    # ========================================================================

    def _build_prompt(
        self,
        response: str,
        thought_summary: str,
        is_trivial: bool,
        prev_trivial: bool
    ) -> str:
        if is_trivial or prev_trivial:
            dup_section = "DUPLICATE CHECK: SKIP — one or both responses are short/trivial. Auto-pass criterion 3."
        elif self._last_response:
            dup_section = f"PREVIOUS RESPONSE:\n{self._last_response[:300]}"
        else:
            dup_section = "PREVIOUS RESPONSE: None (first response)"

        return (
            "You are a strict response filter. Evaluate the CURRENT RESPONSE against exactly three criteria.\n\n"
            "## CONTEXT (recent thought chain):\n"
            f"{thought_summary[:600]}\n\n"
            f"{dup_section}\n\n"
            "## CURRENT RESPONSE:\n"
            f"{response[:800]}\n\n"
            "## CRITERIA:\n"
            "1. CONTEXT  — Is this response COMPLETELY unrelated to the context above?\n"
            "              (Minor tangents are fine. Only fail if totally off-topic.)\n"
            "2. LANGUAGE — Does this response contain substantial text in a language\n"
            "              OTHER than English or Japanese?\n"
            "3. DUPLICATE — Is this response identical or nearly identical to PREVIOUS RESPONSE?\n"
            "               (Only applies when both are non-trivial length.)\n\n"
            "## REPLY WITH EXACTLY ONE OF:\n"
            "  PASS\n"
            "  FAIL:CONTEXT\n"
            "  FAIL:LANGUAGE\n"
            "  FAIL:DUPLICATE\n"
            "No explanation. No other text."
        )

    def _call_ollama(self, prompt: str) -> str:
        try:
            payload = {
                "model": self._filter_model,
                "prompt": prompt,
                "stream": False,
                "temperature": 0.0,
                "top_p": 1.0,
                "top_k": 1,
                "num_predict": 16,
                "keep_alive": "24h"
            }
            resp = requests.post(
                f"{self.config.ollama_endpoint}/api/generate",
                json=payload,
                timeout=8
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except requests.Timeout:
            self.logger.filter("[CognitiveFilter] Ollama request timed out")
            return ""
        except Exception as e:
            self.logger.filter(f"[CognitiveFilter] Ollama error: {e}")
            return ""

    def _parse_result(self, result: str) -> Tuple[bool, str]:
        upper = result.strip().upper()
        if upper.startswith("PASS"):
            return True, "pass"
        if "CONTEXT" in upper:
            return False, "off_context"
        if "LANGUAGE" in upper:
            return False, "wrong_language"
        if "DUPLICATE" in upper:
            return False, "duplicate"
        # Ambiguous output — approve (fail-open)
        return True, "pass_ambiguous"

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r'\s+', ' ', text.lower().strip())

    def _summarize_context(
        self,
        thought_chain: List,
        context_parts: Optional[List[str]]
    ) -> str:
        parts: List[str] = []

        recent = thought_chain[-5:] if len(thought_chain) > 5 else thought_chain
        for t in recent:
            text = str(t).strip()
            if text:
                parts.append(text[:200])

        if context_parts:
            for ctx in context_parts[:2]:
                stripped = ctx.strip()
                if stripped:
                    parts.append(stripped[:150])

        return "\n".join(parts) if parts else "No context available"