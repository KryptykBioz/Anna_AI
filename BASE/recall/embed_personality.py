# Filename: BASE/memory/embed_personality.py
"""
Personality Training Data Embedder - Two-Stage Architecture
Separates training data into:
1. THOUGHT EXAMPLES - For thought processor (event interpretation, action proactive)
2. RESPONSE EXAMPLES - For response generator (responsive output synthesis)

FIXED: Corrected directory paths:
- Input: personality/base_memory/base_personality/
- Output: personality/base_memory/base_personality/embeddings/

IMPROVED: 
- Consistent chunk formatting (uses 'response' field for both stages internally)
- Better keyword extraction and deduplication
- Improved error handling and validation
- Stage-specific output organization

Usage: python embed_personality.py
"""

import sys
import json
import requests
import hashlib
import importlib.util
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional


class PersonalityEmbedder:
    """Personality training data embedder"""
    
    __slots__ = (
        'ollama_url', 'embed_model', 'input_dir', 'output_dir', 'stats'
    )
    
    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_url = ollama_url
        self.embed_model = "nomic-embed-text"
        
        script_dir = Path(__file__).resolve().parent
        base_dir = script_dir.parents[1]
        
        # FIXED: Input from base_personality, output to base_personality/embeddings
        self.input_dir = base_dir / "personality" / "base_memory" / "base_personality"
        self.output_dir = base_dir / "personality" / "base_memory" / "base_personality" / "embeddings"
        
        self.stats = {
            'total_files': 0,
            'processed_files': 0,
            'failed_files': 0,
            'thought_chunks': 0,
            'response_chunks': 0,
            'total_embeddings': 0,
            'failed_embeddings': 0
        }
    
    def get_embedding(self, text: str) -> List[float]:
        """
        Get embedding for text using Ollama.
        
        Args:
            text: Text to embed
        
        Returns:
            Embedding vector or empty list if failed
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
            print(f"Error getting embedding: {e}")
            return []
    
    def load_training_module(self, filepath: Path) -> Optional[Tuple[List[Dict], str, str]]:
        """
        Dynamically load a Python training file.
        
        Returns:
            (examples_list, system_prompt/context, processing_stage)
            processing_stage: 'thought' or 'response'
        """
        try:
            spec = importlib.util.spec_from_file_location("training_module", filepath)
            if not spec or not spec.loader:
                print(f"Could not load {filepath.name}")
                return None
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Try multiple variable names for examples (for compatibility)
            examples = (
                getattr(module, 'response_examples', None) or 
                getattr(module, 'training_examples', None) or
                getattr(module, 'examples', None)
            )
            
            # Try multiple variable names for system info
            system_info = (
                getattr(module, 'system_prompt', None) or 
                getattr(module, 'system_context', None) or
                "AI assistant personality template"
            )
            
            # Get processing stage
            processing_stage = getattr(module, 'processing_stage', 'response')
            
            if not examples:
                print(f"[WARNING] {filepath.name}: No training examples found")
                return None
            
            if not isinstance(examples, list):
                print(f"[WARNING] {filepath.name}: Examples must be a list")
                return None
            
            print(f"[SUCCESS] Loaded {filepath.name}: {len(examples)} examples (stage: {processing_stage})")
            return examples, system_info, processing_stage
            
        except Exception as e:
            print(f"Error loading {filepath.name}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def create_chunk(self, item: Dict, idx: int, source_file: str, stage: str) -> Optional[Dict[str, Any]]:
        """
        Create chunk for either thought or response stage.
        
        UNIFIED: Both stages use 'response' field internally
        External access should check metadata['stage'] to determine type
        
        Args:
            item: Example dictionary with 'context', 'response', 'keywords'
            idx: Index in examples list
            source_file: Source filename
            stage: 'thought' or 'response'
        
        Returns:
            Formatted chunk dict or None if invalid
        """
        # Extract fields from example
        context = item.get('context', '').strip()
        response = item.get('response', '').strip()
        keywords = item.get('keywords', [])
        
        # Validate
        if not context or not response:
            return None
        
        # Ensure keywords is a list
        if isinstance(keywords, str):
            keywords = [keywords]
        elif not isinstance(keywords, list):
            keywords = []
        
        # Clean and deduplicate keywords
        keywords = list(set(kw.lower().strip() for kw in keywords if kw))
        
        # Create searchable text (used for vector similarity)
        searchable_parts = [context, response] + keywords
        searchable_text = ' '.join(searchable_parts)
        
        # Create display text
        if stage == 'thought':
            display_text = f"""SITUATION: {context}

