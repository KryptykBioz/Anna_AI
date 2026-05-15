# Filename: BASE/handlers/base_tool.py
"""
Base Tool - Simplified Architecture
Single class per tool with start/end lifecycle

Each tool inherits from BaseTool and implements:
- name property (tool identifier)
- initialize() - Setup/connect
- cleanup() - Teardown/disconnect
- is_available() - Availability check
- execute() - Command execution

Optional:
- has_context_loop() - Return True if tool needs background updates
- context_loop() - Background task for injecting context to thought buffer
"""
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
import asyncio


class BaseTool(ABC):
    """Base class for all tools in the simplified architecture"""
    
    __slots__ = (
        '_config', '_controls', '_logger', '_running', '_context_task', '_thought_buffer'
    )
    
    def __init__(self, config, controls, logger=None):
        self._config = config
        self._controls = controls
        self._logger = logger
        self._running = False
        self._context_task = None
        self._thought_buffer = None
        
    # ==================== REQUIRED METHODS ====================
    
    @property
    @abstractmethod
    def name(self) -> str:
        """
        Return tool name (must match control variable)
        
        Example:
            @property
            def name(self) -> str:
                return "wiki_search"
        
        Returns:
            Tool name string (e.g., 'wiki_search', 'calculator')
        """
        pass
    
    @abstractmethod
    async def initialize(self) -> bool:
        """
        Initialize the tool (connect, setup, etc.)
        
        Called by start() before the tool becomes active.
        Use this to:
        - Connect to APIs or services
        - Load configurations
        - Setup internal state
        - Verify availability
        
        Example:
            async def initialize(self) -> bool:
                self.api_key = self._config.get('api_key')
                self.connected = await self._connect_to_service()
                if self._logger:
                    self._logger.success(f"[{self.name}] Connected!")
                return self.connected
        
        Returns:
            True if initialization successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def cleanup(self):
        """
        Cleanup tool resources (disconnect, close, etc.)
        
        Called by end() when the tool is being stopped.
        Use this to:
        - Disconnect from services
        - Close connections
        - Save state
        - Free resources
        
        Example:
            async def cleanup(self):
                await self._disconnect_from_service()
                self._cache.clear()
                if self._logger:
                    self._logger.system(f"[{self.name}] Cleaned up")
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if tool is currently available for use
        
        Example:
            def is_available(self) -> bool:
                return self._connected and self._api_key is not None
        
        Returns:
            True if tool can execute commands, False otherwise
        """
        pass
    
    @abstractmethod
    async def execute(self, command: str, args: List[Any]) -> Dict[str, Any]:
        """
        Execute a tool command
        
        Args:
            command: Command name (e.g., 'search', 'add', 'fetch')
            args: Command arguments as a list
            
        Example:
            async def execute(self, command: str, args: List[Any]) -> Dict[str, Any]:
                if command == 'search':
                    query = args[0]
                    results = await self._search(query)
                    return self._success_result(results)
                else:
                    return self._error_result(f'Unknown command: {command}')
        
        Returns:
            Standardized result dict with keys:
            - success: bool (True if command succeeded)
            - content: str (result message or data)
            - source: str (tool name)
            - metadata: dict (additional info)
            - guidance: str (usage guidance or error help)
        """
        pass
    
    # ==================== OPTIONAL METHODS ====================
    
    def has_context_loop(self) -> bool:
        """
        Does this tool need a background context loop?
        
        Override to return True if tool needs to inject periodic updates
        into the thought buffer (e.g., monitoring, notifications, status).
        
        Example:
            def has_context_loop(self) -> bool:
                return True  # This tool needs background updates
        
        Returns:
            False by default (no background loop needed)
        """
        return False
    
    async def context_loop(self, thought_buffer):
        """
        Background loop for injecting context updates.
        
        Only called if has_context_loop() returns True.
        This runs continuously while the tool is active.
        
        Example:
            async def context_loop(self, thought_buffer):
                while self._running:
                    # Get current state
                    status = await self._get_status()
                    
                    # Inject into thought buffer
                    thought_buffer.add_processed_thought(
                        content=f"[{self.name}] Status: {status}",
                        source='tool_context',
                    )
                    
                    # Wait before next update
                    await asyncio.sleep(5.0)
        
        Args:
            thought_buffer: ThoughtBuffer instance for injecting thoughts
        """
        pass
    
    # ==================== LIFECYCLE MANAGEMENT ====================
    
    async def start(self, thought_buffer=None, event_loop=None):
        if self._running:
            if self._logger:
                self._logger.warning(f"[{self.name}] Already running")
            return

        success = await self.initialize()

        if not success:
            if self._logger:
                self._logger.error(f"[{self.name}] Initialization failed")
            return

        self._running = True
        self._thought_buffer = thought_buffer

        if self.has_context_loop() and thought_buffer and event_loop:
            self._context_task = event_loop.create_task(
                self._safe_context_loop(thought_buffer)
            )
            if self._logger:
                self._logger.system(f"[{self.name}] Context loop started")

        if self._logger:
            self._logger.success(f"[{self.name}] Tool started successfully")
    
    async def end(self):
        """
        Stop the tool (called when control variable disabled)
        
        This method:
        1. Checks if running
        2. Stops context loop (if active)
        3. Calls cleanup()
        4. Logs shutdown
        """
        if not self._running:
            return
        
        self._running = False
        
        # Stop context loop
        if self._context_task:
            self._context_task.cancel()
            try:
                await self._context_task
            except asyncio.CancelledError:
                pass
            self._context_task = None
            if self._logger:
                self._logger.system(f"[{self.name}] Context loop stopped")
        
        # Cleanup tool
        await self.cleanup()
        
        if self._logger:
            self._logger.system(f"[{self.name}] Tool stopped")
    
    async def _safe_context_loop(self, thought_buffer):
        """
        Wrapper for context loop with error handling
        
        Args:
            thought_buffer: ThoughtBuffer instance
        """
        try:
            await self.context_loop(thought_buffer)
        except asyncio.CancelledError:
            # Normal cancellation when tool stops
            pass
        except Exception as e:
            if self._logger:
                self._logger.error(f"[{self.name}] Context loop error: {e}")
    
    # ==================== HELPER METHODS ====================
    
    def _success_result(
        self, 
        content: str, 
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Create standardized success result
        
        Use this helper to return successful execution results.
        
        Example:
            return self._success_result(
                "Search completed!",
                metadata={'results': 5, 'query': 'Python'}
            )
        
        Args:
            content: Success message or data
            metadata: Optional additional information
            
        Returns:
            Standardized success dict
        """
        return {
            'success': True,
            'content': content,
            'source': self.name,
            'metadata': metadata or {},
            'guidance': f'{self.name} executed successfully'
        }
    
    def _error_result(
        self, 
        content: str, 
        metadata: Optional[Dict] = None,
        guidance: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create standardized error result
        
        Use this helper to return error results with guidance.
        
        Example:
            return self._error_result(
                "No results found",
                metadata={'query': 'invalid'},
                guidance='Try different search terms'
            )
        
        Args:
            content: Error message
            metadata: Optional additional information
            guidance: Optional usage guidance for user
            
        Returns:
            Standardized error dict
        """
        return {
            'success': False,
            'content': content,
            'source': self.name,
            'metadata': metadata or {},
            'guidance': guidance or f'{self.name} execution failed'
        }
    def _get_result_limits(self) -> tuple:
        """
        Compute (n_results, chars_per_result) from config.

        MAX_TOOL_RESULT_CHARS / MAX_TOOL_RESULTS = chars allocated per entry.
        Both values floor at safe minimums.

        Returns:
            (n_results: int, chars_per_result: int)
        """
        max_chars   = max(50, getattr(self._config, 'MAX_TOOL_RESULT_CHARS', 1000))
        n_results   = max(1,  getattr(self._config, 'MAX_TOOL_RESULTS',       3))
        chars_each  = max(50, max_chars // n_results)
        return n_results, chars_each