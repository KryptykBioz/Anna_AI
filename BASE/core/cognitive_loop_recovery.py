# Filename: BASE/core/cognitive_loop_recovery.py
"""
Cognitive Loop Recovery Manager
================================
Manages crash recovery for the cognitive loop with configurable auto-restart.

Features:
- Automatic restart after crashes (configurable)
- Exponential backoff to prevent rapid crash loops
- Success-based counter reset
- Manual restart capability
- Comprehensive crash statistics
"""

import time
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class CrashEvent:
    """Record of a single crash event"""
    __slots__ = ('timestamp', 'error_message', 'error_type', 'traceback', 'cycle_count', 'run_duration')
    
    def __init__(self, timestamp: float, error_message: str, error_type: str,
                 traceback: str, cycle_count: int, run_duration: float):
        self.timestamp = timestamp
        self.error_message = error_message
        self.error_type = error_type
        self.traceback = traceback
        self.cycle_count = cycle_count
        self.run_duration = run_duration
    
    def __repr__(self):
        return (f"CrashEvent(timestamp={self.timestamp}, error_type={self.error_type!r}, "
                f"cycle_count={self.cycle_count}, run_duration={self.run_duration})")
    
    def __eq__(self, other):
        if not isinstance(other, CrashEvent):
            return NotImplemented
        return (self.timestamp == other.timestamp and 
                self.error_type == other.error_type and
                self.cycle_count == other.cycle_count)


