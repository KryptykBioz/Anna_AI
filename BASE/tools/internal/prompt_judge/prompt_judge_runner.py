# Filename: BASE/tools/internal/prompt_judge/prompt_judge_runner.py
"""
Prompt Judge Runner
====================
Six-judge panel that evaluates a prompt+response pair across character,
autonomy, cognition, tools, interaction, and effectiveness dimensions.

Judges are mode-aware: weights shift per prompt_type so that e.g. character
counts heavily in responsive mode but near-zero in action mode, and tool
correctness dominates in action mode but is minor in responsive mode.

If the mode-weighted composite < IMPROVEMENT_THRESHOLD, the final judge picks
one method from the _parts sections and recommends a minimal text change,
focused on the dimension with the highest weighted deficit.
"""

import re
import asyncio
from typing import Optional

try:
    import aiohttp
    _AIOHTTP = True
except ImportError:
    _AIOHTTP = False

IMPROVEMENT_THRESHOLD = 75.0

# Per-mode weights: (character, autonomy, cognition, tools, interaction, effectiveness)
# Each row sums to 1.0
_MODE_WEIGHTS = {
    "action":     (0.05, 0.10, 0.15, 0.40, 0.05, 0.25),
    "reactive":   (0.10, 0.10, 0.20, 0.25, 0.15, 0.20),
    "reflective": (0.10, 0.15, 0.30, 0.15, 0.05, 0.25),
    "proactive":  (0.15, 0.30, 0.20, 0.20, 0.05, 0.10),
    "responsive": (0.35, 0.05, 0.10, 0.05, 0.25, 0.20),
}
_JUDGE_NAMES = ("character", "autonomy", "cognition", "tools", "interaction", "effectiveness")

# Mode descriptions injected into each judge to calibrate scoring
_MODE_CONTEXT = {
    "action": (
        "ACTION mode: the agent constructs exact tool commands with correct parameters. "
        "Personality and interaction are irrelevant here. Focus entirely on whether the "
        "agent picked the right tool command, extracted correct parameters from thoughts, "
        "and produced well-formed output. Structural correctness dominates."
    ),
    "reactive": (
        "REACTIVE mode: the agent processes the most current incoming data and makes "
        "immediate decisions — responding to user messages, game events, or real-time signals. "
        "Fast, accurate responses and correct tool decisions matter most. "
        "Personality is secondary; effectiveness and cognition are primary."
    ),
    "reflective": (
        "REFLECTIVE mode: the agent retrieves memory context and interprets recent events "
        "against past experience. Logical thought flow and memory-grounded reasoning matter most. "
        "The agent should be drawing meaningful connections, not looping or inventing memories. "
        "Autonomy is secondary; cognition and effectiveness are primary."
    ),
    "proactive": (
        "PROACTIVE mode: the agent drives itself forward — researching, planning, taking notes, "
        "setting reminders, and advancing goals without waiting for the user. "
        "Self-directed initiative and purposeful tool use matter most. "
        "Personality is secondary; autonomy and cognition are primary."
    ),
    "responsive": (
        "RESPONSIVE mode: the agent is generating a spoken TTS response heard aloud by the user. "
        "Personality, voice, tone, and user engagement matter most. "
        "The response must sound natural, reflect the agent's character, and drive interaction. "
        "Tool use is irrelevant here; character and interaction are primary."
    ),
}


