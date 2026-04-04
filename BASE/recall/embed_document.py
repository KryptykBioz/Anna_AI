# Filename: BASE/memory/embed_document.py
"""
Batch Document Embedding Script for RAG System
Processes all files in a directory and saves embeddings to another directory
NOW SUPPORTS: Base memory AND Game guides (separate directories)

FIXED: Preserves newlines and formatting in chunks

Usage: 
  python embed_document.py                    # Process base memory files
  python embed_document.py --game-guides      # Process game guide files
  python embed_document.py --all              # Process both
"""

import sys
import json
import os
import requests
from typing import List, Dict, Any
import hashlib
import re
from pathlib import Path
import argparse


class DocumentEmbedder:
    """Batch document embedding for RAG system"""
    
    __slots__ = (
        'ollama_url', 'embed_model', 'input_dir', 'output_dir', 'mode'
    )
    
    def __init__(self, ollama_url: str = "http://localhost:11434", mode: str = "base"):
        self.ollama_url = ollama_url
        self.embed_model = "nomic-embed-text"
        self.mode = mode  # "base" or "game_guides"
        
        # Get the script's directory and build paths relative to it
        script_dir = Path(__file__).parent
        base_dir = script_dir.parent.parent
        
        # Define the directory paths based on mode
        if mode == "game_guides":
            self.input_dir = base_dir / "personality" / "base_memory" / "game_guides"
            self.output_dir = base_dir / "personality" / "base_memory" / "game_guides" / "embeddings"
        else:  # base
            self.input_dir = base_dir / "personality" / "base_memory" / "base_files"
            self.output_dir = base_dir / "personality" / "base_memory" / "base_files" / "embeddings"
        
    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """
        Split text into overlapping chunks while PRESERVING formatting.
        
        FIXED: No longer collapses all whitespace to single spaces.
        Preserves newlines, paragraph breaks, and basic formatting.
        """
        # MINIMAL cleaning: only normalize excessive consecutive spaces on same line
        # Preserve newlines and paragraph breaks
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            # Only collapse multiple spaces within a line, preserve leading/trailing
            cleaned_line = re.sub(r' {2,}', ' ', line)
            cleaned_lines.append(cleaned_line)
        
        text = '\n'.join(cleaned_lines)
        
        if len(text) <= chunk_size:
            return [text.strip()]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            # If we're not at the end, try to break at natural boundaries
            if end < len(text):
                # First try: paragraph break (double newline)
                para_break = text.rfind('\n\n', start, end)
                if para_break > start + chunk_size // 3:
                    end = para_break + 2  # Include the paragraph break
                else:
                    # Second try: single newline
                    line_break = text.rfind('\n', start, end)
                    if line_break > start + chunk_size // 3:
                        end = line_break + 1
                    else:
                        # Third try: sentence boundary
                        sentence_end = max(
                            text.rfind('. ', start, end),
                            text.rfind('! ', start, end),
                            text.rfind('? ', start, end)
                        )
                        if sentence_end > start + chunk_size // 2:
                            end = sentence_end + 2
                        else:
                            # Last resort: word boundary
                            word_end = text.rfind(' ', start, end)
                            if word_end > start + chunk_size // 2:
                                end = word_end + 1
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # Move start position with overlap
            start = end - overlap
            if start >= len(text):
                break
                
        return chunks
    
    def get_embedding(self, text: str) -> List[float]:
        """Get embedding for text using Ollama."""
        try:
            response = requests.post(
                f"{self.ollama_url}/api/embeddings",
                json={
                    "model": self.embed_model,
                    "prompt": text
                },
                timeout=30
            )
            response.raise_for_status()
            return response.json()["embedding"]
        except Exception as e:
            print(f"Error getting embedding: {e}")
            return []
    
    def load_document(self, filepath: Path) -> str:
        """Load document content from file."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # Try with different encodings
            for encoding in ['latin-1', 'cp1252', 'utf-16']:
                try:
                    with open(filepath, 'r', encoding=encoding) as f:
                        return f.read()
                except UnicodeDecodeError:
                    continue
            raise Exception(f"Unable to decode file {filepath}")
    
    def extract_game_metadata(self, filepath: Path, content: str) -> Dict[str, Any]:
        """Extract metadata from game guide (game name, sections, etc.)"""
        metadata = {
            'type': 'game_guide',
            'game_name': filepath.stem,  # Use filename as default
            'sections': []
        }
        
        # Try to extract game name from first heading
        lines = content.split('\n')
        for line in lines[:10]:  # Check first 10 lines
            if line.startswith('# '):
                metadata['game_name'] = line.replace('# ', '').strip()
                break
        
        # Extract section headings
        for line in lines:
            if line.startswith('## '):
                section = line.replace('## ', '').strip()
                metadata['sections'].append(section)
        
        return metadata
    
    def embed_document(self, filepath: Path) -> Dict[str, Any]:
        """Process document and create embeddings."""
        if not filepath.exists():
            raise FileNotFoundError(f"File {filepath} not found")
        
        print(f"Loading document: {filepath}")
        text = self.load_document(filepath)
        
        print(f"Document loaded. Length: {len(text)} characters")
        
        # Extract metadata if game guide
        doc_metadata = {}
        if self.mode == "game_guides":
            doc_metadata = self.extract_game_metadata(filepath, text)
            print(f"Game: {doc_metadata['game_name']}")
            print(f"Sections: {len(doc_metadata['sections'])}")
        
        # Create chunks
        print("Chunking document...")
        chunks = self.chunk_text(text)
        print(f"Created {len(chunks)} chunks")
        
        # Create embeddings
        print("Creating embeddings...")
        embeddings_data = {
            "source_file": str(filepath),
            "total_chunks": len(chunks),
            "embed_model": self.embed_model,
            "mode": self.mode,
            "chunks": []
        }
        
        # Add metadata if game guide
        if self.mode == "game_guides":
            embeddings_data["metadata"] = doc_metadata
        
        for i, chunk in enumerate(chunks):
            print(f"Processing chunk {i+1}/{len(chunks)}")
            embedding = self.get_embedding(chunk)
            
            if embedding:
                chunk_data = {
                    "id": i,
                    "text": chunk,
                    "embedding": embedding,
                    "hash": hashlib.md5(chunk.encode()).hexdigest()
                }
                
                # Add chunk-level metadata for game guides
                if self.mode == "game_guides":
                    chunk_data["metadata"] = {
                        "type": "game_guide",
                        "game_name": doc_metadata['game_name'],
                        "source_file": filepath.name
                    }
                
                embeddings_data["chunks"].append(chunk_data)
            else:
                print(f"Failed to get embedding for chunk {i+1}")
        
        return embeddings_data
    
    def save_embeddings(self, embeddings_data: Dict[str, Any], output_file: Path):
        """Save embeddings to JSON file."""
        print(f"Saving embeddings to {output_file}")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(embeddings_data, f, indent=2)
        print(f"Embeddings saved successfully!")

    def get_supported_files(self) -> List[Path]:
        """Get list of supported files from input directory."""
        # Common text file extensions
        supported_extensions = {'.txt', '.md', '.rst', '.py', '.js', '.html', '.css', '.json', '.xml', '.csv', '.log'}
        
        files = []
        if self.input_dir.exists():
            for file_path in self.input_dir.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                    files.append(file_path)
        
        return files

    def process_all_files(self):
        """Process all files in the input directory."""
        # Create output directory if it doesn't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Get all supported files
        files_to_process = self.get_supported_files()
        
        if not files_to_process:
            print(f"No supported files found in {self.input_dir}")
            print("Supported extensions: .txt, .md, .rst, .py, .js, .html, .css, .json, .xml, .csv, .log")
            return
        
        mode_label = "GAME GUIDES" if self.mode == "game_guides" else "BASE MEMORY"
        print(f"\n{'='*80}")
        print(f"PROCESSING {mode_label}")
        print(f"{'='*80}")
        print(f"Found {len(files_to_process)} files to process\n")
        
        successful_embeddings = 0
        failed_embeddings = 0
        
        for i, file_path in enumerate(files_to_process, 1):
            print(f"\n{'='*80}")
            print(f"Processing file {i}/{len(files_to_process)}: {file_path.name}")
            print(f"{'='*80}")
            
            try:
                # Generate output filename
                output_filename = f"{file_path.stem}_embeddings.json"
                output_path = self.output_dir / output_filename
                
                # Skip if embeddings already exist
                if output_path.exists():
                    print(f"Embeddings already exist for {file_path.name}, skipping...")
                    continue
                
                # Process document
                embeddings_data = self.embed_document(file_path)
                self.save_embeddings(embeddings_data, output_path)
                
                print(f"\n[SUCCESS] Successfully processed {file_path.name}")
                print(f"  Output: {output_path}")
                print(f"  Total chunks: {embeddings_data['total_chunks']}")
                print(f"  Successful embeddings: {len(embeddings_data['chunks'])}")
                
                successful_embeddings += 1
                
            except Exception as e:
                print(f"\n[ERROR] Error processing {file_path.name}: {e}")
                failed_embeddings += 1
        
        print(f"\n{'='*80}")
        print(f"BATCH PROCESSING COMPLETE - {mode_label}")
        print(f"{'='*80}")
        print(f"Total files processed: {len(files_to_process)}")
        print(f"Successful embeddings: {successful_embeddings}")
        print(f"Failed embeddings: {failed_embeddings}")
        print(f"Input directory: {self.input_dir}")
        print(f"Output directory: {self.output_dir}")
        print(f"{'='*80}\n")


def main():
    parser = argparse.ArgumentParser(
        description='Embed documents for RAG system'
    )
    parser.add_argument(
        '--game-guides',
        action='store_true',
        help='Process game guide files'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Process both base memory and game guides'
    )
    
    args = parser.parse_args()
    
    # Determine which modes to run
    modes = []
    if args.all:
        modes = ["base", "game_guides"]
    elif args.game_guides:
        modes = ["game_guides"]
    else:
        modes = ["base"]
    
    for mode in modes:
        try:
            embedder = DocumentEmbedder(mode=mode)
            
            # Check if input directory exists
            if not embedder.input_dir.exists():
                print(f"Error: Input directory {embedder.input_dir} does not exist")
                if mode == "game_guides":
                    print(f"Creating game guides directory: {embedder.input_dir}")
                    embedder.input_dir.mkdir(parents=True, exist_ok=True)
                    print("Please add your game guide .md files to this directory and run again.")
                continue
            
            # Check if Ollama is running
            try:
                response = requests.get(f"{embedder.ollama_url}/api/tags", timeout=5)
                response.raise_for_status()
            except:
                print("Error: Cannot connect to Ollama. Please ensure Ollama is running.")
                print("Start Ollama with: ollama serve")
                sys.exit(1)
            
            # Check if embedding model is available
            try:
                test_embedding = embedder.get_embedding("test")
                if not test_embedding:
                    print(f"Error: Cannot use embedding model '{embedder.embed_model}'")
                    print(f"Please pull the model with: ollama pull {embedder.embed_model}")
                    sys.exit(1)
            except:
                print(f"Error: Embedding model '{embedder.embed_model}' not available")
                print(f"Please pull the model with: ollama pull {embedder.embed_model}")
                sys.exit(1)
            
            # Process all files
            embedder.process_all_files()
            
        except Exception as e:
            print(f"Error processing {mode}: {e}")
            continue


if __name__ == "__main__":
    main()