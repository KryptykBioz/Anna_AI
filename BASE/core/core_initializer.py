# Filename: BASE/core/core_initializer.py
"""
Core Initializer - System Initialization and Integration Management
FIXED: Proper initialization order for PromptBuilder creation
"""
from typing import Optional
from pathlib import Path
import asyncio
import requests


class CoreInitializer:
    """
    Handles initialization of all AI Core subsystems
    Separates initialization logic from runtime operations
    """
    __slots__ = (
        'ai_core', 'config', 'controls', 'project_root', 'logger', 'main_loop',
        'memory_manager', 'memory_search', 'session_file_manager',
        'processing_delegator', 'control_manager', 'tool_manager',
        'action_state_manager', 'instruction_persistence_manager'
    )
    
    def __init__(self, ai_core, config, controls, project_root, logger, main_loop):
        """Initialize CoreInitializer"""
        self.ai_core = ai_core
        self.config = config
        self.controls = controls
        self.project_root = project_root
        self.logger = logger
        self.main_loop = main_loop
        
        # Initialized components
        self.memory_manager = None
        self.memory_search = None
        self.session_file_manager = None
        self.processing_delegator = None
        self.control_manager = None
        self.tool_manager = None
        self.action_state_manager = None
        self.instruction_persistence_manager = None
    
    # ========================================================================
    # MAIN INITIALIZATION
    # ========================================================================
    
    def initialize_all_systems(self):
        """Initialize all core systems in correct order"""
        self._init_memory_system()
        self._init_tool_system()
        self._init_processing_system()  # CRITICAL: This must fully complete first
        self._inject_tool_manager()      # THEN inject tool manager
        self._init_control_system()
        self._start_continuous_thinking()
        self._preload_models()
        self._log_initialization_summary()
    
    # ========================================================================
    # SUBSYSTEM INITIALIZATION
    # ========================================================================
    
    def _init_memory_system(self):
        """Initialize four-tier memory management"""
        try:
            from BASE.recall.memory_manager import MemoryManager
            from BASE.recall.memory_search import MemorySearch
            from BASE.recall.session_file_manager import SessionFileManager

            self.memory_manager = MemoryManager(
                config=self.config,
                controls_module=self.controls,
                logger=self.logger,
                project_root=self.project_root
            )

            self.memory_search = MemorySearch(self.memory_manager, config=self.config)

            self.session_file_manager = SessionFileManager(
                self.logger, self.memory_manager, self.project_root
            )

            self.logger.system("Memory system initialized")
        except Exception as e:
            self.logger.error(f"Memory system initialization failed: {e}")
            raise
    
    def _init_tool_system(self):
        """Initialize simplified tool system with persistence"""
        try:
            from BASE.handlers.tool_manager import ToolManager
            from BASE.core.action_state_manager import ActionStateManager
            
            # Create action state manager
            self.action_state_manager = ActionStateManager(self.logger)
            
            self.logger.system("[Init] [SUCCESS] Action state manager created")
            
            # Create tool manager
            self.tool_manager = ToolManager(
                config=self.config,
                controls_module=self.controls,
                action_state_manager=self.action_state_manager,
                project_root=self.project_root,
                logger=self.logger
            )
            
            # CRITICAL FIX: Set event loop BEFORE starting tools
            if self.main_loop:
                self.tool_manager.set_event_loop(self.main_loop)
                self.logger.system("[Init] Event loop set for tool manager")
            
            if self.main_loop:
                future = asyncio.run_coroutine_threadsafe(
                    self.tool_manager.start_enabled_tools(),
                    self.main_loop
                )
                # Wait for tools to start (30 second timeout)
                try:
                    started_count = future.result(timeout=30.0)
                    self.logger.system(
                        f"[Init] Auto-started {started_count} tool(s) from control variables"
                    )
                except Exception as e:
                    self.logger.error(f"[Init] Error auto-starting tools: {e}")
            
            # Get enabled tools count
            enabled_tools = self.tool_manager.get_enabled_tool_names()
            self.logger.system(
                f"Tool system initialized: {len(enabled_tools)} tools enabled"
            )
            
            if enabled_tools:
                self.logger.system(f"Enabled tools: {', '.join(enabled_tools)}")
        
        except Exception as e:
            self.logger.error(f"Tool system initialization failed: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def _init_processing_system(self):
        """
        Initialize thought processor and response generator
        FIXED: Don't verify prompt_builder until after tool injection
        """
        try:
            from BASE.core.processing_delegator import ProcessingDelegator
            
            # Create ProcessingDelegator with all dependencies
            self.processing_delegator = ProcessingDelegator(
                config=self.config,
                controls_module=self.controls,
                project_root=self.project_root,
                memory_manager=self.memory_manager,
                gui_logger=self.ai_core.gui_logger,
                session_file_manager=self.session_file_manager
            )
            
            # CRITICAL: Verify ProcessingDelegator has thought_processor
            if not hasattr(self.processing_delegator, 'thought_processor'):
                raise RuntimeError("ProcessingDelegator missing thought_processor")
            
            thought_processor = self.processing_delegator.thought_processor
            
            # Pass event loop to thought processor
            thought_processor.event_loop = self.main_loop
            
            self.logger.system("[Init] Processing system base initialization complete")
            self.logger.system("[Init] ThoughtProcessor created")
            
        except Exception as e:
            self.logger.error(f"Processing system initialization failed: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def _inject_tool_manager(self):
        """
        Inject tool manager into processing system
        FIXED: Set thought buffer BEFORE starting tools
        """
        try:
            if not hasattr(self, 'tool_manager') or not self.tool_manager:
                self.logger.warning("Tool manager not initialized - tools will not work!")
                return
            
            self.logger.system("INJECTING TOOL MANAGER INTO PROCESSING SYSTEM")
            
            # Query tool manager state
            enabled = self.tool_manager.get_enabled_tool_names()
            all_tools = list(self.tool_manager._tool_metadata.keys())
            
            self.logger.system(f"Tool Manager State:")
            self.logger.system(f"  - Total tools discovered: {len(all_tools)}")
            self.logger.system(f"  - Enabled tools: {len(enabled)}")
            if enabled:
                self.logger.system(f"  - Tool names: {enabled}")
            else:
                self.logger.system(f"  - No tools currently enabled")
                
            disabled = [name for name in all_tools if name not in enabled]
            if disabled:
                self.logger.system(f"  - Disabled tools: {disabled}")
            
            # Verify injection method exists
            if not hasattr(self.processing_delegator, 'set_tool_manager'):
                self.logger.error("")
                self.logger.error("[Error] CRITICAL ERROR")
                self.logger.error("ProcessingDelegator missing set_tool_manager() method!")
                raise RuntimeError("ProcessingDelegator missing required method")
            
            # Inject into processing delegator
            self.processing_delegator.set_tool_manager(self.tool_manager)
            
            # ================================================================
            # VERIFICATION: Check injection chain - NEW MODULAR ARCHITECTURE
            # ================================================================
            thought_processor = self.processing_delegator.thought_processor
            
            # NEW ARCHITECTURE: No single PromptBuilder
            # Instead: ResponsiveConstructor, ReactiveConstructor, etc.
            verification_results = {
                'tp_exists': thought_processor is not None,
                'tp_has_manager': hasattr(thought_processor, 'tool_manager'),
                'tp_manager_set': getattr(thought_processor, 'tool_manager', None) is not None,
                'uses_modular_constructors': True,  # NEW FLAG
                'responsive_exists': hasattr(self.processing_delegator, 'responsive_constructor')
            }
            
            # Log verification results
            self.logger.system("")
            self.logger.system("Injection Chain Verification:")
            self.logger.system(f"  1. ThoughtProcessor exists: {verification_results['tp_exists']}")
            self.logger.system(f"  2. ThoughtProcessor.tool_manager exists: {verification_results['tp_has_manager']}")
            self.logger.system(f"  3. ThoughtProcessor.tool_manager is set: {verification_results['tp_manager_set']}")
            self.logger.system(f"  4. Uses modular constructors: {verification_results['uses_modular_constructors']}")
            self.logger.system(f"  5. ResponsiveConstructor exists: {verification_results['responsive_exists']}")
            
            # SUCCESS: Only need ThoughtProcessor with tool_manager
            # Modular constructors don't need tool_manager reference
            all_checks_passed = all([
                verification_results['tp_exists'],
                verification_results['tp_has_manager'],
                verification_results['tp_manager_set']
            ])
            
            if all_checks_passed:
                self.logger.system("")
                self.logger.system("[Confirmed] TOOL SYSTEM FULLY CONNECTED")
                self.logger.system("Using modular prompt constructors (Responsive, Reactive, etc.)")
                self.logger.system("Tool instructions will appear in agent prompts")
                self.logger.system("")
            
            else:
                self.logger.error("")
                self.logger.error("[Error] TOOL SYSTEM NOT FULLY CONNECTED")
                self.logger.error("")
                
                # Specific diagnostics
                if not verification_results['tp_exists']:
                    self.logger.error("  -> ThoughtProcessor not created")
                elif not verification_results['tp_has_manager']:
                    self.logger.error("  -> ThoughtProcessor never received tool_manager")
                elif not verification_results['tp_manager_set']:
                    self.logger.error("  -> ThoughtProcessor.tool_manager is None")
                
                self.logger.error("")
                self.logger.error("Tools will NOT work until injection chain is fixed!")
            
            # ====================================================================
            # Inject event loop and thought buffer into tool manager
            # ====================================================================
            # Set event loop for async operations
            self.tool_manager.set_event_loop(self.main_loop)
            
            # Set thought buffer for tool context injection
            thought_buffer = self.processing_delegator.thought_processor.thought_buffer
            self.tool_manager.set_thought_buffer(thought_buffer)
            
            self.logger.system(
                "[Init] [SUCCESS] Thought buffer set for tool manager"
            )
            
            # NOW start enabled tools (they'll have access to thought buffer)
            enabled_tools = self.tool_manager.get_enabled_tool_names()
            for tool_name in enabled_tools:
                asyncio.run_coroutine_threadsafe(
                    self.tool_manager._start_tool(tool_name),
                    self.main_loop
                )
            
            if enabled_tools:
                self.logger.system(
                    f"[Init] Starting {len(enabled_tools)} enabled tool(s)..."
                )

            # NEW: Verify injection worked
            if hasattr(self.processing_delegator.thought_processor, 'verify_tool_injection'):
                if self.processing_delegator.thought_processor.verify_tool_injection():
                    self.logger.success(
                        "[Init] Tool injection verification PASSED"
                    )
                else:
                    self.logger.error(
                        "[Init] Tool injection verification FAILED"
                    )
            
        except Exception as e:
            self.logger.error(f"Tool manager injection failed: {e}")
            import traceback
            traceback.print_exc()
            # Don't raise - allow system to continue without tools
    
    def _init_control_system(self):
        """Initialize control manager for dynamic settings"""
        try:
            from BASE.core.control_manager import ControlManager
            
            # Create control manager WITH config reference
            self.control_manager = ControlManager(
                controls_module=self.controls,
                logger=self.logger,
                config=self.config
            )
            
            # Inject tool manager for control notifications
            if hasattr(self, 'tool_manager') and self.tool_manager:
                self.control_manager.set_tool_manager(self.tool_manager)
                self.logger.system(
                    "[Init] [SUCCESS] Tool manager connected to control system"
                )
            else:
                self.logger.warning(
                    "[Init] [WARNING] No tool manager - control updates won't affect tools"
                )
            
            # Inject AI core reference
            self.control_manager.set_ai_core(self.ai_core)
            
            self.logger.system("Control system initialized")
        except Exception as e:
            self.logger.error(f"Control system initialization failed: {e}")
            raise
    
    def _start_continuous_thinking(self):
        """Start autonomous continuous thinking loop"""
        if not getattr(self.controls, 'ENABLE_CONTINUOUS_THINKING', True):
            return
        
        try:
            thought_processor = self.processing_delegator.thought_processor
            thought_processor.event_loop = self.main_loop
            thought_processor.set_ai_core_reference(self.ai_core)
            thought_processor.start_continuous_thinking()
            
            self.logger.system("Autonomous thinking ACTIVE")
        except Exception as e:
            self.logger.error(f"Failed to start continuous thinking: {e}")
            import traceback
            traceback.print_exc()
    
    def _preload_models(self):
        """Preload models into VRAM"""
        try:
            models_to_preload = list(set([
                self.config.thought_model,
                self.config.text_model
            ]))
            
            for model in models_to_preload:
                self.logger.system(f"Preloading model: {model}")
                
                payload = {
                    "model": model,
                    "prompt": "initialize",
                    "stream": False,
                    "keep_alive": "24h"
                }
                
                try:
                    response = requests.post(
                        f"{self.config.ollama_endpoint}/api/generate",
                        json=payload,
                        timeout=60
                    )
                    response.raise_for_status()
                    self.logger.system(f"Model loaded: {model}")
                except Exception as e:
                    self.logger.warning(f"Could not preload {model}: {e}")
            
            self.logger.system("Model preloading complete")
        except Exception as e:
            self.logger.warning(f"Model preload failed: {e}")
    
    def _log_initialization_summary(self):
        """Log summary of initialized systems"""
        # Memory stats
        stats = self.memory_manager.get_stats()
        self.logger.memory(
            f"Memory: Short={stats['short_memory_entries']}, "
            f"Medium={stats['medium_memory_entries']}, "
            f"Long={stats['long_memory_summaries']}, "
            f"Base={stats['base_knowledge_chunks']}"
        )
        
        # Tool system stats
        if hasattr(self, 'tool_manager') and self.tool_manager:
            enabled_tools = self.tool_manager.get_enabled_tool_names()
            if enabled_tools:
                self.logger.system(
                    f"Tools: {len(enabled_tools)} enabled ({', '.join(enabled_tools)})"
                )