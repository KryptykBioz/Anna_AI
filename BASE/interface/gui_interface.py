# File: BASE/interface/gui_interface.py
"""
REFACTORED GUI: Uses centralized AI Core with new modular tool system
Removed hardcoded Coding panel - now uses modular component system
PERFORMANCE FIX: Properly counts actual Text widget lines, not log entries
FIXED: Corrected TTSTool initialization to match class signature
"""
import tkinter as tk
from tkinter import messagebox
import sys
import time
import queue
import threading
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from BASE.core.ai_core import AICore
    from BASE.core.config import Config
    from BASE.core.logger import Logger, MessageType
    from personality.bot_info import agentname
    import personality.controls as controls

    from BASE.interface.voice_manager import VoiceManager
    from BASE.interface.gui_components import ControlPanelManager
    from BASE.interface.gui_session_files_panel import SessionFilesPanel
    from BASE.interface.gui_message_processor import MessageProcessor
    from BASE.interface.gui_message_handler import GUIMessageHandler
    from BASE.interface.gui_ui_builder import UIBuilder
    from BASE.interface.gui_chat_view import ChatView

except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Please ensure you're running from the correct directory structure")
    sys.exit(1)

class OllamaGUI:
    # PERFORMANCE: Maximum log lines to keep in system log (actual Text widget lines)
    MAX_LOG_LINES = 6000
    
    def __init__(self, root):
        """
        Initialize GUI with VERIFIED singleton Config and Logger
        """
        self.root = root
        
        from personality.bot_info import agentname
        self.agentname = agentname
        
        import personality.controls as controls
        self.controls = controls
        
        self.root.title(f"{agentname} - Ollama Agent GUI")
        self.root.geometry("1600x1000")
        
        self.twitch_chat = None
        self.youtube_chat = None

        # Create singleton Config
        from BASE.core.config import Config
        self.config = Config()
        
        print(f"[Init] Created singleton Config: {id(self.config)}")

        # Create Logger with Config reference
        from BASE.core.logger import Logger
        
        self.logger = Logger(
            name="GUI",
            enable_timestamps=True,
            enable_console=False,
            gui_callback=self._gui_log_callback,
            config=self.config
        )
        
        # Verify logger has config reference
        if not hasattr(self.logger, 'config') or self.logger.config is None:
            raise RuntimeError("CRITICAL: Logger initialization failed - no config reference!")
        
        if id(self.logger.config) != id(self.config):
            raise RuntimeError(f"CRITICAL: Logger has DIFFERENT config instance!")
        
        print(f"[Init] Logger has correct config: {id(self.logger.config)}")

        # Create AI Core with same Config
        from BASE.core.ai_core import AICore
        
        self.ai_core = AICore(
            config=self.config,
            controls_module=controls,
            project_root=project_root,
            gui_logger=self._gui_log_callback
        )
        
        self._verify_config_chain()

        # Verify tool execution manager
        if not hasattr(self.ai_core, 'tool_manager'):
            self.logger.error("CRITICAL: AI Core missing tool_manager!")
            raise RuntimeError("Tool manager not initialized")

        self.logger.system(f"[SUCCESS] Tool manager initialized")
        enabled_tools = self.ai_core.tool_manager.get_enabled_tool_names()
        if enabled_tools:
            self.logger.system(f"Enabled tools: {', '.join(enabled_tools)}")
        else:
            self.logger.system("No tools currently enabled")

        # ====================================================================
        # CRITICAL FIX: Initialize Hot-Reload Manager
        # ====================================================================
        from BASE.core.tool_hot_reload_manager import HotReloadManager
        
        self.hot_reload_manager = HotReloadManager(
            project_root=project_root,
            logger=self.logger,
            config=self.config
        )
        
        # Register with tool manager
        if hasattr(self.ai_core, 'tool_manager'):
            self.hot_reload_manager.register_tool_manager(self.ai_core.tool_manager)
            self.logger.system("[Hot-Reload] Manager initialized and registered")
        else:
            self.logger.warning("[Hot-Reload] No tool manager - hot-reload disabled")
        # ====================================================================

        # Setup external tools
        self._setup_tts_tool()
        # self._setup_integrations()

        # GUI-specific components
        import queue
        self.message_queue = queue.Queue()
        self.input_queue = queue.Queue()
        self.processing = False
        self.current_message = None
        self.speech_stop_flag = threading.Event()
        self.last_interaction = time.time()
        self.last_auto_prompt = time.time()

        # Voice manager
        from BASE.interface.voice_manager import VoiceManager
        self.voice_manager = VoiceManager(
            self.message_queue,
            self.input_queue,
            self.logger,
            ai_core=self.ai_core  # NEW: Pass ai_core for thought buffer access
        )

        # Control panel manager
        from BASE.interface.gui_components import ControlPanelManager
        self.control_panel_manager = ControlPanelManager(self.ai_core, self.logger)

        # Inject AI core into control manager
        if hasattr(self.ai_core, 'control_manager') and self.ai_core.control_manager:
            self.ai_core.control_manager.set_ai_core(self.ai_core)
            
            if hasattr(self.ai_core, 'tool_manager'):
                self.ai_core.control_manager.set_tool_manager(
                    self.ai_core.tool_manager
                )
                self.logger.system("[SUCCESS] Control manager connected to tool manager")
            
            self.logger.system("[SUCCESS] AI Core injected into ControlManager")
        else:
            self.logger.warning("[WARNING] Control manager not found")

        # Session files panel (no longer needs coding panel reference)
        from BASE.interface.gui_session_files_panel import SessionFilesPanel
        self.session_files_panel = SessionFilesPanel(
            self.root,
            self.ai_core,
            self.logger
        )

        # Message processor
        from BASE.interface.gui_message_processor import MessageProcessor
        self.message_processor = MessageProcessor(
            self.ai_core,
            self.message_queue,
            self.speech_stop_flag,
            self.logger
        )

        # Message handler
        from BASE.interface.gui_message_handler import GUIMessageHandler
        self.chat_handler = GUIMessageHandler(
            ai_core=self.ai_core,
            message_processor=self.message_processor,
            message_queue=self.message_queue,
            logger=self.logger
        )

        # UI components
        from BASE.interface.gui_ui_builder import UIBuilder
        self.ui_builder = UIBuilder(self)
        self.send_button = None
        self.processing_label = None
        self.system_log = None
        self.context_text = None  # Initialize for current_context
        self.reminders_text = None  # Initialize for important_reminders

        # Setup external tools
        self._setup_tts_tool()  # This will now initialize even if disabled
        # self._setup_integrations()

        # Apply theme and setup GUI
        # Note: Theme manager is now initialized in UIBuilder
        self.ui_builder.setup_gui()

        # Start queue processor
        self.start_queue_processor()

        self.logger.system("GUI initialized successfully")
        self.logger.system("INITIALIZATION SUMMARY")
        self._print_config_summary()

    def _verify_config_chain(self):
        """Verify all components share the same config instance"""
        print("CONFIG CHAIN VERIFICATION")
        
        base_id = id(self.config)
        all_match = True
        
        components = {
            "Main Config": self.config,
            "Logger Config": self.logger.config if hasattr(self.logger, 'config') else None,
            "AICore Config": self.ai_core.config if hasattr(self.ai_core, 'config') else None,
        }
        
        if hasattr(self.ai_core, 'control_manager') and self.ai_core.control_manager:
            components["ControlManager Config"] = self.ai_core.control_manager.config if hasattr(self.ai_core.control_manager, 'config') else None
        
        print(f"\nBase Config ID: {base_id}\n")
        print("Component Verification:")
        
        for name, component_config in components.items():
            if component_config is None:
                print(f"  {name}: Missing")
                all_match = False
            elif id(component_config) == base_id:
                print(f"  {name}: Correct ({id(component_config)})")
            else:
                print(f"  {name}: MISMATCH ({id(component_config)})")
                all_match = False
        
        if all_match:
            print("[SUCCESS] SUCCESS: All components share same config instance")
        else:
            print("[ERROR] ERROR: Config instance mismatch detected!")
            raise RuntimeError("Config chain verification failed!")

    def _print_config_summary(self):
        """Print configuration summary"""
        try:
            settings = {
                "Model": self.config.thought_model,
                "Temp (Action/Cognitive/Response)": f"{getattr(self.config, 'ollama_temperature_action', 0.2)}/{getattr(self.config, 'ollama_temperature_cognitive', 0.6)}/{getattr(self.config, 'ollama_temperature_response', 0.9)}",
                "Max Tokens": self.config.ollama_max_tokens,
            }
            
            self.logger.system("=== Configuration ===")
            for key, value in settings.items():
                self.logger.system(f"  {key}: {value}")
                
        except Exception as e:
            self.logger.warning(f"Could not print config summary: {e}")

    def _setup_tts_tool(self):
        """
        Initialize TTS tool via internal tool manager
        REFACTORED: Uses modular internal tool system instead of legacy voice directory
        """
        try:
            # Check if internal tool manager is available
            if not hasattr(self.ai_core, 'internal_tool_manager'):
                self.logger.warning("[TTS] Internal tool manager not available - TTS disabled")
                self.ai_core.tts_tool = None
                return
            
            if not self.ai_core.internal_tool_manager:
                self.logger.warning("[TTS] Internal tool manager is None - TTS disabled")
                self.ai_core.tts_tool = None
                return
            
            # Get active TTS tool from internal tool manager
            # The tool is already initialized by the internal tool manager
            tts_tool = self.ai_core.internal_tool_manager.get_active_tts_tool()
            
            if tts_tool:
                # Tool is initialized and available
                info = tts_tool.get_voice_info()
                backend_name = info.get('name', 'Unknown')
                backend_type = info.get('type', 'Unknown')
                
                # The ai_core.tts_tool reference is already set by internal tool manager
                # but we also set it here for clarity
                self.ai_core.tts_tool = tts_tool
                self.tts_tool = tts_tool
                
                # Log status based on AVATAR_SPEECH control
                if self.controls.AVATAR_SPEECH:
                    self.logger.success(f"[TTS] Initialized and enabled: {backend_name} ({backend_type})")
                else:
                    self.logger.system(f"[TTS] Initialized but disabled: {backend_name} ({backend_type})")
                
                # Log additional info
                if 'volume_percent' in info:
                    self.logger.system(f"[TTS] Volume: {info['volume_percent']}")
                    
            else:
                # No TTS tool active
                self.logger.system("[TTS] No TTS tool active - speech disabled")
                self.ai_core.tts_tool = None
                self.tts_tool = None
                
        except Exception as e:
            self.logger.error(f"[TTS] Setup failed: {e}")
            import traceback
            traceback.print_exc()
            self.ai_core.tts_tool = None
            self.tts_tool = None

    def _get_actual_line_count(self):
        """
        Get actual line count from Text widget
        CRITICAL FIX: Counts actual lines in widget, not log entries
        """
        try:
            # Get line count using Tkinter's index method
            # "end-1c" means the position before the final newline
            last_line = self.system_log.index("end-1c").split('.')[0]
            return int(last_line)
        except Exception as e:
            self.logger.warning(f"Error getting line count: {e}")
            return 0

    def _trim_system_log(self):
        """
        PERFORMANCE OPTIMIZATION: Trim system log to MAX_LOG_LINES
        FIXED: Now counts actual Text widget lines, not log entries
        """
        try:
            # Get actual line count from widget
            actual_lines = self._get_actual_line_count()
            
            if actual_lines <= self.MAX_LOG_LINES:
                return
            
            # Calculate how many lines to remove
            lines_to_remove = actual_lines - self.MAX_LOG_LINES
            
            self.system_log.config(state=tk.NORMAL)
            
            # Delete from start (line 1.0 to line N.0)
            self.system_log.delete("1.0", f"{lines_to_remove + 1}.0")
            
            self.system_log.config(state=tk.DISABLED)
            
        except Exception as e:
            self.logger.warning(f"Error trimming system log: {e}")

    def _gui_log_callback(self, message: str, msg_type: str, color: str):
        """Callback for logger to send messages to GUI with color information and performance optimization"""
        if not hasattr(self, 'system_log') or not self.system_log:
            if not hasattr(self, '_pending_log_messages'):
                self._pending_log_messages = []
            self._pending_log_messages.append((message, msg_type, color))
            return
        
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}\n"
        
        def update_log():
            try:
                self.system_log.config(state=tk.NORMAL)
                
                # Insert with color tag
                tag_name = f"color_{color.replace('#', '')}"
                self.system_log.tag_config(tag_name, foreground=color)
                self.system_log.insert(tk.END, formatted_message, tag_name)
                
                self.system_log.see(tk.END)
                self.system_log.config(state=tk.DISABLED)
                
                # Trim log if needed (performance optimization)
                self._trim_system_log()
                
            except Exception as e:
                print(f"Error updating system log: {e}")
        
        if threading.current_thread() != threading.main_thread():
            self.root.after(0, update_log)
        else:
            update_log()

    def flush_pending_log_messages(self):
        """Flush any messages that were logged before GUI was ready"""
        if hasattr(self, '_pending_log_messages'):
            for message, msg_type, color in self._pending_log_messages:
                self._gui_log_callback(message, msg_type, color)
            del self._pending_log_messages

    def start_queue_processor(self):
        """Start the message queue processor"""
        self.process_queues()

    def handle_autonomous_response(self, response: str):
        """
        Handle autonomous responses from cognitive loop
        FIXED: Use string type for queue compatibility and ensure TTS plays
        """
        if not response or not response.strip():
            return
        
        try:
            # Queue for GUI display - use string "agent" for compatibility
            self.message_queue.put(("agent", self.agentname, response))
            
            self.logger.system(f"[Autonomous] Queued for display: {response[:60]}...")
            
            # Handle TTS if enabled
            import personality.controls as controls
            if controls.AVATAR_SPEECH and len(response) < 1000:
                self.message_processor._play_tts(response)
                self.logger.speech(f"[Autonomous] Speaking: {response[:60]}...")
            else:
                self.logger.system(f"[Autonomous] No TTS (disabled or too long)")
            
        except Exception as e:
            self.logger.error(f"Error handling autonomous response: {e}")
            import traceback
            traceback.print_exc()

    def process_queues(self):
        """Process message and input queues - FIXED to handle MessageType enums"""
        try:
            current_time = time.time()
            auto_prompt_interval = getattr(controls, 'AUTO_RESPOND_INTERVAL', 60)
            time_since_last_interaction = current_time - self.last_interaction
            time_since_last_auto_prompt = current_time - self.last_auto_prompt

            should_auto_prompt = (
                controls.AUTO_RESPOND and
                time_since_last_interaction >= auto_prompt_interval and
                time_since_last_auto_prompt >= auto_prompt_interval and
                not self.processing and
                self.input_queue.empty()
            )

            if should_auto_prompt:
                self.logger.system(f"Triggering auto-prompt ({auto_prompt_interval}s of inactivity)")
                self.input_queue.put("__AUTO_PROMPT__")
                self.last_auto_prompt = current_time

            # Process message queue
            messages_processed = 0
            while not self.message_queue.empty():
                try:
                    msg_type, sender, message = self.message_queue.get_nowait()
                    messages_processed += 1

                    # Handle special control messages
                    if msg_type == "processing_complete":
                        self.processing = False
                        if self.send_button:
                            self.send_button.config(state=tk.NORMAL)
                        if self.processing_label:
                            self.processing_label.config(text="")
                        self.current_message = None
                        continue
                    
                    # Import MessageType for type checking
                    from BASE.core.logger import MessageType
                    
                    # Handle voice input (legacy string type)
                    if msg_type == "voice_input":
                        ChatView.add_chat_message(self, sender, message, MessageType.USER)
                        continue
                    
                    # CRITICAL FIX: Check if msg_type is already a MessageType enum
                    
                    if isinstance(msg_type, MessageType):
                        # Already an enum - use directly
                        if msg_type == MessageType.AGENT:
                            self.logger.system(f"[Display] Agent enum response: {message[:60]}...")
                        display_type = msg_type
                    else:
                        # Legacy string type - convert to enum
                        type_map = {
                            "user": MessageType.USER,
                            "agent": MessageType.AGENT,
                            "bot": MessageType.AGENT,
                            "system": MessageType.SYSTEM,
                            "error": MessageType.ERROR,
                            "warning": MessageType.WARNING,
                            "success": MessageType.SUCCESS,
                            "tool": MessageType.TOOL,
                            "memory": MessageType.MEMORY,
                            "discord": MessageType.DISCORD,
                            "youtube": MessageType.YOUTUBE,
                            "twitch": MessageType.TWITCH,
                        }
                        display_type = type_map.get(msg_type, MessageType.SYSTEM)
                        
                        # if msg_type == "agent":
                        #     self.logger.system(f"[Display] Agent string response: {message[:60]}...")
                    
                    # Display message with correct type
                    ChatView.add_chat_message(self, sender, message, display_type)

                except queue.Empty:
                    break
                except Exception as e:
                    self.logger.error(f"Error processing message from queue: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Log queue processing if messages were processed
            if messages_processed > 0:
                self.logger.system(f"[Queue] Processed {messages_processed} message(s)")

            # Input queue processing (unchanged)
            if not self.processing and not self.input_queue.empty():
                combined = []
                while not self.input_queue.empty():
                    combined.append(self.input_queue.get())
                combined_message = " ".join(combined).strip()

                is_auto_prompt = combined_message == "__AUTO_PROMPT__"

                if is_auto_prompt:
                    self.logger.system("Auto-prompt detected - checking for proactive response")
                    process_message = ""
                else:
                    if not combined_message:
                        self.logger.warning("Skipping empty user input")
                        return
                    process_message = combined_message
                    self.last_interaction = current_time

                self.current_message = process_message
                self.processing = True
                if self.send_button:
                    self.send_button.config(state=tk.DISABLED)
                if self.processing_label:
                    if is_auto_prompt:
                        self.processing_label.config(text="Checking...")
                    else:
                        self.processing_label.config(text="Processing...")

                threading.Thread(
                    target=self._process_message_with_handler,
                    args=(process_message, is_auto_prompt),
                    daemon=True
                ).start()

        except Exception as e:
            self.logger.error(f"Error in process_queues: {e}")
            import traceback
            traceback.print_exc()

        self.root.after(100, self.process_queues)

    def _process_message_with_handler(self, message: str, is_auto_prompt: bool):
        """Process message through chat_handler"""
        try:
            self.chat_handler.handle_user_message(message, is_auto_prompt=is_auto_prompt)
        except Exception as e:
            self.logger.error(f"Error in message handler: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if is_auto_prompt:
                self.logger.system("Auto-prompt check complete")

    def setup_chat_with_history(self):
        """Setup chat interface with loaded conversation history"""
        try:
            self.ai_core.start_integrations()
        except Exception as e:
            self.logger.error(f"Error starting integrations: {e}")

        try:
            self.chat_handler.load_conversation_history(messages_to_load=400)
        except Exception as e:
            self.logger.error(f"Error loading conversation history: {e}")

        # CRITICAL FIX: Register autonomous callback through the proper method
        if hasattr(self.ai_core, 'processing_delegator'):
            if hasattr(self.ai_core.processing_delegator, 'thought_processor'):
                thought_processor = self.ai_core.processing_delegator.thought_processor
                
                # Use new method to register callback
                thought_processor.set_autonomous_response_callback(self.handle_autonomous_response)
                self.logger.system("[Init] Autonomous response callback registered via thought_processor")
            else:
                self.logger.warning("[Init] No thought_processor found - autonomous responses disabled")
        else:
            self.logger.warning("[Init] No processing_delegator found - autonomous responses disabled")

        try:
            memory_manager = self.ai_core.get_memory_manager()
            stats = memory_manager.get_stats()

            summary_msg = f"Memory Status - Short: {stats['short_memory_entries']}, "
            summary_msg += f"Medium: {stats['medium_memory_entries']}, "
            summary_msg += f"Long: {stats['long_memory_summaries']}, "
            summary_msg += f"Base: {stats['base_knowledge_chunks']}"

            self.logger.memory(summary_msg)

            if stats['long_memory_summaries'] > 0:
                self.logger.memory(f"You have {stats['long_memory_summaries']} past day summaries available for context")

        except Exception as e:
            self.logger.error(f"Error checking memory stats: {e}")

    def on_closing(self):
        try:
            self.voice_manager.stop_voice_input()

            if hasattr(self, 'tts_tool') and self.tts_tool:
                self.tts_tool.stop()
            
            # Disconnect from Voice Hub if connected (NEW)
            if hasattr(self.voice_manager, 'hub_client') and \
            self.voice_manager.hub_client and \
            self.voice_manager.hub_client.is_connected():
                self.logger.system("[Shutdown] Disconnecting from Voice Hub...")
                try:
                    self.voice_manager.hub_client.disconnect()
                except Exception as e:
                    self.logger.warning(f"[Shutdown] Hub disconnect error: {e}")

            if messagebox.askokcancel("Quit", "Do you want to quit?"):
                self.ai_core.shutdown()
                self.root.destroy()

        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
            self.root.destroy()


def main():
    try:
        root = tk.Tk()
        app = OllamaGUI(root)
        app.setup_chat_with_history()
        root.protocol("WM_DELETE_WINDOW", app.on_closing)
        root.mainloop()
    except Exception as e:
        print(f"Error starting GUI: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()