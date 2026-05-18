# Filename: BASE/recall/embed_guide.py
"""
Game Guide Embedding Script for RAG System
Processes guide files in personality/base_memory/game_guides/
and saves embeddings to personality/base_memory/game_guides/embeddings/

Usage: python embed_guide.py
"""

import sys
import json
import requests
from typing import List, Dict, Any
import hashlib
import re
from pathlib import Path


class GuideEmbedder:
    """Batch game guide embedding for RAG system"""

    __slots__ = ('ollama_url', 'embed_model', 'input_dir', 'output_dir')

    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_url = ollama_url
        self.embed_model = "nomic-embed-text"

        script_dir = Path(__file__).parent
        base_dir = script_dir.parent.parent

        self.input_dir = base_dir / "personality" / "base_memory" / "game_guides"
        self.output_dir = base_dir / "personality" / "base_memory" / "game_guides" / "embeddings"

    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        lines = text.split('\n')
        cleaned_lines = [re.sub(r' {2,}', ' ', line) for line in lines]
        text = '\n'.join(cleaned_lines)

        if len(text) <= chunk_size:
            return [text.strip()]

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size

            if end < len(text):
                para_break = text.rfind('\n\n', start, end)
                if para_break > start + chunk_size // 3:
                    end = para_break + 2
                else:
                    line_break = text.rfind('\n', start, end)
                    if line_break > start + chunk_size // 3:
                        end = line_break + 1
                    else:
                        sentence_end = max(
                            text.rfind('. ', start, end),
                            text.rfind('! ', start, end),
                            text.rfind('? ', start, end)
                        )
                        if sentence_end > start + chunk_size // 2:
                            end = sentence_end + 2
                        else:
                            word_end = text.rfind(' ', start, end)
                            if word_end > start + chunk_size // 2:
                                end = word_end + 1

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - overlap
            if start >= len(text):
                break

        return chunks

    def get_embedding(self, text: str) -> List[float]:
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

    def load_document(self, filepath: Path) -> str:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            for encoding in ['latin-1', 'cp1252', 'utf-16']:
                try:
                    with open(filepath, 'r', encoding=encoding) as f:
                        return f.read()
                except UnicodeDecodeError:
                    continue
            raise Exception(f"Unable to decode file {filepath}")

    def extract_game_metadata(self, filepath: Path, content: str) -> Dict[str, Any]:
        metadata = {
            'type': 'game_guide',
            'game_name': filepath.stem,
            'sections': []
        }

        lines = content.split('\n')
        for line in lines[:10]:
            if line.startswith('# '):
                metadata['game_name'] = line[2:].strip()
                break

        for line in lines:
            if line.startswith('## '):
                metadata['sections'].append(line[3:].strip())

        return metadata

    def embed_document(self, filepath: Path) -> Dict[str, Any]:
        if not filepath.exists():
            raise FileNotFoundError(f"File {filepath} not found")

        print(f"Loading guide: {filepath.name}")
        text = self.load_document(filepath)
        print(f"Loaded. Length: {len(text)} characters")

        doc_metadata = self.extract_game_metadata(filepath, text)
        print(f"Game: {doc_metadata['game_name']}")
        print(f"Sections: {len(doc_metadata['sections'])}")

        print("Chunking...")
        chunks = self.chunk_text(text)
        print(f"Created {len(chunks)} chunks")

        print("Creating embeddings...")
        embeddings_data = {
            "source_file": str(filepath),
            "total_chunks": len(chunks),
            "embed_model": self.embed_model,
            "metadata": doc_metadata,
            "chunks": []
        }

        for i, chunk in enumerate(chunks):
            print(f"Processing chunk {i+1}/{len(chunks)}")
            embedding = self.get_embedding(chunk)

            if embedding:
                embeddings_data["chunks"].append({
                    "id": i,
                    "text": chunk,
                    "embedding": embedding,
                    "hash": hashlib.md5(chunk.encode()).hexdigest(),
                    "metadata": {
                        "type": "game_guide",
                        "game_name": doc_metadata['game_name'],
                        "source_file": filepath.name
                    }
                })
            else:
                print(f"Failed to get embedding for chunk {i+1}")

        return embeddings_data

    def save_embeddings(self, embeddings_data: Dict[str, Any], output_file: Path):
        print(f"Saving embeddings to {output_file}")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(embeddings_data, f, indent=2)
        print("Saved successfully!")

    def get_supported_files(self) -> List[Path]:
        supported_extensions = {'.txt', '.md', '.rst', '.html', '.csv', '.log'}
        if not self.input_dir.exists():
            return []
        return [
            f for f in self.input_dir.iterdir()
            if f.is_file() and f.suffix.lower() in supported_extensions
        ]

    def process_all_files(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)

        files_to_process = self.get_supported_files()

        if not files_to_process:
            print(f"No supported files found in {self.input_dir}")
            print("Supported extensions: .txt, .md, .rst, .html, .csv, .log")
            return

        print(f"\n{'='*80}")
        print("PROCESSING GAME GUIDES")
        print(f"{'='*80}")
        print(f"Found {len(files_to_process)} files to process\n")

        successful = 0
        failed = 0

        for i, file_path in enumerate(files_to_process, 1):
            print(f"\n{'='*80}")
            print(f"Processing file {i}/{len(files_to_process)}: {file_path.name}")
            print(f"{'='*80}")

            try:
                output_path = self.output_dir / f"{file_path.stem}_embeddings.json"

                if output_path.exists():
                    print(f"Skipping {file_path.name}: embeddings already exist")
                    continue

                embeddings_data = self.embed_document(file_path)
                self.save_embeddings(embeddings_data, output_path)

                print(f"\n[Confirmed] Successfully processed {file_path.name}")
                print(f"  Output: {output_path}")
                print(f"  Game: {embeddings_data['metadata']['game_name']}")
                print(f"  Sections: {len(embeddings_data['metadata']['sections'])}")
                print(f"  Total chunks: {embeddings_data['total_chunks']}")
                print(f"  Successful embeddings: {len(embeddings_data['chunks'])}")

                successful += 1

            except Exception as e:
                print(f"\n[Warning] Error processing {file_path.name}: {e}")
                failed += 1

        print(f"\n{'='*80}")
        print("BATCH PROCESSING COMPLETE")
        print(f"{'='*80}")
        print(f"Total files found: {len(files_to_process)}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print(f"Input:  {self.input_dir}")
        print(f"Output: {self.output_dir}")
        print(f"{'='*80}\n")


def main():
    embedder = GuideEmbedder()

    if not embedder.input_dir.exists():
        print(f"Creating game guides directory: {embedder.input_dir}")
        embedder.input_dir.mkdir(parents=True, exist_ok=True)
        print("Add guide files (.md, .txt, etc.) to that directory and run again.")
        sys.exit(0)

    try:
        response = requests.get(f"{embedder.ollama_url}/api/tags", timeout=5)
        response.raise_for_status()
    except Exception:
        print("Error: Cannot connect to Ollama.")
        print("Start Ollama with: ollama serve")
        sys.exit(1)

    test = embedder.get_embedding("test")
    if not test:
        print(f"Error: Embedding model '{embedder.embed_model}' not available")
        print(f"Pull it with: ollama pull {embedder.embed_model}")
        sys.exit(1)

    embedder.process_all_files()


if __name__ == "__main__":
    main()