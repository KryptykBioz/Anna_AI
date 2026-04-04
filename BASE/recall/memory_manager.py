# Filename: BASE/memory/memory_manager.py
"""
Four-Tier Memory System for AI Agent
Refactored for centralized architecture with dependency injection

Tier 1: Short Memory (most recent 25 messages, not embedded, always in context)
Tier 2: Medium Memory (today's older messages, embedded, searchable)
Tier 3: Long Memory (daily summaries, embedded, searchable)
Tier 4: Base Knowledge (read-only external knowledge, searchable)

Key Changes:
- Accepts Config and Logger instances (dependency injection)
- No direct imports of personality modules
- Clean initialization with minimal dependencies
- All logging through injected Logger
- AES-256-GCM encrypted storage for Tiers 1-3 (crash-safe atomic writes)
"""

import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable

from BASE.core.logger import Logger
from BASE.recall.memory_encryption import (
    save_encrypted,
    load_encrypted_with_fallback,
    recover_pending_writes,
    setup_or_unlock,
)

from personality.controls import KILL_COMMAND

class MemoryManager:
    """Four-tier memory manager with dependency injection and encrypted persistence"""
    
    __slots__ = (
        'config', 'controls', 'logger', 'project_root', 'ollama_endpoint',
        'embed_model', 'agentname', 'username', 'short_memory_limit',
        'max_context_entries', 'memory_dir', 'short_memory_file',
        'medium_memory_file', 'long_memory_file', 'short_memory',
        'medium_memory', 'long_memory', 'base_knowledge',
        'interaction_count', 'last_summarization_count', 'current_date',
        'encryption_key',
    )
    
    def __init__(
        self, 
        config,
        controls_module,
        logger: Logger,
        project_root: Path,
        short_memory_limit: int = 25,
        max_context_entries: int = 50
    ):
        # Injected dependencies
        self.config = config
        self.controls = controls_module
        self.logger = logger
        self.project_root = project_root
        
        # Configuration from config object
        self.ollama_endpoint = config.ollama_endpoint
        self.embed_model = config.embed_model
        self.agentname = config.agentname
        self.username = config.username
        
        # Memory limits
        self.short_memory_limit = short_memory_limit
        self.max_context_entries = max_context_entries
        
        # Memory file paths
        self.memory_dir = project_root / "personality" / "memory"
        self.short_memory_file = self.memory_dir / "short_memory.json"
        self.medium_memory_file = self.memory_dir / "medium_memory.json"
        self.long_memory_file = self.memory_dir / "long_memory.json"
        
        # Memory storage
        self.short_memory: List[Dict[str, Any]] = []
        self.medium_memory: List[Dict[str, Any]] = []
        self.long_memory: List[Dict[str, Any]] = []
        self.base_knowledge: List[Dict[str, Any]] = []
        
        # Interaction tracking
        self.interaction_count = 0
        self.last_summarization_count = 0
        self.current_date = datetime.now().strftime('%Y-%m-%d')
        
        # Encryption key — derived from password at startup, held in memory only
        self.encryption_key = None
        
        # Unlock memory encryption before any file I/O
        self._unlock_memory()
        
        # Initialize memory system
        self._init_embeddings()
        self._load_all_memory()
        
        # Log initialization complete
        self.logger.memory("[SUCCESS] Memory Manager initialized")
    
    # ========================================================================
    # INITIALIZATION
    # ========================================================================

    def _unlock_memory(self):
        """
        Startup encryption tasks:
        1. Recover any interrupted writes from a previous crash
        2. Prompt for password and derive session key (stored in self.encryption_key)
        """
        recover_pending_writes(self.memory_dir)
        km = setup_or_unlock(self.memory_dir)
        self.encryption_key = km.key

    def _init_embeddings(self):
        """Test Ollama embedding model availability"""
        try:
            test_response = self._get_ollama_embedding("test")
            if test_response is not None:
                self.logger.memory(f"Embedding model ready: {self.embed_model}")
            else:
                self.logger.error(f"Failed to load embedding model: {self.embed_model}")
        except Exception as e:
            self.logger.error(f"Embedding test failed: {e}")
    
    def _load_all_memory(self):
        """Load all memory tiers"""
        self._load_short_memory()
        self._load_medium_memory()
        self._load_long_memory()
        self._load_base_memory()
    
    def _get_ollama_embedding(self, text: str) -> Optional[List[float]]:
        """
        Get embedding from Ollama API
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats (embedding vector) or None if failed
        """
        try:
            url = f"{self.ollama_endpoint}/api/embeddings"
            payload = {"model": self.embed_model, "prompt": text}
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            return response.json().get("embedding")
        except Exception as e:
            self.logger.error(f"Embedding API error: {e}")
            return None
    
    # ========================================================================
    # TIER 1: SHORT MEMORY (Recent Messages, Not Embedded)
    # ========================================================================
    
    def _load_short_memory(self):
        """Load Tier 1: Short memory (decrypt with .bak fallback)"""
        try:
            plaintext = load_encrypted_with_fallback(
                self.short_memory_file, self.encryption_key
            )
            if plaintext is None:
                self.short_memory = []
                self._save_short_memory()
                return
            self.short_memory = json.loads(plaintext.decode('utf-8'))
            self.logger.memory(
                f"[Tier 1] Loaded {len(self.short_memory)} short memory entries"
            )
        except Exception as e:
            self.logger.error(f"[Tier 1] Load failed: {e}")
            self.short_memory = []
    
    def _save_short_memory(self):
        """Save Tier 1: Short memory (encrypted, atomic write)"""
        try:
            self.memory_dir.mkdir(parents=True, exist_ok=True)
            plaintext = json.dumps(
                self.short_memory, ensure_ascii=False, indent=2
            ).encode('utf-8')
            save_encrypted(self.short_memory_file, plaintext, self.encryption_key)
        except Exception as e:
            self.logger.error(f"[Tier 1] Save failed: {e}")
    
    def _move_to_medium_memory(self):
        """Move oldest entries from short to medium memory when limit exceeded"""
        while len(self.short_memory) > self.short_memory_limit:
            oldest_entry = self.short_memory.pop(0)
            
            # Generate embedding for the entry
            content = oldest_entry['content']
            embedding = self._get_ollama_embedding(content)
            
            if embedding:
                oldest_entry['embedding'] = embedding
                oldest_entry['date'] = self.current_date
                self.medium_memory.append(oldest_entry)
                self.logger.memory("Moved entry to medium memory (embedded)")
            else:
                self.logger.error("Failed to embed entry, discarding")
        
        self._save_short_memory()
        self._save_medium_memory()
    
    # ========================================================================
    # TIER 2: MEDIUM MEMORY (Today's Older Messages, Embedded)
    # ========================================================================
    
    def _load_medium_memory(self):
        """Load Tier 2: Medium memory (decrypt with .bak fallback)"""
        try:
            plaintext = load_encrypted_with_fallback(
                self.medium_memory_file, self.encryption_key
            )
            if plaintext is None:
                self.medium_memory = []
                self._save_medium_memory()
                return

            loaded_entries = json.loads(plaintext.decode('utf-8'))

            # Ensure all entries have embeddings
            missing_embeddings = 0
            for entry in loaded_entries:
                if 'embedding' not in entry or not entry['embedding']:
                    content = entry.get('content', '')
                    if content:
                        embedding = self._get_ollama_embedding(content)
                        if embedding:
                            entry['embedding'] = embedding
                            missing_embeddings += 1
                        else:
                            continue
                    else:
                        continue
                self.medium_memory.append(entry)

            if missing_embeddings > 0:
                self.logger.warning(
                    f"[Tier 2] Generated {missing_embeddings} missing embeddings"
                )
                self._save_medium_memory()

            self.logger.memory(
                f"[Tier 2] Loaded {len(self.medium_memory)} medium memory entries"
            )
        except Exception as e:
            self.logger.error(f"[Tier 2] Load failed: {e}")
            self.medium_memory = []
    
    def _save_medium_memory(self):
        """Save Tier 2: Medium memory (encrypted, atomic write)"""
        try:
            self.memory_dir.mkdir(parents=True, exist_ok=True)
            plaintext = json.dumps(
                self.medium_memory, ensure_ascii=False, indent=2
            ).encode('utf-8')
            save_encrypted(self.medium_memory_file, plaintext, self.encryption_key)
        except Exception as e:
            self.logger.error(f"[Tier 2] Save failed: {e}")
    
    # ========================================================================
    # TIER 3: LONG MEMORY (Daily Summaries, Embedded)
    # ========================================================================
    
    def _load_long_memory(self):
        """Load Tier 3: Long memory (decrypt with .bak fallback)"""
        try:
            plaintext = load_encrypted_with_fallback(
                self.long_memory_file, self.encryption_key
            )
            if plaintext is None:
                self.long_memory = []
                self._save_long_memory()
                return

            loaded_summaries = json.loads(plaintext.decode('utf-8'))

            # Ensure all summaries have embeddings
            missing_embeddings = 0
            for entry in loaded_summaries:
                if 'embedding' not in entry or not entry['embedding']:
                    summary = entry.get('summary', '')
                    if summary:
                        embedding = self._get_ollama_embedding(summary)
                        if embedding:
                            entry['embedding'] = embedding
                            missing_embeddings += 1
                        else:
                            continue
                    else:
                        continue
                self.long_memory.append(entry)

            if missing_embeddings > 0:
                self.logger.warning(
                    f"[Tier 3] Generated {missing_embeddings} missing embeddings"
                )
                self._save_long_memory()

            self.logger.memory(
                f"[Tier 3] Loaded {len(self.long_memory)} long memory summaries"
            )
        except Exception as e:
            self.logger.error(f"[Tier 3] Load failed: {e}")
            self.long_memory = []
    
    def _save_long_memory(self):
        """Save Tier 3: Long memory (encrypted, atomic write)"""
        try:
            self.memory_dir.mkdir(parents=True, exist_ok=True)
            plaintext = json.dumps(
                self.long_memory, ensure_ascii=False, indent=2
            ).encode('utf-8')
            save_encrypted(self.long_memory_file, plaintext, self.encryption_key)
        except Exception as e:
            self.logger.error(f"[Tier 3] Save failed: {e}")
    
    # ========================================================================
    # TIER 4: BASE KNOWLEDGE (External Knowledge, Read-Only)
    # ========================================================================
    
    def _load_base_memory(self):
        """Load Tier 4: Base knowledge from external files"""
        self.base_knowledge = []
        
        try:
            base_dir = self.project_root / "personality" / "base_memory" / "base_files" / "embeddings"
            if not base_dir.exists():
                self.logger.memory(f"[Tier 4] Base memory directory not found: {base_dir}")
                return
            
            json_files = list(base_dir.glob("*.json"))
            
            if not json_files:
                self.logger.memory("[Tier 4] No base knowledge files found")
                return
            
            total_loaded = 0
            personality_count = 0
            document_count = 0
            
            for json_file in json_files:
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        file_data = json.load(f)
                    
                    # Extract chunks from various formats
                    chunks = self._extract_chunks_from_file(file_data, json_file.name)
                    
                    file_count = 0
                    for chunk in chunks:
                        # Only add chunks with valid embeddings
                        if chunk.get('embedding') and isinstance(chunk['embedding'], list):
                            self.base_knowledge.append(chunk)
                            file_count += 1
                            
                            # Track types
                            chunk_type = chunk.get('metadata', {}).get('type', 'unknown')
                            if chunk_type in ['conversation_example', 'category_summary', 'system_prompt']:
                                personality_count += 1
                            else:
                                document_count += 1
                    
                    total_loaded += file_count
                    self.logger.success(f"[Tier 4] Loaded {file_count} chunks from {json_file.name}")
                    
                except Exception as e:
                    self.logger.error(f"[Tier 4] Failed to load {json_file.name}: {e}")
            
            self.logger.success(f"[Tier 4] Total: {total_loaded} chunks from {len(json_files)} files")
            self.logger.memory(f"[Tier 4] Breakdown: {personality_count} personality, {document_count} document")
            
        except Exception as e:
            self.logger.error(f"[Tier 4] Base memory load failed: {e}")
    
    def _extract_chunks_from_file(self, file_data: Dict[str, Any], filename: str) -> List[Dict[str, Any]]:
        """Extract and normalize chunks from different file formats"""
        chunks = []
        
        # Handle different file structures
        if isinstance(file_data, dict) and 'chunks' in file_data:
            raw_chunks = file_data['chunks']
            file_metadata = {
                'source_file': file_data.get('source_file', filename),
                'embed_model': file_data.get('embed_model', 'unknown'),
                'chunk_method': file_data.get('chunk_method', 'unknown')
            }
        elif isinstance(file_data, list):
            raw_chunks = file_data
            file_metadata = {'source_file': filename}
        else:
            return []
        
        # Normalize each chunk
        for chunk in raw_chunks:
            if isinstance(chunk, dict):
                normalized = self._normalize_chunk(chunk, file_metadata)
                if normalized:
                    chunks.append(normalized)
        
        return chunks
    
    def _normalize_chunk(self, chunk: Dict[str, Any], file_metadata: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalize different chunk formats to standard structure"""
        try:
            # Must have embedding
            embedding = chunk.get('embedding')
            if not embedding or not isinstance(embedding, list):
                return None
            
            # Get text content (try different keys)
            text = chunk.get('text') or chunk.get('content')
            if not text or not isinstance(text, str) or len(text.strip()) == 0:
                return None
            
            # Build metadata by merging file-level and chunk-level metadata
            metadata = dict(file_metadata)  # Start with file-level metadata
            
            # Add chunk-specific metadata if present
            if 'metadata' in chunk and isinstance(chunk['metadata'], dict):
                metadata.update(chunk['metadata'])
            
            # Extract searchable text
            searchable_text = chunk.get('searchable_text', text)
            
            return {
                'text': text,
                'searchable_text': searchable_text,
                'embedding': embedding,
                'metadata': metadata,
                'char_count': chunk.get('char_count', len(text))
            }
            
        except Exception as e:
            self.logger.error(f"[Normalize] Error: {e}")
            return None
    
    # ========================================================================
    # INTERACTION MANAGEMENT
    # ========================================================================

    def save_user_message(self, user_input: str) -> Dict[str, Any]:
        """
        Save user message immediately to memory (for real-time display)
        
        Args:
            user_input: User's message
            
        Returns:
            Dictionary with the saved entry for immediate display
        """
        if not self.controls.SAVE_MEMORY or not user_input or (user_input == KILL_COMMAND):
            return None
        
        # Generate timestamp
        timestamp = self._format_timestamp()
        
        # Create user entry
        user_entry = {
            "role": "user",
            "content": user_input,
            "timestamp": timestamp,
            "date": self.current_date
        }
        
        # Add to short memory
        self.short_memory.append(user_entry)
        
        # Check for overflow to medium memory
        self._move_to_medium_memory()
        
        # Save to file
        self._save_short_memory()
        
        # Log if enabled
        self.logger.memory(
            f"Saved user message (Short: {len(self.short_memory)}, "
            f"Medium: {len(self.medium_memory)})"
        )
        
        # Return entry for GUI display
        return user_entry


    def save_bot_response(self, bot_response: str) -> Dict[str, Any]:
        """
        Save bot response to memory (after processing completes)
        
        Args:
            bot_response: Bot's response
            
        Returns:
            Dictionary with the saved entry for display
        """
        if not self.controls.SAVE_MEMORY or not bot_response or (bot_response == KILL_COMMAND):
            return None
        
        # Generate timestamp
        timestamp = self._format_timestamp()
        
        # Create bot entry
        bot_entry = {
            "role": "assistant",
            "content": bot_response,
            "timestamp": timestamp,
            "date": self.current_date
        }
        
        # Add to short memory
        self.short_memory.append(bot_entry)
        
        # Check for overflow to medium memory
        self._move_to_medium_memory()
        
        # Save to file
        self._save_short_memory()
        
        # Update interaction count
        self.interaction_count += 1
        
        # Log if enabled
        self.logger.memory(
            f"Saved bot response (Short: {len(self.short_memory)}, "
            f"Medium: {len(self.medium_memory)})"
        )
        
        # Return entry for GUI display
        return bot_entry
        
    def check_and_summarize_previous_day(self):
        """
        Summarize entries from 2+ days ago, keep yesterday's full detail
        ONLY called on GUI/CLI startup, not on every save_interaction
        """
        current_date = datetime.now().date()
        yesterday = (current_date - timedelta(days=1)).strftime('%Y-%m-%d')
        current_date_str = current_date.strftime('%Y-%m-%d')
        
        self.logger.memory(f"Checking for entries to archive (today: {current_date_str}, yesterday: {yesterday})")
        
        # Collect dates from all active memory
        dates = set()
        for e in self.short_memory + self.medium_memory:
            d = e.get('date', '')
            if d and d != current_date_str:
                dates.add(d)
        
        # Separate yesterday from older dates
        dates_to_summarize = []
        yesterday_entries = 0
        
        for d in sorted(dates):
            if d == yesterday:
                # Count yesterday's entries but don't summarize yet
                yesterday_entries = sum(
                    1 for e in self.short_memory + self.medium_memory 
                    if e.get('date') == d
                )
                self.logger.memory(f"Keeping {yesterday_entries} entries from yesterday ({d}) in full detail")
            else:
                dates_to_summarize.append(d)
        
        # Summarize dates older than yesterday
        if dates_to_summarize:
            self.logger.memory(f"Found {len(dates_to_summarize)} older day(s) to summarize: {dates_to_summarize}")
            
            for past_date in dates_to_summarize:
                self.logger.memory(f"Summarizing {past_date}...")
                from BASE.recall.summarizer import summarize_previous_day
                success = summarize_previous_day(self, past_date)
                
                if success:
                    self.logger.success(f"Archived {past_date} to long-term")
            
            # Remove ONLY the summarized entries (2+ days old)
            orig_medium = len(self.medium_memory)
            self.medium_memory = [
                e for e in self.medium_memory 
                if e.get('date') in [current_date_str, yesterday]
            ]
            removed_medium = orig_medium - len(self.medium_memory)
            
            orig_short = len(self.short_memory)
            self.short_memory = [
                e for e in self.short_memory 
                if e.get('date') in [current_date_str, yesterday]
            ]
            removed_short = orig_short - len(self.short_memory)
            
            if removed_medium or removed_short:
                self.logger.memory(f"Removed {removed_medium + removed_short} entries from 2+ days ago")
                self._save_medium_memory()
                self._save_short_memory()
        else:
            self.logger.memory("No entries older than yesterday found")
        
        # Update current date tracker
        self.current_date = current_date_str
    
    def archive_current_day(self, summary: str):
        """
        Archive today's conversation to Tier 3 (called by summarizer)
        
        Args:
            summary: Summary text for today's conversation
        """
        if not self.short_memory and not self.medium_memory:
            return
        
        summary_entry = {
            'summary': summary,
            'date': self.current_date,
            'timestamp': self._format_timestamp(),
            'entry_count': len(self.short_memory) + len(self.medium_memory),
            'metadata': {
                'archived_from': 'short_and_medium',
                'entry_type': 'daily_summary'
            }
        }
        
        # Generate embedding
        embedding = self._get_ollama_embedding(summary)
        if embedding:
            summary_entry['embedding'] = embedding
        
        # Add to long memory
        self.long_memory.append(summary_entry)
        self._save_long_memory()
        
        # Clear today's memories
        self.short_memory = []
        self.medium_memory = []
        self._save_short_memory()
        self._save_medium_memory()
        
        self.last_summarization_count = self.interaction_count
        self.logger.success("Current day archived to long memory")
    
    def archive_previous_day(self, summary: str, date: str):
        """
        Archive a previous day's summary to Tier 3 (long memory)
        Called by summarizer after generating summary for a past day
        
        Args:
            summary: The summary text to archive
            date: The date being archived (YYYY-MM-DD format)
        """
        if not summary:
            self.logger.error(f"Cannot archive empty summary for {date}")
            return
        
        # Generate embedding for the summary
        embedding = self._get_ollama_embedding(summary)
        
        if not embedding:
            self.logger.warning(f"Could not generate embedding for {date} summary")
            embedding = []
        
        # Create archive entry
        archive_entry = {
            'summary': summary,
            'date': date,
            'timestamp': self._format_timestamp(),
            'embedding': embedding,
            'metadata': {
                'archived_from': 'previous_day',
                'entry_type': 'daily_summary'
            }
        }
        
        # Add to long memory
        self.long_memory.append(archive_entry)
        
        # Save to file
        self._save_long_memory()
        
        self.logger.success(f"Archived summary for {date} to long-term memory")
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def _format_timestamp(self, dt: Optional[datetime] = None) -> str:
        """Format datetime to human-readable string using local time"""
        if dt is None:
            dt = datetime.now()
        return dt.strftime("%A, %B %d, %Y at %I:%M:%S %p")
    
    def _get_sortable_timestamp(self, dt: Optional[datetime] = None) -> str:
        """Get ISO format timestamp for sorting purposes"""
        if dt is None:
            dt = datetime.now()
        return dt.isoformat()
    
    # ========================================================================
    # MEMORY OPERATIONS (For GUI/API)
    # ========================================================================
    
    def clear_memory(self):
        """Clear personal memory (Tiers 1-3), preserve base knowledge (Tier 4)"""
        self.short_memory = []
        self.medium_memory = []
        self.long_memory = []
        self._save_short_memory()
        self._save_medium_memory()
        self._save_long_memory()
        self.interaction_count = 0
        self.last_summarization_count = 0
        self.logger.success("Personal memory cleared (base knowledge preserved)")
    
    def clear_today_memory(self) -> bool:
        """
        Clear today's memory only (for GUI button)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.short_memory = []
            self.medium_memory = []
            self._save_short_memory()
            self._save_medium_memory()
            self.logger.success("Today's memory cleared")
            return True
        except Exception as e:
            self.logger.error(f"Clear today's memory failed: {e}")
            return False
    
    def reload_base_knowledge(self) -> Dict[str, int]:
        """
        Reload base knowledge (for GUI refresh button)
        
        Returns:
            Dictionary with chunks_loaded and files_loaded counts
        """
        self._load_base_memory()
        summary = self.get_base_knowledge_breakdown()
        return {
            'chunks_loaded': summary['total_chunks'],
            'files_loaded': len(summary['by_source'])
        }
    
    def get_current_day_for_summary(self) -> List[Dict[str, Any]]:
        """Get all of today's entries for summarization (short + medium)"""
        return self.medium_memory + self.short_memory
    
    def needs_summarization(self, threshold: int = 50) -> bool:
        """
        Check if today's conversation should be summarized
        
        Args:
            threshold: Number of entries before summarization recommended
            
        Returns:
            True if summarization recommended
        """
        total_today = len(self.short_memory) + len(self.medium_memory)
        return total_today >= threshold
    
    # ========================================================================
    # STATISTICS (For GUI/API)
    # ========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get memory statistics for all tiers
        
        Returns:
            Dictionary with memory statistics
        """
        personality_count = sum(
            1 for chunk in self.base_knowledge 
            if chunk.get('metadata', {}).get('type') in [
                'conversation_example', 
                'category_summary', 
                'system_prompt'
            ]
        )
        document_count = len(self.base_knowledge) - personality_count
        
        return {
            'short_memory_entries': len(self.short_memory),
            'medium_memory_entries': len(self.medium_memory),
            'long_memory_summaries': len(self.long_memory),
            'base_knowledge_chunks': len(self.base_knowledge),
            'base_personality_chunks': personality_count,
            'base_document_chunks': document_count,
            'total_interactions': self.interaction_count,
            'interactions_since_summary': self.interaction_count - self.last_summarization_count,
            'current_date': self.current_date
        }
    
    def get_memory_stats_detailed(self) -> Dict[str, Any]:
        """
        Enhanced stats for GUI display
        
        Returns:
            Dictionary with detailed memory statistics
        """
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        yesterday_count = sum(
            1 for e in self.short_memory + self.medium_memory 
            if e.get('date') == yesterday
        )
        today_count = sum(
            1 for e in self.short_memory + self.medium_memory 
            if e.get('date') == self.current_date
        )
        
        return {
            'today_count': today_count,
            'yesterday_count': yesterday_count,
            'short_memory_entries': len(self.short_memory),
            'medium_memory_entries': len(self.medium_memory),
            'long_memory_summaries': len(self.long_memory),
            'base_knowledge_chunks': len(self.base_knowledge),
            'total_interactions': self.interaction_count,
            'current_date': self.current_date
        }
    
    def get_base_knowledge_breakdown(self) -> Dict[str, Any]:
        """
        Detailed base knowledge analysis for GUI
        
        Returns:
            Dictionary with breakdown by source, type, etc.
        """
        by_source = {}
        by_type = {}
        
        for chunk in self.base_knowledge:
            metadata = chunk.get('metadata', {})
            
            # Count by source file
            source = metadata.get('source_file', 'unknown')
            by_source[source] = by_source.get(source, 0) + 1
            
            # Count by type
            chunk_type = metadata.get('type', 'document')
            type_label = (
                'personality' 
                if chunk_type in ['conversation_example', 'category_summary', 'system_prompt'] 
                else 'document'
            )
            by_type[type_label] = by_type.get(type_label, 0) + 1
        
        return {
            'total_chunks': len(self.base_knowledge),
            'by_source': by_source,
            'by_type': by_type
        }
    
    def get_base_knowledge_summary(self) -> Dict[str, Any]:
        """
        Get detailed summary of loaded base knowledge
        
        Returns:
            Dictionary with comprehensive base knowledge summary
        """
        summary = {
            'total_chunks': len(self.base_knowledge),
            'by_source': {},
            'by_type': {},
            'by_category': {}
        }
        
        for chunk in self.base_knowledge:
            metadata = chunk.get('metadata', {})
            
            # Count by source file
            source = metadata.get('source_file', 'unknown')
            summary['by_source'][source] = summary['by_source'].get(source, 0) + 1
            
            # Count by type (personality vs document)
            chunk_type = metadata.get('type', 'document')
            if chunk_type in ['conversation_example', 'category_summary', 'system_prompt']:
                type_label = 'personality'
            else:
                type_label = 'document'
            summary['by_type'][type_label] = summary['by_type'].get(type_label, 0) + 1
            
            # Count by category (for personality chunks)
            if 'category' in metadata:
                category = metadata['category']
                summary['by_category'][category] = summary['by_category'].get(category, 0) + 1
        
        return summary