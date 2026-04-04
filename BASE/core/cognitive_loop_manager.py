# Filename: BASE/core/cognitive_loop_manager.py
"""
Cognitive Loop Manager - WITH CRASH RECOVERY
=============================================
Agent decides with <speak>YES/NO</speak> - that's it
FIXED: Autonomous responses now properly saved to memory
NEW: Crash recovery with configurable auto-restart (AUTO_RESTART control)
NEW: SpeakJudge secondary AI veto to prevent repetitive TTS output

Crash Recovery Behavior:
- When AUTO_RESTART=True: Auto-restarts up to 3 times with exponential backoff
- When AUTO_RESTART=False: Stops completely on first error, requires manual restart
- Manual restart always available via restart_cognition()
"""

import asyncio
import time
import traceback
from typing import Optional
from BASE.core.logger import Logger
from BASE.core.cognitive_loop_recovery import CognitiveLoopRecovery
from BASE.core.speak_judge import SpeakJudge


class CognitiveLoopManager:
    """Manages continuous autonomous thinking loop with crash recovery"""
    
    __slots__ = (
        'thought_processor', 'controls', 'logger', 'is_running', 'loop_task',
        'total_cycles', 'reactive_cycles', 'proactive_cycles', 'idle_cycles',
        'last_stats_log', 'last_response_time', 'min_response_interval',
        'autonomous_response_callback', 'recovery', 'ai_core_ref', 'speak_judge'
    )
    
    def __init__(self, thought_processor, controls, logger: Logger):
        self.thought_processor = thought_processor
        self.controls = controls
        self.logger = logger
        
        self.is_running = False
        self.loop_task = None
        
        # Statistics
        self.total_cycles = 0
        self.reactive_cycles = 0
        self.proactive_cycles = 0
        self.idle_cycles = 0
        self.last_stats_log = time.time()
        
        # Response rate limiting
        self.last_response_time = 0.0
        self.min_response_interval = 30.0
        
        # Callback for autonomous responses
        self.autonomous_response_callback = None
        
        # AI Core reference
        self.ai_core_ref = None
        
        # Crash recovery manager
        self.recovery = CognitiveLoopRecovery(
            controls=controls,
            logger=logger,
            max_auto_restarts=3,
            initial_cooldown=5.0,
            success_threshold=300.0,  # 5 minutes of success resets counter
            max_backoff=30.0
        )
        
        # Secondary AI judge - vetoes low-value TTS triggers
        self.speak_judge = SpeakJudge(
            thought_processor=thought_processor,
            logger=logger
        )
        
        self.logger.system("[Cognitive Loop] Recovery system initialized")
    
    async def start_continuous_loop(self):
        """Start the continuous cognitive loop"""
        if self.is_running:
            self.logger.warning("[Cognitive Loop] Already running")
            return
        
        self.is_running = True
        self.logger.system("[Cognitive Loop] Starting - Agent decides with <speak>YES/NO</speak>")
        
        # Update processing delay logging
        LIMIT_PROCESSING = getattr(self.controls, 'LIMIT_PROCESSING', False)
        if LIMIT_PROCESSING:
            delay = getattr(self.controls, 'PROCESSING_DELAY', 30)
            self.logger.system(f"[Cognitive Loop] Processing rate: 1 cycle per {delay}s")
        else:
            self.logger.system("[Cognitive Loop] Processing rate: Maximum")
        
        # Update response interval (LIMIT_SPEAKING)
        LIMIT_SPEAKING = getattr(self.controls, 'LIMIT_SPEAKING', False)
        if LIMIT_SPEAKING:
            speaking_delay = getattr(self.controls, 'SPEAKING_DELAY', 60)
            self.min_response_interval = speaking_delay
            self.logger.system(f"[Cognitive Loop] Speaking rate: 1 response per {speaking_delay}s")
        else:
            self.min_response_interval = 0.0
            self.logger.system("[Cognitive Loop] Speaking rate: Unlimited (judge active)")
        
        # Record loop start for recovery tracking
        self.recovery.on_loop_start()
        
        self.loop_task = asyncio.create_task(self._cognitive_loop())
    
    async def stop_continuous_loop(self):
        """Stop the cognitive loop gracefully"""
        if not self.is_running:
            return
        
        self.is_running = False
        self.logger.system("[Cognitive Loop] Stopping...")
        
        if self.loop_task:
            self.loop_task.cancel()
            try:
                await self.loop_task
            except asyncio.CancelledError:
                pass
        
        self.logger.system("[Cognitive Loop] Stopped")
    
    async def restart_cognition(self):
        """
        Manually restart the cognitive loop
        This resets the crash counter and allows restart regardless of crash count
        """
        self.logger.system("[Cognitive Loop] Manual restart requested")
        
        # Request manual restart (resets crash counter)
        self.recovery.request_manual_restart()
        
        # Stop current loop if running
        if self.is_running:
            await self.stop_continuous_loop()
            await asyncio.sleep(1.0)  # Brief pause
        
        # Start fresh loop
        await self.start_continuous_loop()
        
        self.logger.system("[SUCCESS] [Cognitive Loop] Manual restart complete")
    
    async def _cognitive_loop(self):
        """
        Main cognitive loop with crash recovery
        """
        self.logger.system("[Cognitive Loop] Agent-driven response mode")
        
        while self.is_running:
            try:
                # Kill command check
                if self.thought_processor.thought_buffer.is_shutdown_requested():
                    self.logger.system("[Cognitive Loop] Kill command - STOPPING")
                    self.is_running = False
                    break
                
                if hasattr(self, 'ai_core_ref') and self.ai_core_ref:
                    if self.ai_core_ref.shutdown_flag.is_set():
                        self.logger.system("[Cognitive Loop] AI Core shutdown - STOPPING")
                        self.is_running = False
                        break
                
                self.total_cycles += 1
                
                # [CRITICAL FIX] Update response interval dynamically each cycle
                # This allows runtime changes to SPEAKING_DELAY to take effect
                LIMIT_SPEAKING = getattr(self.controls, 'LIMIT_SPEAKING', False)
                if LIMIT_SPEAKING:
                    speaking_delay = getattr(self.controls, 'SPEAKING_DELAY', 60)
                    self.min_response_interval = speaking_delay
                else:
                    self.min_response_interval = 0.0
                
                # ============================================================
                # PROCESS THOUGHTS (reactive or proactive)
                # Agent outputs <speak>YES/NO</speak> during this
                # ============================================================
                context_parts = await self.thought_processor.thinking_modes.build_thought_context()
                processing_occurred = await self.thought_processor.process_thoughts(
                    context_parts=context_parts
                )
                
                if processing_occurred:
                    # Track cycle type
                    if self.thought_processor.thought_buffer.get_unprocessed_events():
                        self.reactive_cycles += 1
                        cycle_type = "reactive"
                    else:
                        self.proactive_cycles += 1
                        cycle_type = "proactive"
                    
                    stats = self.thought_processor.thought_buffer.get_thinking_stats()
                    time_since_user = self.thought_processor.thought_buffer.get_time_since_last_user_input()
                    
                    self.logger.thinking(
                        f"[Loop] Cycle {self.total_cycles} ({cycle_type}) | "
                        f"Stream: {stats['consecutive_proactive']} | "
                        f"Momentum: {stats['momentum']:.2f} | "
                        f"Last input: {time_since_user:.0f}s ago"
                    )
                else:
                    self.idle_cycles += 1
                
                # ============================================================
                # CHECK IF AGENT SAID <speak>YES</speak>
                # Two-stage gate: rate limit → speak judge → generate
                # ============================================================
                if self.thought_processor.thought_buffer.response_trigger.should_respond():
                    time_since_last_response = time.time() - self.last_response_time

                    if LIMIT_SPEAKING and time_since_last_response < self.min_response_interval:
                        remaining = self.min_response_interval - time_since_last_response
                        self.thought_processor.thought_buffer.response_trigger.clear()
                        self.logger.system(
                            f"[Rate Limit] Speaking blocked - {remaining:.1f}s remaining "
                            f"(delay: {self.min_response_interval}s). Agent continues thinking."
                        )
                    else:
                        # Secondary AI veto before TTS fires
                        time_since_user = self.thought_processor.thought_buffer.get_time_since_last_user_input()
                        judge_approved = self.speak_judge.should_speak(
                            time_since_last_response=time_since_last_response,
                            time_since_last_user=time_since_user
                        )

                        if judge_approved:
                            await self._generate_response()
                        else:
                            self.thought_processor.thought_buffer.response_trigger.clear()
                
                # Log statistics periodically
                current_time = time.time()
                if current_time - self.last_stats_log >= 300:
                    self._log_statistics()
                    self.last_stats_log = current_time
                
                # Minimal delay to prevent tight loop spinning
                await asyncio.sleep(0.1)
                
            except asyncio.CancelledError:
                self.logger.system("[Cognitive Loop] Cancelled")
                break
                
            except Exception as e:
                self.logger.error(f"[Cognitive Loop] CRASHED: {e}")
                traceback.print_exc()
                
                # Use recovery.on_crash instead of should_auto_restart
                should_restart = self.recovery.on_crash(
                    error=e,
                    traceback_str=traceback.format_exc(),
                    cycle_count=self.total_cycles
                )
                
                if should_restart:
                    cooldown = self.recovery.get_current_cooldown()
                    self.logger.warning(
                        f"[Recovery] Auto-restart #{self.recovery.crash_count} "
                        f"in {cooldown:.1f}s"
                    )
                    
                    # Wait cooldown
                    await asyncio.sleep(cooldown)
                    
                    # Record successful restart
                    self.recovery.successful_restarts += 1
                    
                    # Continue loop (restart)
                    self.logger.system("[Recovery] Restarting cognitive loop...")
                    continue
                else:
                    # Don't auto-restart
                    if self.recovery.crash_count > self.recovery.max_auto_restarts:
                        self.logger.error(
                            f"[Recovery] Max auto-restarts ({self.recovery.max_auto_restarts}) "
                            "reached. Loop STOPPED."
                        )
                    else:
                        # AUTO_RESTART is False
                        self.logger.warning(
                            "[Recovery] AUTO_RESTART disabled. Loop STOPPED."
                        )
                    
                    self.logger.system(
                        "[Recovery] Use restart_cognition() or GUI button to restart"
                    )
                    break
        
        self.logger.system("[Cognitive Loop] STOPPED")

    async def _generate_response(self):
        """
        Generate autonomous spoken response
        NOTE: Rate limiting and speak judge handled in cognitive loop before this is called
        """
        # Check AI core
        if not hasattr(self, 'ai_core_ref') or not self.ai_core_ref:
            self.logger.warning("[Autonomous] No AI core - cannot generate")
            self.thought_processor.thought_buffer.response_trigger.clear()
            return
        
        try:
            # Use processing_delegator to generate response
            if hasattr(self.ai_core_ref, 'processing_delegator'):
                delegator = self.ai_core_ref.processing_delegator
                
                # Generate autonomous response
                response = await delegator._generate_responsive_response(
                    user_text="",
                    context_parts=[],
                    chat_context=None,
                    is_chat_engagement=False
                )
                
                if response:
                    # Add response echo to thought buffer FIRST
                    thought_buffer = self.thought_processor.thought_buffer
                    thought_buffer.add_response_echo(
                        response_text=response,
                        timestamp=time.time()
                    )
                    
                    # Save to memory
                    if hasattr(self.ai_core_ref, 'memory_manager'):
                        memory_mgr = self.ai_core_ref.memory_manager
                        if self.controls.SAVE_MEMORY:
                            saved_entry = memory_mgr.save_bot_response(response)
                            
                            if saved_entry:
                                self.logger.memory(
                                    f"[Autonomous] Saved (Short: {len(memory_mgr.short_memory)})"
                                )
                    
                    # CRITICAL FIX: Wait for group chat tool to be ready (10 seconds)
                    if getattr(self.controls, 'IN_GROUP_CHAT', False):
                        if hasattr(self.ai_core_ref, 'tool_manager') and self.ai_core_ref.tool_manager:
                            # Wait for tool to be active (10 seconds for group chat)
                            tool_ready = await self.ai_core_ref.tool_manager.wait_for_tool_ready(
                                'group_chat',
                                timeout=10.0
                            )
                            
                            if tool_ready:
                                group_chat_tool = self.ai_core_ref.tool_manager._active_tools.get('group_chat')
                                if group_chat_tool and hasattr(group_chat_tool, 'broadcast_spoken_response'):
                                    try:
                                        # Verify tool has connections
                                        if len(group_chat_tool._clients) == 0:
                                            self.logger.warning(
                                                "[Autonomous] [Group Chat] Tool ready but no peer connections"
                                            )
                                        
                                        result = group_chat_tool.broadcast_spoken_response(response)
                                        if result:
                                            self.logger.success(
                                                f"[Autonomous] [Group Chat] Broadcast to "
                                                f"{len(group_chat_tool._clients)} peer(s)"
                                            )
                                        else:
                                            self.logger.warning(
                                                f"[Autonomous] [Group Chat] Broadcast returned False"
                                            )
                                    except Exception as e:
                                        self.logger.error(
                                            f"[Autonomous] [Group Chat] Broadcast failed: {e}"
                                        )
                                        import traceback
                                        traceback.print_exc()
                            else:
                                self.logger.warning(
                                    "[Autonomous] [Group Chat] Tool not ready after 10s wait"
                                )
                    
                    # Call the callback to queue for GUI
                    if self.autonomous_response_callback:
                        try:
                            self.autonomous_response_callback(response)
                            
                            # Clear trigger ONLY after successful callback
                            thought_buffer.response_trigger.clear()
                            
                        except Exception as e:
                            self.logger.error(f"[Autonomous] Callback error: {e}")
                            import traceback
                            traceback.print_exc()
                            return
                    else:
                        self.logger.error("[Autonomous] [FAILED] No callback registered!")
                        return
                    
                    # Update timestamp (only after successful callback)
                    self.last_response_time = time.time()
                else:
                    self.logger.warning("[Autonomous] Empty response")
                    self.thought_processor.thought_buffer.response_trigger.clear()
            else:
                self.logger.error("[Autonomous] No processing_delegator")
                self.thought_processor.thought_buffer.response_trigger.clear()
            
        except Exception as e:
            self.logger.error(f"[Autonomous] Error: {e}")
            import traceback
            traceback.print_exc()
            self.thought_processor.thought_buffer.response_trigger.clear()

    def set_ai_core(self, ai_core):
        """Inject AI core reference"""
        self.ai_core_ref = ai_core
        # No nested cognitive_loop - this IS the cognitive loop manager
        # The ai_core reference is now set and will be used during loop execution
        
    def _log_statistics(self):
        """Log statistics"""
        total = self.total_cycles
        if total == 0:
            return
        
        reactive = self.reactive_cycles
        proactive = self.proactive_cycles
        idle = self.idle_cycles
        
        reactive_pct = (reactive / total * 100)
        proactive_pct = (proactive / total * 100)
        idle_pct = (idle / total * 100)
        
        judge_stats = self.speak_judge.get_stats()
        
        self.logger.system(
            f"[Loop Stats] Total: {total} | "
            f"Reactive: {reactive} ({reactive_pct:.1f}%) | "
            f"Proactive: {proactive} ({proactive_pct:.1f}%) | "
            f"Idle: {idle} ({idle_pct:.1f}%) | "
            f"Judge: {judge_stats['approvals']}A/{judge_stats['denials']}D "
            f"({judge_stats['denial_rate']:.0%} denied)"
        )
    
    def get_statistics(self) -> dict:
        """Get comprehensive statistics including recovery and judge stats"""
        base_stats = {
            'total_cycles': self.total_cycles,
            'reactive_cycles': self.reactive_cycles,
            'proactive_cycles': self.proactive_cycles,
            'idle_cycles': self.idle_cycles,
            'is_running': self.is_running,
            'last_response_time': self.last_response_time,
            'min_response_interval': self.min_response_interval
        }
        
        # Add recovery statistics
        recovery_stats = self.recovery.get_statistics()
        base_stats['recovery'] = recovery_stats

        # Add speak judge statistics
        base_stats['speak_judge'] = self.speak_judge.get_stats()
        
        return base_stats
    
    def get_recovery_status(self) -> str:
        """Get formatted recovery status string"""
        return self.recovery.format_crash_summary()