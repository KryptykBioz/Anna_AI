# Filename: BASE/tools/internal/prompt_judge/prompt_judge.py
"""
Prompt Judge - Internal Tool
=============================
Evaluates built prompts against agent responses using a three-judge panel.
When judges determine improvement is needed, the final judge modifies one
section in the associated _parts file directly, saves it, and triggers
hot reload so changes take effect immediately.

Activated by USE_PROMPT_JUDGE control variable.
Interval controlled by PROMPT_JUDGE_INTERVAL (seconds, default 300).
"""

import asyncio
import time
import threading
from pathlib import Path
from typing import Optional


PROMPT_TYPES = ("action", "reactive", "reflective", "proactive", "responsive")

# Maps prompt type to its _parts file path (relative to project root)
_PARTS_FILE_MAP = {
    "action":     "BASE/core/action/action_parts.py",
    "reactive":   "BASE/core/reactive/reactive_parts.py",
    "reflective": "BASE/core/reflective/reflective_parts.py",
    "proactive":  "BASE/core/proactive/proactive_parts.py",
    "responsive": "BASE/core/responsive/responsive_parts.py",
}


class PromptJudge:
    """
    Background tool that periodically evaluates prompts and applies minimal
    improvements directly to _parts source files via hot reload.
    """

    __slots__ = (
        'config', 'controls', 'project_root', 'logger',
        '_runner', '_queue', '_thread', '_running',
        '_last_judge_times', '_hot_reload_manager'
    )

    def __init__(self, config, controls, project_root: Path, logger):
        self.config = config
        self.controls = controls
        self.project_root = project_root
        self.logger = logger

        self._runner = None
        self._queue: Optional[asyncio.Queue] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._last_judge_times: dict = {t: 0.0 for t in PROMPT_TYPES}
        self._hot_reload_manager = None

    def set_hot_reload_manager(self, mgr):
        self._hot_reload_manager = mgr

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="PromptJudge"
        )
        self._thread.start()
        self.logger.judge("[Prompt Judge] Started background judge thread")

    def stop(self):
        self._running = False
        if self._queue:
            try:
                self._queue.put_nowait(None)
            except Exception:
                pass

    # =========================================================================
    # SUBMISSION
    # =========================================================================

    def submit(self, prompt_type: str, prompt: str, response: str):
        """
        Submit a prompt+response pair for judging.
        Non-blocking — skips silently if the interval hasn't elapsed or
        the judge is disabled.
        """
        if not self._running:
            return
        if not getattr(self.controls, 'USE_PROMPT_JUDGE', False):
            return
        if prompt_type not in PROMPT_TYPES:
            return
        if not self._queue:
            return

        interval = getattr(self.controls, 'PROMPT_JUDGE_INTERVAL', 300)
        now = time.time()
        if now - self._last_judge_times.get(prompt_type, 0.0) < interval:
            return

        self._last_judge_times[prompt_type] = now

        try:
            self._queue.put_nowait((prompt_type, prompt, response))
            self.logger.judge(
                f"[Prompt Judge] Queued {prompt_type} prompt for evaluation"
            )
        except asyncio.QueueFull:
            pass

    # =========================================================================
    # BACKGROUND LOOP
    # =========================================================================

    def _run_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._queue = asyncio.Queue(maxsize=len(PROMPT_TYPES))
        loop.run_until_complete(self._consume())
        loop.close()

    async def _consume(self):
        from BASE.tools.internal.prompt_judge.prompt_judge_runner import PromptJudgeRunner
        self._runner = PromptJudgeRunner(
            ollama_endpoint=self.config.ollama_endpoint,
            model=self.config.thought_model,
            logger=self.logger
        )

        while self._running:
            try:
                item = await asyncio.wait_for(self._queue.get(), timeout=5.0)
            except asyncio.TimeoutError:
                continue

            if item is None:
                break

            prompt_type, prompt, response = item
            try:
                await self._evaluate(prompt_type, prompt, response)
            except Exception as e:
                self.logger.error(
                    f"[Prompt Judge] Evaluation error ({prompt_type}): {e}"
                )

    # =========================================================================
    # EVALUATION
    # =========================================================================

    async def _evaluate(self, prompt_type: str, prompt: str, response: str):
        self.logger.judge(f"[Prompt Judge] Evaluating {prompt_type} prompt...")

        parts_file = self.project_root / _PARTS_FILE_MAP[prompt_type]
        if not parts_file.exists():
            self.logger.judge(f"[Prompt Judge] Parts file not found: {parts_file}")
            return

        sections = _extract_parts_sections(parts_file)
        if not sections:
            self.logger.judge(f"[Prompt Judge] No sections extracted from {parts_file.name}")
            return

        result = await self._runner.run(
            prompt_type=prompt_type,
            prompt=prompt,
            response=response,
            parts_sections=sections
        )

        if result is None:
            self.logger.judge(f"[Prompt Judge] {prompt_type}: no improvement needed")
            return

        method_name, original, replacement, scores, rationale = result

        ok, line_no = _apply_to_parts_file(parts_file, method_name, original, replacement)
        if not ok:
            self.logger.judge(
                f"[Prompt Judge] Could not apply change to {parts_file.name} "
                f"(method={method_name})"
            )
            return

        score_str = " ".join(
            f"{k}={v}" for k, v in scores.items()
            if k not in ("composite", "weights_used")
        )
        self.logger.judge(
            f"[Prompt Judge] {prompt_type} improved "
            f"({score_str} composite={scores['composite']}) "
            f"— saved to {parts_file.name}"
        )
        self.logger.judge(
            f"[Prompt Judge] Change in {method_name}: "
            f"'{original}' -> '{replacement}'"
        )
        self.logger.judge(f"[Prompt Judge] Rationale: {rationale}")

        self._write_judge_log(
            prompt_type=prompt_type,
            parts_file=parts_file,
            method_name=method_name,
            line_no=line_no,
            original=original,
            replacement=replacement,
            scores=scores,
            rationale=rationale
        )

        self._trigger_hot_reload(prompt_type, parts_file)

    def _write_judge_log(
        self,
        prompt_type: str,
        parts_file: Path,
        method_name: str,
        line_no: int,
        original: str,
        replacement: str,
        scores: dict,
        rationale: str
    ):
        import json
        from datetime import datetime, timezone

        log_path = self.project_root / "logs" / "judge_log.json"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        entry = {
            "timestamp":   datetime.now(timezone.utc).isoformat(),
            "prompt_type": prompt_type,
            "file":        parts_file.name,
            "method":      method_name,
            "line":        line_no,
            "scores":      scores,
            "original":    original,
            "replacement": replacement,
            "rationale":   rationale
        }

        try:
            if log_path.exists():
                existing = json.loads(log_path.read_text(encoding="utf-8"))
                if not isinstance(existing, list):
                    existing = []
            else:
                existing = []
        except Exception:
            existing = []

        existing.append(entry)
        log_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")

    # =========================================================================
    # HOT RELOAD
    # =========================================================================

    def _trigger_hot_reload(self, prompt_type: str, parts_file: Path):
        mgr = self._hot_reload_manager
        if not mgr or not mgr.enabled:
            self.logger.judge(
                "[Prompt Judge] Hot reload not available — "
                "restart required for changes to take effect"
            )
            return

        # The constructor module name is what the hot reload manager tracks.
        # Reloading the constructor causes it to reimport its _parts dependency.
        constructor_name = f"{prompt_type}_constructor"

        if constructor_name not in mgr.modules:
            # Fall back to triggering via file path — watchdog path
            self.logger.judge(
                f"[Prompt Judge] '{constructor_name}' not in hot reload registry, "
                f"triggering via file path"
            )
            mgr._on_file_changed(str(parts_file))
            return

        self.logger.judge(
            f"[Prompt Judge] Triggering hot reload for {constructor_name}"
        )
        mgr._reload_with_dependents(constructor_name)


