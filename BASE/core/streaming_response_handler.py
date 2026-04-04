# ============================================================================
# FILE: BASE/core/streaming_response_handler.py
# Streaming Response Handler with Complete Memory Integration
# ============================================================================
"""
Streaming Response Handler
===========================
Handles streaming responses from Ollama with TTS streaming and complete memory storage.

Key Features:
- Buffer-then-store: Collects complete response before memory storage
- Stores ALL responses to memory (complete AND interrupted)
- Integrates with existing 4-tier memory system
- Thread-safe streaming state management
- Performance-optimized for minimal latency
"""

import asyncio
import threading
from typing import Optional, List, Dict, AsyncIterator
from datetime import datetime
from dataclasses import dataclass
import re


@dataclass
class StreamingResponse:
    """Container for streaming response state"""
    __slots__ = ('buffer', 'start_time', 'interrupted', 'word_count', 'chunk_count')
    
    def __init__(self, buffer: List[str] = None, start_time: datetime = None,
                 interrupted: bool = False, word_count: int = 0, chunk_count: int = 0):
        self.buffer = buffer if buffer is not None else []
        self.start_time = start_time if start_time is not None else datetime.now()
        self.interrupted = interrupted
        self.word_count = word_count
        self.chunk_count = chunk_count
    
    def get_complete_text(self) -> str:
        """Get complete buffered response text"""
        return "".join(self.buffer).strip()
    
    def get_metadata(self) -> Dict:
        """Get response metadata for memory storage"""
        duration = (datetime.now() - self.start_time).total_seconds()
        complete_text = self.get_complete_text()
        
        return {
            'timestamp': datetime.now().isoformat(),
            'complete': not self.interrupted,
            'interrupted': self.interrupted,
            'duration_seconds': round(duration, 2),
            'word_count': len(complete_text.split()),
            'chunk_count': self.chunk_count,
            'char_count': len(complete_text)
        }
    
    def __repr__(self):
        return (f"StreamingResponse(buffer_len={len(self.buffer)}, "
                f"start_time={self.start_time}, interrupted={self.interrupted}, "
                f"word_count={self.word_count}, chunk_count={self.chunk_count})")