INTERNAL COGNITION: {response}

KEYWORDS: {', '.join(keywords)}"""
        else:  # response
            display_text = f"""SITUATION: {context}

RESPONSE: {response}

KEYWORDS: {', '.join(keywords)}"""
        
        chunk = {
            "text": display_text,
            "searchable_text": searchable_text,
            "metadata": {
                "type": f"{stage}_example",
                "stage": stage,
                "context": context,
                "response": response,
                "keywords": keywords,
                "source_file": source_file,
                "example_index": idx
            }
        }
        
        return chunk
    
    def create_stage_summary(
        self,
        examples: List[Dict],
        stage: str,
        system_info: str,
        source_file: str
    ) -> Dict[str, Any]:
        """
        Create summary chunk including system prompt/context.
        
        Summary is NOT a regular example but provides stage-specific guidance.
        """
        # Collect all keywords from examples
        all_keywords = []
        for ex in examples:
            keywords = ex.get('keywords', [])
            if isinstance(keywords, str):
                keywords = [keywords]
            all_keywords.extend(keywords)
        
        # Deduplicate and take top 20
        unique_keywords = list(set(kw.lower() for kw in all_keywords if kw))
        top_keywords = sorted(unique_keywords)[:20]
        
        # Create summary text
        if stage == 'thought':
            summary_text = f"""PERSONALITY TRAINING - THOUGHT PROCESSING

STAGE: Internal cognitive processing and event interpretation

SYSTEM CONTEXT:
{system_info}

TRAINING COVERAGE:
This personality file contains {len(examples)} thought processing examples covering:
{', '.join(top_keywords)}

PURPOSE:
These examples guide how the AI interprets events, situations, and stimuli.
They shape internal reasoning patterns and cognitive responses."""
        else:  # response
            summary_text = f"""PERSONALITY TRAINING - RESPONSE GENERATION

STAGE: External response and output synthesis

SYSTEM CONTEXT:
{system_info}

TRAINING COVERAGE:
This personality file contains {len(examples)} response examples covering:
{', '.join(top_keywords)}

