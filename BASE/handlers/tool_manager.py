# Filename: BASE/handlers/tool_manager.py
"""
Tool Manager - FIXED Control Variable to Tool Name Mapping
===========================================================
CRITICAL FIX: Maps control variables (USE_WIKI_SEARCH) to tool names (wiki_search)
"""
from typing import List, Dict, Any, Optional
import asyncio
import time
from pathlib import Path

from BASE.handlers.tool_lifecycle import ToolLifecycleManager


class ToolManager:
    """Simplified tool manager for BaseTool architecture"""
    
    __slots__ = (
        'config', 'controls', 'action_state_manager', 'project_root', 'logger',
        '_active_tools', '_starting_tools', '_control_to_tool_map', '_tools_lock',
        'lifecycle_manager', '_event_loop', '_thought_buffer', 'tool_instances'
    )
    
    def __init__(self, config, controls_module, action_state_manager, project_root, logger=None):
        self.config = config
        self.controls = controls_module
        self.action_state_manager = action_state_manager
        self.project_root = project_root
        self.logger = logger
        
        # Active tool instances (shared with lifecycle manager)
        self._active_tools: Dict[str, Any] = {}
        
        # Track tools currently being started (race condition fix)
        self._starting_tools: set = set()
        
        # CRITICAL FIX: Map control variables to tool names
        self._control_to_tool_map: Dict[str, str] = {}
        
        # Lock for thread-safe operations
        self._tools_lock = asyncio.Lock()
        
        # Lifecycle manager
        self.lifecycle_manager = ToolLifecycleManager(
            project_root=project_root,
            logger=logger
        )
        self.lifecycle_manager.set_active_tools(self._active_tools)
        
        # Event loop and thought buffer
        self._event_loop = None
        self._thought_buffer = None
        
        # For property access compatibility
        self.tool_instances = self._active_tools
        
        # Discover available tools and build control mapping
        discovered = self.lifecycle_manager.discover_tools()
        self._build_control_mapping(discovered)
        
        if self.logger:
            discovered_count = len(self.lifecycle_manager.get_all_metadata())
            self.logger.system(
                f"[Tool Manager] Initialized with {discovered_count} tools discovered"
            )

    def _build_control_mapping(self, discovered_tools: Dict[str, Dict]):
        """Build mapping from control variables to tool names"""
        self._control_to_tool_map.clear()
        
        for tool_name, metadata in discovered_tools.items():
            # CRITICAL FIX: Try both key names (for backward compatibility)
            control_var = metadata.get('control_variable_name') or metadata.get('control_variable_name')
            
            if control_var:
                self._control_to_tool_map[control_var] = tool_name
                
                if self.logger:
                    self.logger.system(
                        f"[Tool Manager] Mapped control: {control_var} → {tool_name}"
                    )
            else:
                if self.logger:
                    self.logger.warning(
                        f"[Tool Manager] No control variable for {tool_name}\n"
                        f"  Metadata keys: {list(metadata.keys())}"
                    )
        
        if self.logger and self._control_to_tool_map:
            self.logger.success(
                f"[Tool Manager] Built control mapping for {len(self._control_to_tool_map)} tools:\n"
                f"  {dict(list(self._control_to_tool_map.items())[:5])}"  # Show first 5
            )
        elif self.logger:
            self.logger.error(
                "[Tool Manager] CRITICAL: Control mapping is EMPTY!\n"
                f"  Discovered tools: {list(discovered_tools.keys())}"
            )
            
    def _resolve_tool_name(self, control_or_tool_name: str) -> Optional[str]:
        if control_or_tool_name in self._control_to_tool_map:
            return self._control_to_tool_map[control_or_tool_name]

        if control_or_tool_name in self.lifecycle_manager._tool_metadata:
            return control_or_tool_name

        return None
    
    async def refresh_tools(self) -> Dict[str, Any]:
        """
        Re-discover tools from disk, rebuild control mapping, and restart
        any tools whose control variable is still enabled.

        Safe to call at runtime. Stops all active tools first, then
        rediscovers and restarts enabled ones.

        Returns:
            Dict with keys: stopped, discovered, started, failed
        """
        stopped = list(self._active_tools.keys())
        self._starting_tools.clear()

        await self.lifecycle_manager.cleanup_all_tools()

        if self.logger:
            self.logger.system(
                f"[Tool Manager] Refresh: stopped {len(stopped)} tool(s), rediscovering..."
            )

        discovered = self.lifecycle_manager.refresh_tool_discovery()
        self._build_control_mapping(discovered)

        if self.logger:
            self.logger.system(
                f"[Tool Manager] Refresh: discovered {len(discovered)} tool(s)"
            )

        started = []
        failed = []

        if not self._event_loop:
            if self.logger:
                self.logger.warning("[Tool Manager] Refresh: no event loop — skipping restart")
            return {'stopped': stopped, 'discovered': list(discovered.keys()), 'started': started, 'failed': failed}

        for tool_name, metadata in self.lifecycle_manager._tool_metadata.items():
            control_var = metadata.get('control_variable_name')
            if not control_var:
                continue

            if not getattr(self.controls, control_var, False):
                continue

            self._starting_tools.add(tool_name)
            try:
                success = await self.lifecycle_manager.start_tool(
                    tool_name=tool_name,
                    config=self.config,
                    controls=self.controls
                )
                if success:
                    started.append(tool_name)
                    if self.logger:
                        self.logger.success(f"[Tool Manager] Refresh: restarted {tool_name}")
                else:
                    failed.append(tool_name)
                    if self.logger:
                        self.logger.error(f"[Tool Manager] Refresh: failed to restart {tool_name}")
            except Exception as e:
                failed.append(tool_name)
                if self.logger:
                    self.logger.error(f"[Tool Manager] Refresh: error restarting {tool_name}: {e}")
            finally:
                self._starting_tools.discard(tool_name)

        if self.logger:
            self.logger.success(
                f"[Tool Manager] Refresh complete — "
                f"started: {started}, failed: {failed}"
            )

        return {
            'stopped': stopped,
            'discovered': list(discovered.keys()),
            'started': started,
            'failed': failed
        }
    
    async def start_enabled_tools(self):
        """
        Start all tools that have their control variables set to True
        
        Call this after initialization to auto-start enabled tools.
        Should be called from CoreInitializer after setting event_loop.
        
        Returns:
            Number of tools started
        """
        if not self._event_loop:
            if self.logger:
                self.logger.warning(
                    "[Tool Manager] Cannot start tools - event loop not set"
                )
            return 0
        
        if self.logger:
            self.logger.system(
                "[Tool Manager] Checking control variables to start enabled tools..."
            )
        
        started_count = 0
        
        # Check each discovered tool
        for tool_name, metadata in self._tool_metadata.items():
            control_var = metadata.get('control_variable_name')
            
            if not control_var:
                continue
            
            # Check if control variable is True
            control_value = getattr(self.controls, control_var, False)
            
            if control_value:
                # Tool should be enabled - start it
                if self.logger:
                    self.logger.system(
                        f"[Tool Manager] Starting {tool_name} ({control_var}=True)"
                    )
                
                # Use handle_control_update to properly start the tool
                self.handle_control_update(control_var, True)
                started_count += 1
                
                # Give each tool a moment to start
                await asyncio.sleep(0.1)
        
        if self.logger:
            if started_count > 0:
                self.logger.success(
                    f"[Tool Manager] Started {started_count} tool(s) from control variables"
                )
            else:
                self.logger.system(
                    "[Tool Manager] No tools enabled in control variables"
                )
        
        return started_count

    # ========================================================================
    # SETUP AND CONFIGURATION
    # ========================================================================
    
    def set_event_loop(self, event_loop):
        """Set event loop for async operations"""
        self._event_loop = event_loop
        self.lifecycle_manager.set_event_loop(event_loop)
        
        if self.logger:
            self.logger.system("[Tool Manager] Event loop set")
    
    def set_thought_buffer(self, thought_buffer):
        """Set thought buffer for tool context injection"""
        self._thought_buffer = thought_buffer
        self.lifecycle_manager.set_thought_buffer(thought_buffer)
        
        if self.logger:
            self.logger.system("[Tool Manager] Thought buffer set")
    
    # ========================================================================
    # METADATA ACCESS
    # ========================================================================
    
    @property
    def _tool_metadata(self) -> Dict:
        """Access tool metadata through lifecycle manager"""
        return self.lifecycle_manager._tool_metadata
    
    def get_tool_metadata(self, tool_name: str) -> Optional[Dict]:
        """Get metadata for a specific tool"""
        return self.lifecycle_manager.get_tool_metadata(tool_name)
    
    def get_all_tool_metadata(self) -> Dict[str, Dict]:
        """Get all tool metadata"""
        return self.lifecycle_manager.get_all_metadata()
    
    def get_control_to_tool_mapping(self) -> Dict[str, str]:
        """
        Get the control variable to tool name mapping
        
        Returns:
            Dict mapping control vars to tool names
        """
        return self._control_to_tool_map.copy()
    
    def get_enabled_tool_names(self) -> List[str]:
        """Get list of enabled (active + starting) tool names"""
        enabled = list(self._active_tools.keys())
        
        # Include tools that are starting up (prevents race conditions)
        starting = list(self._starting_tools)
        
        # Combine and deduplicate
        all_enabled = list(set(enabled + starting))
        
        return sorted(all_enabled)
    
    def get_active_tool_names(self) -> List[str]:
        """Get list of fully active tool names (excludes starting)"""
        return sorted(list(self._active_tools.keys()))
    
    def is_tool_enabled(self, tool_name: str) -> bool:
        """Check if tool is enabled (active OR starting up)"""
        # Resolve to actual tool name
        resolved = self._resolve_tool_name(tool_name)
        if not resolved:
            return False
        
        return (resolved in self._active_tools or 
                resolved in self._starting_tools)
    
    def is_tool_active(self, tool_name: str) -> bool:
        """Check if tool is fully active (not just starting)"""
        # Resolve to actual tool name
        resolved = self._resolve_tool_name(tool_name)
        if not resolved:
            return False
        
        return resolved in self._active_tools
    
    def is_tool_available(self, tool_name: str) -> bool:
        """
        Check if tool is available for execution
        
        A tool is available if:
        1. It's in active tools dict AND
        2. Its is_available() method returns True
        """
        # Resolve to actual tool name
        resolved = self._resolve_tool_name(tool_name)
        if not resolved or resolved not in self._active_tools:
            return False
        
        tool_instance = self._active_tools[resolved]
        
        try:
            return tool_instance.is_available()
        except Exception as e:
            if self.logger:
                self.logger.error(
                    f"[Tool Manager] Error checking availability for {resolved}: {e}"
                )
            return False
    
    async def wait_for_tool_ready(
        self, 
        tool_name: str, 
        timeout: float = 10.0,
        check_interval: float = 0.2
    ) -> bool:
        """
        Wait for a tool to become active and available
        FIXED: Better logging and longer default timeout
        
        Args:
            tool_name: Tool name or control variable
            timeout: Maximum time to wait (seconds)
            check_interval: How often to check (seconds)
        
        Returns:
            True if tool became available, False if timeout
        """
        # Resolve to actual tool name
        resolved = self._resolve_tool_name(tool_name)
        if not resolved:
            if self.logger:
                self.logger.warning(
                    f"[Tool Manager] wait_for_tool_ready: Unknown tool '{tool_name}'"
                )
            return False
        
        start_time = time.time()
        last_log = 0.0
        
        while (time.time() - start_time) < timeout:
            # Check if fully active
            is_active = self.is_tool_active(resolved)
            is_available = self.is_tool_available(resolved) if is_active else False
            
            # Log every 2 seconds
            if time.time() - last_log >= 2.0:
                if self.logger:
                    self.logger.system(
                        f"[Tool Manager] Waiting for {resolved}: "
                        f"active={is_active}, available={is_available}"
                    )
                last_log = time.time()
            
            if is_active and is_available:
                if self.logger:
                    elapsed = time.time() - start_time
                    self.logger.success(
                        f"[Tool Manager] {resolved} ready after {elapsed:.1f}s"
                    )
                return True
            
            # Wait before next check
            await asyncio.sleep(check_interval)
        
        # Timeout - log detailed diagnostics
        if self.logger:
            is_active = self.is_tool_active(resolved)
            is_available = self.is_tool_available(resolved) if is_active else False
            
            self.logger.error(
                f"[Tool Manager] {resolved} NOT ready after {timeout}s timeout\n"
                f"  Active: {is_active}\n"
                f"  Available: {is_available}\n"
                f"  In _active_tools: {resolved in self._active_tools}\n"
                f"  In _starting_tools: {resolved in self._starting_tools}"
            )
            
            # Get tool instance for more diagnostics
            if resolved in self._active_tools:
                tool = self._active_tools[resolved]
                if hasattr(tool, '_clients'):
                    self.logger.error(
                        f"  Tool has {len(tool._clients)} clients\n"
                        f"  Tool has server: {tool._server is not None}"
                    )
        
        return False
    
    # ========================================================================
    # CONTROL VARIABLE MONITORING
    # ========================================================================
    
    def handle_control_update(self, control_variable: str, new_state: bool):
        """
        Handle control variable state change
        
        FIXED: Properly resolves control variable to tool name
        
        Args:
            control_variable: Control variable name (e.g., USE_WIKI_SEARCH)
            new_state: New enabled state (True = enable, False = disable)
        """
        # CRITICAL FIX: Resolve control variable to tool name
        tool_name = self._resolve_tool_name(control_variable)
        
        if not tool_name:
            # if self.logger:
            #     self.logger.warning(
            #         f"[Tool Manager] Unknown control variable: {control_variable} "
            #         f"(no matching tool found)"
            #     )
            return
        
        if self.logger:
            self.logger.system(
                f"[Tool Manager] Control update: {control_variable} → {tool_name} "
                f"({'enabled' if new_state else 'disabled'})"
            )
        
        if new_state:
            # Tool being ENABLED
            
            # Check if already active or starting
            if tool_name in self._active_tools:
                if self.logger:
                    self.logger.system(
                        f"[Tool Manager] {tool_name} already active"
                    )
                return
            
            if tool_name in self._starting_tools:
                if self.logger:
                    self.logger.system(
                        f"[Tool Manager] {tool_name} already starting"
                    )
                return
            
            # Mark as starting immediately (before async call)
            self._starting_tools.add(tool_name)
            
            if self.logger:
                self.logger.system(
                    f"[Tool Manager] {tool_name} marked as starting"
                )
            
            # Start tool asynchronously
            if self._event_loop:
                asyncio.run_coroutine_threadsafe(
                    self._start_tool(tool_name),
                    self._event_loop
                )
            else:
                # No event loop - remove from starting since we can't actually start
                self._starting_tools.discard(tool_name)
                if self.logger:
                    self.logger.warning(
                        f"[Tool Manager] Cannot start {tool_name} - no event loop"
                    )
        else:
            # Tool being DISABLED
            # Remove from starting set immediately
            self._starting_tools.discard(tool_name)
            
            # Stop tool asynchronously
            if self._event_loop:
                asyncio.run_coroutine_threadsafe(
                    self.lifecycle_manager.stop_tool(tool_name),
                    self._event_loop
                )
            else:
                # Fallback: at least remove from active tools
                if tool_name in self._active_tools:
                    del self._active_tools[tool_name]
                    if self.logger:
                        self.logger.system(
                            f"[Tool Manager] Removed {tool_name} from active tools"
                        )
    
    async def _start_tool(self, tool_name: str):
        """
        Start a BaseTool by loading and initializing it
        
        Args:
            tool_name: Name of tool to start (actual tool name, not control var)
        """
        try:
            if self.logger:
                self.logger.system(
                    f"[Tool Manager] Starting {tool_name}..."
                )
            
            # Use lifecycle manager to start
            success = await self.lifecycle_manager.start_tool(
                tool_name=tool_name,
                config=self.config,
                controls=self.controls
            )
            
            if success:
                if self.logger:
                    self.logger.success(
                        f"[Tool Manager] {tool_name} started successfully and is now ACTIVE"
                    )
            else:
                if self.logger:
                    self.logger.error(
                        f"[Tool Manager] Failed to start {tool_name}"
                    )
        
        except Exception as e:
            if self.logger:
                self.logger.error(
                    f"[Tool Manager] Error starting {tool_name}: {e}"
                )
        
        finally:
            # Remove from starting set once complete (success or failure)
            self._starting_tools.discard(tool_name)
            
            if self.logger:
                status = "ACTIVE" if tool_name in self._active_tools else "FAILED"
                self.logger.system(
                    f"[Tool Manager] {tool_name} startup complete: {status}"
                )
    
    # ========================================================================
    # ACTION EXECUTION (Simplified - No Instruction Retrieval)
    # ========================================================================
    
    async def execute_structured_actions(
        self,
        actions: List[Dict[str, Any]],
        thought_buffer
    ):
        """Execute structured actions directly"""
        for action in actions:
            await self._execute_single_action(action, thought_buffer)
    
    async def _execute_single_action(
        self,
        action: Dict[str, Any],
        thought_buffer
    ):
        """Execute a single tool action"""
        tool_call = action.get('tool', '')
        args = action.get('args', [])
        
        if not tool_call:
            if self.logger:
                self.logger.warning("[Tool Manager] Empty tool name in action")
            return
        
        await self.execute_tool_action(
            tool_call=tool_call,
            args=args,
            thought_buffer=thought_buffer
        )
    
    async def execute_tool_action(
        self,
        tool_call: str,
        args: List[Any],
        thought_buffer
    ):
        if '.' in tool_call:
            tool_identifier, command = tool_call.rsplit('.', 1)
        else:
            tool_identifier = tool_call
            command = ''

        tool_name = self._resolve_tool_name(tool_identifier)

        if not tool_name:
            error_msg = f"Unknown tool identifier: {tool_identifier}"
            thought_buffer.add_processed_thought(
                content=error_msg, source='tool_failed', original_ref=tool_call
            )
            if self.logger:
                self.logger.error(f"[Tool Manager] {error_msg}")
            return

        tool_instance = self._active_tools.get(tool_name)

        if not tool_instance:
            error_msg = f"Tool {tool_name} not available (not started or disabled)"
            thought_buffer.add_processed_thought(
                content=error_msg, source='tool_failed', original_ref=tool_call
            )
            if self.logger:
                self.logger.error(f"[Tool Manager] {error_msg}")
            return

        if not self.is_tool_available(tool_name):
            error_msg = f"Tool {tool_name} is not available (initialization incomplete or failed)"
            thought_buffer.add_processed_thought(
                content=error_msg, source='tool_failed', original_ref=tool_call
            )
            if self.logger:
                self.logger.error(f"[Tool Manager] {error_msg}")
            return

        action_id = self.action_state_manager.register_action(
            tool_name=tool_name, args=args
        )
        self.action_state_manager.mark_in_progress(action_id)

        try:
            if self.logger:
                self.logger.tool(
                    f"[Tool Manager] Executing {tool_name}.{command} with args: {args}"
                )

            result = await tool_instance.execute(command, args)

            if result is None:
                error_content = f"{tool_name}.{command} returned None (unhandled code path)"
                self.action_state_manager.fail_action(
                    action_id=action_id, error=error_content
                )
                thought_buffer.add_processed_thought(
                    content=f"{tool_name} failed: {error_content}",
                    source='tool_failed',
                    original_ref=str(args)
                )
                if self.logger:
                    self.logger.error(f"[Tool Manager] {error_content}")
                return

            if result.get('success'):
                content = result.get('content', '')

                self.action_state_manager.complete_action(
                    action_id=action_id, result=result
                )
                thought_buffer.add_processed_thought(
                    content=f"{tool_name} result: {content}",
                    source='tool_result',
                    original_ref=str(args)
                )
                if self.logger:
                    self.logger.success(f"[Tool Manager] {tool_name} completed successfully")

                # Fire registered result callback if present (e.g. GUI components)
                cb = getattr(tool_instance, '_result_callback', None)
                if callable(cb):
                    try:
                        cb(command, result)
                    except Exception as cb_exc:
                        if self.logger:
                            self.logger.error(
                                f"[Tool Manager] Result callback error for {tool_name}: {cb_exc}"
                            )

            else:
                error_content = result.get('content', 'Unknown error')
                self.action_state_manager.fail_action(
                    action_id=action_id, error=error_content
                )
                thought_buffer.add_processed_thought(
                    content=f"{tool_name} failed: {error_content}",
                    source='tool_failed',
                    original_ref=str(args)
                )
                if self.logger:
                    self.logger.error(f"[Tool Manager] {tool_name} failed: {error_content}")

        except asyncio.TimeoutError:
            error_msg = f"{tool_name} timed out"
            self.action_state_manager.fail_action(
                action_id=action_id, error="Timeout", reason="timeout"
            )
            thought_buffer.add_processed_thought(
                content=error_msg, source='tool_timeout', original_ref=str(args)
            )
            if self.logger:
                self.logger.error(f"[Tool Manager] {error_msg}")

        except Exception as e:
            error_msg = f"{tool_name} execution failed: {str(e)}"
            self.action_state_manager.fail_action(
                action_id=action_id, error=str(e)
            )
            thought_buffer.add_processed_thought(
                content=error_msg, source='tool_failed', original_ref=str(args)
            )
            if self.logger:
                self.logger.error(f"[Tool Manager] {error_msg}")
            import traceback
            traceback.print_exc()
    
    # ========================================================================
    # CLEANUP
    # ========================================================================
    
    async def cleanup_all_tools(self):
        """Cleanup all active tools"""
        await self.lifecycle_manager.cleanup_all_tools()
        self._starting_tools.clear()
        
        # if self.logger:
        #     self.logger.system("[Tool Manager] All tools cleaned up")
    
    # ========================================================================
    # STATISTICS AND MONITORING
    # ========================================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get tool manager statistics with optimization metrics"""
        cache_stats = self.lifecycle_manager.get_cache_stats()
        
        return {
            'discovered_count': len(self._tool_metadata),
            'active_count': len(self._active_tools),
            'starting_count': len(self._starting_tools),
            'control_mappings': len(self._control_to_tool_map),
            'enabled_tools': self.get_enabled_tool_names(),
            'active_tools': self.get_active_tool_names(),
            'starting_tools': sorted(list(self._starting_tools)),
            'optimization': {
                'fully_loaded_tools': cache_stats['fully_loaded_tools'],
                'minimal_only_tools': cache_stats['minimal_only_tools'],
                'cached_json_files': cache_stats['cached_json_files'],
                'memory_saved_kb': cache_stats['memory_saved_estimate_kb']
            }
        }

    def get_status_summary(self) -> str:
        """Get human-readable status summary with optimization info"""
        stats = self.get_statistics()
        opt = stats['optimization']
        
        lines = [
            f"Tool Manager Status:",
            f"  Discovered: {stats['discovered_count']}",
            f"  Control Mappings: {stats['control_mappings']}",
            f"  Active: {stats['active_count']}",
            f"  Starting: {stats['starting_count']}",
            f"  Total Enabled: {len(stats['enabled_tools'])}",
            f"",
            f"Optimization:",
            f"  Fully Loaded: {opt['fully_loaded_tools']}",
            f"  Lazy (Minimal): {opt['minimal_only_tools']}",
            f"  JSON Cache Size: {opt['cached_json_files']} files",
            f"  Memory Saved: ~{opt['memory_saved_kb']}KB"
        ]
        
        if stats['active_tools']:
            lines.append(f"")
            lines.append(f"Active Tools: {', '.join(stats['active_tools'])}")
        
        if stats['starting_tools']:
            lines.append(f"Starting Tools: {', '.join(stats['starting_tools'])}")
        
        return "\n".join(lines)