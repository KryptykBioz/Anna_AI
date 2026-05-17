# Filename: BASE/interface/gui_config_view.py
"""
Dynamic Configuration Editor with Hot-Reload Integration
Provides input fields for modifying all config values with real-time application
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from pathlib import Path
import json
import importlib
from BASE.interface.gui_themes import DarkTheme

class ConfigView:
    """Dynamic configuration editor with hot-reload support"""
    
    __slots__ = ('parent','project_root','config_json_path','bot_info_path','controls_path',
                 'config_data','bot_info_data','controls_data','canvas','scroll_frame',
                 'input_fields','category_frames','save_status_label','hot_reload_enabled',
                 'left_column','right_column','personality_path','personality_text',
                 'personality_status_label')
    
    def __init__(self, parent, project_root):
        self.parent = parent
        self.project_root = Path(project_root)
        
        # FIXED: Point to correct config location in personality/ directory
        self.config_json_path = self.project_root / "personality" / "config.json"
        self.bot_info_path = self.project_root / "personality" / "bot_info.py"
        self.controls_path = self.project_root / "personality" / "controls.py"
        self.personality_path = self.project_root / "personality" / "prompts" / "personality_prompt_parts.py"
        
        self.config_data = {}
        self.bot_info_data = {}
        self.controls_data = {}
        self.input_fields = {}
        self.category_frames = {}
        self.hot_reload_enabled = False
        self._check_hot_reload_available()
    
    def _check_hot_reload_available(self):
        """Check if hot-reload system is available"""
        try:
            import watchdog
            self.hot_reload_enabled=True
            if self.parent.logger:
                self.parent.logger.system("[Config View] Hot-reload available")
        except ImportError:
            self.hot_reload_enabled=False
            if self.parent.logger:
                self.parent.logger.warning("[Config View] Hot-reload unavailable (watchdog not installed)")
    
    def create_config_view(self):
        """Create dynamic config editor with scrollable sections"""
        config_frame=self.parent.config_view
        header_frame=tk.Frame(config_frame,bg=DarkTheme.BG_DARKER,height=70)
        header_frame.pack(fill=tk.X,padx=0,pady=0)
        header_frame.pack_propagate(False)
        title_label=tk.Label(header_frame,text="[Config] Configuration Editor",
                            font=("Segoe UI",14,"bold"),bg=DarkTheme.BG_DARKER,
                            fg=DarkTheme.FG_PRIMARY)
        title_label.pack(side=tk.LEFT,padx=15,pady=5)
        
        status_frame=tk.Frame(header_frame,bg=DarkTheme.BG_DARKER)
        status_frame.pack(side=tk.LEFT,padx=15,pady=5)
        
        if self.hot_reload_enabled:
            status_text="[Confirmed] Hot-reload enabled"
            status_color=DarkTheme.ACCENT_GREEN
        else:
            status_text="[Warning] Restart required"
            status_color=DarkTheme.ACCENT_ORANGE
        reload_status=tk.Label(status_frame,text=status_text,
                            font=("Segoe UI",8,"italic"),
                            bg=DarkTheme.BG_DARKER,fg=status_color)
        reload_status.pack()
        
        self.save_status_label=tk.Label(status_frame,text="",
                                        font=("Segoe UI",8,"italic"),
                                        bg=DarkTheme.BG_DARKER,
                                        fg=DarkTheme.FG_MUTED)
        self.save_status_label.pack()
        
        btn_frame=tk.Frame(header_frame,bg=DarkTheme.BG_DARKER)
        btn_frame.pack(side=tk.RIGHT,padx=10,pady=5)
        reload_btn=tk.Button(btn_frame,text="[Reload] Reload",
                            command=self.reload_all_configs,
                            font=("Segoe UI",8,"bold"),bg=DarkTheme.BUTTON_BG,
                            fg=DarkTheme.FG_PRIMARY,
                            activebackground=DarkTheme.BUTTON_HOVER,
                            relief=tk.FLAT,cursor="hand2",padx=10,pady=4)
        reload_btn.pack(side=tk.LEFT,padx=2)
        if self.hot_reload_enabled:
            apply_btn=tk.Button(btn_frame,text="[Apply] Apply",
                            command=self.apply_changes_hot,
                            font=("Segoe UI",8,"bold"),bg=DarkTheme.ACCENT_GREEN,
                            fg="white",activebackground=DarkTheme.BUTTON_HOVER,
                            relief=tk.FLAT,cursor="hand2",padx=10,pady=4)
            apply_btn.pack(side=tk.LEFT,padx=2)
        save_btn=tk.Button(btn_frame,text="[Save] Save",
                        command=self.save_all_configs,
                        font=("Segoe UI",8,"bold"),bg=DarkTheme.ACCENT_PURPLE,
                        fg="white",activebackground=DarkTheme.BUTTON_HOVER,
                        relief=tk.FLAT,cursor="hand2",padx=10,pady=4)
        save_btn.pack(side=tk.LEFT,padx=2)
        container=tk.Frame(config_frame,bg=DarkTheme.BG_DARK)
        container.pack(fill=tk.BOTH,expand=True,padx=10,pady=10)
        self.canvas=tk.Canvas(container,bg=DarkTheme.BG_DARK,highlightthickness=0)
        scrollbar=ttk.Scrollbar(container,orient="vertical",command=self.canvas.yview)
        self.scroll_frame=tk.Frame(self.canvas,bg=DarkTheme.BG_DARK)
        self.scroll_frame.bind("<Configure>",
                            lambda e:self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        canvas_window=self.canvas.create_window((0,0),window=self.scroll_frame,anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        def _on_canvas_configure(event):
            self.canvas.itemconfig(canvas_window,width=event.width)
        
        self.canvas.bind("<Configure>",_on_canvas_configure)
        self.canvas.pack(side=tk.LEFT,fill=tk.BOTH,expand=True)
        scrollbar.pack(side=tk.RIGHT,fill=tk.Y)
        
        def _bind_mousewheel(event):
            self.canvas.bind_all("<MouseWheel>",self._on_mousewheel)
        
        def _unbind_mousewheel(event):
            self.canvas.unbind_all("<MouseWheel>")
        
        self.canvas.bind("<Enter>",_bind_mousewheel)
        self.canvas.bind("<Leave>",_unbind_mousewheel)
        
        columns_container=tk.Frame(self.scroll_frame,bg=DarkTheme.BG_DARK)
        columns_container.pack(fill=tk.BOTH,expand=True)
        columns_container.grid_columnconfigure(0,weight=48,uniform="col")
        columns_container.grid_columnconfigure(1,weight=4,uniform="col")
        columns_container.grid_columnconfigure(2,weight=48,uniform="col")
        
        self.left_column=tk.Frame(columns_container,bg=DarkTheme.BG_DARK)
        self.left_column.grid(row=0,column=0,sticky="nsew")
        
        self.right_column=tk.Frame(columns_container,bg=DarkTheme.BG_DARK)
        self.right_column.grid(row=0,column=2,sticky="nsew")
        
        self.load_all_configs()
        self.create_config_sections()
    
    def _on_mousewheel(self,event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)),"units")
    
    def load_all_configs(self):
        try:
            if self.config_json_path.exists():
                with open(self.config_json_path,'r')as f:
                    self.config_data=json.load(f)
            if self.bot_info_path.exists():
                self.bot_info_data=self.parse_python_config(self.bot_info_path)
            if self.controls_path.exists():
                self.controls_data=self.parse_python_config(self.controls_path)
            self.parent.logger.system("[Config View] Loaded all configurations")
        except Exception as e:
            self.parent.logger.error(f"[Config View] Load error: {e}")
            messagebox.showerror("Load Error",f"Failed to load configs:\n{str(e)}")
    
    def parse_python_config(self,filepath):
        data={}
        try:
            with open(filepath,'r')as f:
                lines=f.readlines()
            for line in lines:
                line=line.strip()
                if not line or line.startswith('#')or line.startswith('"""')or line.startswith("'''"):
                    continue
                if '='in line and not line.startswith('def ')and not line.startswith('class '):
                    parts=line.split('=',1)
                    if len(parts)==2:
                        key=parts[0].strip()
                        value=parts[1].strip()
                        # FIXED: Strip inline comments properly
                        if '#' in value:
                            value=value.split('#')[0].strip()
                        if value.startswith('"')or value.startswith("'"):
                            value=value.strip('"\'')
                        data[key]=value
        except Exception as e:
            self.parent.logger.error(f"[Config View] Parse error for {filepath.name}: {e}")
        return data
    
    def create_config_sections(self):
        self.create_bot_identity_section()
        self.create_model_config_section()
        self.create_ollama_section()
        self.create_memory_section()
        self.create_features_section()
        self.create_performance_section()
        self.create_volume_section()
        self.create_logging_section()
        self.create_cognitive_section()
        self.create_rate_limiting_section()
        self.create_integrations_section()
        self.create_personality_editor_section()
    
    def create_section_frame(self,title,icon="[Config]",hot_reload=False,column="left"):
        section_title=f"{icon} {title}"
        if hot_reload and self.hot_reload_enabled:
            section_title+=" (Hot reload)"
        
        parent_column=self.left_column if column=="left" else self.right_column
        
        container=tk.Frame(parent_column,bg=DarkTheme.BG_DARK)
        container.pack(fill=tk.X,pady=5)
        
        frame=ttk.LabelFrame(container,text=section_title,
                            style="Accent.TLabelframe")
        frame.pack(fill=tk.BOTH,expand=True,padx=10)
        
        content_frame=tk.Frame(frame,bg=DarkTheme.BG_DARKER)
        content_frame.pack(fill=tk.BOTH,expand=True,padx=10,pady=10)
        self.category_frames[title]=content_frame
        return content_frame
    
    def add_input_field(self,parent,label,key,value,field_type="entry",
                    options=None,width=30,tooltip=None):
        row_frame=tk.Frame(parent,bg=DarkTheme.BG_DARKER)
        row_frame.pack(fill=tk.X,pady=3)
        label_widget=tk.Label(row_frame,text=label,font=("Segoe UI",9),
                            bg=DarkTheme.BG_DARKER,fg=DarkTheme.FG_PRIMARY,
                            anchor=tk.W,width=20)
        label_widget.pack(side=tk.LEFT,padx=(0,10))
        
        clean_value=str(value).split('#')[0].strip() if isinstance(value,str) else str(value)
        
        if field_type=="entry":
            field=tk.Entry(row_frame,font=("Segoe UI",9),bg=DarkTheme.BG_LIGHTER,
                        fg=DarkTheme.FG_PRIMARY,insertbackground=DarkTheme.ACCENT_GREEN,
                        relief=tk.FLAT,width=width)
            field.insert(0,clean_value)
            field.pack(side=tk.LEFT,fill=tk.X,expand=True)
        elif field_type=="text":
            text_frame=tk.Frame(row_frame,bg=DarkTheme.BG_DARKER)
            text_frame.pack(side=tk.LEFT,fill=tk.BOTH,expand=True)
            field=scrolledtext.ScrolledText(text_frame,height=3,wrap=tk.WORD,
                                        font=("Segoe UI",9),bg=DarkTheme.BG_LIGHTER,
                                        fg=DarkTheme.FG_PRIMARY,
                                        insertbackground=DarkTheme.ACCENT_GREEN,
                                        relief=tk.FLAT)
            field.insert(1.0,clean_value)
            field.pack(fill=tk.BOTH,expand=True)
        elif field_type=="checkbox":
            field=tk.BooleanVar(value=self._parse_bool(value))
            cb=tk.Checkbutton(row_frame,variable=field,bg=DarkTheme.BG_DARKER,
                            fg=DarkTheme.FG_PRIMARY,activebackground=DarkTheme.BG_DARKER,
                            selectcolor=DarkTheme.BG_LIGHTER)
            cb.pack(side=tk.LEFT)
        elif field_type=="combobox":
            field=ttk.Combobox(row_frame,values=options,state='readonly',
                            font=("Segoe UI",9),width=width)
            field.set(clean_value)
            field.pack(side=tk.LEFT,fill=tk.X,expand=True)
        elif field_type=="spinbox":
            spinbox_container=tk.Frame(row_frame,bg=DarkTheme.BG_DARKER)
            spinbox_container.pack(side=tk.LEFT,fill=tk.X,expand=True)
            
            field=tk.Spinbox(spinbox_container,from_=0,to=10000,font=("Segoe UI",9),
                            bg=DarkTheme.BG_LIGHTER,fg=DarkTheme.FG_PRIMARY,
                            relief=tk.FLAT,buttonbackground=DarkTheme.BG_LIGHTER,
                            buttoncursor="hand2")
            field.delete(0,tk.END)
            field.insert(0,clean_value)
            field.pack(side=tk.LEFT,fill=tk.X,expand=True)
        self.input_fields[key]=field
        if tooltip:
            self._add_tooltip(label_widget,tooltip)
    
    def _parse_bool(self,value):
        if isinstance(value,bool):
            return value
        return str(value).strip().lower()in('true','1','yes','on')
    
    def _add_tooltip(self,widget,text):
        def on_enter(e):
            tooltip=tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{e.x_root+10}+{e.y_root+10}")
            label=tk.Label(tooltip,text=text,bg=DarkTheme.BG_LIGHTER,
                          fg=DarkTheme.FG_PRIMARY,relief=tk.SOLID,borderwidth=1,
                          font=("Segoe UI",8),padx=5,pady=3)
            label.pack()
            widget.tooltip=tooltip
        def on_leave(e):
            if hasattr(widget,'tooltip'):
                widget.tooltip.destroy()
        widget.bind('<Enter>',on_enter)
        widget.bind('<Leave>',on_leave)
    
    def create_bot_identity_section(self):
        frame=self.create_section_frame("Bot & User Identity","[Identity]",hot_reload=True,column="left")
        self.add_input_field(frame,"Bot Name","agentname",
                            self.bot_info_data.get('agentname','Anna'),
                            tooltip="How the bot refers to itself")
        self.add_input_field(frame,"User Name","username",
                            self.bot_info_data.get('username','Sir'),
                            tooltip="How bot refers to the user")
        self.add_input_field(frame,"Game Username","game_username",
                            self.bot_info_data.get('game_username','Player'),
                            tooltip="User's in-game username")
        
        frame2=self.create_section_frame("Bot Configuration","[Bot]",hot_reload=False,column="left")
        self.add_input_field(frame2,"Voice Index","voiceIndex",
                            self.bot_info_data.get('voiceIndex','0'),
                            field_type="spinbox",
                            tooltip="pyttsx3 voice index (run test_voices.py)")
        self.add_input_field(frame2,"VB-Cable Name","vb_cable_name",
                            self.bot_info_data.get('vb_cable_name','CABLE Input'),
                            tooltip="Virtual audio cable device name")
        self.add_input_field(frame2,"Group Chat Port","group_chat_port",
                            self.bot_info_data.get('group_chat_port','54321'),
                            field_type="spinbox",
                            tooltip="Multi-agent Voice Hub port (unique per agent)")
    
    def create_model_config_section(self):
        frame=self.create_section_frame("Model Configuration","[Model]",column="left")
        models=self.bot_info_data
        self.add_input_field(frame,"Thought Model","thoughtmodel",
                            models.get('thoughtmodel','gemma4:latest'),
                            tooltip="Model for cognitive processing")
        self.add_input_field(frame,"Response Model","responsemodel",
                            models.get('responsemodel','gemma4:latest'),
                            tooltip="Model for response generation")
        self.add_input_field(frame,"Tool Model","toolmodel",
                            models.get('toolmodel','gemma4:latest'),
                            tooltip="Model for tool selection")
        self.add_input_field(frame,"Action Model","actionmodel",
                            models.get('actionmodel','gemma4:latest'),
                            tooltip="Model for action execution")
        self.add_input_field(frame,"Vision Model","visionmodel",
                            models.get('visionmodel','gemma4:latest'),
                            tooltip="Model for image analysis")
        self.add_input_field(frame,"Embed Model","embedmodel",
                            models.get('embedmodel','nomic-embed-text:latest'),
                            tooltip="Model for semantic embeddings")
    
    def create_ollama_section(self):
        frame=self.create_section_frame("Ollama API","[API]",column="right")
        ollama=self.config_data.get('ollama',{})
        self.add_input_field(frame,"Endpoint","ollama_endpoint",
                            ollama.get('endpoint','http://localhost:11434'))
        self.add_input_field(frame,"Temperature","ollama_temperature",
                            ollama.get('temperature',0.85),field_type="entry",width=10,
                            tooltip="Base temperature (0.0-2.0)")
        self.add_input_field(frame,"Temp: Action","ollama_temperature_action",
                            ollama.get('temperature_action',0.2),field_type="entry",width=10)
        self.add_input_field(frame,"Temp: Cognitive","ollama_temperature_cognitive",
                            ollama.get('temperature_cognitive',0.7),field_type="entry",width=10)
        self.add_input_field(frame,"Temp: Response","ollama_temperature_response",
                            ollama.get('temperature_response',0.9),field_type="entry",width=10)
        self.add_input_field(frame,"Max Tokens","ollama_max_tokens",
                            ollama.get('max_tokens',1000),field_type="spinbox")
        self.add_input_field(frame,"Context Size","ollama_num_ctx",
                            ollama.get('num_ctx',3000),field_type="spinbox")
        self.add_input_field(frame,"Top P","ollama_top_p",
                            ollama.get('top_p',0.92),field_type="entry",width=10)
        self.add_input_field(frame,"Top K","ollama_top_k",
                            ollama.get('top_k',60),field_type="spinbox")
        self.add_input_field(frame,"Repeat Penalty","ollama_repeat_penalty",
                            ollama.get('repeat_penalty',1.4),field_type="entry",width=10)
        self.add_input_field(frame,"Timeout (sec)","ollama_timeout",
                            ollama.get('timeout',600),field_type="spinbox")
    
    def create_memory_section(self):
        frame=self.create_section_frame("Memory System","[Memory]",column="left")
        memory=self.config_data.get('memory',{})
        ctrl=self.controls_data
        self.add_input_field(frame,"Use Base Memory","USE_BASE_MEMORY",
                            ctrl.get('USE_BASE_MEMORY','True'),field_type="checkbox",
                            tooltip="Document embeddings")
        self.add_input_field(frame,"Use Long Memory","USE_LONG_MEMORY",
                            ctrl.get('USE_LONG_MEMORY','True'),field_type="checkbox",
                            tooltip="Conversation summaries")
        self.add_input_field(frame,"Use Short Memory","USE_SHORT_MEMORY",
                            ctrl.get('USE_SHORT_MEMORY','True'),field_type="checkbox",
                            tooltip="Today's conversation")
        self.add_input_field(frame,"Save Memory","SAVE_MEMORY",
                            ctrl.get('SAVE_MEMORY','True'),field_type="checkbox")
        self.add_input_field(frame,"Memory Length","MEMORY_LENGTH",
                            ctrl.get('MEMORY_LENGTH','50'),field_type="spinbox",
                            tooltip="Recent interactions to keep")
        self.add_input_field(frame,"Max Context Entries","memory_max_context_entries",
                            memory.get('max_context_entries',50),field_type="spinbox")
        self.add_input_field(frame,"Long-term Results","MAX_LONG_TERM_MEMORIES",
                            ctrl.get('MAX_LONG_TERM_MEMORIES','1'),field_type="spinbox")
        self.add_input_field(frame,"Base Memory Results","MAX_BASE_MEMORIES",
                            ctrl.get('MAX_BASE_MEMORIES','1'),field_type="spinbox")
        self.add_input_field(frame,"Auto-summarize At","memory_auto_summarize_threshold",
                            memory.get('auto_summarize_threshold',50),field_type="spinbox")
    
    def create_features_section(self):
        frame=self.create_section_frame("Features","[Features]",hot_reload=True,column="left")
        ctrl=self.controls_data
        features=self.config_data.get('features',{})
        self.add_input_field(frame,"Vision System","use_vision",
                            features.get('use_vision',False),field_type="checkbox")
        self.add_input_field(frame,"OpenCV Vision","USE_OPENCV_VISION",
                            ctrl.get('USE_OPENCV_VISION','False'),field_type="checkbox")
        self.add_input_field(frame,"Warudo Integration","use_warudo",
                            features.get('use_warudo',True),field_type="checkbox")
        self.add_input_field(frame,"Sound Effects","use_sound_effects",
                            features.get('use_sound_effects',True),field_type="checkbox")
        self.add_input_field(frame,"Streaming","USE_STREAMING",
                            ctrl.get('USE_STREAMING','False'),field_type="checkbox")
        self.add_input_field(frame,"Thought Buffer","USE_THOUGHT_BUFFER",
                            ctrl.get('USE_THOUGHT_BUFFER','True'),field_type="checkbox")
        self.add_input_field(frame,"Tool Selection AI","INTELLIGENT_TOOL_SELECTION",
                            ctrl.get('INTELLIGENT_TOOL_SELECTION','False'),field_type="checkbox")
        self.add_input_field(frame,"Tool Verification AI","USE_AI_TOOL_VERIFICATION",
                            ctrl.get('USE_AI_TOOL_VERIFICATION','False'),field_type="checkbox")
    
    def create_performance_section(self):
        frame=self.create_section_frame("Performance","[Performance]",hot_reload=True,column="left")
        ctrl=self.controls_data
        self.add_input_field(frame,"Max Tokens","MAX_TOKENS",
                            ctrl.get('MAX_TOKENS','2000'),field_type="spinbox")
        self.add_input_field(frame,"Temperature","TEMPERATURE",
                            ctrl.get('TEMPERATURE','0.7'),field_type="entry",width=10)
        self.add_input_field(frame,"Max Tool Result Chars","MAX_TOOL_RESULT_CHARS",
                            ctrl.get('MAX_TOOL_RESULT_CHARS','1000'),field_type="spinbox",
                            tooltip="Max characters returned per tool result")
        self.add_input_field(frame,"Max Tool Results","MAX_TOOL_RESULTS",
                            ctrl.get('MAX_TOOL_RESULTS','3'),field_type="spinbox",
                            tooltip="Max number of tool results included in context")
        self.add_input_field(frame,"OpenCV FPS","opencv_vision_fps",
                            ctrl.get('opencv_vision_fps','15'),field_type="spinbox",
                            tooltip="Vision capture frame rate")
        self.add_input_field(frame,"Vision Interval","opencv_vision_interval",
                            ctrl.get('opencv_vision_interval','5.0'),field_type="entry",width=10,
                            tooltip="Vision analysis interval (seconds)")
        self.add_input_field(frame,"Vision Width","opencv_vision_width",
                            ctrl.get('opencv_vision_width','1024'),field_type="spinbox")
        self.add_input_field(frame,"Vision Height","opencv_vision_height",
                            ctrl.get('opencv_vision_height','768'),field_type="spinbox")
        self.add_input_field(frame,"Change Threshold","opencv_vision_change_threshold",
                            ctrl.get('opencv_vision_change_threshold','50000'),
                            field_type="spinbox")
    
    def create_volume_section(self):
        frame=self.create_section_frame("Volume","[Volume]",hot_reload=True,column="right")
        ctrl=self.controls_data
        self.add_input_field(frame,"Voice Volume (0.0-1.0)","VOICE_VOLUME",
                            ctrl.get('VOICE_VOLUME','1.0'),field_type="entry",width=10)
        self.add_input_field(frame,"Sound FX Volume (0.0-1.0)","SOUND_EFFECT_VOLUME",
                            ctrl.get('SOUND_EFFECT_VOLUME','1.0'),field_type="entry",width=10)
        self.add_input_field(frame,"Avatar Speech","AVATAR_SPEECH",
                            ctrl.get('AVATAR_SPEECH','True'),field_type="checkbox")
        
    def create_logging_section(self):
        frame=self.create_section_frame("Logging","[Logging]",hot_reload=True,column="right")
        ctrl=self.controls_data
        self.add_input_field(frame,"Tool Execution","LOG_TOOL_EXECUTION",
                            ctrl.get('LOG_TOOL_EXECUTION','True'),field_type="checkbox")
        self.add_input_field(frame,"Prompt Construction","LOG_PROMPT_CONSTRUCTION",
                            ctrl.get('LOG_PROMPT_CONSTRUCTION','False'),field_type="checkbox")
        self.add_input_field(frame,"Reactive Prompts","LOG_REACTIVE_PROMPT",
                            ctrl.get('LOG_REACTIVE_PROMPT','True'),field_type="checkbox")
        self.add_input_field(frame,"Reflective Prompts","LOG_REFLECTIVE_PROMPT",
                            ctrl.get('LOG_REFLECTIVE_PROMPT','True'),field_type="checkbox")
        self.add_input_field(frame,"Proactive Prompts","LOG_PROACTIVE_PROMPT",
                            ctrl.get('LOG_PROACTIVE_PROMPT','True'),field_type="checkbox")
        self.add_input_field(frame,"Responsive Prompts","LOG_RESPONSIVE_PROMPT",
                            ctrl.get('LOG_RESPONSIVE_PROMPT','True'),field_type="checkbox")
        self.add_input_field(frame,"Action Prompts","LOG_ACTION_PROMPT",
                            ctrl.get('LOG_ACTION_PROMPT','True'),field_type="checkbox")
        self.add_input_field(frame,"Response Processing","LOG_RESPONSE_PROCESSING",
                            ctrl.get('LOG_RESPONSE_PROCESSING','True'),field_type="checkbox")
        self.add_input_field(frame,"System Info","LOG_SYSTEM_INFORMATION",
                            ctrl.get('LOG_SYSTEM_INFORMATION','True'),field_type="checkbox")
        self.add_input_field(frame,"Show Chat","SHOW_CHAT",
                            ctrl.get('SHOW_CHAT','False'),field_type="checkbox")
    
    def create_cognitive_section(self):
        frame=self.create_section_frame("Cognitive Loop","[Cognitive]",hot_reload=True,column="right")
        ctrl=self.controls_data
        self.add_input_field(frame,"Continuous Thinking","ENABLE_CONTINUOUS_THINKING",
                            ctrl.get('ENABLE_CONTINUOUS_THINKING','False'),
                            field_type="checkbox",
                            tooltip="Master toggle for autonomous thinking")
        self.add_input_field(frame,"Min Proactive Interval","MIN_PROACTIVE_INTERVAL",
                            ctrl.get('MIN_PROACTIVE_INTERVAL','5.0'),
                            field_type="entry",width=10,
                            tooltip="Min seconds between thoughts")
        self.add_input_field(frame,"Max Proactive Interval","MAX_PROACTIVE_INTERVAL",
                            ctrl.get('MAX_PROACTIVE_INTERVAL','15.0'),
                            field_type="entry",width=10)
        self.add_input_field(frame,"Max Consecutive","MAX_CONSECUTIVE_PROACTIVE",
                            ctrl.get('MAX_CONSECUTIVE_PROACTIVE','200'),
                            field_type="spinbox")
        self.add_input_field(frame,"Chat Engagement","CHAT_ENGAGEMENT",
                            ctrl.get('CHAT_ENGAGEMENT','False'),field_type="checkbox")
        self.add_input_field(frame,"Auto-Restart","AUTO_RESTART",
                            ctrl.get('AUTO_RESTART','False'),field_type="checkbox",
                            tooltip="Auto-restart on crash (max 3 times)")
        self.add_input_field(frame,"Auto-Respond","AUTO_RESPOND",
                            ctrl.get('AUTO_RESPOND','False'),field_type="checkbox")
        self.add_input_field(frame,"Auto-Respond Interval","AUTO_RESPOND_INTERVAL",
                            ctrl.get('AUTO_RESPOND_INTERVAL','60'),field_type="spinbox")
        self.add_input_field(frame,"Auto-Prompt","AUTO_PROMPT",
                            ctrl.get('AUTO_PROMPT','False'),field_type="checkbox")
        self.add_input_field(frame,"Auto-Prompt Interval","AUTO_PROMPT_INTERVAL",
                            ctrl.get('AUTO_PROMPT_INTERVAL','300'),field_type="spinbox")
        self.add_input_field(frame,"Kill Command","KILL_COMMAND",
                            ctrl.get('KILL_COMMAND','shut down sleep now'),
                            field_type="entry")
    
    def create_rate_limiting_section(self):
        frame=self.create_section_frame("Rate Limiting","[Rate Limit]",hot_reload=True,column="left")
        ctrl=self.controls_data
        self.add_input_field(frame,"Limit Processing","LIMIT_PROCESSING",
                            ctrl.get('LIMIT_PROCESSING','False'),field_type="checkbox")
        self.add_input_field(frame,"Processing Delay (sec)","PROCESSING_DELAY",
                            ctrl.get('PROCESSING_DELAY','10'),field_type="spinbox")
        self.add_input_field(frame,"Limit Speaking","LIMIT_SPEAKING",
                            ctrl.get('LIMIT_SPEAKING','False'),field_type="checkbox")
        self.add_input_field(frame,"Speaking Delay (sec)","SPEAKING_DELAY",
                            ctrl.get('SPEAKING_DELAY','30'),field_type="spinbox")
    
    def create_integrations_section(self):
        frame=self.create_section_frame("Integrations","[Integrations]",hot_reload=True,column="right")
        ctrl=self.controls_data
        warudo=self.config_data.get('warudo',{})
        chat_eng=self.config_data.get('chat_engagement',{})
        self.add_input_field(frame,"Group Chat","GROUP_CHAT",
                            ctrl.get('GROUP_CHAT','False'),field_type="checkbox",
                            tooltip="Multi-agent Voice Hub")
        self.add_input_field(frame,"Warudo URL","warudo_websocket_url",
                            warudo.get('websocket_url','ws://127.0.0.1:19190'))
        self.add_input_field(frame,"Warudo Enabled","warudo_enabled",
                            warudo.get('enabled',True),field_type="checkbox")
        self.add_input_field(frame,"Warudo Auto-Connect","warudo_auto_connect",
                            warudo.get('auto_connect',True),field_type="checkbox")
        self.add_input_field(frame,"Chat Engagement","chat_engagement_enabled",
                            chat_eng.get('enabled',False),field_type="checkbox")
        self.add_input_field(frame,"Chat Autonomous","chat_engagement_autonomous",
                            chat_eng.get('autonomous',True),field_type="checkbox")
        self.add_input_field(frame,"Check Interval","chat_engagement_check_interval",
                            chat_eng.get('check_interval',30),field_type="spinbox")
        self.add_input_field(frame,"Max Unengaged","chat_engagement_max_unengaged_messages",
                            chat_eng.get('max_unengaged_messages',5),field_type="spinbox")
    
    def create_personality_editor_section(self):
        """Create full-width personality editor at bottom"""
        full_width_container=tk.Frame(self.scroll_frame,bg=DarkTheme.BG_DARK)
        full_width_container.pack(fill=tk.BOTH,expand=True,pady=10)
        
        frame=ttk.LabelFrame(full_width_container,
                            text="[Personality] Unified Personality Editor",
                            style="Accent.TLabelframe")
        frame.pack(fill=tk.BOTH,expand=True,padx=10)
        
        content_frame=tk.Frame(frame,bg=DarkTheme.BG_DARKER)
        content_frame.pack(fill=tk.BOTH,expand=True,padx=15,pady=15)
        
        info_label=tk.Label(content_frame,
                           text="Edit the core personality prompt used across all AI interactions. Changes apply immediately with hot-reload.",
                           font=("Segoe UI",9,"italic"),
                           bg=DarkTheme.BG_DARKER,fg=DarkTheme.FG_MUTED,
                           wraplength=700,justify=tk.LEFT)
        info_label.pack(anchor=tk.W,pady=(0,10))
        
        text_frame=tk.Frame(content_frame,bg=DarkTheme.BG_DARKER)
        text_frame.pack(fill=tk.BOTH,expand=True,pady=(0,10))
        
        self.personality_text=scrolledtext.ScrolledText(text_frame,
                                                       height=20,wrap=tk.WORD,
                                                       font=("Consolas",9),
                                                       bg=DarkTheme.BG_LIGHTER,
                                                       fg=DarkTheme.FG_PRIMARY,
                                                       insertbackground=DarkTheme.ACCENT_GREEN,
                                                       relief=tk.FLAT,borderwidth=1,
                                                       highlightthickness=1,
                                                       highlightbackground=DarkTheme.BORDER,
                                                       highlightcolor=DarkTheme.ACCENT_PURPLE)
        self.personality_text.pack(fill=tk.BOTH,expand=True)
        
        button_frame=tk.Frame(content_frame,bg=DarkTheme.BG_DARKER)
        button_frame.pack(fill=tk.X,pady=(10,0))
        
        if self.hot_reload_enabled:
            apply_btn=tk.Button(button_frame,text="[Apply] Apply (Hot-Reload)",
                               command=self.apply_personality_hot,
                               font=("Segoe UI",9,"bold"),
                               bg=DarkTheme.ACCENT_GREEN,fg="white",
                               activebackground=DarkTheme.BUTTON_HOVER,
                               activeforeground="white",relief=tk.FLAT,
                               cursor="hand2",padx=15,pady=5)
            apply_btn.pack(side=tk.LEFT,padx=(0,5))
        
        save_btn=tk.Button(button_frame,text="[Save] Save to File",
                          command=self.save_personality_to_file,
                          font=("Segoe UI",9,"bold"),
                          bg=DarkTheme.ACCENT_PURPLE,fg="white",
                          activebackground=DarkTheme.BUTTON_HOVER,
                          activeforeground="white",relief=tk.FLAT,
                          cursor="hand2",padx=15,pady=5)
        save_btn.pack(side=tk.LEFT,padx=(0,5))
        
        reset_btn=tk.Button(button_frame,text="[Reload] Reload from File",
                           command=self.load_personality_prompt,
                           font=("Segoe UI",9),
                           bg=DarkTheme.BUTTON_BG,fg=DarkTheme.FG_PRIMARY,
                           activebackground=DarkTheme.BUTTON_HOVER,
                           activeforeground=DarkTheme.FG_PRIMARY,
                           relief=tk.FLAT,cursor="hand2",
                           padx=15,pady=5)
        reset_btn.pack(side=tk.LEFT,padx=(0,5))
        
        self.personality_status_label=tk.Label(button_frame,text="",
                                              font=("Segoe UI",8,"italic"),
                                              bg=DarkTheme.BG_DARKER,
                                              fg=DarkTheme.FG_MUTED)
        self.personality_status_label.pack(side=tk.LEFT,padx=(10,0))
        
        self.load_personality_prompt()
    
    def load_personality_prompt(self):
        """Load personality prompt from file"""
        try:
            if not self.personality_path.exists():
                self.personality_status_label.config(text="[Warning] File not found",
                                                    fg=DarkTheme.ACCENT_RED)
                return
            
            with open(self.personality_path,'r',encoding='utf-8')as f:
                content=f.read()
            
            start_marker='return f"""'
            end_marker='"""'
            
            start_idx=content.find(start_marker)
            if start_idx==-1:
                self.personality_status_label.config(text="[Warning] Marker not found",
                                                    fg=DarkTheme.ACCENT_RED)
                return
            
            start_idx+=len(start_marker)
            end_idx=content.find(end_marker,start_idx)
            
            if end_idx==-1:
                self.personality_status_label.config(text="[Warning] End marker not found",
                                                    fg=DarkTheme.ACCENT_RED)
                return
            
            personality_content=content[start_idx:end_idx].strip()
            
            self.personality_text.delete(1.0,tk.END)
            self.personality_text.insert(1.0,personality_content)
            
            self.personality_status_label.config(text="[Confirmed] Loaded",
                                                fg=DarkTheme.ACCENT_GREEN)
            self.parent.root.after(2000,lambda:self.personality_status_label.config(text=""))
            
            self.parent.logger.system("[Config View] Personality prompt loaded")
            
        except Exception as e:
            self.parent.logger.error(f"[Config View] Personality load error: {e}")
            self.personality_status_label.config(text="[Warning] Load error",
                                                fg=DarkTheme.ACCENT_RED)
    
    def apply_personality_hot(self):
        """Hot-reload personality into live module"""
        try:
            new_personality=self.personality_text.get(1.0,tk.END).strip()
            
            from personality.prompts.personality_prompt_parts import PersonalityPromptParts
            
            @staticmethod
            def new_get_unified_personality()->str:
                return new_personality
            
            PersonalityPromptParts.get_unified_personality=new_get_unified_personality
            
            self.personality_status_label.config(text="[Confirmed] Applied (hot-reload)",
                                                fg=DarkTheme.ACCENT_GREEN)
            self.parent.root.after(3000,lambda:self.personality_status_label.config(text=""))
            
            self.parent.logger.success("[Config View] Personality hot-reloaded")
            
        except Exception as e:
            self.parent.logger.error(f"[Config View] Personality hot-reload error: {e}")
            self.personality_status_label.config(text="[Warning] Apply error",
                                                fg=DarkTheme.ACCENT_RED)
            import traceback
            traceback.print_exc()
    
    def save_personality_to_file(self):
        """Save personality prompt to file"""
        try:
            result=messagebox.askyesno("Save Personality",
                                      "Save personality prompt to file?\n\n"
                                      "[Warning] This will modify personality_prompt_parts.py",
                                      icon='warning')
            if not result:
                return
            
            new_personality=self.personality_text.get(1.0,tk.END).strip()
            
            with open(self.personality_path,'r',encoding='utf-8')as f:
                content=f.read()
            
            start_marker='return f"""'
            end_marker='"""'
            
            start_idx=content.find(start_marker)
            if start_idx==-1:
                raise ValueError("Could not find start marker in file")
            
            start_idx+=len(start_marker)
            end_idx=content.find(end_marker,start_idx)
            
            if end_idx==-1:
                raise ValueError("Could not find end marker in file")
            
            new_content=(content[:start_idx]+'\n'+new_personality+'\n'+content[end_idx:])
            
            import shutil
            backup_path=self.personality_path.with_suffix('.py.bak')
            shutil.copy2(self.personality_path,backup_path)
            
            with open(self.personality_path,'w',encoding='utf-8')as f:
                f.write(new_content)
            
            self.personality_status_label.config(text="[Confirmed] Saved to file",
                                                fg=DarkTheme.ACCENT_GREEN)
            self.parent.root.after(3000,lambda:self.personality_status_label.config(text=""))
            
            self.parent.logger.success("[Config View] Personality saved to file")
            messagebox.showinfo("Saved","Personality saved to personality_prompt_parts.py\n\n"
                               "Backup created at .py.bak")
            
        except Exception as e:
            self.parent.logger.error(f"[Config View] Personality save error: {e}")
            self.personality_status_label.config(text="[Warning] Save error",
                                                fg=DarkTheme.ACCENT_RED)
            messagebox.showerror("Save Error",f"Failed to save personality:\n{str(e)}")
    
    def apply_changes_hot(self):
        """Hot-reload changes to bot_info and controls without restart"""
        try:
            self.parent.logger.system("[Config View] Applying hot-reload changes...")
            
            import personality.bot_info as bot_info
            import BASE.config.controls as controls
            
            # Bot info and model configuration
            for key,field in self.input_fields.items():
                if key in('agentname','username','game_username','voiceIndex',
                        'vb_cable_name','group_chat_port','thoughtmodel','responsemodel',
                        'toolmodel','actionmodel','visionmodel','embedmodel'):
                    value=self._get_field_value(field)
                    if hasattr(bot_info,key):
                        setattr(bot_info,key,value)
                        self.parent.logger.system(f"[Config View] Set bot_info.{key} = {value}")
                
                # Regular control variables
                elif key.startswith('USE_')or key.startswith('ENABLE_')or \
                key in('SAVE_MEMORY','MEMORY_LENGTH','MAX_LONG_TERM_MEMORIES','MAX_BASE_MEMORIES',
                        'MAX_TOKENS','MAX_TOOL_RESULT_CHARS','MAX_TOOL_RESULTS',
                        'TEMPERATURE','VOICE_VOLUME','SOUND_EFFECT_VOLUME',
                        'AVATAR_SPEECH','STREAM_RESPONSES',
                        'opencv_vision_fps','opencv_vision_interval',
                        'opencv_vision_width','opencv_vision_height','opencv_vision_change_threshold',
                        'MIN_PROACTIVE_INTERVAL','MAX_PROACTIVE_INTERVAL','MAX_CONSECUTIVE_PROACTIVE',
                        'CHAT_ENGAGEMENT','AUTO_RESTART','AUTO_RESPOND','AUTO_RESPOND_INTERVAL',
                        'AUTO_PROMPT','AUTO_PROMPT_INTERVAL','KILL_COMMAND','LIMIT_PROCESSING',
                        'PROCESSING_DELAY','LIMIT_SPEAKING','SPEAKING_DELAY','GROUP_CHAT','SHOW_CHAT',
                        'INTELLIGENT_TOOL_SELECTION','USE_AI_TOOL_VERIFICATION'):
                    value=self._get_field_value(field)
                    if hasattr(controls,key):
                        setattr(controls,key,value)
                        self.parent.logger.system(f"[Config View] Set controls.{key} = {value}")
            
            # Logging controls - sync to BOTH controls and config
            logging_controls = [
                'LOG_TOOL_EXECUTION', 'LOG_PROMPT_CONSTRUCTION',
                'LOG_RESPONSE_PROCESSING', 'LOG_SYSTEM_INFORMATION', 'SHOW_CHAT',
                'LOG_REACTIVE_PROMPT', 'LOG_REFLECTIVE_PROMPT', 'LOG_PROACTIVE_PROMPT',
                'LOG_RESPONSIVE_PROMPT', 'LOG_ACTION_PROMPT', 'LOG_CODING_EXECUTION',
                'LOG_DISCORD_EXECUTION', 'LOG_MINECRAFT_EXECUTION'
            ]
            
            for key in logging_controls:
                if key in self.input_fields:
                    value = self._get_field_value(self.input_fields[key])
                    
                    # Update controls module
                    if hasattr(controls, key):
                        setattr(controls, key, value)
                        self.parent.logger.system(f"[Config View] Set controls.{key} = {value}")
                    
                    # Update config (CRITICAL for logger to see changes)
                    if hasattr(self.parent.config, key):
                        setattr(self.parent.config, key, value)
                        self.parent.logger.system(f"[Config View] Set config.{key} = {value}")
            
            self.parent.logger.success("[Config View] Controls hot-reloaded into live module")
            
        except Exception as e:
            self.parent.logger.error(f"[Config View] Controls hot-reload failed: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def reload_all_configs(self):
        try:
            self.load_all_configs()
            for widget in self.scroll_frame.winfo_children():
                widget.destroy()
            
            columns_container=tk.Frame(self.scroll_frame,bg=DarkTheme.BG_DARK)
            columns_container.pack(fill=tk.BOTH,expand=True)
            columns_container.grid_columnconfigure(0,weight=48,uniform="col")
            columns_container.grid_columnconfigure(1,weight=4,uniform="col")
            columns_container.grid_columnconfigure(2,weight=48,uniform="col")
            
            self.left_column=tk.Frame(columns_container,bg=DarkTheme.BG_DARK)
            self.left_column.grid(row=0,column=0,sticky="nsew")
            
            self.right_column=tk.Frame(columns_container,bg=DarkTheme.BG_DARK)
            self.right_column.grid(row=0,column=2,sticky="nsew")
            
            self.input_fields.clear()
            self.category_frames.clear()
            self.create_config_sections()
            self.save_status_label.config(text="[Confirmed] Reloaded",
                                        fg=DarkTheme.ACCENT_GREEN)
            self.parent.root.after(3000,lambda:self.save_status_label.config(text=""))
            self.parent.logger.success("[Config View] Configurations reloaded")
        except Exception as e:
            self.parent.logger.error(f"[Config View] Reload error: {e}")
            messagebox.showerror("Reload Error",f"Failed to reload:\n{str(e)}")
    
    def save_all_configs(self):
        try:
            result=messagebox.askyesno("Save Changes",
                                      "Save all changes to disk?\n\n"
                                      "[Warning] Restart required for some changes.",
                                      icon='warning')
            if not result:
                return
            self.save_config_json()
            self.save_bot_info_py()
            self.save_controls_py()
            self.save_status_label.config(text="[Confirmed] Saved!",
                                         fg=DarkTheme.ACCENT_GREEN)
            self.parent.root.after(5000,lambda:self.save_status_label.config(text=""))
            self.parent.logger.success("[Config View] All configurations saved to disk")
            messagebox.showinfo("Saved","All configurations saved!\n\n"
                               "[Reload] Restart for changes to take effect.")
        except Exception as e:
            self.parent.logger.error(f"[Config View] Save error: {e}")
            self.save_status_label.config(text="[Warning] Save failed",
                                         fg=DarkTheme.ACCENT_RED)
            messagebox.showerror("Save Error",f"Failed to save:\n{str(e)}")
    
    def save_config_json(self):
        # Map from input_field key → (config.json section, sub_key)
        _CONTROLS_JSON_KEYS = {
            'MAX_TOKENS':           ('controls', 'max_tokens'),
            'MAX_TOOL_RESULT_CHARS':('controls', 'max_tool_result_chars'),
            'MAX_TOOL_RESULTS':     ('controls', 'max_tool_results'),
            'TEMPERATURE':          ('controls', 'temperature'),
        }
        for key,field in self.input_fields.items():
            if key.startswith('ollama_'):
                section='ollama'
                sub_key=key.replace('ollama_','')
            elif key.startswith('memory_'):
                section='memory'
                sub_key=key.replace('memory_','')
            elif key.startswith('warudo_'):
                section='warudo'
                sub_key=key.replace('warudo_','')
            elif key.startswith('chat_engagement_'):
                section='chat_engagement'
                sub_key=key.replace('chat_engagement_','')
            elif key in('use_vision','use_warudo','use_sound_effects'):
                section='features'
                sub_key=key
            elif key in _CONTROLS_JSON_KEYS:
                section, sub_key = _CONTROLS_JSON_KEYS[key]
            else:
                continue
            if section not in self.config_data:
                self.config_data[section]={}
            value=self._get_field_value(field)
            self.config_data[section][sub_key]=value
        with open(self.config_json_path,'w')as f:
            json.dump(self.config_data,f,indent=2)
        self.parent.logger.system("[Config View] Saved config.json")
    
    def save_bot_info_py(self):
        updates={}
        for key in('agentname','username','game_username','voiceIndex',
                   'vb_cable_name','group_chat_port','thoughtmodel','responsemodel',
                   'toolmodel','actionmodel','visionmodel','embedmodel'):
            if key in self.input_fields:
                updates[key]=self._get_field_value(self.input_fields[key])
        self._update_python_file(self.bot_info_path,updates)
        self.parent.logger.system("[Config View] Saved bot_info.py")
    
    def save_controls_py(self):
        updates={}
        for key,field in self.input_fields.items():
            if key.startswith('USE_')or key.startswith('ENABLE_')or \
               key.startswith('LOG_')or \
               key in('SAVE_MEMORY','MEMORY_LENGTH','MAX_LONG_TERM_MEMORIES','MAX_BASE_MEMORIES',
                      'MAX_TOKENS','MAX_TOOL_RESULT_CHARS','MAX_TOOL_RESULTS',
                      'TEMPERATURE','VOICE_VOLUME','SOUND_EFFECT_VOLUME',
                      'AVATAR_SPEECH','STREAM_RESPONSES',
                      'opencv_vision_fps','opencv_vision_interval',
                      'opencv_vision_width','opencv_vision_height','opencv_vision_change_threshold',
                      'MIN_PROACTIVE_INTERVAL','MAX_PROACTIVE_INTERVAL','MAX_CONSECUTIVE_PROACTIVE',
                      'CHAT_ENGAGEMENT','AUTO_RESTART','AUTO_RESPOND','AUTO_RESPOND_INTERVAL',
                      'AUTO_PROMPT','AUTO_PROMPT_INTERVAL','KILL_COMMAND','LIMIT_PROCESSING',
                      'PROCESSING_DELAY','LIMIT_SPEAKING','SPEAKING_DELAY','GROUP_CHAT','SHOW_CHAT',
                      'INTELLIGENT_TOOL_SELECTION','USE_AI_TOOL_VERIFICATION'):
                updates[key]=self._get_field_value(field)
        self._update_python_file(self.controls_path,updates)
        self.parent.logger.system("[Config View] Saved controls.py")
    
    def _get_field_value(self,field):
        if isinstance(field,tk.BooleanVar):
            return field.get()
        elif isinstance(field,tk.Entry)or isinstance(field,tk.Spinbox)or isinstance(field,ttk.Combobox):
            val=field.get()
            if val.replace('.','',1).replace('-','',1).isdigit():
                return float(val)if'.'in val else int(val)
            return val
        elif isinstance(field,scrolledtext.ScrolledText):
            return field.get(1.0,tk.END).strip()
        return None
    
    def _update_python_file(self,filepath,updates):
        with open(filepath,'r')as f:
            lines=f.readlines()
        new_lines=[]
        for line in lines:
            modified=False
            for key,value in updates.items():
                if line.strip().startswith(f"{key}=")or line.strip().startswith(f"{key} ="):
                    if isinstance(value,str):
                        if not value.replace('.','',1).replace('-','',1).isdigit():
                            new_lines.append(f'{key} = "{value}"\n')
                        else:
                            new_lines.append(f'{key} = {value}\n')
                    elif isinstance(value,bool):
                        new_lines.append(f'{key} = {value}\n')
                    else:
                        new_lines.append(f'{key} = {value}\n')
                    modified=True
                    break
            if not modified:
                new_lines.append(line)
        import shutil
        backup_path=filepath.with_suffix('.py.bak')
        shutil.copy2(filepath,backup_path)
        with open(filepath,'w')as f:
            f.writelines(new_lines)