# =============================================================================
# PARTS FILE HELPERS
# =============================================================================

def _extract_parts_sections(parts_file: Path) -> dict:
    """
    Parse a _parts file and return {method_name: return_string_body}.
    Only extracts @staticmethod methods that return a single string literal.
    """
    import ast

    try:
        source = parts_file.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except Exception:
        return {}

    sections = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if not isinstance(item, ast.FunctionDef):
                continue
            # Must be a @staticmethod
            is_static = any(
                (isinstance(d, ast.Name) and d.id == 'staticmethod') or
                (isinstance(d, ast.Attribute) and d.attr == 'staticmethod')
                for d in item.decorator_list
            )
            if not is_static:
                continue
            # Must have a single return of a string constant
            ret_nodes = [n for n in ast.walk(item) if isinstance(n, ast.Return)]
            if len(ret_nodes) != 1:
                continue
            val = ret_nodes[0].value
            if isinstance(val, ast.Constant) and isinstance(val.value, str):
                sections[item.name] = val.value
    return sections


def _apply_to_parts_file(
    parts_file: Path, method_name: str, original: str, replacement: str
) -> tuple:
    """
    Apply a text replacement inside a specific method's return string in the
    _parts source file. Writes the file in-place.
    Returns (True, line_no) on success, (False, 0) on failure.
    """
    import ast

    try:
        source = parts_file.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except Exception:
        return False, 0

    target_start = target_end = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name == method_name:
                target_start = item.lineno - 1
                target_end   = item.end_lineno
                break
        if target_start is not None:
            break

    if target_start is None:
        return False, 0

    lines = source.splitlines(keepends=True)
    method_src = "".join(lines[target_start:target_end])

    if original not in method_src:
        return False, 0

    orig_pos = method_src.find(original)
    line_no = target_start + method_src[:orig_pos].count('\n') + 1

    new_method_src = method_src.replace(original, replacement, 1)
    new_source = (
        "".join(lines[:target_start])
        + new_method_src
        + "".join(lines[target_end:])
    )

    parts_file.write_text(new_source, encoding="utf-8")
    return True, line_no