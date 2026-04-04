# Filename: BASE/interface/gui_tools_view.py
"""
Dynamic Tools View - Creates GUI pages for installed tool components
Uses vertical sidebar navigation - each tool gets its own page
"""
import tkinter as tk
from tkinter import ttk
from typing import Dict, Any, List
from BASE.interface.gui_themes import DarkTheme
from BASE.interface.dynamic_tool_panel_loader import DynamicToolPanelLoader


class ToolsView:
    """
    Manages the Tools view with dynamically loaded tool panels
    Each installed tool with a component.py gets its own page
    """

    __slots__ = ('parent', 'project_root', 'hot_reload_manager', 'panel_loader', 
                 'sidebar_container', 'content_frame', 'tool_frames', 'tool_components', 
                 'current_tool', 'sidebar_buttons')

    def __init__(self, parent, project_root, hot_reload_manager=None):
        self.parent = parent
        self.project_root = project_root
        self.hot_reload_manager = hot_reload_manager
        
        self.panel_loader = DynamicToolPanelLoader(
            project_root=project_root,
            logger=parent.logger,
            hot_reload_manager=hot_reload_manager
        )
        
        self.sidebar_container = None
        self.content_frame = None
        self.tool_frames: Dict[str, tk.Frame] = {}
        self.tool_components: Dict[str, Any] = {}
        self.current_tool = None
        self.sidebar_buttons: Dict[str, tk.Button] = {}
    
    def create_tools_view(self):
        main_container = ttk.Frame(self.parent.tools_view)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        self._create_header(main_container)
        
        paned_window = tk.PanedWindow(
            main_container,
            orient=tk.HORIZONTAL,
            bg=DarkTheme.BG_DARKER,
            sashwidth=3,
            sashrelief=tk.FLAT
        )
        paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.sidebar_container = self._create_sidebar()
        self.content_frame = self._create_content_area()
        
        paned_window.add(self.sidebar_container, minsize=180, width=200)
        paned_window.add(self.content_frame, minsize=400)
        
        self._discover_and_create_panels()
        
        return main_container
    
    def _create_header(self, parent):
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill=tk.X, padx=5, pady=(5, 5))
        
        title_label = tk.Label(
            header_frame,
            text="[Tool] Tool Panels",
            font=("Segoe UI", 11, "bold"),
            foreground=DarkTheme.ACCENT_PURPLE,
            background=DarkTheme.BG_DARKER
        )
        title_label.pack(side=tk.LEFT)
        
        info_label = tk.Label(
            header_frame,
            text="Auto-discovered from BASE/tools/installed/",
            font=("Segoe UI", 8, "italic"),
            foreground=DarkTheme.FG_MUTED,
            background=DarkTheme.BG_DARKER
        )
        info_label.pack(side=tk.LEFT, padx=(10, 0))
        
        refresh_button = ttk.Button(
            header_frame,
            text="Refresh",
            command=self._refresh_panels,
            width=12
        )
        refresh_button.pack(side=tk.RIGHT)
    
    def _create_sidebar(self):
        sidebar_container = tk.Frame(bg=DarkTheme.BG_DARKER)
        
        sidebar_label = tk.Label(
            sidebar_container,
            text="Tool Panels",
            font=("Segoe UI", 10, "bold"),
            bg=DarkTheme.BG_DARKER,
            fg=DarkTheme.ACCENT_GREEN,
            anchor="w",
            padx=10,
            pady=8
        )
        sidebar_label.pack(fill=tk.X)
        
        separator = ttk.Separator(sidebar_container, orient='horizontal')
        separator.pack(fill=tk.X, padx=5, pady=(0, 5))
        
        canvas = tk.Canvas(sidebar_container, bg=DarkTheme.BG_DARKER, highlightthickness=0)
        scrollbar = ttk.Scrollbar(sidebar_container, orient="vertical", command=canvas.yview)
        sidebar_frame = tk.Frame(canvas, bg=DarkTheme.BG_DARKER)
        
        sidebar_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        
        canvas.create_window((0, 0), window=sidebar_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        
        sidebar_container._sidebar_frame = sidebar_frame
        
        return sidebar_container
    
    def _create_content_area(self):
        content_container = tk.Frame(bg=DarkTheme.BG_DARK)
        return content_container
    
    def _discover_and_create_panels(self):
        panels = self.panel_loader.discover_tool_panels()
        
        if not panels:
            self._create_no_tools_message()
            return
        
        tools_with_components = [p for p in panels if p['has_component']]
        
        if not tools_with_components:
            self._create_no_components_message()
            return
        
        tools_with_components.sort(key=lambda x: x['display_name'] or x['tool_name'] or '')
        
        for panel_info in tools_with_components:
            self._create_sidebar_button(panel_info)
            self._create_tool_panel(panel_info)
        
        if tools_with_components:
            first_tool = tools_with_components[0]['tool_name']
            self._switch_tool(first_tool)
        
        self.parent.logger.system(f"[Tools View] Created {len(tools_with_components)} tool panel(s)")
    
    def _create_sidebar_button(self, panel_info: Dict):
        tool_name = panel_info['tool_name']
        display_name = panel_info['display_name'] or tool_name.replace('_', ' ').title()
        icon = panel_info.get('icon', '[Tool]')
        
        sidebar_frame = self.sidebar_container._sidebar_frame
        
        button = tk.Button(
            sidebar_frame,
            text=f"{icon} {display_name}",
            font=("Segoe UI", 9),
            bg=DarkTheme.BG_DARK,
            fg=DarkTheme.FG_PRIMARY,
            activebackground=DarkTheme.BUTTON_HOVER,
            activeforeground=DarkTheme.ACCENT_GREEN,
            relief=tk.FLAT,
            cursor="hand2",
            anchor="w",
            padx=10,
            pady=8,
            command=lambda t=tool_name: self._switch_tool(t)
        )
        button.pack(fill=tk.X, padx=3, pady=1)
        
        self.sidebar_buttons[tool_name] = button
    
    def _create_tool_panel(self, panel_info: Dict):
        tool_name = panel_info['tool_name']
        component_path = panel_info['component_path']
        
        tool_container = tk.Frame(self.content_frame, bg=DarkTheme.BG_DARK)
        
        canvas = tk.Canvas(tool_container, bg=DarkTheme.BG_DARK, highlightthickness=0)
        scrollbar = ttk.Scrollbar(tool_container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        def update_scroll_region(event=None):
            canvas.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))
            
            bbox = canvas.bbox("all")
            canvas_height = canvas.winfo_height()
            
            if bbox and bbox[3] > canvas_height:
                scrollbar.pack(side="right", fill="y")
            else:
                scrollbar.pack_forget()
        
        def configure_canvas_width(event):
            canvas.itemconfig(canvas_window, width=event.width)
            update_scroll_region()
        
        scrollable_frame.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", configure_canvas_width)
        
        def _on_mousewheel(event):
            bbox = canvas.bbox("all")
            canvas_height = canvas.winfo_height()
            if bbox and bbox[3] > canvas_height:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        def _bind_mousewheel(event):
            bbox = canvas.bbox("all")
            canvas_height = canvas.winfo_height()
            if bbox and bbox[3] > canvas_height:
                canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        def _unbind_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")
        
        canvas.bind("<Enter>", _bind_mousewheel)
        canvas.bind("<Leave>", _unbind_mousewheel)
        
        canvas.pack(side="left", fill="both", expand=True)
        
        self._load_tool_component(scrollable_frame, panel_info)
        
        self.tool_frames[tool_name] = tool_container
    
    def _switch_tool(self, tool_name: str):
        """Switch to a different tool panel"""
        for frame in self.tool_frames.values():
            frame.pack_forget()
        
        if tool_name in self.tool_frames:
            self.tool_frames[tool_name].pack(fill=tk.BOTH, expand=True)
            self.current_tool = tool_name
            
            for btn_tool, btn in self.sidebar_buttons.items():
                if btn_tool == tool_name:
                    btn.config(bg=DarkTheme.ACCENT_PURPLE, fg=DarkTheme.ACCENT_GREEN)
                else:
                    btn.config(bg=DarkTheme.BG_DARK, fg=DarkTheme.FG_PRIMARY)
    
    def _load_tool_component(self, parent, panel_info: Dict):
        tool_name = panel_info['tool_name']
        component_path = panel_info['component_path']
        
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill=tk.X, padx=5, pady=(5, 2))
        
        title_label = tk.Label(
            header_frame,
            text=f"{panel_info.get('icon', '[Tool]')} {panel_info['display_name']}",
            font=("Segoe UI", 11, "bold"),
            foreground=DarkTheme.ACCENT_PURPLE,
            background=DarkTheme.BG_DARKER
        )
        title_label.pack(side=tk.LEFT)
        
        if self.hot_reload_manager:
            version = self.hot_reload_manager.get_tool_version(tool_name)
            version_label = tk.Label(
                header_frame,
                text=f"v{version}",
                font=("Segoe UI", 8),
                foreground=DarkTheme.FG_MUTED,
                background=DarkTheme.BG_DARKER
            )
            version_label.pack(side=tk.LEFT, padx=(5, 0))
        
        if self.hot_reload_manager:
            reload_btn = self.panel_loader.create_reload_button_for_tool(parent=header_frame, tool_name=tool_name)
            if reload_btn:
                reload_btn.pack(side=tk.RIGHT, padx=2)
        
        separator = ttk.Separator(parent, orient='horizontal')
        separator.pack(fill=tk.X, padx=5, pady=(2, 5))
        
        component = self.panel_loader.load_component(
            tool_name=tool_name,
            component_path=component_path,
            parent_gui=self.parent,
            ai_core=self.parent.ai_core
        )
        
        if not component:
            self.parent.logger.warning(f"[Tools View] Failed to load component for {tool_name}")
            self._create_error_panel(parent, tool_name)
            return
        
        try:
            panel_frame = component.create_panel(parent)
            self.tool_components[tool_name] = component
            self.parent.logger.system(f"[Tools View] Loaded panel for {tool_name}")
        except Exception as e:
            self.parent.logger.error(f"[Tools View] Error creating panel for {tool_name}: {e}")
            import traceback
            traceback.print_exc()
            self._create_error_panel(parent, tool_name, str(e))
    
    def _create_error_panel(self, parent, tool_name: str, error_msg: str = ""):
        error_frame = ttk.LabelFrame(parent, text=f"[X] Error Loading {tool_name}", style="Dark.TLabelframe")
        error_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        error_text = f"Failed to load component for {tool_name}"
        if error_msg:
            error_text += f"\n\nError: {error_msg}"
        
        error_label = tk.Label(
            error_frame,
            text=error_text,
            font=("Segoe UI", 10),
            foreground=DarkTheme.ACCENT_RED,
            background=DarkTheme.BG_DARKER,
            justify=tk.LEFT,
            wraplength=500
        )
        error_label.pack(expand=True, padx=20, pady=20)
    
    def _create_no_tools_message(self):
        message_label = tk.Label(
            self.content_frame,
            text="No tools found in BASE/tools/installed/",
            font=("Segoe UI", 10),
            foreground=DarkTheme.FG_MUTED,
            background=DarkTheme.BG_DARKER
        )
        message_label.pack(expand=True)
    
    def _create_no_components_message(self):
        message_label = tk.Label(
            self.content_frame,
            text=("Tools are installed but none have GUI components.\n\n"
                  "To add a GUI component, create a component.py file\n"
                  "in the tool's directory with a create_component() function."),
            font=("Segoe UI", 10),
            foreground=DarkTheme.FG_MUTED,
            background=DarkTheme.BG_DARKER,
            justify=tk.CENTER
        )
        message_label.pack(expand=True)
    
    def _refresh_panels(self):
        self.parent.logger.system("[Tools View] [Refresh] Starting hot-reload refresh...")
        
        active_tools = []
        if hasattr(self.parent, 'ai_core') and hasattr(self.parent.ai_core, 'tool_manager'):
            active_tools = self.parent.ai_core.tool_manager.get_active_tool_names()
            self.parent.logger.system(f"[Tools View] Found {len(active_tools)} active tools")
        
        if self.hot_reload_manager and active_tools:
            import asyncio
            
            self.parent.logger.system("[Tools View] Hot-reloading Python modules...")
            
            async def reload_all_tools():
                success_count = 0
                fail_count = 0
                
                for tool_name in active_tools:
                    self.parent.logger.system(f"[Hot-Reload] Reloading {tool_name}...")
                    
                    try:
                        success = await self.hot_reload_manager.reload_tool(tool_name, notify_gui=False)
                        
                        if success:
                            self.parent.logger.success(f"[Hot-Reload] [Confirmed] {tool_name} reloaded")
                            success_count += 1
                        else:
                            self.parent.logger.error(f"[Hot-Reload] [X] {tool_name} reload failed")
                            fail_count += 1
                    except Exception as e:
                        self.parent.logger.error(f"[Hot-Reload] [X] {tool_name} error: {e}")
                        fail_count += 1
                
                return success_count, fail_count
            
            if hasattr(self.parent.ai_core, 'main_loop') and self.parent.ai_core.main_loop:
                future = asyncio.run_coroutine_threadsafe(reload_all_tools(), self.parent.ai_core.main_loop)
                
                try:
                    success_count, fail_count = future.result(timeout=30.0)
                    self.parent.logger.system(f"[Hot-Reload] Module reload complete: {success_count} succeeded, {fail_count} failed")
                except TimeoutError:
                    self.parent.logger.error("[Hot-Reload] [Time] Reload timed out after 30s")
                except Exception as e:
                    self.parent.logger.error(f"[Hot-Reload] Error during reload: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                self.parent.logger.warning("[Hot-Reload] No event loop - skipping module reload")
        elif self.hot_reload_manager and not active_tools:
            self.parent.logger.system("[Hot-Reload] No active tools to reload")
        elif not self.hot_reload_manager:
            self.parent.logger.warning("[Hot-Reload] Hot-reload manager not available")
        
        self.parent.logger.system("[Tools View] Refreshing GUI panels...")
        
        cleanup_count = 0
        for tool_name, component in list(self.tool_components.items()):
            if hasattr(component, 'cleanup'):
                try:
                    component.cleanup()
                    cleanup_count += 1
                except Exception as e:
                    self.parent.logger.warning(f"[Tools View] Error cleaning up {tool_name}: {e}")
        
        for frame in self.tool_frames.values():
            frame.destroy()
        
        for btn in self.sidebar_buttons.values():
            btn.destroy()
        
        self.tool_frames.clear()
        self.tool_components.clear()
        self.sidebar_buttons.clear()
        
        self.parent.logger.system("[Tools View] Discovering and creating new panels...")
        self._discover_and_create_panels()
        
        new_panel_count = len(self.tool_frames)
        self.parent.logger.success(f"[Tools View] [Confirmed] Complete refresh finished! ({new_panel_count} tool panels active)")
    
    def cleanup(self):
        self.panel_loader.cleanup_all()
        self.tool_frames.clear()
        self.tool_components.clear()
        self.sidebar_buttons.clear()