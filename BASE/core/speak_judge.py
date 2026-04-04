# Filename: BASE/core/speak_judge.py
"""
Speak Judge
===========
Secondary AI pass that vetoes a <speak>YES</speak> decision before TTS fires.

The cognitive model is optimistic about speaking; this judge applies a stricter
filter using recent response history and conversational context to prevent
repetitive or low-value TTS output.

Called from CognitiveLoopManager AFTER response_trigger.should_respond() is True
and BEFORE _generate_response() executes.

Returns True  → allow TTS
Returns False → suppress TTS, clear trigger, continue thinking
"""

import re
import time
from typing import Optional


# Prompt template kept outside the class to avoid per-instance overhead
_JUDGE_PROMPT_TEMPLATE = """\
You are a strict gatekeeper deciding whether an AI agent should speak aloud right now.

## RECENT SPOKEN RESPONSES (chronological, oldest first)
{recent_responses}

## RECENT INTERNAL THOUGHTS
{recent_thoughts}

## TIMING
- Seconds since last spoken response: {time_since_response:.0f}s
- Seconds since last user input: {time_since_user:.0f}s

## TASK
Answer YES or NO only.

Approve speaking (YES) if:
- The agent has something meaningfully new to say
- The user asked a question or addressed the agent directly
- Significant time has passed (>120s) AND the agent has a novel observation
- A tool result just arrived that the user would care about

Deny speaking (NO) if:
- Recent spoken responses cover the same topic or sentiment
- The agent would just be restating a thought it already said aloud
- The agent is speculating internally with no new value for the user
- Less than 60 seconds since the last spoken response AND content is similar
- The recent responses already contain excitement, check-ins, or greetings that haven't been acknowledged

Output exactly one word: YES or NO"""


class SpeakJudge:
    """
    Fast secondary judge that vetoes low-value TTS triggers.

    Attributes:
        thought_processor: ThoughtProcessor instance (provides _call_ollama + thought_buffer)
        logger: Logger instance
        model: Ollama model name to use (defaults to thought_model; override for speed)
        recent_response_window: How many past spoken responses to include in context
        recent_thought_window: How many past thoughts to include in context
    """

    __slots__ = (
        'thought_processor', 'logger', 'model',
        'recent_response_window', 'recent_thought_window',
        '_judge_calls', '_judge_approvals', '_judge_denials'
    )

    def __init__(
        self,
        thought_processor,
        logger=None,
        model: Optional[str] = None,
        recent_response_window: int = 5,
        recent_thought_window: int = 8
    ):
        self.thought_processor = thought_processor
        self.logger = logger
        self.model = model  # None = resolved lazily from config
        self.recent_response_window = recent_response_window
        self.recent_thought_window = recent_thought_window

        # Lightweight stats
        self._judge_calls = 0
        self._judge_approvals = 0
        self._judge_denials = 0

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def should_speak(
        self,
        time_since_last_response: float,
        time_since_last_user: float
    ) -> bool:
        """
        Run the judge inference and return True if speaking is approved.

        Args:
            time_since_last_response: Seconds elapsed since last TTS output
            time_since_last_user:     Seconds elapsed since last user input

        Returns:
            True  → approved, allow TTS
            False → denied, suppress TTS
        """
        self._judge_calls += 1

        prompt = self._build_prompt(time_since_last_response, time_since_last_user)
        if not prompt:
            # Fallback: approve if we can't build context
            self._judge_approvals += 1
            return True

        model = self.model or getattr(self.thought_processor.config, 'thought_model', None)
        if not model:
            self._judge_approvals += 1
            return True

        raw = self.thought_processor._call_ollama(
            prompt=prompt,
            model=model,
            system_prompt=None,
            mode="cognitive"
        )

        approved = self._parse_verdict(raw)

        if approved:
            self._judge_approvals += 1
        else:
            self._judge_denials += 1

        if self.logger:
            verdict_str = "APPROVED" if approved else "DENIED"
            self.logger.system(
                f"[Speak Judge] {verdict_str} "
                f"(calls={self._judge_calls}, "
                f"approvals={self._judge_approvals}, "
                f"denials={self._judge_denials})"
            )

        return approved

    def get_stats(self) -> dict:
        total = self._judge_calls
        return {
            'total': total,
            'approvals': self._judge_approvals,
            'denials': self._judge_denials,
            'denial_rate': (self._judge_denials / total) if total else 0.0
        }

    # =========================================================================
    # INTERNAL HELPERS
    # =========================================================================

    def _build_prompt(
        self,
        time_since_last_response: float,
        time_since_last_user: float
    ) -> str:
        buf = self.thought_processor.thought_buffer

        # Recent spoken responses (SELF-tagged entries)
        all_thoughts = buf.get_thoughts_for_response()
        spoken = [
            str(t) for t in all_thoughts
            if self._is_spoken_response(str(t))
        ][-self.recent_response_window:]

        # Recent internal thoughts (non-SELF, non-USER)
        internal = [
            str(t) for t in all_thoughts
            if not self._is_spoken_response(str(t))
        ][-self.recent_thought_window:]

        if not spoken and not internal:
            return ""

        recent_responses_str = (
            "\n".join(f"- {r}" for r in spoken)
            if spoken else "(none yet)"
        )
        recent_thoughts_str = (
            "\n".join(f"- {t}" for t in internal)
            if internal else "(none)"
        )

        return _JUDGE_PROMPT_TEMPLATE.format(
            recent_responses=recent_responses_str,
            recent_thoughts=recent_thoughts_str,
            time_since_response=time_since_last_response,
            time_since_user=time_since_last_user,
        )

    @staticmethod
    def _is_spoken_response(text: str) -> bool:
        """Identify thought buffer entries that are past TTS outputs."""
        lower = text.lower()
        return lower.startswith('[self]') or '[self]' in lower[:20]

    @staticmethod
    def _parse_verdict(raw: str) -> bool:
        """Extract YES/NO from raw model output; default deny on ambiguity."""
        if not raw:
            return False
        cleaned = raw.strip().upper()
        # Accept bare YES/NO or the first word of a longer response
        match = re.search(r'\b(YES|NO)\b', cleaned)
        if match:
            return match.group(1) == 'YES'
        # Fallback: deny
        return False