class PromptJudgeRunner:
    __slots__ = ('endpoint', 'model', 'logger', '_session')

    def __init__(self, ollama_endpoint: str, model: str, logger):
        self.endpoint = ollama_endpoint.rstrip('/')
        self.model = model
        self.logger = logger
        self._session = None

    # =========================================================================
    # PUBLIC
    # =========================================================================

    async def run(
        self,
        prompt_type: str,
        prompt: str,
        response: str,
        parts_sections: dict
    ) -> Optional[tuple]:
        """
        Evaluate a prompt+response pair across six mode-weighted dimensions.

        Returns:
            None if composite >= IMPROVEMENT_THRESHOLD.
            (method_name, original, replacement, scores_dict, rationale) otherwise.
            scores_dict keys: character, autonomy, cognition, tools, interaction,
                              effectiveness, composite, weights_used
        """
        if not _AIOHTTP:
            self.logger.judge("[Prompt Judge] aiohttp not installed — skipping")
            return None

        async with aiohttp.ClientSession() as session:
            self._session = session
            mode_ctx = _MODE_CONTEXT.get(prompt_type, _MODE_CONTEXT["reactive"])
            weights = _MODE_WEIGHTS.get(prompt_type, _MODE_WEIGHTS["reactive"])

            results = await asyncio.gather(
                self._judge_character(prompt, response, prompt_type, mode_ctx),
                self._judge_autonomy(prompt, response, prompt_type, mode_ctx),
                self._judge_cognition(prompt, response, prompt_type, mode_ctx),
                self._judge_tools(prompt, response, prompt_type, mode_ctx),
                self._judge_interaction(prompt, response, prompt_type, mode_ctx),
                self._judge_effectiveness(prompt, response, prompt_type, mode_ctx),
            )

            scores = [r[0] for r in results]
            reasons = [r[1] for r in results]

            composite = sum(s * w for s, w in zip(scores, weights))

            scores_dict = {name: scores[i] for i, name in enumerate(_JUDGE_NAMES)}
            scores_dict["composite"] = round(composite, 1)
            scores_dict["weights_used"] = prompt_type

            score_str = " ".join(f"{n}={scores[i]}" for i, n in enumerate(_JUDGE_NAMES))
            self.logger.judge(
                f"[Prompt Judge] {prompt_type} — {score_str} "
                f"composite={composite:.1f} (threshold={IMPROVEMENT_THRESHOLD})"
            )
            for name, reason in zip(_JUDGE_NAMES, reasons):
                self.logger.judge(f"[Prompt Judge] {name}: {reason}")

            if composite >= IMPROVEMENT_THRESHOLD:
                return None

            # Find the dimension with the highest weighted deficit to focus the fix
            weighted_deficits = [
                (100 - scores[i]) * weights[i] for i in range(len(_JUDGE_NAMES))
            ]
            weakest_idx = weighted_deficits.index(max(weighted_deficits))
            weakest_dim = _JUDGE_NAMES[weakest_idx]

            action = await self._final_judge(
                prompt_type=prompt_type,
                prompt=prompt,
                response=response,
                parts_sections=parts_sections,
                scores=scores,
                reasons=reasons,
                weakest_dim=weakest_dim,
                mode_ctx=mode_ctx
            )

            if not action:
                return None

            method_name = _extract_field(action, "method")
            original    = _extract_field(action, "original")
            replacement = _extract_field(action, "replacement")
            rationale   = _extract_field(action, "rationale") or "no rationale"

            if not method_name or not original or not replacement:
                self.logger.judge("[Prompt Judge] Final judge returned incomplete action")
                return None

            if method_name not in parts_sections:
                self.logger.judge(f"[Prompt Judge] Final judge returned unknown method: {method_name}")
                return None

            if original not in parts_sections[method_name]:
                self.logger.judge(f"[Prompt Judge] 'original' text not found in {method_name}")
                return None

            return (method_name, original, replacement, scores_dict, rationale)

    # =========================================================================
    # JUDGES
    # =========================================================================

    async def _judge_character(
        self, prompt: str, response: str, prompt_type: str, mode_ctx: str
    ) -> tuple:
        system = (
            "You are a character consistency judge for an AI agent. "
            f"MODE CONTEXT: {mode_ctx} "
            "Evaluate whether the agent's internal thoughts and spoken responses reflect its "
            "established personality. Consider: Does the response sound like the agent's "
            "defined character? Does the tone, vocabulary, and emotional register match the "
            "personality described in the prompt? In modes where character matters less "
            "(action, reflective), weight correctness of format over tone. "
            "In responsive mode, penalize heavily if the response sounds generic, robotic, "
            "or mismatched to the agent's personality. "
            'Reply ONLY with JSON: {"score": <1-100>, "reason": "<one sentence>"}'
        )
        user = (
            f"PROMPT TYPE: {prompt_type}\n\n"
            f"PROMPT:\n{prompt}\n\n"
            f"RESPONSE:\n{response}\n\n"
            "Score how well the response reflects the agent's defined personality and character."
        )
        return await self._query_judge(system, user)

    async def _judge_autonomy(
        self, prompt: str, response: str, prompt_type: str, mode_ctx: str
    ) -> tuple:
        system = (
            "You are an autonomy judge for an AI agent. "
            f"MODE CONTEXT: {mode_ctx} "
            "Evaluate whether the agent is self-directing its behavior appropriately. "
            "Consider: Is the agent initiating its own actions rather than waiting? "
            "In proactive mode, is it finding research topics, planning ahead, and "
            "advancing goals without user prompts? In reactive mode, is it making "
            "decisive choices rather than deferring? Penalize heavily if the agent "
            "outputs thoughts like 'I should wait for the user' or 'I will check later' "
            "without taking any concrete action. Penalize passive, indecisive cycles. "
            "In action mode, autonomy is about correct command construction, not initiative. "
            'Reply ONLY with JSON: {"score": <1-100>, "reason": "<one sentence>"}'
        )
        user = (
            f"PROMPT TYPE: {prompt_type}\n\n"
            f"PROMPT:\n{prompt}\n\n"
            f"RESPONSE:\n{response}\n\n"
            "Score how autonomously and self-directedly the agent is operating in this mode."
        )
        return await self._query_judge(system, user)

    async def _judge_cognition(
        self, prompt: str, response: str, prompt_type: str, mode_ctx: str
    ) -> tuple:
        system = (
            "You are a cognition judge for an AI agent. "
            f"MODE CONTEXT: {mode_ctx} "
            "Evaluate the logical quality of the agent's thought process. Consider: "
            "Does the thought follow logically from the incoming data? Is there a clear "
            "causal chain from observation to decision? "
            "Penalize severely for repetition — if the thought is nearly identical to a "
            "recent thought in the prompt's RECENT EXPERIENCES section, that is a cognition "
            "failure (loop). Penalize for mode-switching contradictions (e.g., declaring "
            "next_mode=reactive while doing proactive research). "
            "In reflective mode, check that the agent is drawing genuine connections to "
            "memory rather than restating what was already known. "
            'Reply ONLY with JSON: {"score": <1-100>, "reason": "<one sentence>"}'
        )
        user = (
            f"PROMPT TYPE: {prompt_type}\n\n"
            f"PROMPT:\n{prompt}\n\n"
            f"RESPONSE:\n{response}\n\n"
            "Score the logical quality of the agent's thought process and absence of loops."
        )
        return await self._query_judge(system, user)

    async def _judge_tools(
        self, prompt: str, response: str, prompt_type: str, mode_ctx: str
    ) -> tuple:
        system = (
            "You are a tool-use judge for an AI agent. "
            f"MODE CONTEXT: {mode_ctx} "
            "Evaluate the quality of the agent's tool-calling decisions. "
            "CRITICAL: The prompt may contain an AVAILABLE TOOLS section. "
            "Only tools listed there are valid — penalize any call to an unlisted tool. "
            "Consider six failure modes: "
            "(1) No tool called when the situation clearly required one — score low. "
            "(2) A tool called when the situation did not warrant any tool — score medium-low. "
            "(3) A tool called, but a better-fit available tool exists — score medium-low. "
            "(4) A static/memory tool used when a live web search tool was available and "
            "the query requires current information — score low. "
            "(5) The same tool called repeatedly on the same query without refinement — "
            "this is tool spam — score low. "
            "(6) A correct tool was called, but the tool was used to create an entry that "
            "already exists or the tool was used without first retrieving tool context when "
            "context retrieval is available — score medium. "
            "In action mode, evaluate whether the exact command syntax and parameters are "
            "correct per the tool documentation provided. "
            "In responsive mode, tool use is not expected — score 80 if no tool is used. "
            'Reply ONLY with JSON: {"score": <1-100>, "reason": "<one sentence>"}'
        )
        user = (
            f"PROMPT TYPE: {prompt_type}\n\n"
            f"PROMPT:\n{prompt}\n\n"
            f"RESPONSE:\n{response}\n\n"
            "Score the correctness and appropriateness of tool use given the available tools "
            "and the mode's requirements."
        )
        return await self._query_judge(system, user)

    async def _judge_interaction(
        self, prompt: str, response: str, prompt_type: str, mode_ctx: str
    ) -> tuple:
        system = (
            "You are an interaction quality judge for an AI agent. "
            f"MODE CONTEXT: {mode_ctx} "
            "Evaluate whether the agent is actively fostering engagement with the user. "
            "Consider: Is the agent using avatar, animation, or expression tools "
            "(e.g., Warudo, Unity) to communicate its internal state? "
            "If such tools are listed in AVAILABLE TOOLS and the agent is in a mode "
            "where it can express itself (reactive, proactive, responsive), penalize "
            "if these are consistently skipped. "
            "In responsive mode, is the response inviting further conversation — asking "
            "a question, making an observation that elicits reaction, or referencing "
            "something the user cares about? "
            "Penalize flat, closed-ended responses that shut down the conversation. "
            "In action mode, interaction is irrelevant — score 75 neutrally. "
            'Reply ONLY with JSON: {"score": <1-100>, "reason": "<one sentence>"}'
        )
        user = (
            f"PROMPT TYPE: {prompt_type}\n\n"
            f"PROMPT:\n{prompt}\n\n"
            f"RESPONSE:\n{response}\n\n"
            "Score how well the agent is fostering interaction and using available "
            "avatar/expression tools to communicate its state."
        )
        return await self._query_judge(system, user)

    async def _judge_effectiveness(
        self, prompt: str, response: str, prompt_type: str, mode_ctx: str
    ) -> tuple:
        system = (
            "You are an effectiveness judge for an AI agent. "
            f"MODE CONTEXT: {mode_ctx} "
            "Evaluate whether the agent is making real progress toward its goals and "
            "the user's stated needs. "
            "CRITICAL: If the prompt contains a recent user message or request, check "
            "whether the agent is addressing it. An agent that ignores or deflects a "
            "user request in favor of unrelated work is an effectiveness failure. "
            "In proactive mode, is the agent completing meaningful research or preparation "
            "tasks, or spinning in unproductive loops? "
            "In reflective mode, is the memory retrieval producing actionable context, "
            "or just surfacing irrelevant entries? "
            "In action mode, did the tool calls actually accomplish the intended task? "
            "Penalize hollow cycles where the agent appears busy but makes no progress. "
            'Reply ONLY with JSON: {"score": <1-100>, "reason": "<one sentence>"}'
        )
        user = (
            f"PROMPT TYPE: {prompt_type}\n\n"
            f"PROMPT:\n{prompt}\n\n"
            f"RESPONSE:\n{response}\n\n"
            "Score how effectively the agent is advancing goals and addressing the user's needs."
        )
        return await self._query_judge(system, user)

    # =========================================================================
    # FINAL JUDGE
    # =========================================================================

    async def _final_judge(
        self,
        prompt_type: str,
        prompt: str,
        response: str,
        parts_sections: dict,
        scores: list,
        reasons: list,
        weakest_dim: str,
        mode_ctx: str
    ) -> str:
        sections_block = _format_sections_for_judge(parts_sections)
        scores_block = "\n".join(
            f"- {_JUDGE_NAMES[i].capitalize()}: {scores[i]}/100 | {reasons[i]}"
            for i in range(len(_JUDGE_NAMES))
        )

        system = (
            "You are a prompt optimization expert for an AI agent. "
            f"MODE CONTEXT: {mode_ctx} "
            "You will be shown the agent's static prompt instruction sections "
            "and a response that was judged to need improvement. "
            f"The weakest scoring dimension for this mode is: {weakest_dim.upper()}. "
            "Your job is to recommend ONE minimal change to ONE of the static sections "
            "to improve future responses on that dimension. "
            "The change must be either: "
            "(a) swap ONE word for a more appropriate synonym, or "
            "(b) rephrase ONE sentence in similar terms. "
            "IMPORTANT: Only modify text from the provided STATIC SECTIONS. "
            "Do not reference or modify the assembled prompt or the response itself. "
            'Reply ONLY with JSON: '
            '{"method": "<exact method name from sections>", '
            '"original": "<exact text to replace from that method>", '
            '"replacement": "<new text>", '
            '"rationale": "<one sentence>"}'
        )
        user = (
            f"PROMPT TYPE: {prompt_type}\n\n"
            f"AGENT RESPONSE:\n{response}\n\n"
            f"JUDGE SCORES:\n{scores_block}\n\n"
            f"WEAKEST DIMENSION (focus here): {weakest_dim.upper()}\n\n"
            f"STATIC PROMPT SECTIONS (modify only these):\n{sections_block}\n\n"
            f"Pick the section most responsible for the {weakest_dim} failure "
            "and recommend one minimal change."
        )
        return await self._query_raw(system, user)

    # =========================================================================
    # OLLAMA ASYNC
    # =========================================================================

    async def _query_judge(self, system: str, user: str) -> tuple:
        raw = await self._query_raw(system, user)
        score  = _extract_score(raw)
        reason = _extract_field(raw, "reason") or raw[:120]
        return score, reason

    async def _query_raw(self, system: str, user: str) -> str:
        if not self._session:
            return ""
        payload = {
            "model":  self.model,
            "prompt": f"{system}\n\n{user}",
            "stream": False,
            "options": {"temperature": 0.1}
        }
        try:
            async with self._session.post(
                f"{self.endpoint}/api/generate",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return (data.get("response") or "").strip()
        except Exception as e:
            self.logger.judge(f"[Prompt Judge] Ollama query failed: {e}")
            return ""


# =============================================================================
# HELPERS
# =============================================================================

def _format_sections_for_judge(sections: dict) -> str:
    parts = []
    for method_name, body in sections.items():
        parts.append(f"[METHOD: {method_name}]\n{body.strip()}")
    return "\n\n---\n\n".join(parts)


def _extract_score(text: str) -> int:
    nums = re.findall(r'\b([0-9]{1,3})\b', text)
    for n in nums:
        v = int(n)
        if 1 <= v <= 100:
            return v
    return 50


def _extract_field(text: str, field: str) -> str:
    m = re.search(rf'"{field}"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
    if m:
        return m.group(1).replace('\\"', '"').replace('\\n', '\n')
    m2 = re.search(rf'"{field}"\s*:\s*([^\n,}}]+)', text)
    if m2:
        return m2.group(1).strip().strip('"')
    return ""