class StreamingResponseHandler:
    """
    Manages streaming responses with complete memory integration
    
    Responsibilities:
    - Stream response chunks to TTS as they arrive
    - Buffer complete response for memory storage
    - Store complete/interrupted responses to all memory tiers
    - Handle interruptions gracefully
    """
    
    __slots__ = (
        'memory_manager', 'memory_search', 'tts_tool', 'logger',
        '_active_response', '_response_lock', '_streaming_active'
    )
    
    def __init__(self, memory_manager, memory_search, tts_tool, logger):
        """
        Initialize streaming handler
        
        Args:
            memory_manager: MemoryManager instance for Tier 2/3 storage
            memory_search: MemorySearch instance for retrieval and Tier 4
            tts_tool: TTSTool instance for speech output
            logger: Logger instance
        """
        self.memory_manager = memory_manager
        self.memory_search = memory_search
        self.tts_tool = tts_tool
        self.logger = logger
        
        # Streaming state
        self._active_response: Optional[StreamingResponse] = None
        self._response_lock = threading.Lock()
        self._streaming_active = False
    
    # ========================================================================
    # MAIN STREAMING INTERFACE
    # ========================================================================
    
    async def stream_and_store(
        self,
        response_stream: AsyncIterator[str],
        thought_buffer,
        context_parts: List[str] = None,
        user_input: str = ""
    ) -> str:
        """
        Stream response to TTS and store to memory
        
        This is the main entry point for streaming responses.
        
        Args:
            response_stream: Async iterator yielding response chunks
            thought_buffer: ThoughtBuffer instance for Tier 1 storage
            context_parts: Additional context for memory storage
            user_input: Original user input that prompted this response
        
        Returns:
            Complete response text (even if interrupted)
        """
        context_parts = context_parts or []
        
        # Initialize streaming response
        streaming_response = StreamingResponse(
            buffer=[],
            start_time=datetime.now(),
            interrupted=False,
            word_count=0,
            chunk_count=0
        )
        
        with self._response_lock:
            self._active_response = streaming_response
            self._streaming_active = True
        
        try:
            # Stream chunks to TTS while buffering
            async for chunk in response_stream:
                if not chunk or not chunk.strip():
                    continue
                
                # Add to buffer
                streaming_response.buffer.append(chunk)
                streaming_response.chunk_count += 1
                
                # Stream to TTS immediately (non-blocking)
                result = await self._speak_chunk_async(chunk)
                
                # Check for interruption
                if result == "Interrupted":
                    streaming_response.interrupted = True
                    self.logger.speech("Response streaming interrupted by user")
                    break
            
        except Exception as e:
            self.logger.error(f"Streaming error: {e}")
            streaming_response.interrupted = True
            import traceback
            traceback.print_exc()
        
        finally:
            # Always store to memory (complete or partial)
            complete_response = streaming_response.get_complete_text()
            
            if complete_response:
                await self._store_to_all_memory_tiers(
                    streaming_response=streaming_response,
                    thought_buffer=thought_buffer,
                    context_parts=context_parts,
                    user_input=user_input
                )
            else:
                self.logger.warning("Empty response received - nothing to store")
            
            # Clear streaming state
            with self._response_lock:
                self._active_response = None
                self._streaming_active = False
            
            return complete_response
    
    async def _speak_chunk_async(self, chunk: str) -> str:
        """
        Speak chunk asynchronously (non-blocking)
        
        Args:
            chunk: Text chunk to speak
        
        Returns:
            "Speech completed", "Interrupted", or error message
        """
        # Run TTS in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            self.tts_tool.speak,
            chunk,
            True  # stream=True
        )
        return result
    
    # ========================================================================
    # MEMORY STORAGE (ALL TIERS)
    # ========================================================================
    
    async def _store_to_all_memory_tiers(
        self,
        streaming_response: StreamingResponse,
        thought_buffer,
        context_parts: List[str],
        user_input: str
    ):
        """
        Store response to ALL memory tiers (complete or interrupted)
        
        Storage Strategy:
        - Tier 1 (Short Memory): ALWAYS store via ThoughtBuffer
        - Tier 2 (Medium Memory): ALWAYS store via MemoryManager
        - Tier 3 (Long Memory): ALWAYS store (will be in daily summary)
        - Tier 4 (Base Knowledge): Only complete, high-quality responses
        
        Args:
            streaming_response: StreamingResponse with buffered text
            thought_buffer: ThoughtBuffer for Tier 1
            context_parts: Context for storage
            user_input: User input that prompted response
        """
        complete_text = streaming_response.get_complete_text()
        metadata = streaming_response.get_metadata()
        interrupted = streaming_response.interrupted
        
        # Prepare display text (with interruption marker if needed)
        display_text = complete_text
        if interrupted:
            display_text = f"{complete_text}... [interrupted]"
        
        self.logger.memory(
            f"\n{'='*70}\n"
            f"STORING RESPONSE TO MEMORY\n"
            f"{'='*70}\n"
            f"Status: {'INTERRUPTED' if interrupted else 'COMPLETE'}\n"
            f"Word count: {metadata['word_count']}\n"
            f"Duration: {metadata['duration_seconds']}s\n"
            f"Chunks: {metadata['chunk_count']}\n"
            f"Text: {complete_text[:100]}{'...' if len(complete_text) > 100 else ''}\n"
            f"{'='*70}"
        )
        
        # TIER 1: Short Memory (via ThoughtBuffer)
        self._store_tier1_short_memory(
            display_text=display_text,
            original_text=complete_text,
            thought_buffer=thought_buffer,
            metadata=metadata
        )
        
        # TIER 2: Medium Memory (via MemoryManager - today's context)
        self._store_tier2_medium_memory(
            response_text=complete_text,
            metadata=metadata
        )
        
        # TIER 3: Long Memory (via MemoryManager - automatic daily summary)
        # No explicit storage needed - daily summary will process all Tier 2 entries
        self.logger.memory("[Tier 3] Will be included in daily summary")
        
        # TIER 4: Base Knowledge (personality examples - complete only)
        if not interrupted:
            await self._store_tier4_base_knowledge(
                response_text=complete_text,
                user_input=user_input,
                context_parts=context_parts,
                metadata=metadata
            )
    
    def _store_tier1_short_memory(
        self,
        display_text: str,
        original_text: str,
        thought_buffer,
        metadata: Dict
    ):
        """
        Store to Tier 1: Short Memory (ThoughtBuffer)
        
        This is the most recent conversation context.
        ALWAYS store, even if interrupted - user heard it.
        """
        thought_buffer.add_processed_thought(
            thought=display_text,  # Include [interrupted] marker for display
            source='agent_response',
            original_ref=original_text  # Clean text for reference
        )
        
        status = "INTERRUPTED" if metadata['interrupted'] else "COMPLETE"
        self.logger.memory(
            f"[Tier 1] Stored to short memory [{status}] "
            f"({metadata['word_count']} words)"
        )
    
    def _store_tier2_medium_memory(
        self,
        response_text: str,
        metadata: Dict
    ):
        """
        Store to Tier 2: Medium Memory (Today's context via MemoryManager)
        
        CRITICAL: Store ALL responses (complete AND interrupted)
        The agent should remember everything it said, even partial responses.
        """
        if not self.memory_manager:
            self.logger.warning("[Tier 2] MemoryManager not available - skipping")
            return
        
        try:
            # Store with interruption metadata
            storage_metadata = metadata.copy()
            
            self.memory_manager.add_interaction(
                role='assistant',
                content=response_text,
                metadata=storage_metadata
            )
            
            status = "INTERRUPTED" if metadata['interrupted'] else "COMPLETE"
            self.logger.memory(
                f"[Tier 2] Stored to medium memory [{status}] "
                f"(today's context)"
            )
        
        except Exception as e:
            self.logger.error(f"[Tier 2] Storage failed: {e}")
    
    async def _store_tier4_base_knowledge(
        self,
        response_text: str,
        user_input: str,
        context_parts: List[str],
        metadata: Dict
    ):
        """
        Store to Tier 4: Base Knowledge (Personality examples)
        
        Only store COMPLETE, high-quality responses as personality examples.
        These are used for response generation retrieval.
        """
        if not self.memory_search:
            self.logger.warning("[Tier 4] MemorySearch not available - skipping")
            return
        
        # Check if response is worthy of personality storage
        if not self._is_personality_worthy(response_text, metadata):
            self.logger.memory(
                "[Tier 4] Response not personality-worthy (too short/generic)"
            )
            return
        
        try:
            # Create personality example entry
            example_entry = {
                'situation': user_input[:200] if user_input else "General conversation",
                'response': response_text,
                'context': " ".join(context_parts[:3]) if context_parts else "",
                'timestamp': metadata['timestamp'],
                'quality_score': self._calculate_quality_score(response_text, metadata),
                'word_count': metadata['word_count'],
                'type': 'conversation_example'
            }
            
            # Store to base knowledge (if method exists)
            if hasattr(self.memory_search, 'add_personality_example'):
                await self.memory_search.add_personality_example(example_entry)
                self.logger.memory(
                    f"[Tier 4] Stored as personality example "
                    f"(quality: {example_entry['quality_score']:.2f})"
                )
            else:
                self.logger.memory(
                    "[Tier 4] add_personality_example not implemented - skipping"
                )
        
        except Exception as e:
            self.logger.error(f"[Tier 4] Storage failed: {e}")
    
    # ========================================================================
    # QUALITY ASSESSMENT
    # ========================================================================
    
    def _is_personality_worthy(self, response_text: str, metadata: Dict) -> bool:
        """
        Determine if response should be stored as personality example
        
        Criteria:
        - Complete (not interrupted)
        - Appropriate length (5-100 words)
        - Contains personality markers (opinions, emotions, uncertainty)
        - Natural conversational quality
        
        Args:
            response_text: Response text to evaluate
            metadata: Response metadata
        
        Returns:
            True if worthy of personality storage
        """
        word_count = metadata['word_count']
        
        # Length check
        if word_count < 5 or word_count > 100:
            return False
        
        # Must be complete
        if metadata['interrupted']:
            return False
        
        response_lower = response_text.lower()
        
        # Personality markers (opinions, emotions, uncertainty)
        personality_markers = [
            'i think', 'i believe', 'i feel', 'i wonder',
            'seems like', 'looks like', 'in my opinion',
            'i noticed', 'i see', 'interesting', 'curious',
            'hmm', 'ah', 'oh', 'well', 'actually',
            'probably', 'maybe', 'perhaps', 'might'
        ]
        
        has_personality = any(marker in response_lower for marker in personality_markers)
        
        # Question check (questions often show personality)
        has_question = '?' in response_text
        
        # Avoid generic responses
        generic_patterns = [
            'okay', 'alright', 'sure', 'yes', 'no',
            'thanks', 'thank you', 'you\'re welcome'
        ]
        
        is_generic = response_text.strip().lower() in generic_patterns
        
        return (has_personality or has_question) and not is_generic
    
    def _calculate_quality_score(self, response_text: str, metadata: Dict) -> float:
        """
        Calculate quality score for personality example
        
        Factors:
        - Length (prefer 10-40 words)
        - Personality markers
        - Natural language indicators
        - Variety (questions, emotions, etc.)
        
        Returns:
            Quality score (0.0 to 1.0)
        """
        score = 0.0
        word_count = metadata['word_count']
        response_lower = response_text.lower()
        
        # Length score (optimal: 10-40 words)
        if 10 <= word_count <= 40:
            score += 0.4
        elif 5 <= word_count <= 50:
            score += 0.2
        
        # Personality markers (max 0.3)
        personality_markers = [
            'i think', 'i believe', 'i feel', 'i wonder',
            'seems', 'looks', 'noticed', 'curious'
        ]
        marker_count = sum(1 for m in personality_markers if m in response_lower)
        score += min(0.3, marker_count * 0.1)
        
        # Natural language indicators (max 0.2)
        if '?' in response_text:
            score += 0.1  # Questions are valuable
        if any(word in response_lower for word in ['hmm', 'ah', 'oh', 'well']):
            score += 0.05  # Natural speech patterns
        if any(word in response_lower for word in ['probably', 'maybe', 'perhaps']):
            score += 0.05  # Uncertainty shows reasoning
        
        # Variety bonus (max 0.1)
        unique_words = len(set(response_text.lower().split()))
        if unique_words > word_count * 0.7:  # High word variety
            score += 0.1
        
        return min(1.0, score)
    
    # ========================================================================
    # STATE QUERIES
    # ========================================================================
    
    def is_streaming(self) -> bool:
        """Check if currently streaming a response"""
        with self._response_lock:
            return self._streaming_active
    
    def get_current_response_text(self) -> Optional[str]:
        """Get currently buffered response text (for debugging/monitoring)"""
        with self._response_lock:
            if self._active_response:
                return self._active_response.get_complete_text()
        return None
    
    def get_streaming_status(self) -> Dict:
        """Get detailed streaming status"""
        with self._response_lock:
            if not self._active_response:
                return {'active': False}
            
            return {
                'active': True,
                'word_count': len(self._active_response.get_complete_text().split()),
                'chunk_count': self._active_response.chunk_count,
                'duration': (datetime.now() - self._active_response.start_time).total_seconds(),
                'interrupted': self._active_response.interrupted
            }


