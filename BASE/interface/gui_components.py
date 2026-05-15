# Filename: BASE/interface/gui_components.py
"""
Component managers for control panel functionality.
ENHANCED: Dynamic internal tool discovery with mutual exclusivity
Automatically discovers and creates toggles for all tools in tools/internal/
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import json

from BASE.interface.gui_themes import DarkTheme

try:
    import BASE.config.controls as controls
except ImportError as e:
    print(f"Warning: Some imports failed: {e}")


class ControlPanelManager:
    """
    Manages the control panel GUI with dynamic internal tool discovery
    Handles mutual exclusivity for TTS and voice input tools
    """
    __slots__ = ('ai_core', 'control_manager', 'logger', 'control_vars', 'status_labels',
                 'proc_delay_var', 'speak_delay_var', 'internal_tool_widgets',
                 'internal_tool_metadata', 'category_status_labels')

    def __init__(self, ai_core, logger):
        """Initialize control panel manager"""
        self.ai_core = ai_core
        self.control_manager = ai_core.get_control_manager()
        self.logger = logger

        self.control_vars = {}
        self.status_labels = {}
        
        # Track internal tool toggle widgets for mutual exclusivity UI updates
        # Structure: {service_type: {control_var: (checkbutton, status_label)}}
        self.internal_tool_widgets = {}
        
        # Store internal tool metadata
        # Structure: {control_var: {'tool_name': ..., 'service_type': ..., ...}}
        self.internal_tool_metadata = {}
        
        # Category status labels showing active tool
        # Structure: {service_type: status_label_widget}
        self.category_status_labels = {}

    def toggle_control(self, var_name):
        """Toggle a control via AI Core's control manager"""
        
        # Get current value
        current_value = getattr(controls, var_name, False)
        new_value = not current_value
        
        # Check if this is an internal tool control
        if self._is_internal_tool_control(var_name):
            success = self._handle_internal_tool_toggle(var_name, new_value)
            
            if success:
                # Update GUI
                self.control_vars[var_name].set(new_value)
                self.status_labels[var_name].config(
                    text="ON" if new_value else "OFF",
                    foreground=DarkTheme.ACCENT_GREEN if new_value else DarkTheme.FG_MUTED
                )
                
                # Update other tools in same category (mutual exclusivity)
                self._update_tool_category_ui(var_name)
            else:
                # Revert GUI if toggle failed
                self.control_vars[var_name].set(current_value)
            
            return
        
        # Regular control toggle
        success = self.control_manager.update_control(var_name, new_value)
        
        if success:
            # Update GUI
            self.control_vars[var_name].set(new_value)
            if var_name in self.status_labels:
                self.status_labels[var_name].config(
                    text="ON" if new_value else "OFF",
                    foreground=DarkTheme.ACCENT_GREEN if new_value else DarkTheme.FG_MUTED
                )
            
            # Handle special cases
            if var_name == "ENABLE_CONTINUOUS_THINKING":
                self._update_continuous_thinking_ui(new_value)
    
    def _is_internal_tool_control(self, var_name: str) -> bool:
        """Check if control is for an internal tool"""
        return var_name in self.internal_tool_metadata
    
    def _get_tool_service_type(self, var_name: str) -> Optional[str]:
        """Get service type of internal tool"""
        metadata = self.internal_tool_metadata.get(var_name)
        return metadata['service_type'] if metadata else None
    
    def _handle_internal_tool_toggle(self, var_name: str, new_value: bool) -> bool:
        """Handle internal tool toggle with mutual exclusivity"""
        try:
            # Use control manager which handles mutual exclusivity
            success = self.control_manager.update_control(var_name, new_value)
            
            if success and new_value:
                # Log success
                metadata = self.internal_tool_metadata.get(var_name, {})
                tool_name = metadata.get('tool_name', var_name)
                service_type = metadata.get('service_type', 'unknown')
                self.logger.success(f"[{service_type.upper()}] {tool_name} enabled")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to toggle {var_name}: {e}")
            return False
    
    def _update_tool_category_ui(self, toggled_var: str):
        """Update UI for all tools in same category after toggle"""
        service_type = self._get_tool_service_type(toggled_var)
        if not service_type or service_type not in self.internal_tool_widgets:
            return
        
        # Update all tools in this service type
        for tool_var, (checkbox, status_label) in self.internal_tool_widgets[service_type].items():
            current_value = getattr(controls, tool_var, False)
            
            # Update checkbox
            if tool_var in self.control_vars:
                self.control_vars[tool_var].set(current_value)
            
            # Update status label
            status_label.config(
                text="ON" if current_value else "OFF",
                foreground=DarkTheme.ACCENT_GREEN if current_value else DarkTheme.FG_MUTED
            )
        
        # Update category status label
        self._update_category_status(service_type)
    
    def _update_category_status(self, service_type: str):
        """Update the category status display"""
        if service_type not in self.category_status_labels:
            return
        
        status_label = self.category_status_labels[service_type]
        
        # Find active tool in this service type
        active_tool = None
        for tool_var, metadata in self.internal_tool_metadata.items():
            if metadata['service_type'] == service_type:
                if getattr(controls, tool_var, False):
                    active_tool = metadata['tool_name']
                    break
        
        if active_tool:
            status_label.config(
                text=f"[Active] {active_tool.upper()}",
                foreground=DarkTheme.ACCENT_GREEN
            )
        else:
            service_display = service_type.replace('_', ' ').title()
            status_label.config(
                text=f"No {service_display} active",
                foreground=DarkTheme.FG_MUTED
            )
    
    def _update_continuous_thinking_ui(self, enabled: bool):
        """Update UI for continuous thinking toggle"""
        if enabled:
            self.logger.system("[Continuous Thinking] STARTED")
        else:
            self.logger.system("[Continuous Thinking] STOPPED")

    def create_control_panel(self, parent):
        """Create the main control panel with scrolling"""
        # Create canvas with scrollbar
        control_canvas = tk.Canvas(
            parent,
            bg=DarkTheme.BG_DARKER,
            highlightthickness=0
        )
        scrollbar = ttk.Scrollbar(
            parent,
            orient="vertical",
            command=control_canvas.yview
        )
        scrollable_frame = ttk.Frame(control_canvas, style="Dark.TFrame")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: control_canvas.configure(scrollregion=control_canvas.bbox("all"))
        )

        control_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        control_canvas.configure(yscrollcommand=scrollbar.set)

        control_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Enable mousewheel scrolling
        def _on_mousewheel(event):
            control_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_mousewheel(event):
            control_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind_mousewheel(event):
            control_canvas.unbind_all("<MouseWheel>")

        control_canvas.bind("<Enter>", _bind_mousewheel)
        control_canvas.bind("<Leave>", _unbind_mousewheel)

        # STATIC control groups
        static_control_groups = {
            "AI Behavior": [
                ("Continuous Thinking", "ENABLE_CONTINUOUS_THINKING",
                 "Enable continuous thought processing"),
                ("Auto Restart", "AUTO_RESTART",
                 "Automatically restart the agent after errors"),
            ],
            "Rate Limiting": [
                ("Limit Processing", "LIMIT_PROCESSING",
                 "Limit how fast the agent can think/process"),
                ("Limit Speaking", "LIMIT_SPEAKING",
                 "Limit how often the agent can speak"),
            ],
            "Agent Memory": [
                ("Base Memory", "USE_BASE_MEMORY", "Include base knowledge context"),
                ("Short Memory", "USE_SHORT_MEMORY", "Include working memory (latest messages)"),
                ("Long Memory", "USE_LONG_MEMORY", "Include past day summaries"),
                ("Save Memory", "SAVE_MEMORY", "Save conversations to memory system"),
            ],
            "Filters": [
                ("Content Filter", "ENABLE_CONTENT_FILTER",
                 "Filter profanity and controversial content"),
                ("AI Filter", "USE_AI_CONTENT_FILTER",
                 "Use AI model for semantic filtering"),
            ],
            "Debug & Logging": [
                ("Log System", "LOG_SYSTEM_INFORMATION", "Log system messages"),
                ("Log Responsive Prompts", "LOG_RESPONSIVE_PROMPT", "Log responsive prompt details"),
                ("Log Reactive Prompts", "LOG_REACTIVE_PROMPT", "Log reactive prompt details"),
                ("Log Reflective Prompts", "LOG_REFLECTIVE_PROMPT", "Log reflective prompt details"),
                ("Log Proactive Prompts", "LOG_PROACTIVE_PROMPT", "Log proactive prompt details"),
                ("Log Action Prompts", "LOG_ACTION_PROMPT", "Log action prompt details"),
                ("Log Responses", "LOG_RESPONSE_PROCESSING", "Log response generation"),
                ("Log Tools", "LOG_TOOL_EXECUTION", "Log tool executions"),
                ("Log Live Chat", "SHOW_CHAT", "Print live chat messages"),
                ("Log Prompt Construction", "LOG_PROMPT_CONSTRUCTION", "Log prompt building details"),
            ],
        }

        # Create static control sections
        for group_name, controls_list in static_control_groups.items():
            self.create_control_group(scrollable_frame, group_name, controls_list)
            
            # Add numeric controls after Rate Limiting section
            if group_name == "Rate Limiting":
                self.create_timing_controls(scrollable_frame)

        # Create internal tool sections (DYNAMIC DISCOVERY)
        self.create_internal_tools_sections(scrollable_frame)

        # Create dynamic tool sections (external tools)
        dynamic_tool_groups = self._get_dynamic_tool_groups()
        for category_name, tools_list in dynamic_tool_groups.items():
            self.create_dynamic_tool_group(scrollable_frame, category_name, tools_list)

        # Global control buttons
        global_frame = ttk.LabelFrame(
            scrollable_frame, text="Global Controls", style="Dark.TLabelframe"
        )
        global_frame.pack(fill=tk.X, padx=3, pady=1)

        button_frame = ttk.Frame(global_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=5)

        enable_all_btn = tk.Button(
            button_frame,
            text="Enable All",
            command=self.enable_all_controls,
            bg=DarkTheme.ACCENT_GREEN,
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT,
            cursor="hand2"
        )
        enable_all_btn.pack(side=tk.LEFT, padx=2)

        disable_all_btn = tk.Button(
            button_frame,
            text="Disable All",
            command=self.disable_all_controls,
            bg=DarkTheme.ACCENT_RED,
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT,
            cursor="hand2"
        )
        disable_all_btn.pack(side=tk.LEFT, padx=2)

    def create_internal_tools_sections(self, parent):
        """
        Dynamically discover and create GUI sections for internal tools
        Groups by service_type, handles mutual exclusivity
        """
        try:
            # Get project root
            project_root = Path(__file__).parent.parent.parent
            internal_tools_dir = project_root / 'BASE' / 'tools' / 'internal'
            
            if not internal_tools_dir.exists():
                self.logger.warning("[GUI] Internal tools directory not found")
                return
            
            # Discover all internal tools
            discovered_tools = self._discover_internal_tools(internal_tools_dir)
            
            if not discovered_tools:
                return
            
            # Group by service_type
            service_groups = {}
            for tool_data in discovered_tools:
                service_type = tool_data['service_type']
                
                if service_type not in service_groups:
                    service_groups[service_type] = []
                
                service_groups[service_type].append(tool_data)
            
            # Create GUI section for each service type
            for service_type, tools in sorted(service_groups.items()):
                self._create_internal_service_group(parent, service_type, tools)
        
        except Exception as e:
            self.logger.error(f"[GUI] Error creating internal tools sections: {e}")
            import traceback
            traceback.print_exc()
    
    def _discover_internal_tools(self, tools_dir: Path) -> List[Dict]:
        """
        Discover all internal tools by scanning information.json files
        
        Returns:
            List of tool metadata dicts
        """
        discovered = []
        
        for tool_dir in tools_dir.iterdir():
            if not tool_dir.is_dir() or tool_dir.name.startswith('_'):
                continue
            
            if tool_dir.name == 'shared':  # Skip shared utilities
                continue
            
            info_file = tool_dir / 'information.json'
            
            if not info_file.exists():
                continue
            
            try:
                with open(info_file, 'r') as f:
                    info = json.load(f)
                
                tool_name = info.get('tool_name')
                control_var = info.get('control_variable_name')
                service_type = info.get('service_type')
                
                if not tool_name or not control_var or not service_type:
                    continue
                
                # Store metadata
                tool_data = {
                    'tool_name': tool_name,
                    'control_var': control_var,
                    'service_type': service_type,
                    'description': info.get('tool_description', 'No description'),
                    'display_name': tool_name.replace('_', ' ').title(),
                    'priority': info.get('priority', 0),
                    'features': info.get('features', {}),
                    'requirements': info.get('requirements', {})
                }
                
                discovered.append(tool_data)
                
                # Store in metadata lookup
                self.internal_tool_metadata[control_var] = tool_data
            
            except Exception as e:
                self.logger.warning(f"[GUI] Failed to load {tool_dir.name}/information.json: {e}")
                continue
        
        return discovered
    
    def _create_internal_service_group(self, parent, service_type: str, tools: List[Dict]):
        """
        Create GUI section for a service type (e.g., TTS, voice_input)
        Shows all tools in that category with mutual exclusivity
        """
        # Create friendly display name
        service_display = service_type.replace('_', ' ').title()
        
        group_frame = ttk.LabelFrame(
            parent,
            text=f"Internal Tools: {service_display}",
            style="Dark.TLabelframe"
        )
        group_frame.pack(fill=tk.X, padx=3, pady=1)
        
        # Category status header
        status_frame = ttk.Frame(group_frame, style="Dark.TFrame")
        status_frame.pack(fill=tk.X, padx=5, pady=(2, 0))
        
        tk.Label(
            status_frame,
            text=f"[Warning] Only ONE {service_display} tool can be active at a time",
            font=("Segoe UI", 8, "italic"),
            bg=DarkTheme.BG_DARK,
            fg=DarkTheme.ACCENT_ORANGE
        ).pack(side=tk.LEFT, padx=2)
        
        # Active tool indicator
        status_label = tk.Label(
            status_frame,
            text="",
            font=("Segoe UI", 8, "bold"),
            bg=DarkTheme.BG_DARK,
            fg=DarkTheme.FG_MUTED
        )
        status_label.pack(side=tk.LEFT, padx=10)
        
        self.category_status_labels[service_type] = status_label
        
        # Initialize widget tracking for this service type
        if service_type not in self.internal_tool_widgets:
            self.internal_tool_widgets[service_type] = {}
        
        # Sort tools by priority (higher first)
        tools.sort(key=lambda x: x['priority'], reverse=True)
        
        # Create toggle for each tool
        for tool_data in tools:
            self._create_internal_tool_toggle(
                parent=group_frame,
                display_name=tool_data['display_name'],
                var_name=tool_data['control_var'],
                description=tool_data['description'],
                service_type=service_type,
                features=tool_data.get('features', {})
            )
        
        # Update initial status
        self._update_category_status(service_type)
    
    def _create_internal_tool_toggle(self, parent, display_name, var_name, description, 
                                    service_type, features=None):
        """Create a toggle for an internal tool with feature indicators"""
        item_frame = ttk.Frame(parent, style="Dark.TFrame")
        item_frame.pack(fill=tk.X, padx=5, pady=2)
        
        # Create boolean variable
        var = tk.BooleanVar(value=getattr(controls, var_name, False))
        self.control_vars[var_name] = var
        
        # Checkbox
        check = tk.Checkbutton(
            item_frame,
            text=display_name,
            variable=var,
            command=lambda: self.toggle_control(var_name),
            bg=DarkTheme.BG_DARK,
            fg=DarkTheme.FG_PRIMARY,
            selectcolor=DarkTheme.BG_DARKER,
            activebackground=DarkTheme.BG_DARK,
            activeforeground=DarkTheme.ACCENT_GREEN,
            font=("Segoe UI", 9),
            anchor="w",
            width=20
        )
        check.pack(side=tk.LEFT, padx=2)
        
        # Add tooltip to checkbox
        self._add_tooltip(check, description)
        
        # Status label
        current_value = getattr(controls, var_name, False)
        status = tk.Label(
            item_frame,
            text="ON" if current_value else "OFF",
            font=("Segoe UI", 9, "bold"),
            bg=DarkTheme.BG_DARK,
            fg=DarkTheme.ACCENT_GREEN if current_value else DarkTheme.FG_MUTED,
            width=4
        )
        status.pack(side=tk.LEFT, padx=5)
        
        self.status_labels[var_name] = status
        
        # Feature badges (optional)
        if features:
            badge_frame = tk.Frame(item_frame, bg=DarkTheme.BG_DARK)
            badge_frame.pack(side=tk.LEFT, padx=5)
            
            # Show key features as small badges
            if features.get('gpu_accelerated'):
                self._create_badge(badge_frame, "GPU", DarkTheme.ACCENT_PURPLE)
            if features.get('streaming'):
                self._create_badge(badge_frame, "Stream", DarkTheme.ACCENT_BLUE)
            if features.get('voice_hub'):
                self._create_badge(badge_frame, "Hub", DarkTheme.ACCENT_GREEN)
        
        # Track widget for UI updates
        self.internal_tool_widgets[service_type][var_name] = (check, status)
    
    def _create_badge(self, parent, text, color):
        """Create a small feature badge"""
        badge = tk.Label(
            parent,
            text=text,
            font=("Segoe UI", 7, "bold"),
            bg=color,
            fg="white",
            padx=3,
            pady=1
        )
        badge.pack(side=tk.LEFT, padx=1)

    def create_control_group(self, parent, group_name, controls_list):
        """Create a control group section"""
        group_frame = ttk.LabelFrame(
            parent,
            text=group_name,
            style="Dark.TLabelframe"
        )
        group_frame.pack(fill=tk.X, padx=3, pady=1)

        for display_name, var_name, description in controls_list:
            item_frame = ttk.Frame(group_frame, style="Dark.TFrame")
            item_frame.pack(fill=tk.X, padx=5, pady=2)

            # Create boolean variable
            var = tk.BooleanVar(value=getattr(controls, var_name, False))
            self.control_vars[var_name] = var

            # Checkbox
            check = tk.Checkbutton(
                item_frame,
                text=display_name,
                variable=var,
                command=lambda v=var_name: self.toggle_control(v),
                bg=DarkTheme.BG_DARK,
                fg=DarkTheme.FG_PRIMARY,
                selectcolor=DarkTheme.BG_DARKER,
                activebackground=DarkTheme.BG_DARK,
                activeforeground=DarkTheme.ACCENT_GREEN,
                font=("Segoe UI", 9),
                anchor="w",
                width=20
            )
            check.pack(side=tk.LEFT, padx=2)
            
            # Add tooltip to checkbox
            self._add_tooltip(check, description)

            # Status label
            current_value = getattr(controls, var_name, False)
            status = tk.Label(
                item_frame,
                text="ON" if current_value else "OFF",
                font=("Segoe UI", 9, "bold"),
                bg=DarkTheme.BG_DARK,
                fg=DarkTheme.ACCENT_GREEN if current_value else DarkTheme.FG_MUTED,
                width=4
            )
            status.pack(side=tk.LEFT, padx=5)

            self.status_labels[var_name] = status

    def _add_tooltip(self, widget, text):
        """Add tooltip to widget that appears on hover"""
        def on_enter(e):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{e.x_root+10}+{e.y_root+10}")
            label = tk.Label(
                tooltip,
                text=text,
                bg=DarkTheme.BG_LIGHTER,
                fg=DarkTheme.FG_PRIMARY,
                relief=tk.SOLID,
                borderwidth=1,
                font=("Segoe UI", 8),
                padx=5,
                pady=3,
                wraplength=300
            )
            label.pack()
            widget.tooltip = tooltip
        
        def on_leave(e):
            if hasattr(widget, 'tooltip'):
                widget.tooltip.destroy()
        
        widget.bind('<Enter>', on_enter)
        widget.bind('<Leave>', on_leave)

    def create_timing_controls(self, parent):
        """Create numeric input controls for timing"""
        timing_frame = ttk.LabelFrame(
            parent, text="Timing Settings", style="Dark.TLabelframe"
        )
        timing_frame.pack(fill=tk.X, padx=3, pady=1)

        # Processing delay
        proc_frame = ttk.Frame(timing_frame, style="Dark.TFrame")
        proc_frame.pack(fill=tk.X, padx=5, pady=2)

        proc_label = tk.Label(
            proc_frame,
            text="Processing Delay (s):",
            font=("Segoe UI", 9),
            bg=DarkTheme.BG_DARK,
            fg=DarkTheme.FG_PRIMARY,
            width=20,
            anchor="w"
        )
        proc_label.pack(side=tk.LEFT, padx=2)
        
        # Add tooltip to label
        self._add_tooltip(proc_label, "Seconds between processing cycles when rate limiting is enabled")

        self.proc_delay_var = tk.StringVar(value=str(controls.PROCESSING_DELAY))
        proc_entry = tk.Entry(
            proc_frame,
            textvariable=self.proc_delay_var,
            width=10,
            bg=DarkTheme.BG_DARKER,
            fg=DarkTheme.FG_PRIMARY,
            insertbackground=DarkTheme.ACCENT_GREEN,
            font=("Segoe UI", 9)
        )
        proc_entry.pack(side=tk.LEFT, padx=5)

        proc_apply = tk.Button(
            proc_frame,
            text="Apply",
            command=lambda: self._apply_timing("PROCESSING_DELAY", self.proc_delay_var),
            bg=DarkTheme.ACCENT_PURPLE,
            fg="white",
            font=("Segoe UI", 8),
            relief=tk.FLAT,
            cursor="hand2"
        )
        proc_apply.pack(side=tk.LEFT, padx=2)

        # Speaking delay
        speak_frame = ttk.Frame(timing_frame, style="Dark.TFrame")
        speak_frame.pack(fill=tk.X, padx=5, pady=2)

        speak_label = tk.Label(
            speak_frame,
            text="Speaking Delay (s):",
            font=("Segoe UI", 9),
            bg=DarkTheme.BG_DARK,
            fg=DarkTheme.FG_PRIMARY,
            width=20,
            anchor="w"
        )
        speak_label.pack(side=tk.LEFT, padx=2)
        
        # Add tooltip to label
        self._add_tooltip(speak_label, "Minimum seconds between spoken responses when rate limiting is enabled")

        self.speak_delay_var = tk.StringVar(value=str(controls.SPEAKING_DELAY))
        speak_entry = tk.Entry(
            speak_frame,
            textvariable=self.speak_delay_var,
            width=10,
            bg=DarkTheme.BG_DARKER,
            fg=DarkTheme.FG_PRIMARY,
            insertbackground=DarkTheme.ACCENT_GREEN,
            font=("Segoe UI", 9)
        )
        speak_entry.pack(side=tk.LEFT, padx=5)

        speak_apply = tk.Button(
            speak_frame,
            text="Apply",
            command=lambda: self._apply_timing("SPEAKING_DELAY", self.speak_delay_var),
            bg=DarkTheme.ACCENT_PURPLE,
            fg="white",
            font=("Segoe UI", 8),
            relief=tk.FLAT,
            cursor="hand2"
        )
        speak_apply.pack(side=tk.LEFT, padx=2)

    def _apply_timing(self, control_name, var):
        """Apply timing control value"""
        try:
            value = float(var.get())
            setattr(controls, control_name, value)
            self.logger.system(f"[Controls] {control_name} = {value}")
        except ValueError:
            self.logger.error(f"[Controls] Invalid value for {control_name}")

    def _get_dynamic_tool_groups(self) -> Dict[str, List[Tuple]]:
        """
        Discover external tools from tools/installed directory
        Groups tools by category from metadata
        """
        try:
            project_root = Path(__file__).parent.parent.parent
            tools_dir = project_root / 'BASE' / 'tools' / 'installed'
            
            if not tools_dir.exists():
                return {}
            
            discovered_tools = []
            
            for tool_dir in tools_dir.iterdir():
                if not tool_dir.is_dir():
                    continue
                
                info_file = tool_dir / 'information.json'
                if not info_file.exists():
                    continue
                
                try:
                    with open(info_file, 'r') as f:
                        info = json.load(f)
                    
                    tool_name = info.get('tool_name')
                    control_var = info.get('control_variable_name')
                    
                    if not tool_name or not control_var:
                        continue
                    
                    metadata = info.get('metadata', {})
                    category = metadata.get('category', 'Other Tools')
                    display_name = metadata.get('gui_label',
                                               tool_name.replace('_', ' ').title())
                    description = info.get('tool_description', 'No description')
                    
                    discovered_tools.append({
                        'tool_name': tool_name,
                        'control_var': control_var,
                        'category': category,
                        'display_name': display_name,
                        'description': description,
                        'info': info
                    })
                    
                except Exception as e:
                    continue
            
            # Group by category
            categories = {}
            for tool in discovered_tools:
                category = tool['category']
                
                if category not in categories:
                    categories[category] = []
                
                categories[category].append((
                    tool['display_name'],
                    tool['control_var'],
                    tool['description'],
                    tool['tool_name'],
                    tool['info']
                ))
            
            return categories
            
        except Exception as e:
            return {}

    def create_dynamic_tool_group(self, parent, category_name: str, tools_list):
        """Create GUI section for dynamically discovered external tools"""
        group_frame = ttk.LabelFrame(
            parent,
            text=f"{category_name}",
            style="Dark.TLabelframe"
        )
        group_frame.pack(fill=tk.X, padx=3, pady=1)
        
        for display_name, control_var, description, tool_name, info in tools_list:
            self._create_tool_toggle(group_frame, display_name, control_var, description)
    
    def _create_tool_toggle(self, parent, display_name, var_name, description):
        """Create a toggle for an external tool"""
        item_frame = ttk.Frame(parent, style="Dark.TFrame")
        item_frame.pack(fill=tk.X, padx=5, pady=2)
        
        var = tk.BooleanVar(value=getattr(controls, var_name, False))
        self.control_vars[var_name] = var
        
        check = tk.Checkbutton(
            item_frame,
            text=display_name,
            variable=var,
            command=lambda: self.toggle_control(var_name),
            bg=DarkTheme.BG_DARK,
            fg=DarkTheme.FG_PRIMARY,
            selectcolor=DarkTheme.BG_DARKER,
            activebackground=DarkTheme.BG_DARK,
            activeforeground=DarkTheme.ACCENT_GREEN,
            font=("Segoe UI", 9),
            anchor="w",
            width=20
        )
        check.pack(side=tk.LEFT, padx=2)
        
        # Add tooltip to checkbox
        self._add_tooltip(check, description)
        
        current_value = getattr(controls, var_name, False)
        status = tk.Label(
            item_frame,
            text="ON" if current_value else "OFF",
            font=("Segoe UI", 9, "bold"),
            bg=DarkTheme.BG_DARK,
            fg=DarkTheme.ACCENT_GREEN if current_value else DarkTheme.FG_MUTED,
            width=4
        )
        status.pack(side=tk.LEFT, padx=5)
        
        self.status_labels[var_name] = status

    def enable_all_controls(self):
        """Enable all controls"""
        for var_name, var in self.control_vars.items():
            if not var.get():
                self.toggle_control(var_name)

    def disable_all_controls(self):
        """Disable all controls"""
        for var_name, var in self.control_vars.items():
            if var.get():
                self.toggle_control(var_name)

    def reset_controls(self):
        """Reset all controls to defaults"""
        self.logger.system("Resetting all controls to defaults...")
        # Implementation depends on how defaults are stored