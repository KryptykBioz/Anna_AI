# Filename: BASE/core/action_state_manager.py
"""
Action State Manager - OPTIMIZED IMPLEMENTATION
Tracks async tool executions with full context and attempt counting
OPTIMIZED: String interning + bounded history size
"""
import sys
import time
from typing import Dict, List, Optional, Any, Set, Tuple
from enum import Enum


# ============================================================================
# STRING INTERNING OPTIMIZATION
# ============================================================================

_FAILURE_REASONS = {
    'timeout', 'backend_offline', 'invalid_args', 'tool_unavailable',
    'rate_limit', 'network_error', 'authentication_failed', 'unknown'
}
_INTERNED_FAILURE_REASONS = {r: sys.intern(r) for r in _FAILURE_REASONS}

_TOOL_NAMES_CACHE: Dict[str, str] = {}

def _intern_tool_name(tool_name: str) -> str:
    """Intern tool names for memory efficiency"""
    if tool_name not in _TOOL_NAMES_CACHE:
        _TOOL_NAMES_CACHE[tool_name] = sys.intern(tool_name)
    return _TOOL_NAMES_CACHE[tool_name]


# ============================================================================
# ENUMS
# ============================================================================

class ActionStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ============================================================================
# DATA STRUCTURES
# ============================================================================

class ActionState:
    """Represents state of an in-flight action"""
    __slots__ = (
        'action_id', 'tool_name', 'args', 'status', 'initiated_at',
        'completed_at', 'result', 'error', 'acknowledged', 'result_integrated',
        'context', 'attempt_number', 'query_simplified'
    )
    
    def __init__(
        self, action_id: str, tool_name: str, args: List[Any], status: ActionStatus,
        initiated_at: float, completed_at: Optional[float] = None,
        result: Optional[Dict[str, Any]] = None, error: Optional[str] = None,
        acknowledged: bool = False, result_integrated: bool = False,
        context: Optional[Dict[str, Any]] = None, attempt_number: int = 1,
        query_simplified: bool = False
    ):
        self.action_id = action_id
        self.tool_name = _intern_tool_name(tool_name)
        self.args = args
        self.status = status
        self.initiated_at = initiated_at
        self.completed_at = completed_at
        self.result = result
        self.error = error
        self.acknowledged = acknowledged
        self.result_integrated = result_integrated
        self.context = context or {}
        self.attempt_number = attempt_number
        self.query_simplified = query_simplified