# ============================================================================
# OLLAMA STREAMING INTERFACE
# ============================================================================

class OllamaStreamingInterface:
    """
    Interface for streaming responses from Ollama
    Generates async iterator of text chunks
    """
    
    __slots__ = ('base_url',)
    
    def __init__(self, ollama_base_url: str = "http://localhost:11434"):
        """
        Initialize Ollama streaming interface
        
        Args:
            ollama_base_url: Base URL for Ollama API
        """
        self.base_url = ollama_base_url
    
    async def stream_chat_response(
        self,
        prompt: str,
        model: str,
        system_prompt: Optional[str] = None
    ) -> AsyncIterator[str]:
        """
        Stream chat response from Ollama
        
        Args:
            prompt: User prompt
            model: Model name (e.g., "llama3.2:3b")
            system_prompt: Optional system prompt
        
        Yields:
            Text chunks as they arrive from Ollama
        """
        import aiohttp
        
        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        # Request payload
        payload = {
            "model": model,
            "messages": messages,
            "stream": True
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/chat",
                    json=payload
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Ollama API error: {error_text}")
                    
                    # Stream response chunks
                    async for line in response.content:
                        if not line:
                            continue
                        
                        try:
                            # Parse JSON line
                            import json
                            data = json.loads(line.decode('utf-8'))
                            
                            # Extract message content
                            if 'message' in data and 'content' in data['message']:
                                chunk = data['message']['content']
                                if chunk:
                                    yield chunk
                            
                            # Check for completion
                            if data.get('done', False):
                                break
                        
                        except json.JSONDecodeError:
                            continue
        
        except Exception as e:
            raise Exception(f"Streaming error: {e}")


# ============================================================================
# TTS STREAMING ENHANCEMENTS
# ============================================================================

class StreamingTTSEnhancer:
    """
    Enhancements for TTSTool to support chunk-level streaming
    
    This extends the existing TTSTool with streaming-optimized methods
    """
    
    __slots__ = ()  # Static utility class, no instance variables
    
    @staticmethod
    def prepare_chunk_for_speech(chunk: str) -> Optional[str]:
        """
        Prepare text chunk for speech
        
        Rules:
        - Accumulate until natural break point (punctuation)
        - Minimum 3 words for natural speech
        - Clean formatting artifacts
        
        Args:
            chunk: Raw text chunk from LLM
        
        Returns:
            Cleaned chunk ready for TTS, or None if should buffer more
        """
        # Clean chunk
        chunk = chunk.strip()
        if not chunk:
            return None
        
        # Remove markdown artifacts
        chunk = re.sub(r'\*\*', '', chunk)  # Remove bold
        chunk = re.sub(r'__', '', chunk)    # Remove underline
        chunk = re.sub(r'~~', '', chunk)    # Remove strikethrough
        
        # Check for natural break point
        has_break = any(char in chunk for char in '.!?,;:')
        word_count = len(chunk.split())
        
        # Speak if:
        # 1. Has punctuation break, OR
        # 2. Has 5+ words (for long chunks without punctuation)
        if has_break or word_count >= 5:
            return chunk
        
        # Buffer for more content
        return None
    
    @staticmethod
    def split_into_speakable_chunks(text: str, max_words: int = 8) -> List[str]:
        """
        Split text into optimal chunks for streaming TTS
        
        Balances latency (small chunks) with quality (complete phrases)
        
        Args:
            text: Complete text to split
            max_words: Maximum words per chunk
        
        Returns:
            List of speakable chunks
        """
        # Split on sentence boundaries first
        sentences = re.split(r'([.!?]+)', text)
        
        chunks = []
        current_chunk = ""
        
        for part in sentences:
            part = part.strip()
            if not part:
                continue
            
            # Check if adding this part exceeds max words
            combined = f"{current_chunk} {part}".strip()
            word_count = len(combined.split())
            
            if word_count > max_words and current_chunk:
                # Current chunk is full - emit it
                chunks.append(current_chunk.strip())
                current_chunk = part
            else:
                current_chunk = combined
        
        # Add final chunk
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks


# ============================================================================
# INTEGRATION EXAMPLE
# ============================================================================

async def example_streaming_integration(ai_core, thought_buffer, user_input: str):
    """
    Example of how to integrate streaming into cognitive loop
    
    This shows the complete flow from Ollama streaming to memory storage
    """
    # Initialize streaming components
    streaming_handler = StreamingResponseHandler(
        memory_manager=ai_core.memory_manager,
        memory_search=ai_core.memory_search,
        tts_tool=ai_core.tts_tool,
        logger=ai_core.logger
    )
    
    ollama_streaming = OllamaStreamingInterface()
    
    # Build prompt (use existing prompt builder)
    from BASE.core.responsive.responsive_constructor import ResponsiveConstructor
    prompt_builder = ResponsiveConstructor(
        memory_search=ai_core.memory_search,
        logger=ai_core.logger
    )
    
    thoughts = thought_buffer.get_thoughts_for_response()
    context_parts = []  # Add context as needed
    
    prompt = prompt_builder.build_responsive_prompt(
        thought_chain=[str(t) for t in thoughts],
        user_text=user_input,
        context_parts=context_parts
    )
    
    # Stream response from Ollama
    response_stream = ollama_streaming.stream_chat_response(
        prompt=prompt,
        model="llama3.2:3b"
    )
    
    # Stream to TTS and store to memory
    complete_response = await streaming_handler.stream_and_store(
        response_stream=response_stream,
        thought_buffer=thought_buffer,
        context_parts=context_parts,
        user_input=user_input
    )
    
    return complete_response