class CognitiveLoopRecovery:
    """
    Manages cognitive loop crash recovery and restart logic
    
    Auto-restart behavior is controlled by controls.AUTO_RESTART flag:
    - True: Auto-restart up to max_auto_restarts times with exponential backoff
    - False: Stop completely on first error, require manual restart
    """
    
    __slots__ = (
        'controls', 'logger', 'max_auto_restarts', 'initial_cooldown',
        'success_threshold', 'max_backoff', 'crash_count', 'total_crashes',
        'last_crash_time', 'loop_start_time', 'manual_restart_requested',
        'crash_history', 'max_history', 'successful_restarts',
        'manual_restarts', 'total_runtime'
    )
    
    def __init__(
        self,
        controls,
        logger,
        max_auto_restarts: int = 3,
        initial_cooldown: float = 5.0,
        success_threshold: float = 300.0,
        max_backoff: float = 30.0
    ):
        """
        Initialize recovery manager
        
        Args:
            controls: Controls module reference (for AUTO_RESTART flag)
            logger: Logger instance
            max_auto_restarts: Maximum number of auto-restarts before requiring manual intervention
            initial_cooldown: Initial cooldown period in seconds (doubles with each crash)
            success_threshold: Seconds of successful runtime to reset crash counter
            max_backoff: Maximum backoff delay in seconds
        """
        self.controls = controls
        self.logger = logger
        
        # Configuration
        self.max_auto_restarts = max_auto_restarts
        self.initial_cooldown = initial_cooldown
        self.success_threshold = success_threshold
        self.max_backoff = max_backoff
        
        # State tracking
        self.crash_count = 0
        self.total_crashes = 0
        self.last_crash_time = 0.0
        self.loop_start_time = 0.0
        self.manual_restart_requested = False
        
        # Crash history (keep last 10)
        self.crash_history = []
        self.max_history = 10
        
        # Statistics
        self.successful_restarts = 0
        self.manual_restarts = 0
        self.total_runtime = 0.0
    
    # ========================================================================
    # MAIN API
    # ========================================================================
    
    def on_loop_start(self):
        """
        Call when cognitive loop starts/restarts
        Records start time and resets manual restart flag
        """
        self.loop_start_time = time.time()
        self.manual_restart_requested = False
        
        self.logger.system(
            f"[Recovery] Loop started (Crash count: {self.crash_count}/{self.max_auto_restarts})"
        )
    
    def on_crash(
        self,
        error: Exception,
        traceback_str: str,
        cycle_count: int = 0
    ) -> bool:
        """
        Handle a crash event and determine if auto-restart is allowed
        
        Args:
            error: The exception that caused the crash
            traceback_str: Full traceback string
            cycle_count: Number of cycles completed before crash
        
        Returns:
            True if auto-restart should occur, False if manual restart required
        """
        crash_time = time.time()
        run_duration = crash_time - self.loop_start_time if self.loop_start_time > 0 else 0.0
        
        # Check if this was a successful run (ran long enough to reset counter)
        if run_duration >= self.success_threshold:
            self.logger.system(
                f"[Recovery] Loop ran successfully for {run_duration:.1f}s - resetting crash counter"
            )
            self.crash_count = 0  # Reset on success
            self.total_runtime += run_duration
        
        # Increment counters
        self.crash_count += 1
        self.total_crashes += 1
        self.last_crash_time = crash_time
        
        # Record crash event
        crash_event = CrashEvent(
            timestamp=crash_time,
            error_message=str(error),
            error_type=type(error).__name__,
            traceback=traceback_str,
            cycle_count=cycle_count,
            run_duration=run_duration
        )
        
        self.crash_history.append(crash_event)
        if len(self.crash_history) > self.max_history:
            self.crash_history.pop(0)
        
        # Log crash details
        self.logger.error(
            f"[Recovery] CRASH #{self.total_crashes} (Recent: {self.crash_count}/{self.max_auto_restarts})\n"
            f"Error: {crash_event.error_type}: {crash_event.error_message}\n"
            f"Runtime: {run_duration:.1f}s | Cycles: {cycle_count}"
        )
        
        # Check AUTO_RESTART control flag
        auto_restart_enabled = getattr(self.controls, 'AUTO_RESTART', True)
        
        if not auto_restart_enabled:
            self.logger.warning(
                "[Recovery] AUTO_RESTART disabled - stopping completely. Use manual restart."
            )
            return False
        
        # Check if auto-restart is allowed
        if self.crash_count > self.max_auto_restarts:
            self.logger.error(
                f"[Recovery] Maximum auto-restarts exceeded ({self.max_auto_restarts})\n"
                "[Recovery] Manual restart required - use restart_cognition() or GUI button"
            )
            return False
        
        # Auto-restart allowed
        cooldown = self.get_current_cooldown()
        self.logger.warning(
            f"[Recovery] Auto-restart {self.crash_count}/{self.max_auto_restarts} in {cooldown:.1f}s"
        )
        
        return True
    
    def request_manual_restart(self) -> bool:
        """
        Request manual restart of cognitive loop
        Resets crash counter and allows restart regardless of crash count
        
        Returns:
            True if restart should proceed, False if already running
        """
        self.logger.system("[Recovery] Manual restart requested")
        
        # Reset crash counter on manual restart
        old_count = self.crash_count
        self.crash_count = 0
        self.manual_restart_requested = True
        self.manual_restarts += 1
        
        self.logger.system(
            f"[Recovery] Crash counter reset: {old_count} → 0 (Manual restart)"
        )
        
        return True
    
    def get_current_cooldown(self) -> float:
        """
        Calculate current cooldown period with exponential backoff
        
        Returns:
            Cooldown duration in seconds
        """
        # Exponential backoff: initial * (2 ^ (crashes - 1))
        backoff = self.initial_cooldown * (2 ** (self.crash_count - 1))
        return min(backoff, self.max_backoff)
    
    def get_cooldown_remaining(self) -> float:
        """
        Get remaining cooldown time
        
        Returns:
            Remaining cooldown in seconds (0 if cooldown expired)
        """
        if self.last_crash_time == 0:
            return 0.0
        
        cooldown = self.get_current_cooldown()
        elapsed = time.time() - self.last_crash_time
        remaining = max(0.0, cooldown - elapsed)
        
        return remaining
    
    def should_restart_now(self) -> bool:
        """
        Check if enough time has passed to restart
        
        Returns:
            True if cooldown period has elapsed
        """
        return self.get_cooldown_remaining() == 0.0
    
    # ========================================================================
    # STATISTICS & REPORTING
    # ========================================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive recovery statistics
        
        Returns:
            Dictionary with all recovery stats
        """
        current_runtime = 0.0
        if self.loop_start_time > 0:
            current_runtime = time.time() - self.loop_start_time
        
        auto_restart_enabled = getattr(self.controls, 'AUTO_RESTART', True)
        
        return {
            'auto_restart_enabled': auto_restart_enabled,
            'crash_count': self.crash_count,
            'max_auto_restarts': self.max_auto_restarts,
            'total_crashes': self.total_crashes,
            'successful_restarts': self.successful_restarts,
            'manual_restarts': self.manual_restarts,
            'current_cooldown': self.get_current_cooldown(),
            'cooldown_remaining': self.get_cooldown_remaining(),
            'can_auto_restart': self.crash_count <= self.max_auto_restarts,
            'current_runtime': current_runtime,
            'total_runtime': self.total_runtime,
            'success_threshold': self.success_threshold,
            'crash_history_count': len(self.crash_history),
            'last_crash_time': datetime.fromtimestamp(self.last_crash_time).isoformat() if self.last_crash_time > 0 else None,
        }
    
    def get_recent_crashes(self, limit: int = 5) -> list:
        """
        Get recent crash events
        
        Args:
            limit: Maximum number of crashes to return
        
        Returns:
            List of recent CrashEvent objects (most recent first)
        """
        return list(reversed(self.crash_history[-limit:]))
    
    def format_crash_summary(self) -> str:
        """
        Format a human-readable crash summary
        
        Returns:
            Formatted string with crash statistics
        """
        stats = self.get_statistics()
        
        lines = [
            "=== Cognitive Loop Recovery Status ===",
            f"Auto-Restart: {'ENABLED' if stats['auto_restart_enabled'] else 'DISABLED'}",
            f"Recent Crashes: {stats['crash_count']}/{stats['max_auto_restarts']}",
            f"Total Crashes: {stats['total_crashes']}",
            f"Manual Restarts: {stats['manual_restarts']}",
            f"Total Runtime: {stats['total_runtime']:.1f}s",
            f"Current Runtime: {stats['current_runtime']:.1f}s",
        ]
        
        if stats['cooldown_remaining'] > 0:
            lines.append(f"Cooldown: {stats['cooldown_remaining']:.1f}s remaining")
        
        if stats['crash_count'] > 0:
            lines.append("")
            lines.append("Recent Crashes:")
            for i, crash in enumerate(self.get_recent_crashes(3), 1):
                crash_time = datetime.fromtimestamp(crash.timestamp).strftime("%H:%M:%S")
                lines.append(
                    f"  {i}. [{crash_time}] {crash.error_type}: {crash.error_message[:50]}"
                )
        
        return "\n".join(lines)
    
    def reset_statistics(self):
        """Reset all statistics (useful for testing)"""
        self.crash_count = 0
        self.total_crashes = 0
        self.last_crash_time = 0.0
        self.loop_start_time = 0.0
        self.crash_history.clear()
        self.successful_restarts = 0
        self.manual_restarts = 0
        self.total_runtime = 0.0
        
        self.logger.system("[Recovery] Statistics reset")
    
    # ========================================================================
    # CONFIGURATION
    # ========================================================================
    
    def update_config(
        self,
        max_auto_restarts: Optional[int] = None,
        initial_cooldown: Optional[float] = None,
        success_threshold: Optional[float] = None,
        max_backoff: Optional[float] = None
    ):
        """
        Update recovery configuration
        
        Args:
            max_auto_restarts: New max auto-restart count
            initial_cooldown: New initial cooldown seconds
            success_threshold: New success threshold seconds
            max_backoff: New maximum backoff seconds
        """
        if max_auto_restarts is not None:
            self.max_auto_restarts = max_auto_restarts
            self.logger.system(f"[Recovery] Max auto-restarts: {max_auto_restarts}")
        
        if initial_cooldown is not None:
            self.initial_cooldown = initial_cooldown
            self.logger.system(f"[Recovery] Initial cooldown: {initial_cooldown}s")
        
        if success_threshold is not None:
            self.success_threshold = success_threshold
            self.logger.system(f"[Recovery] Success threshold: {success_threshold}s")
        
        if max_backoff is not None:
            self.max_backoff = max_backoff
            self.logger.system(f"[Recovery] Max backoff: {max_backoff}s")