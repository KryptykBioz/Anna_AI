# Filename: BASE/core/tool_hot_reload_manager.py
"""
Hot-Reload Manager - Tool-Specific Implementation
=================================================
Integrates with BaseTool architecture and ToolManager
Enables live editing and reloading of tools without restart

Features:
- Tool-specific hot-reloading (BASE/tools/installed/)
- State preservation across reloads
- Version tracking per tool
- GUI integration with reload buttons
- Rollback on failure
- Works with existing ToolManager and ToolLifecycleManager

Usage:
    # In AI Core initialization
    hot_reload = HotReloadManager(
        project_root=project_root,
        logger=logger,
        config=config
    )
    
    # Register tool manager
    hot_reload.register_tool_manager(tool_manager)
    
    # Reload a specific tool
    success = await hot_reload.reload_tool('minecraft')
    
    # Get reload button for GUI
    reload_btn = hot_reload.create_reload_button(parent, 'minecraft', callback)
"""

import importlib
import sys
import time
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from datetime import datetime


class HotReloadManager:
    """
    Manages hot-reloading of BaseTool architecture tools
    
    Integrates with:
    - ToolManager (for active tool instances)
    - ToolLifecycleManager (for loading tool classes)
    - GUI (provides reload buttons for tool panels)
    """
    
    def __init__(self, project_root: Path, logger, config=None):
        """
        Initialize hot-reload manager for tools
        
        Args:
            project_root: Project root path
            logger: Logger instance
            config: Config instance (optional)
        """
        self.project_root = project_root
        self.logger = logger
        self.config = config
        
        # Tool directories
        self.tools_dir = project_root / 'BASE' / 'tools' / 'installed'
        
        # References to external managers
        self.tool_manager = None
        self.lifecycle_manager = None
        self.controls = None
        
        # Tracking
        self.reload_count: Dict[str, int] = {}
        self.last_reload_time: Dict[str, float] = {}
        self.reload_history = []
        
        # State preservation
        self.state_cache: Dict[str, Dict] = {}
        
        # GUI callbacks
        self.gui_callbacks: Dict[str, Callable] = {}
        
        self.logger.system("[Hot-Reload] Tool reload manager initialized")
    
    # ========================================================================
    # REGISTRATION
    # ========================================================================
    
    def register_tool_manager(self, tool_manager):
        """
        Register ToolManager for hot-reload capability
        
        Args:
            tool_manager: ToolManager instance
        """
        self.tool_manager = tool_manager
        
        # Get lifecycle manager reference
        if hasattr(tool_manager, 'lifecycle_manager'):
            self.lifecycle_manager = tool_manager.lifecycle_manager
        
        # Get controls reference
        if hasattr(tool_manager, 'controls'):
            self.controls = tool_manager.controls
        
        # Initialize reload tracking for all tools
        all_metadata = tool_manager.get_all_tool_metadata()
        for tool_name in all_metadata.keys():
            self.reload_count[tool_name] = 0
        
        self.logger.system(
            f"[Hot-Reload] Registered tool manager "
            f"({len(all_metadata)} tools available)"
        )
    
    def register_gui_callback(self, tool_name: str, callback: Callable):
        """
        Register GUI callback for tool reload status updates
        
        Args:
            tool_name: Name of tool
            callback: Callback function(success: bool, message: str)
        """
        self.gui_callbacks[tool_name] = callback
    
    # ========================================================================
    # HOT-RELOAD OPERATIONS
    # ========================================================================
    
    async def reload_tool(self, tool_name: str, notify_gui: bool = True) -> bool:
        """
        Hot-reload a specific tool
        
        Process:
        1. Check if tool is active
        2. Save current tool state
        3. Stop the tool (call end())
        4. Reload tool.py module
        5. Restart the tool (call start())
        6. Restore state
        7. Update version tracking
        8. Notify GUI
        
        Args:
            tool_name: Name of tool to reload
            notify_gui: Whether to notify GUI callback
        
        Returns:
            True if reload successful, False otherwise
        """
        if not self.tool_manager or not self.lifecycle_manager:
            self.logger.error("[Hot-Reload] Tool manager not registered")
            return False
        
        # Check if tool exists
        tool_metadata = self.tool_manager.get_tool_metadata(tool_name)
        if not tool_metadata:
            error_msg = f"Tool not found: {tool_name}"
            self.logger.error(f"[Hot-Reload] {error_msg}")
            if notify_gui:
                self._notify_gui(tool_name, False, error_msg)
            return False
        
        # Get tool file path
        tool_info = self.lifecycle_manager._tool_metadata.get(tool_name)
        if not tool_info:
            error_msg = f"Tool metadata not found: {tool_name}"
            self.logger.error(f"[Hot-Reload] {error_msg}")
            if notify_gui:
                self._notify_gui(tool_name, False, error_msg)
            return False
        
        tool_file = tool_info['tool_file']
        
        start_time = time.time()
        was_active = tool_name in self.tool_manager.tool_instances
        
        try:
            self.logger.system(f"[Hot-Reload] Reloading {tool_name}...")
            
            # Step 1: Save state if tool is active
            if was_active:
                self._save_tool_state(tool_name)
            
            # Step 2: Stop tool if active
            if was_active:
                await self.lifecycle_manager.stop_tool(tool_name)
                self.logger.system(f"[Hot-Reload] Stopped {tool_name}")
            
            # Step 3: Reload tool.py module
            module_name = f"tool_{tool_name}"
            
            if module_name in sys.modules:
                # Module already loaded, reload it
                module = sys.modules[module_name]
                importlib.reload(module)
                self.logger.system(f"[Hot-Reload] Reloaded module: {module_name}")
            else:
                # First time load (shouldn't happen, but handle it)
                spec = importlib.util.spec_from_file_location(module_name, str(tool_file))
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
                    self.logger.system(f"[Hot-Reload] Loaded module: {module_name}")
            
            # Step 4: Restart tool if it was active
            if was_active:
                success = await self.lifecycle_manager.start_tool(
                    tool_name=tool_name,
                    config=self.config,
                    controls=self.controls
                )
                
                if not success:
                    error_msg = f"Failed to restart {tool_name}"
                    self.logger.error(f"[Hot-Reload] {error_msg}")
                    if notify_gui:
                        self._notify_gui(tool_name, False, error_msg)
                    return False
                
                self.logger.system(f"[Hot-Reload] Restarted {tool_name}")
                
                # Step 5: Restore state
                if tool_name in self.state_cache:
                    self._restore_tool_state(tool_name)
            
            # Step 6: Update tracking
            self.reload_count[tool_name] = self.reload_count.get(tool_name, 0) + 1
            self.last_reload_time[tool_name] = time.time()
            
            reload_time = time.time() - start_time
            
            # Step 7: Record in history
            self.reload_history.append({
                'tool_name': tool_name,
                'timestamp': datetime.now().isoformat(),
                'success': True,
                'was_active': was_active,
                'reload_time': reload_time,
                'version': self.reload_count[tool_name]
            })
            
            success_msg = (
                f"Reloaded {tool_name} "
                f"(v{self.reload_count[tool_name]}) "
                f"in {reload_time:.2f}s"
            )
            
            self.logger.system(f"[Hot-Reload] SUCCESS - {success_msg}")
            
            # Step 8: Notify GUI
            if notify_gui:
                self._notify_gui(tool_name, True, success_msg)
            
            return True
            
        except Exception as e:
            reload_time = time.time() - start_time
            error_msg = f"Failed to reload {tool_name}: {str(e)}"
            
            self.logger.error(f"[Hot-Reload] {error_msg}")
            import traceback
            traceback.print_exc()
            
            # Record failure in history
            self.reload_history.append({
                'tool_name': tool_name,
                'timestamp': datetime.now().isoformat(),
                'success': False,
                'error': str(e),
                'reload_time': reload_time
            })
            
            # Notify GUI
            if notify_gui:
                self._notify_gui(tool_name, False, error_msg)
            
            return False
    
    def reload_tool_sync(self, tool_name: str) -> bool:
        """
        Synchronous wrapper for reload_tool (for GUI buttons)
        
        Args:
            tool_name: Name of tool to reload
        
        Returns:
            True if reload successful, False otherwise
        """
        # Get event loop
        if not self.tool_manager or not hasattr(self.tool_manager, 'event_loop'):
            self.logger.error("[Hot-Reload] No event loop available")
            return False
        
        event_loop = self.tool_manager.event_loop
        
        if event_loop is None:
            self.logger.error("[Hot-Reload] Event loop is None")
            return False
        
        try:
            # Schedule coroutine in event loop
            future = asyncio.run_coroutine_threadsafe(
                self.reload_tool(tool_name),
                event_loop
            )
            
            # Wait for result (with timeout)
            return future.result(timeout=10.0)
            
        except Exception as e:
            self.logger.error(f"[Hot-Reload] Sync reload error: {e}")
            return False
    
    # ========================================================================
    # STATE MANAGEMENT
    # ========================================================================
    
    def _save_tool_state(self, tool_name: str):
        """Save tool state before reload"""
        tool_instance = self.tool_manager.tool_instances.get(tool_name)
        if not tool_instance:
            return
        
        # Check if tool implements state management
        if hasattr(tool_instance, 'get_state'):
            try:
                state = tool_instance.get_state()
                self.state_cache[tool_name] = state
                self.logger.system(f"[Hot-Reload] Saved state for {tool_name}")
                return
            except Exception as e:
                self.logger.warning(f"[Hot-Reload] Failed to save state: {e}")
        
        # Fallback: Auto-extract serializable attributes
        state = {}
        for attr in dir(tool_instance):
            # Skip private, methods, and known non-state attributes
            if attr.startswith('_') or callable(getattr(tool_instance, attr, None)):
                continue
            
            # Skip known system attributes
            if attr in ['name', 'logger', 'config', 'controls']:
                continue
            
            try:
                value = getattr(tool_instance, attr)
                if isinstance(value, (int, float, str, bool, list, dict, tuple)):
                    state[attr] = value
            except:
                pass
        
        if state:
            self.state_cache[tool_name] = state
            self.logger.system(
                f"[Hot-Reload] Auto-saved {len(state)} attributes for {tool_name}"
            )
    
    def _restore_tool_state(self, tool_name: str):
        """Restore tool state after reload"""
        state = self.state_cache.get(tool_name)
        if not state:
            return
        
        tool_instance = self.tool_manager.tool_instances.get(tool_name)
        if not tool_instance:
            return
        
        # Check if tool implements state management
        if hasattr(tool_instance, 'set_state'):
            try:
                tool_instance.set_state(state)
                self.logger.system(f"[Hot-Reload] Restored state for {tool_name}")
                return
            except Exception as e:
                self.logger.warning(f"[Hot-Reload] Failed to restore state: {e}")
        
        # Fallback: Auto-restore attributes
        restored = 0
        for attr, value in state.items():
            if hasattr(tool_instance, attr):
                try:
                    setattr(tool_instance, attr, value)
                    restored += 1
                except:
                    pass
        
        if restored > 0:
            self.logger.system(
                f"[Hot-Reload] Auto-restored {restored} attributes for {tool_name}"
            )
    
    # ========================================================================
    # GUI INTEGRATION
    # ========================================================================
    
    def create_reload_button(
        self,
        parent,
        tool_name: str,
        style_config: Optional[Dict] = None
    ):
        """
        Create a reload button widget for tool panel
        
        Args:
            parent: Parent tkinter widget
            tool_name: Name of tool
            style_config: Optional style configuration
        
        Returns:
            Button widget
        """
        import tkinter as tk
        from tkinter import ttk
        
        # Default style
        default_style = {
            'text': 'Reload',
            'width': 10,
        }
        
        if style_config:
            default_style.update(style_config)
        
        def on_reload():
            """Handle reload button click"""
            # Disable button during reload
            reload_btn.config(state='disabled', text='Reloading...')
            parent.update()
            
            # Reload tool
            success = self.reload_tool_sync(tool_name)
            
            # Update button state
            if success:
                reload_btn.config(state='normal', text='✓ Reloaded')
                parent.after(2000, lambda: reload_btn.config(text='Reload'))
            else:
                reload_btn.config(state='normal', text='✗ Failed')
                parent.after(2000, lambda: reload_btn.config(text='Reload'))
        
        reload_btn = ttk.Button(
            parent,
            command=on_reload,
            **default_style
        )
        
        return reload_btn
    
    def _notify_gui(self, tool_name: str, success: bool, message: str):
        """Notify GUI callback about reload status"""
        callback = self.gui_callbacks.get(tool_name)
        if callback:
            try:
                callback(success, message)
            except Exception as e:
                self.logger.warning(f"[Hot-Reload] GUI callback error: {e}")
    
    # ========================================================================
    # STATISTICS & REPORTING
    # ========================================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get hot-reload statistics"""
        return {
            'total_tools': len(self.reload_count),
            'reload_counts': self.reload_count.copy(),
            'last_reload_times': {
                name: datetime.fromtimestamp(ts).isoformat()
                for name, ts in self.last_reload_time.items()
            },
            'total_reloads': sum(self.reload_count.values()),
            'recent_history': self.reload_history[-10:]
        }
    
    def get_tool_version(self, tool_name: str) -> int:
        """Get current version (reload count) of tool"""
        return self.reload_count.get(tool_name, 0)
    
    def get_all_versions(self) -> Dict[str, int]:
        """Get versions of all tools"""
        return self.reload_count.copy()
    
    def format_status(self, tool_name: Optional[str] = None) -> str:
        """Format hot-reload status as string"""
        if tool_name:
            # Single tool status
            version = self.get_tool_version(tool_name)
            last_reload = self.last_reload_time.get(tool_name)
            
            lines = [
                f"=== {tool_name} Hot-Reload Status ===",
                f"Version: v{version}",
            ]
            
            if last_reload:
                time_str = datetime.fromtimestamp(last_reload).strftime('%Y-%m-%d %H:%M:%S')
                lines.append(f"Last Reload: {time_str}")
            else:
                lines.append("Last Reload: Never")
            
            return "\n".join(lines)
        
        else:
            # All tools status
            stats = self.get_statistics()
            
            lines = [
                "=== Hot-Reload Status ===",
                f"Tools Tracked: {stats['total_tools']}",
                f"Total Reloads: {stats['total_reloads']}",
                "",
                "Tool Versions:"
            ]
            
            for name, count in sorted(stats['reload_counts'].items()):
                lines.append(f"  {name}: v{count}")
            
            if stats['recent_history']:
                lines.append("")
                lines.append("Recent Reloads:")
                for event in stats['recent_history'][-5:]:
                    status = "✓" if event['success'] else "✗"
                    time_str = event['timestamp'].split('T')[1].split('.')[0]
                    lines.append(
                        f"  {status} {time_str} - {event['tool_name']} "
                        f"({event.get('reload_time', 0):.2f}s)"
                    )
            
            return "\n".join(lines)