# Filename: BASE/recall/memory_search.py
"""
Memory Search Module - Universal Method Wrapper
Complete implementation with automatic delegation for ANY method call
Uses simplified keyword and cosine similarity matching

FIXED: Corrected path for base memory embeddings:
- Base files: personality/base_memory/base_files/
- Base embeddings: personality/base_memory/base_files/embeddings/

UNIVERSAL: Handles any method call through __getattr__ delegation
- If memory_manager has the method, delegates to it
- Otherwise returns appropriate empty value
- Never crashes due to missing method
"""

import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional, Any, Union
import requests


class MemorySearch:
    """Search personality embeddings for thought and response examples"""
    
    __slots__ = (
        'logger', 'memory_manager', 'memory_dir', 'thought_examples_dir',
        'response_examples_dir', 'thought_embeddings', 'response_embeddings',
        'ollama_url', 'embed_model', 'config', '_chunk_size'
    )

    def __init__(self, memory_dir_or_manager: Optional[Any] = None, logger=None, config=None):
            self.logger  = logger
            self.memory_manager = None
            self.config  = config

            max_chars        = max(50, getattr(config, 'MAX_TOOL_RESULT_CHARS', 1000)) if config else 1000
            n_results        = max(1,  getattr(config, 'MAX_TOOL_RESULTS',       3))   if config else 3
            self._chunk_size = max(50, max_chars // n_results)

            memory_dir = self._resolve_memory_dir(memory_dir_or_manager)

            self.memory_dir = Path(memory_dir) if memory_dir else None

            if self.memory_dir:
                self.thought_examples_dir  = self.memory_dir / "thought_examples"
                self.response_examples_dir = self.memory_dir / "response_examples"
            else:
                self.thought_examples_dir  = None
                self.response_examples_dir = None

            self.thought_embeddings  = {}
            self.response_embeddings = {}

            self.ollama_url  = "http://localhost:11434"
            self.embed_model = "nomic-embed-text"

            self._load_embeddings()
    
    def _resolve_memory_dir(self, memory_input: Optional[Any]) -> Optional[Path]:
        if memory_input is None:
            script_dir = Path(__file__).parent
            base_dir = script_dir.parents[1]
            return base_dir / "personality" / "base_memory" / "base_files"

        if isinstance(memory_input, Path):
            return memory_input

        if isinstance(memory_input, str):
            return Path(memory_input)

        # MemoryManager uses project_root; legacy code used base_dir — handle both
        root = None
        if hasattr(memory_input, 'project_root'):
            self.memory_manager = memory_input
            root = Path(memory_input.project_root)
        elif hasattr(memory_input, 'base_dir'):
            self.memory_manager = memory_input
            root = Path(memory_input.base_dir)

        if root is not None:
            return root / "personality" / "base_memory" / "base_files"

        if self.logger:
            self.logger.warning("[MemorySearch] Unknown memory input type, using auto-detect")

        script_dir = Path(__file__).parent
        base_dir = script_dir.parents[1]
        return base_dir / "personality" / "base_memory" / "base_files"
    
    def _load_embeddings(self):
        """
        Load all embedding files from disk
        
        Loads from personality/base_memory/base_files/embeddings/
        """
        if not self.memory_dir or not self.memory_dir.exists():
            if self.logger:
                self.logger.warning(
                    f"[MemorySearch] Memory directory not found: {self.memory_dir}"
                )
            return
        
        if self.logger:
            self.logger.system("[MemorySearch] Loading personality embeddings...")
        
        # Load thought examples
        if self.thought_examples_dir and self.thought_examples_dir.exists():
            for json_file in self.thought_examples_dir.glob("*.json"):
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        self.thought_embeddings[json_file.stem] = data
                        if self.logger:
                            self.logger.system(
                                f"[MemorySearch] Loaded thought examples: {json_file.name} "
                                f"({data['total_chunks']} chunks)"
                            )
                except Exception as e:
                    if self.logger:
                        self.logger.warning(f"[MemorySearch] Failed to load {json_file.name}: {e}")
        
        # Load response examples
        if self.response_examples_dir and self.response_examples_dir.exists():
            for json_file in self.response_examples_dir.glob("*.json"):
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        self.response_embeddings[json_file.stem] = data
                        if self.logger:
                            self.logger.system(
                                f"[MemorySearch] Loaded response examples: {json_file.name} "
                                f"({data['total_chunks']} chunks)"
                            )
                except Exception as e:
                    if self.logger:
                        self.logger.warning(f"[MemorySearch] Failed to load {json_file.name}: {e}")
    
    # Add these methods to the MemorySearch class in memory_search.py

    def search_medium_memory(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
            if not self.memory_manager:
                if self.logger:
                    self.logger.debug("[MemorySearch] No memory_manager available for medium search")
                return []

            medium_entries = getattr(self.memory_manager, 'medium_memory', [])
            if not medium_entries:
                return []

            query_embedding = self.get_embedding_vector(query)
            if not query_embedding:
                if self.logger:
                    self.logger.warning("[MemorySearch] Failed to get query embedding for medium search")
                return []

            results = []
            for entry in medium_entries:
                if 'embedding' not in entry or not entry['embedding']:
                    continue

                similarity = self._cosine_similarity(query_embedding, entry['embedding'])

                if similarity > 0.3:
                    results.append({
                        'role':      entry.get('role', 'unknown'),
                        'content':   self._truncate_text(entry.get('content', ''), self._chunk_size),
                        'timestamp': entry.get('timestamp', ''),
                        'date':      entry.get('date', ''),
                        'similarity': similarity
                    })

            results.sort(key=lambda x: x['similarity'], reverse=True)
            return results[:k]


    def search_long_memory(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
            if not self.memory_manager:
                if self.logger:
                    self.logger.debug("[MemorySearch] No memory_manager available for long search")
                return []

            long_entries = getattr(self.memory_manager, 'long_memory', [])
            if not long_entries:
                return []

            query_embedding = self.get_embedding_vector(query)
            if not query_embedding:
                if self.logger:
                    self.logger.warning("[MemorySearch] Failed to get query embedding for long search")
                return []

            results = []
            for entry in long_entries:
                if 'embedding' not in entry or not entry['embedding']:
                    continue

                similarity = self._cosine_similarity(query_embedding, entry['embedding'])

                if similarity > 0.3:
                    results.append({
                        'summary':     self._truncate_text(entry.get('summary', ''), self._chunk_size),
                        'date':        entry.get('date', ''),
                        'timestamp':   entry.get('timestamp', ''),
                        'entry_count': entry.get('entry_count', 0),
                        'similarity':  similarity
                    })

            results.sort(key=lambda x: x['similarity'], reverse=True)
            return results[:k]


    def search_base_knowledge(self, query: str, k: int = 5, min_similarity: float = 0.4) -> List[Dict[str, Any]]:
        """
        Search base knowledge (personality and documents)
        
        Args:
            query: Search query text
            k: Number of results to return
            min_similarity: Minimum similarity threshold
        
        Returns:
            List of matching chunks with similarity scores
        """
        if not self.memory_manager:
            if self.logger:
                self.logger.debug("[MemorySearch] No memory_manager available for base knowledge search")
            return []
        
        # Get base knowledge chunks
        base_chunks = getattr(self.memory_manager, 'base_knowledge', [])
        if not base_chunks:
            return []
        
        # Get query embedding
        query_embedding = self.get_embedding_vector(query)
        if not query_embedding:
            if self.logger:
                self.logger.warning("[MemorySearch] Failed to get query embedding for base knowledge search")
            return []
        
        # Calculate similarities
        results = []
        for chunk in base_chunks:
            if 'embedding' not in chunk or not chunk['embedding']:
                continue
            
            similarity = self._cosine_similarity(query_embedding, chunk['embedding'])
            
            if similarity >= min_similarity:
                results.append({
                    'text': chunk.get('text', ''),
                    'metadata': chunk.get('metadata', {}),
                    'similarity': similarity
                })
        
        # Sort by similarity and return top k
        results.sort(key=lambda x: x['similarity'], reverse=True)
        return results[:k]


    def get_short_memory(self) -> str:
        if not self.memory_manager:
            return ""

        short_entries = getattr(self.memory_manager, 'short_memory', [])
        if not short_entries:
            return ""

        lines = []
        username = getattr(self.memory_manager, 'username', 'User')
        agentname = getattr(self.memory_manager, 'agentname', 'Agent')

        # Use max_context_entries from config if available, else full short memory
        limit = (
            getattr(self.config, 'max_context_entries', None)
            or getattr(self.memory_manager, 'max_context_entries', None)
            or len(short_entries)
        )

        for entry in short_entries[-limit:]:
            role = username if entry.get('role') == 'user' else agentname
            timestamp = entry.get('timestamp', 'Unknown time')
            content = entry.get('content', '')
            lines.append(f"[{timestamp}] {role}: {content}")

        return "\n".join(lines)


    def get_yesterday_context(self, max_entries: int = None) -> str:
        if not self.memory_manager:
            return ""

        if max_entries is None:
            max_entries = (
                getattr(self.config, 'max_context_entries', None)
                or getattr(self.memory_manager, 'max_context_entries', None)
                or 10
            )

        from datetime import datetime, timedelta
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

        yesterday_entries = []
        short_memory = getattr(self.memory_manager, 'short_memory', [])
        medium_memory = getattr(self.memory_manager, 'medium_memory', [])

        for entry in short_memory + medium_memory:
            if entry.get('date') == yesterday:
                yesterday_entries.append(entry)

        if not yesterday_entries:
            return ""

        yesterday_entries.sort(key=lambda x: x.get('timestamp', ''))
        yesterday_entries = yesterday_entries[-max_entries:]

        lines = []
        username = getattr(self.memory_manager, 'username', 'User')
        agentname = getattr(self.memory_manager, 'agentname', 'Agent')

        for entry in yesterday_entries:
            role = username if entry.get('role') == 'user' else agentname
            timestamp = entry.get('timestamp', 'Unknown time')
            content = entry.get('content', '')
            lines.append(f"[{timestamp}] {role}: {content}")

        return "\n".join(lines)

    def get_embedding_vector(self, text: str) -> Optional[List[float]]:
        """
        Get embedding vector for text using Ollama
        
        Args:
            text: Text to embed
        
        Returns:
            Embedding vector or None if failed
        """
        try:
            response = requests.post(
                f"{self.ollama_url}/api/embeddings",
                json={"model": self.embed_model, "prompt": text},
                timeout=30
            )
            response.raise_for_status()
            return response.json()["embedding"]
        except Exception as e:
            if self.logger:
                self.logger.warning(f"[MemorySearch] Embedding error: {e}")
            return None
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        try:
            a_arr = np.array(a)
            b_arr = np.array(b)
            norm_a = np.linalg.norm(a_arr)
            norm_b = np.linalg.norm(b_arr)
            
            if norm_a == 0 or norm_b == 0:
                return 0.0
            
            return float(np.dot(a_arr, b_arr) / (norm_a * norm_b))
        except Exception as e:
            if self.logger:
                self.logger.debug(f"[MemorySearch] Cosine similarity error: {e}")
            return 0.0
    
    def _truncate_text(self, text: str, max_length: int) -> str:
        """
        Truncate text at natural boundary
        
        Args:
            text: Text to truncate
            max_length: Maximum length
        
        Returns:
            Truncated text with [...] suffix
        """

        # OVERRIDE: For now, return full text and let LLM handle truncation if needed
        # if len(text) <= max_length:
        return text
        
        truncated = text[:max_length]
        
        sentence_ends = [truncated.rfind('.'), truncated.rfind('!'), truncated.rfind('?')]
        last_sentence = max(sentence_ends)
        if last_sentence > max_length * 0.7:
            return text[:last_sentence + 1].strip() + " [...]"
        
        last_space = truncated.rfind(' ')
        if last_space > 0:
            return text[:last_space].strip() + " [...]"
        
        return truncated.strip() + " [...]"
    
    def _keyword_match_score(self, query_keywords: List[str], chunk_keywords: List[str]) -> float:
        """
        Calculate keyword match score
        
        Args:
            query_keywords: Keywords from search query
            chunk_keywords: Keywords from example chunk
        
        Returns:
            Match score 0.0-1.0
        """
        if not query_keywords or not chunk_keywords:
            return 0.0
        
        query_set = set(kw.lower() for kw in query_keywords if kw)
        chunk_set = set(kw.lower() for kw in chunk_keywords if kw)
        
        if not query_set or not chunk_set:
            return 0.0
        
        intersection = query_set & chunk_set
        union = query_set | chunk_set
        
        return len(intersection) / len(union) if union else 0.0
    
    def _search_embeddings(
        self,
        query: str,
        embeddings_dict: Dict,
        k: int = 3,
        min_similarity: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Search embeddings using combined keyword + similarity matching
        
        Args:
            query: Search query text
            embeddings_dict: Dictionary of loaded embeddings
            k: Number of results to return
            min_similarity: Minimum similarity threshold
        
        Returns:
            List of top k matching chunks
        """
        if not embeddings_dict:
            return []
        
        # Get query embedding
        query_embedding = self.get_embedding_vector(query)
        if not query_embedding:
            # Fallback to keyword-only search
            query_embedding = None
        
        # Extract keywords from query
        query_keywords = query.lower().split()
        
        results = []
        
        # Search all embeddings
        for source_name, embedding_data in embeddings_dict.items():
            chunks = embedding_data.get('chunks', [])
            
            for chunk in chunks:
                # Skip summaries for now (they're not actual examples)
                if chunk.get('metadata', {}).get('type') == 'stage_summary':
                    continue
                
                # Skip if no embedding
                if 'embedding' not in chunk:
                    continue
                
                # Skip if embedding is empty
                if not chunk['embedding']:
                    continue
                
                # Calculate similarity score
                similarity = 0.0
                
                # Vector similarity (if we have query embedding)
                if query_embedding and 'embedding' in chunk:
                    try:
                        similarity = self._cosine_similarity(query_embedding, chunk['embedding'])
                    except Exception as e:
                        if self.logger:
                            self.logger.debug(f"Similarity calculation error: {e}")
                        similarity = 0.0
                
                # Keyword match score (weight: 0.3)
                chunk_keywords = chunk.get('metadata', {}).get('keywords', [])
                keyword_score = self._keyword_match_score(query_keywords, chunk_keywords)
                
                # Combined score: 70% similarity + 30% keyword match
                combined_score = (similarity * 0.7) + (keyword_score * 0.3)
                
                if combined_score >= min_similarity:
                    result = {
                        'text': chunk['text'],
                        'metadata': chunk.get('metadata', {}),
                        'similarity': combined_score,
                        'source': source_name,
                        'hash': chunk.get('hash', '')
                    }
                    results.append(result)
        
        # Sort by similarity and return top k
        results.sort(key=lambda x: x['similarity'], reverse=True)
        return results[:k]
    
    def get_thought_interpretation_examples(
        self,
        context: str,
        k: int = 3,
        min_similarity: float = 0.3
    ) -> str:
        """
        Retrieve thought examples for interpretation/reactive thinking
        
        Args:
            context: Context query (combined thoughts + events)
            k: Number of examples to return
            min_similarity: Minimum similarity threshold
        
        Returns:
            Formatted examples string or empty string
        """
        results = self._search_embeddings(
            query=context,
            embeddings_dict=self.thought_embeddings,
            k=k,
            min_similarity=min_similarity
        )
        
        if not results:
            return ""
        
        return self._format_examples(results, stage='thought')
    
    def get_response_generation_examples(
        self,
        context: str,
        k: int = 3,
        min_similarity: float = 0.3
    ) -> str:
        """
        Retrieve response examples for responsive output generation
        
        Args:
            context: Context query (combined thoughts + user input)
            k: Number of examples to return
            min_similarity: Minimum similarity threshold
        
        Returns:
            Formatted examples string or empty string
        """
        results = self._search_embeddings(
            query=context,
            embeddings_dict=self.response_embeddings,
            k=k,
            min_similarity=min_similarity
        )
        
        if not results:
            return ""
        
        return self._format_examples(results, stage='response')
    
    def _format_examples(self, results: List[Dict[str, Any]], stage: str = 'thought') -> str:
            if not results:
                return ""

            ctx_limit  = max(50, int(self._chunk_size * 0.44))
            resp_limit = max(50, int(self._chunk_size * 0.55))

            lines = []

            for i, result in enumerate(results, 1):
                metadata   = result.get('metadata', {})
                context    = self._truncate_text(metadata.get('context',  ''), ctx_limit)
                response   = self._truncate_text(metadata.get('response', ''), resp_limit)
                keywords   = metadata.get('keywords', [])
                similarity = result['similarity']

                if stage == 'thought':
                    lines.append(f"SITUATION: {context}")
                    lines.append(f"INTERNAL COGNITION: {response}")
                else:
                    lines.append(f"SITUATION: {context}")
                    lines.append(f"RESPONSE: {response}")

                if keywords:
                    lines.append(f"KEYWORDS: {', '.join(keywords[:5])}")

                lines.append(f"(relevance: {similarity:.2f})")

                if i < len(results):
                    lines.append("")

            return "\n".join(lines)
    
    # ========================================================================
    # UNIVERSAL DELEGATION - Handles ANY method call
    # ========================================================================
    
    def __getattr__(self, name: str):
        """
        UNIVERSAL DELEGATION: Handle ANY method call gracefully
        
        This is called when an attribute/method is not found normally.
        
        Behavior:
        1. Check if it's a string query method (returns list or string)
        2. Try to delegate to memory_manager
        3. Return appropriate empty value if delegation fails
        4. Never crash due to missing method
        """
        
        # List of known methods that return lists
        list_return_methods = {
            'search_long_memory',
            'search_medium_memory', 
            'search_medium_memory_combined',
            'search_long_memory_combined',
            'search_base_knowledge',
            'search_personality_examples',
        }
        
        # List of known methods that return strings
        string_return_methods = {
            'get_yesterday_context',
            'get_short_memory',
            'get_long_memory_context',
            'get_medium_memory_context',
        }
        
        def delegated_method(*args, **kwargs):
            """Wrapper function for delegated methods"""
            
            # If no memory_manager, return appropriate empty value
            if not self.memory_manager:
                if name in list_return_methods:
                    return []
                elif name in string_return_methods:
                    return ""
                else:
                    # Try to guess based on name
                    if name.startswith('get_') or name.startswith('search_'):
                        return [] if 'search' in name else ""
                    return None
            
            # Try to delegate to memory_manager
            try:
                if hasattr(self.memory_manager, name):
                    method = getattr(self.memory_manager, name)
                    if callable(method):
                        result = method(*args, **kwargs)
                        if self.logger:
                            self.logger.debug(f"[MemorySearch] Delegated {name}() to memory_manager")
                        return result
            except Exception as e:
                if self.logger:
                    self.logger.debug(f"[MemorySearch] Delegation error for {name}: {e}")
            
            # Return appropriate empty value
            if name in list_return_methods:
                if self.logger:
                    self.logger.debug(f"[MemorySearch] {name}() not available, returning []")
                return []
            elif name in string_return_methods:
                if self.logger:
                    self.logger.debug(f"[MemorySearch] {name}() not available, returning ''")
                return ""
            else:
                if self.logger:
                    self.logger.debug(f"[MemorySearch] {name}() not available, returning None")
                return None
        
        return delegated_method