class ActionStateManager:
    """Tool state awareness system with bounded memory"""
    __slots__ = (
        'actions', 'logger', '_action_counter', '_completed_cache', 
        '_last_cleanup', '_tool_attempt_tracking', '_max_actions'
    )
    
    def __init__(self, logger, max_actions: int = 500):
        self.actions: Dict[str, ActionState] = {}
        self.logger = logger
        self._action_counter = 0
        self._completed_cache: Set[str] = set()
        self._last_cleanup = time.time()
        self._tool_attempt_tracking: Dict[str, Dict[str, int]] = {}
        self._max_actions = max_actions

    def register_action(self, tool_name: str, args: List[Any], 
                       context: Optional[Dict[str, Any]] = None) -> str:
        """Register a new action with full context tracking"""
        if len(self.actions) >= self._max_actions:
            self._evict_oldest_completed()
        
        self._action_counter += 1
        timestamp = int(time.time() * 1000)
        action_id = f"a{self._action_counter}_{timestamp}"
        
        attempt_number = self._get_next_attempt_number(tool_name, args)
        query_simplified = False
        if attempt_number > 1 and args:
            original_query = self._get_last_query(tool_name)
            current_query = str(args[0]) if args else ""
            if original_query and len(current_query.split()) < len(original_query.split()):
                query_simplified = True
        
        self.actions[action_id] = ActionState(
            action_id=action_id, tool_name=tool_name, args=args,
            status=ActionStatus.PENDING, initiated_at=time.time(),
            context=context or {}, attempt_number=attempt_number,
            query_simplified=query_simplified
        )
        
        self.logger.tool(
            f"[Action Manager] Registered {tool_name} as {action_id} "
            f"(attempt #{attempt_number})"
        )
        return action_id
    
    def _evict_oldest_completed(self, count: int = 100):
        """Evict oldest completed actions to maintain size limit"""
        completed = [
            (action_id, action) for action_id, action in self.actions.items()
            if action.status in [ActionStatus.COMPLETED, ActionStatus.FAILED]
            and action.completed_at is not None
        ]
        
        if len(completed) < count:
            return
        
        completed.sort(key=lambda x: x[1].completed_at)
        
        for action_id, _ in completed[:count]:
            del self.actions[action_id]
            self._completed_cache.discard(action_id)
    
    def _get_next_attempt_number(self, tool_name: str, args: List[Any]) -> int:
        """Track retry attempts for tool+query combinations"""
        if not args:
            return 1
        
        tool_name = _intern_tool_name(tool_name)
        query_hash = f"{tool_name}:{str(args[0])}"
        
        if tool_name not in self._tool_attempt_tracking:
            self._tool_attempt_tracking[tool_name] = {}
        
        current_attempt = self._tool_attempt_tracking[tool_name].get(query_hash, 0)
        next_attempt = current_attempt + 1
        self._tool_attempt_tracking[tool_name][query_hash] = next_attempt
        
        return next_attempt
    
    def _get_last_query(self, tool_name: str) -> Optional[str]:
        """Get the last query used for this tool"""
        tool_name = _intern_tool_name(tool_name)
        recent_actions = [
            a for a in sorted(self.actions.values(), key=lambda x: x.initiated_at, reverse=True)
            if a.tool_name == tool_name and a.args
        ]
        
        return str(recent_actions[0].args[0]) if recent_actions else None
    
    def reset_attempt_counter(self, tool_name: str, query: str):
        """Reset attempt counter after successful execution"""
        tool_name = _intern_tool_name(tool_name)
        query_hash = f"{tool_name}:{query}"
        if tool_name in self._tool_attempt_tracking:
            self._tool_attempt_tracking[tool_name][query_hash] = 0
    
    def get_recent_tool_result(self, tool_name: str, max_age: float = 30.0) -> Optional[Dict[str, Any]]:
        """Get most recent result for a tool"""
        tool_name = _intern_tool_name(tool_name)
        current_time = time.time()
        recent_actions = [
            a for a in self.actions.values()
            if a.tool_name == tool_name 
            and a.status in [ActionStatus.COMPLETED, ActionStatus.FAILED]
            and (current_time - a.initiated_at) <= max_age
        ]
        
        if not recent_actions:
            return None
        
        latest = max(recent_actions, key=lambda a: a.initiated_at)
        
        return {
            'tool': tool_name,
            'status': 'success' if latest.status == ActionStatus.COMPLETED else 'failed',
            'result': latest.result if latest.result else None,
            'error': latest.error if latest.error else None,
            'timestamp': latest.initiated_at,
            'elapsed': current_time - latest.initiated_at,
            'attempt_number': latest.attempt_number,
            'args': latest.args
        }
    
    def is_tool_currently_executing(self, tool_name: str) -> bool:
        """Check if tool is currently executing"""
        tool_name = _intern_tool_name(tool_name)
        return any(
            a.tool_name == tool_name 
            and a.status in [ActionStatus.PENDING, ActionStatus.IN_PROGRESS]
            for a in self.actions.values()
        )
    
    def get_tool_awareness_context(self) -> str:
        """Generate tool awareness context for agent"""
        lines = []
        current_time = time.time()
        
        executing = [a for a in self.actions.values() 
                    if a.status in [ActionStatus.PENDING, ActionStatus.IN_PROGRESS]]
        
        if executing:
            lines.append("## TOOLS CURRENTLY EXECUTING")
            lines.append("")
            lines.append("**IMPORTANT**: Results not yet available - do NOT assume outcomes")
            lines.append("")
            
            for action in executing:
                elapsed = current_time - action.initiated_at
                args_preview = str(action.args[0]) if action.args else "no args"
                attempt_info = f" (attempt #{action.attempt_number})" if action.attempt_number > 1 else ""
                
                lines.append(f"- **{action.tool_name}**{attempt_info}: `{args_preview}` - executing for {elapsed:.0f}s")
                
                if elapsed > 20:
                    lines.append(f"   Taking longer than expected")
            
            lines.append("")
            lines.append("[SUCCESS] You can continue thinking and call OTHER tools while waiting")
            lines.append("")
        
        recent_failures = [
            a for a in self.actions.values()
            if a.status == ActionStatus.FAILED
            and (current_time - a.initiated_at) < 120
        ]
        
        if recent_failures:
            lines.append("## RECENT TOOL FAILURES")
            lines.append("")
            
            failures_by_tool = {}
            for action in recent_failures:
                if action.tool_name not in failures_by_tool:
                    failures_by_tool[action.tool_name] = []
                failures_by_tool[action.tool_name].append(action)
            
            for tool_name, actions in failures_by_tool.items():
                most_recent = max(actions, key=lambda a: a.initiated_at)
                elapsed = current_time - most_recent.initiated_at
                attempt = most_recent.attempt_number
                
                error_preview = most_recent.error if most_recent.error else "unknown"
                args_preview = str(most_recent.args[0]) if most_recent.args else ""
                
                lines.append(f"- **{tool_name}** failed {elapsed:.0f}s ago (attempt #{attempt})")
                lines.append(f"  Query: `{args_preview}`")
                lines.append(f"  Error: {error_preview}")
                
                failure_reason = most_recent.context.get('failure_reason', '')
                if failure_reason == 'timeout':
                    if attempt >= 2:
                        lines.append(f"   Already tried {attempt}x - INFORM USER")
                    else:
                        lines.append(f"   Try simpler query if retrying")
                elif failure_reason == 'backend_offline':
                    lines.append(f"   Backend unavailable - inform user")
                
                lines.append("")
        
        return "\n".join(lines) if lines else ""

    def mark_in_progress(self, action_id: str):
        """Mark action as actively executing"""
        action = self.actions.get(action_id)
        if action:
            action.status = ActionStatus.IN_PROGRESS
    
    def complete_action(self, action_id: str, result: Dict[str, Any]):
        """Mark action as completed with result"""
        action = self.actions.get(action_id)
        if action:
            action.status = ActionStatus.COMPLETED
            action.completed_at = time.time()
            action.result = result
            self._completed_cache.add(action_id)
            
            if action.args:
                self.reset_attempt_counter(action.tool_name, str(action.args[0]))
            
            duration = time.time() - action.initiated_at
            self.logger.tool(f"[Action Manager] {action_id} completed in {duration:.2f}s")

    def fail_action(self, action_id: str, error: str, reason: str = ""):
        """Mark action as failed"""
        action = self.actions.get(action_id)
        if action:
            action.status = ActionStatus.FAILED
            action.completed_at = time.time()
            action.error = error
            
            if reason:
                interned_reason = _INTERNED_FAILURE_REASONS.get(reason, sys.intern(reason))
                action.context['failure_reason'] = interned_reason
            
            self._completed_cache.add(action_id)
            self.logger.tool(f"[Action Manager] {action_id} failed: {error}")
    
    def get_pending_actions(self) -> List[ActionState]:
        """Get all pending/in-progress actions"""
        pending_statuses = {ActionStatus.PENDING, ActionStatus.IN_PROGRESS}
        return [
            action for action in self.actions.values()
            if action.status in pending_statuses
        ]
    
    def get_completed_unintegrated(self) -> List[ActionState]:
        """Get completed actions not yet integrated"""
        if not self._completed_cache:
            return []
        
        return [
            self.actions[action_id]
            for action_id in self._completed_cache
            if action_id in self.actions
            and self.actions[action_id].status == ActionStatus.COMPLETED
            and not self.actions[action_id].result_integrated
        ]
    
    def mark_result_integrated(self, action_id: str):
        """Mark result as integrated"""
        action = self.actions.get(action_id)
        if action:
            action.result_integrated = True
            self._completed_cache.discard(action_id)
    
    def get_context_summary(self) -> str:
        """Get summary of in-flight actions"""
        pending = self.get_pending_actions()
        if not pending:
            return ""
        
        lines = ["## PENDING ACTIONS"]
        current_time = time.time()
        
        for action in pending:
            duration = current_time - action.initiated_at
            args_str = ', '.join(str(arg) for arg in action.args)
            if len(action.args) > 2:
                args_str += "..."
            
            status_suffix = f" (attempt #{action.attempt_number})" if action.attempt_number > 1 else ""
            
            lines.append(
                f"- {action.tool_name}({args_str}){status_suffix} "
                f"[{action.status.value}, {duration:.0f}s elapsed]"
            )
        
        return "\n".join(lines)
    
    def get_pending_action_context(self) -> str:
        """Get pending actions context for agent awareness"""
        return self.get_context_summary()
    
    def cleanup_old_actions(self, max_age_seconds: float = 300.0):
        """Clean up old completed/failed actions"""
        current_time = time.time()
        
        old_action_ids = [
            action_id for action_id, action in self.actions.items()
            if action.status in [ActionStatus.COMPLETED, ActionStatus.FAILED]
            and action.completed_at is not None
            and (current_time - action.completed_at) > max_age_seconds
        ]
        
        for action_id in old_action_ids:
            del self.actions[action_id]
            self._completed_cache.discard(action_id)
        
        if current_time - self._last_cleanup > 300.0:
            for tool_name in list(self._tool_attempt_tracking.keys()):
                tool_tracking = self._tool_attempt_tracking[tool_name]
                if len(tool_tracking) > 100:
                    sorted_items = sorted(tool_tracking.items(), key=lambda x: x[1], reverse=True)
                    self._tool_attempt_tracking[tool_name] = dict(sorted_items[:100])
            
            self._last_cleanup = current_time
    
    def get_timed_out_actions(self, timeout_seconds: float = 30.0) -> List[ActionState]:
        """Get actions that have timed out"""
        current_time = time.time()
        pending_statuses = {ActionStatus.PENDING, ActionStatus.IN_PROGRESS}
        
        return [
            action for action in self.actions.values()
            if action.status in pending_statuses
            and (current_time - action.initiated_at) > timeout_seconds
        ]

    def mark_timeout(self, action_id: str):
        """Mark action as timed out"""
        action = self.actions.get(action_id)
        if action:
            action.status = ActionStatus.FAILED
            action.completed_at = time.time()
            action.error = "Timeout: No response within expected time"
            action.context['failure_reason'] = _INTERNED_FAILURE_REASONS['timeout']
            self._completed_cache.add(action_id)
            
            duration = time.time() - action.initiated_at
            self.logger.tool(f"[Action Manager] {action_id} timed out after {duration:.0f}s")

    def get_failed_actions(self) -> List[ActionState]:
        """Get all failed actions"""
        return [
            action for action in self.actions.values()
            if action.status == ActionStatus.FAILED
        ]
    
    def should_throttle_tool(self, tool_name: str, min_interval_seconds: float = 5.0) -> Tuple[bool, Optional[str]]:
        """Check if tool should be throttled"""
        tool_name = _intern_tool_name(tool_name)
        current_time = time.time()
        
        recent_actions = [
            a for a in self.actions.values()
            if a.tool_name == tool_name
        ]
        
        if not recent_actions:
            return False, None
        
        recent_actions.sort(key=lambda x: x.initiated_at, reverse=True)
        most_recent = recent_actions[0]
        
        time_since_last = current_time - most_recent.initiated_at
        if time_since_last < min_interval_seconds:
            return True, f"Tool used {time_since_last:.1f}s ago, wait {min_interval_seconds - time_since_last:.1f}s"
        
        recent_failures = [
            a for a in recent_actions
            if a.status == ActionStatus.FAILED
        ]
        
        if len(recent_failures) >= 2:
            if time_since_last < 30.0:
                return True, f"Tool failed {len(recent_failures)} times recently, wait 30s before retry"
        
        pending = [
            a for a in recent_actions
            if a.status in [ActionStatus.PENDING, ActionStatus.IN_PROGRESS]
        ]
        
        if pending:
            return True, f"Tool already executing ({len(pending)} pending action(s))"
        
        return False, None
    
    def get_recent_failures_summary(self, max_failures: int = 3, max_age: float = 120.0) -> str:
        """Get summary of recent tool failures"""
        current_time = time.time()
        cutoff_time = current_time - max_age
        
        recent_failures = [
            a for a in self.actions.values()
            if a.status == ActionStatus.FAILED
            and a.completed_at is not None
            and a.completed_at > cutoff_time
        ]
        
        if not recent_failures:
            return ""
        
        recent_failures.sort(key=lambda a: a.completed_at, reverse=True)
        failures_to_report = recent_failures[:max_failures]
        
        lines = []
        for action in failures_to_report:
            elapsed = current_time - action.completed_at
            attempt = action.attempt_number
            error_preview = (action.error if action.error else "unknown error")
            args_preview = str(action.args[0]) if action.args else ""
            
            lines.append(
                f"- **{action.tool_name}** failed {elapsed:.0f}s ago "
                f"(attempt #{attempt}): {error_preview}"
            )
            if args_preview:
                lines.append(f"  Args: `{args_preview}`")
        
        return "\n".join(lines) if lines else ""
    
    def get_tools_health_summary(self, include_working: bool = True, max_age: float = 120.0) -> str:
        """Get health summary of all tools"""
        current_time = time.time()
        cutoff_time = current_time - max_age
        
        recent_actions = [
            a for a in self.actions.values()
            if a.completed_at is not None and a.completed_at > cutoff_time
        ]
        
        if not recent_actions:
            return ""
        
        tool_stats = {}
        for action in recent_actions:
            tool = action.tool_name
            if tool not in tool_stats:
                tool_stats[tool] = {
                    'success': 0, 'failed': 0, 'timeout': 0,
                    'total': 0, 'last_status': None, 'last_time': 0
                }
            
            tool_stats[tool]['total'] += 1
            
            if action.status == ActionStatus.COMPLETED:
                tool_stats[tool]['success'] += 1
            elif action.status == ActionStatus.FAILED:
                tool_stats[tool]['failed'] += 1
                failure_reason = action.context.get('failure_reason', '')
                if failure_reason == 'timeout':
                    tool_stats[tool]['timeout'] += 1
            
            if action.completed_at > tool_stats[tool]['last_time']:
                tool_stats[tool]['last_status'] = action.status
                tool_stats[tool]['last_time'] = action.completed_at
        
        if not tool_stats:
            return ""
        
        lines = []
        for tool, stats in sorted(tool_stats.items()):
            total = stats['total']
            success = stats['success']
            failed = stats['failed']
            timeout = stats['timeout']
            success_rate = (success / total) if total > 0 else 0
            
            if timeout >= 2:
                status = "[TIMING OUT]"
                color = "critical"
            elif success_rate < 0.5:
                status = "[UNRELIABLE]"
                color = "warning"
            elif success_rate < 1.0:
                status = "[PARTIAL]"
                color = "caution"
            else:
                status = "[WORKING]"
                color = "ok"
            
            if not include_working and color == "ok":
                continue
            
            elapsed = current_time - stats['last_time']
            lines.append(
                f"- **{tool}**: {status} "
                f"({success}/{total} success, last: {elapsed:.0f}s ago)"
            )
            
            if timeout > 0:
                lines.append(f"   {timeout} timeout(s) - may need simpler queries")
            elif failed > success:
                lines.append(f"   More failures than successes - check availability")
        
        if not lines:
            return ""
        
        return "## TOOL HEALTH STATUS\n\n" + "\n".join(lines)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics"""
        return {
            'total_actions': len(self.actions),
            'pending': len([a for a in self.actions.values() if a.status == ActionStatus.PENDING]),
            'in_progress': len([a for a in self.actions.values() if a.status == ActionStatus.IN_PROGRESS]),
            'completed': len([a for a in self.actions.values() if a.status == ActionStatus.COMPLETED]),
            'failed': len([a for a in self.actions.values() if a.status == ActionStatus.FAILED]),
            'max_actions': self._max_actions,
            'interned_tool_names': len(_TOOL_NAMES_CACHE)
        }