PURPOSE:
These examples guide how the AI formulates external responses and communications.
They shape conversational style, tone, and expression patterns."""
        
        chunk = {
            "text": summary_text,
            "searchable_text": f"{system_info} {' '.join(top_keywords)}",
            "metadata": {
                "type": f"{stage}_summary",
                "stage": stage,
                "is_summary": True,
                "source_file": source_file,
                "example_count": len(examples),
                "keywords": top_keywords
            }
        }
        
        return chunk
    
    def process_training_file(
        self,
        examples: List[Dict],
        system_info: str,
        stage: str,
        source_file: str
    ) -> List[Dict[str, Any]]:
        """
        Process training examples into chunks.
        
        Creates:
        1. One summary chunk (metadata guidance)
        2. Individual example chunks
        
        Args:
            examples: List of training examples
            system_info: System context/prompt
            stage: 'thought' or 'response'
            source_file: Source filename
        
        Returns:
            List of formatted chunks
        """
        chunks = []
        
        # Create summary chunk
        summary = self.create_stage_summary(examples, stage, system_info, source_file)
        chunks.append(summary)
        
        # Create example chunks
        for idx, item in enumerate(examples):
            chunk = self.create_chunk(item, idx, source_file, stage)
            if chunk:
                chunks.append(chunk)
        
        return chunks
    
    def embed_chunks(
        self,
        chunks: List[Dict[str, Any]],
        stage: str
    ) -> List[Dict[str, Any]]:
        """
        Add embeddings to chunks.
        
        Uses 'searchable_text' field for embedding to ensure consistency.
        
        Args:
            chunks: List of chunks to embed
            stage: Processing stage ('thought' or 'response')
        
        Returns:
            List of chunks with embeddings added
        """
        embedded_chunks = []
        success_count = 0
        
        for i, chunk in enumerate(chunks):
            print(f"  Embedding chunk {i+1}/{len(chunks)}", end='\r')
            
            searchable = chunk.get('searchable_text', chunk.get('text', ''))
            embedding = self.get_embedding(searchable)
            
            if embedding:
                chunk['embedding'] = embedding
                chunk['hash'] = hashlib.md5(searchable.encode()).hexdigest()
                embedded_chunks.append(chunk)
                success_count += 1
            else:
                self.stats['failed_embeddings'] += 1
                print(f"\n  [WARNING] Failed to embed chunk {i+1}")
        
        print(f"  Embedded {success_count}/{len(chunks)} chunks")
        
        self.stats['total_embeddings'] += success_count
        return embedded_chunks
    
    def save_embeddings(
        self,
        chunks: List[Dict[str, Any]],
        stage: str,
        source_filename: str
    ):
        """
        Save embedded chunks to appropriate directory.
        
        FIXED: All embeddings now go to single embeddings/ directory
        with stage indicated in filename
        
        Args:
            chunks: List of embedded chunks
            stage: 'thought' or 'response'
            source_filename: Original source filename
        """
        base_name = Path(source_filename).stem
        
        # Create stage-specific filename
        output_filename = f"{base_name}_{stage}_examples.json"
        output_path = self.output_dir / output_filename
        
        # Count unique keywords
        all_keywords = []
        for c in chunks:
            metadata = c.get('metadata', {})
            if not metadata.get('is_summary'):
                keywords = metadata.get('keywords', [])
                all_keywords.extend(keywords)
        
        unique_keywords = list(set(all_keywords))
        
        # Prepare output
        output_data = {
            "source_file": source_filename,
            "processing_stage": stage,
            "embed_model": self.embed_model,
            "total_chunks": len(chunks),
            "unique_keywords": len(unique_keywords),
            "chunks": chunks
        }
        
        # Save to disk
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        file_size_kb = output_path.stat().st_size / 1024
        print(f"  [SUCCESS] Saved {stage} to: {output_filename}")
        print(f"    Size: {file_size_kb:.1f} KB")
        print(f"    Unique keywords: {len(unique_keywords)}")
    
    def process_file(self, filepath: Path) -> bool:
        """
        Process a single training file.
        
        Args:
            filepath: Path to training file
        
        Returns:
            True if successful, False otherwise
        """
        print(f"Processing: {filepath.name}")
        
        # Load module
        result = self.load_training_module(filepath)
        if not result:
            return False
        
        examples, system_info, processing_stage = result
        
        # Validate processing stage
        if processing_stage not in ['thought', 'response']:
            print(f"[WARNING] Invalid processing_stage '{processing_stage}'. Using 'response'.")
            processing_stage = 'response'
        
        print(f"  Creating training chunks for stage: {processing_stage}")
        chunks = self.process_training_file(examples, system_info, processing_stage, filepath.name)
        
        print(f"  Total chunks: {len(chunks)}")
        
        # Track statistics
        if processing_stage == 'thought':
            self.stats['thought_chunks'] += len(chunks)
        else:
            self.stats['response_chunks'] += len(chunks)
        
        # Embed chunks
        embedded_chunks = self.embed_chunks(chunks, processing_stage)
        if not embedded_chunks:
            return False
        
        # Save embeddings
        self.save_embeddings(embedded_chunks, processing_stage, filepath.name)
        
        return True
    
    def process_all_files(self):
        """Process all Python training files in the input directory."""
        # FIXED: Create single output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        if not self.input_dir.exists():
            print(f"Input directory does not exist: {self.input_dir}")
            return False
        
        python_files = [
            f for f in self.input_dir.glob("*.py")
            if not f.name.startswith('__') and not f.name.startswith('.')
        ]
        
        if not python_files:
            print(f"No training files found in {self.input_dir}")
            return False
        
        self.stats['total_files'] = len(python_files)
        
        print("\n" + "="*70)
        print("TWO-STAGE PERSONALITY EMBEDDER")
        print("="*70)
        print(f"Input directory:   {self.input_dir}")
        print(f"Output directory:  {self.output_dir}")
        print(f"Training files:    {len(python_files)}")
        print("="*70 + "\n")
        
        for filepath in python_files:
            if self.process_file(filepath):
                self.stats['processed_files'] += 1
            else:
                self.stats['failed_files'] += 1
        
        self.print_summary()
        return self.stats['processed_files'] > 0
    
    def print_summary(self):
        """Print processing summary."""
        print("\n" + "="*70)
        print("PROCESSING COMPLETE")
        print("="*70)
        print(f"Files found:            {self.stats['total_files']}")
        print(f"Files processed:        {self.stats['processed_files']}")
        print(f"Files failed:           {self.stats['failed_files']}")
        print(f"Thought chunks:         {self.stats['thought_chunks']}")
        print(f"Response chunks:        {self.stats['response_chunks']}")
        print(f"Total embeddings:       {self.stats['total_embeddings']}")
        if self.stats['failed_embeddings'] > 0:
            print(f"Failed embeddings:      {self.stats['failed_embeddings']}")
        print("="*70)
        
        if self.stats['processed_files'] > 0:
            print(f"\n✓ [SUCCESS] Successfully processed {self.stats['processed_files']} personality file(s)")
            print(f"\nEmbedded files ready at:")
            print(f"  {self.output_dir}")
            print(f"\nNext steps:")
            print(f"  1. Verify directory contains .json files")
            print(f"  2. Initialize MemorySearch with the memory directory")
            print(f"  3. Thought/response constructors will automatically retrieve examples")
            print(f"  4. Monitor logs to verify personality example injection")
        else:
            print(f"\n✗ No files were successfully processed")


def check_ollama_available(ollama_url: str) -> bool:
    """Check if Ollama is running and model is available."""
    try:
        response = requests.get(f"{ollama_url}/api/tags", timeout=5)
        response.raise_for_status()
        return True
    except Exception:
        return False


def main():
    """Main entry point for embedding personality files."""
    embedder = PersonalityEmbedder()
    
    print("\nChecking Ollama connection...")
    if not check_ollama_available(embedder.ollama_url):
        print("Cannot connect to Ollama")
        print("Please start Ollama with: ollama serve")
        sys.exit(1)
    print("[SUCCESS] Ollama is running")
    
    print(f"\nTesting embedding model '{embedder.embed_model}'...")
    test_embedding = embedder.get_embedding("test")
    if not test_embedding:
        print(f"Embedding model '{embedder.embed_model}' not available")
        print(f"Pull it with: ollama pull {embedder.embed_model}")
        sys.exit(1)
    print("[SUCCESS] Embedding model is ready")
    
    success = embedder.process_all_files()
    
    if success:
        print("\n✓ Personality embeddings ready for use!")
        print("\nThe system will:")
        print("  • Automatically detect and load all personality files")
        print("  • Use thought examples during event interpretation")
        print("  • Use response examples during responsive output generation")
        print("  • Log personality retrieval statistics")
    else:
        print("\n✗ Embedding process failed")
        sys.exit(1)


if __name__ == "__main__":
    main()