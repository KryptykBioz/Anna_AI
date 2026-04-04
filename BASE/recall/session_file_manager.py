# Filename: BASE/memory/session_file_manager.py
"""
Session File Manager - Temporary file reference system
Refactored for centralized architecture with dependency injection

Supports code files, PDFs, markdown, and other document types
Files are stored in memory only during the session
Fast keyword-based search without embedding
"""

import re
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime

from BASE.core.logger import Logger


class SessionFileManager:
    """Manages temporary session files without persistent storage"""
    
    __slots__ = (
        'logger', 'memory_manager', 'project_root', 'max_file_size_bytes',
        'session_files'
    )
    
    def __init__(
        self, 
        logger: Logger,
        memory_manager,
        project_root: Path,
        max_file_size_mb: float = 1.0
    ):
        self.logger = logger
        self.memory_manager = memory_manager
        self.project_root = project_root
        self.max_file_size_bytes = int(max_file_size_mb * 1024 * 1024)
        
        # In-memory file storage
        self.session_files: Dict[str, Dict[str, Any]] = {}
        
        self.logger.system("[SUCCESS] Session File Manager initialized")
        
    def add_file(self, filepath: str, content: str, file_type: str = "auto") -> Dict[str, Any]:
        """
        Add a file to session memory
        
        Args:
            filepath: Path to the file (used for identification)
            content: File content as string
            file_type: Type of file (auto, code, markdown, pdf, text)
            
        Returns:
            Dict with success status and metadata
        """
        # Validate file size
        content_size = len(content.encode('utf-8'))
        if content_size > self.max_file_size_bytes:
            error_msg = f'File too large: {content_size / 1024 / 1024:.2f}MB (max: {self.max_file_size_bytes / 1024 / 1024:.2f}MB)'
            self.logger.warning(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
        
        # Auto-detect file type if needed
        if file_type == "auto":
            file_type = self._detect_file_type(filepath, content)
        
        # Process file based on type
        file_data = self._process_file(filepath, content, file_type)
        
        # Store in session memory
        file_id = self._generate_file_id(filepath)
        self.session_files[file_id] = file_data
        
        result = {
            'success': True,
            'file_data': file_data,
            'file_id': file_id,
            'filename': Path(filepath).name,
            'file_type': file_type,
            'sections': len(file_data['sections']),
            'size_kb': round(content_size / 1024, 1),
            'line_count': file_data['line_count']
        }
        
        self.logger.system(
            f"📄 Added session file: {result['filename']} "
            f"({result['file_type']}, {result['size_kb']}KB, {result['sections']} sections)"
        )
        
        return result
    
    def _detect_file_type(self, filepath: str, content: str) -> str:
        """Detect file type from extension and content"""
        ext = Path(filepath).suffix.lower()
        
        # Code files
        code_extensions = {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.cs', 
                          '.go', '.rs', '.php', '.rb', '.swift', '.kt'}
        if ext in code_extensions:
            return 'code'
        
        # Document files
        if ext in {'.md', '.markdown'}:
            return 'markdown'
        elif ext == '.pdf':
            return 'pdf'
        elif ext in {'.txt', '.log'}:
            return 'text'
        elif ext in {'.json', '.xml', '.yaml', '.yml', '.toml'}:
            return 'data'
        
        # Fallback: check content
        if any(keyword in content for keyword in ['def ', 'class ', 'function ', 'import ', '#include']):
            return 'code'
        
        return 'text'
    
    def _process_file(self, filepath: str, content: str, file_type: str) -> Dict[str, Any]:
        """Process file and extract sections and keywords"""
        sections = []
        keywords = set()
        
        if file_type == 'code':
            sections = self._extract_code_sections(content, Path(filepath).suffix)
        elif file_type == 'markdown':
            sections = self._extract_markdown_sections(content)
        else:
            sections = self._extract_generic_sections(content)
        
        # Extract keywords from all sections
        for section in sections:
            section_keywords = self._extract_keywords(section['content'])
            keywords.update(section_keywords)
            section['keywords'] = list(section_keywords)
        
        return {
            'filepath': filepath,
            'filename': Path(filepath).name,
            'file_type': file_type,
            'content': content,
            'sections': sections,
            'keywords': list(keywords),
            'added_at': datetime.now().isoformat(),
            'line_count': len(content.split('\n'))
        }
    
    def _extract_code_sections(self, content: str, extension: str) -> List[Dict[str, Any]]:
        """Extract functions, classes, and logical blocks from code"""
        sections = []
        lines = content.split('\n')
        
        # Python-specific patterns
        if extension == '.py':
            current_section = None
            section_lines = []
            indent_level = 0
            
            for i, line in enumerate(lines):
                # Detect function or class definition
                if re.match(r'^(def |class |async def )', line.lstrip()):
                    # Save previous section if exists
                    if current_section:
                        sections.append({
                            'type': current_section['type'],
                            'name': current_section['name'],
                            'content': '\n'.join(section_lines),
                            'line_start': current_section['line_start'],
                            'line_end': i - 1
                        })
                    
                    # Start new section
                    match = re.match(r'^(def |class |async def )(\w+)', line.lstrip())
                    if match:
                        section_type = 'class' if 'class' in match.group(1) else 'function'
                        current_section = {
                            'type': section_type,
                            'name': match.group(2),
                            'line_start': i + 1
                        }
                        section_lines = [line]
                        indent_level = len(line) - len(line.lstrip())
                
                # Continue current section
                elif current_section:
                    # Check if still in same section (based on indentation)
                    stripped = line.lstrip()
                    if stripped and (len(line) - len(stripped)) <= indent_level:
                        # Section ended
                        sections.append({
                            'type': current_section['type'],
                            'name': current_section['name'],
                            'content': '\n'.join(section_lines),
                            'line_start': current_section['line_start'],
                            'line_end': i - 1
                        })
                        current_section = None
                        section_lines = []
                    else:
                        section_lines.append(line)
            
            # Add last section
            if current_section:
                sections.append({
                    'type': current_section['type'],
                    'name': current_section['name'],
                    'content': '\n'.join(section_lines),
                    'line_start': current_section['line_start'],
                    'line_end': len(lines)
                })
        
        # Generic code sections (for other languages)
        else:
            sections = self._extract_generic_sections(content)
        
        return sections
    
    def _extract_markdown_sections(self, content: str) -> List[Dict[str, Any]]:
        """Extract sections from markdown based on headers"""
        sections = []
        lines = content.split('\n')
        current_section = None
        section_lines = []
        
        for i, line in enumerate(lines):
            # Detect header
            header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if header_match:
                # Save previous section
                if current_section:
                    sections.append({
                        'type': 'section',
                        'name': current_section['name'],
                        'level': current_section['level'],
                        'content': '\n'.join(section_lines),
                        'line_start': current_section['line_start'],
                        'line_end': i - 1
                    })
                
                # Start new section
                level = len(header_match.group(1))
                name = header_match.group(2)
                current_section = {
                    'name': name,
                    'level': level,
                    'line_start': i + 1
                }
                section_lines = [line]
            elif current_section:
                section_lines.append(line)
        
        # Add last section
        if current_section:
            sections.append({
                'type': 'section',
                'name': current_section['name'],
                'level': current_section['level'],
                'content': '\n'.join(section_lines),
                'line_start': current_section['line_start'],
                'line_end': len(lines)
            })
        
        return sections
    
    def _extract_generic_sections(self, content: str, chunk_size: int = 500) -> List[Dict[str, Any]]:
        """Extract generic text sections by chunking"""
        sections = []
        lines = content.split('\n')
        current_chunk = []
        current_size = 0
        chunk_number = 1
        line_start = 1
        
        for i, line in enumerate(lines):
            current_chunk.append(line)
            current_size += len(line)
            
            if current_size >= chunk_size or i == len(lines) - 1:
                sections.append({
                    'type': 'chunk',
                    'name': f'Section {chunk_number}',
                    'content': '\n'.join(current_chunk),
                    'line_start': line_start,
                    'line_end': i + 1
                })
                current_chunk = []
                current_size = 0
                chunk_number += 1
                line_start = i + 2
        
        return sections
    
    def _extract_keywords(self, text: str, min_length: int = 3, max_keywords: int = 50) -> set:
        """Extract relevant keywords from text"""
        # Remove special characters and split
        words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', text.lower())
        
        # Common stop words to exclude
        stop_words = {
            'the', 'is', 'at', 'which', 'on', 'and', 'or', 'but', 'in', 'with',
            'a', 'an', 'as', 'for', 'of', 'to', 'from', 'by', 'this', 'that',
            'if', 'else', 'then', 'return', 'def', 'class', 'import', 'from'
        }
        
        # Filter and count
        word_counts = {}
        for word in words:
            if len(word) >= min_length and word not in stop_words:
                word_counts[word] = word_counts.get(word, 0) + 1
        
        # Get top keywords
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        return {word for word, count in sorted_words[:max_keywords]}
    
    def _truncate_text(self, text: str, max_length: int = 1000) -> str:
        """
        Truncate text at natural boundary with max_length limit
        
        Args:
            text: Text to truncate
            max_length: Maximum character limit (default 1000)
        
        Returns:
            Truncated text with [...] suffix if truncated
        """
        if len(text) <= max_length:
            return text
        
        truncated = text[:max_length]
        
        # Try to break at paragraph
        para_break = truncated.rfind('\n\n')
        if para_break > max_length * 0.6:
            return text[:para_break].strip() + "\n\n[...]"
        
        # Try to break at line
        line_break = truncated.rfind('\n')
        if line_break > max_length * 0.7:
            return text[:line_break].strip() + "\n[...]"
        
        # Try to break at sentence
        sentence_ends = [truncated.rfind('.'), truncated.rfind('!'), truncated.rfind('?')]
        last_sentence = max(sentence_ends)
        if last_sentence > max_length * 0.7:
            return text[:last_sentence + 1].strip() + " [...]"
        
        # Break at word
        last_space = truncated.rfind(' ')
        if last_space > 0:
            return text[:last_space].strip() + " [...]"
        
        return truncated.strip() + " [...]"
    
    def search(self, query: str, file_id: Optional[str] = None, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for relevant sections in session files
        
        Args:
            query: Search query
            file_id: Specific file to search (None = search all)
            top_k: Number of top results to return
            
        Returns:
            List of relevant sections with scores (content truncated to 1000 chars)
        """
        query_keywords = self._extract_keywords(query.lower())
        results = []
        
        # Determine which files to search
        files_to_search = {file_id: self.session_files[file_id]} if file_id else self.session_files
        
        for fid, file_data in files_to_search.items():
            for section in file_data['sections']:
                # Calculate relevance score
                section_keywords = set(section.get('keywords', []))
                keyword_overlap = len(query_keywords & section_keywords)
                
                # Also check for direct text match
                text_match = sum(1 for kw in query_keywords if kw in section['content'].lower())
                
                score = keyword_overlap * 2 + text_match
                
                if score > 0:
                    # [Changed] Truncate content to 1000 chars
                    truncated_content = self._truncate_text(section['content'], 1000)
                    
                    results.append({
                        'file_id': fid,
                        'filename': file_data['filename'],
                        'section_name': section['name'],
                        'section_type': section['type'],
                        'content': truncated_content,
                        'line_start': section['line_start'],
                        'line_end': section['line_end'],
                        'score': score
                    })
        
        # Sort by score and return top k
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:top_k]
    
    def get_file_summary(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get summary information about a file"""
        if file_id not in self.session_files:
            return None
        
        file_data = self.session_files[file_id]
        return {
            'filename': file_data['filename'],
            'file_type': file_data['file_type'],
            'line_count': file_data['line_count'],
            'sections': len(file_data['sections']),
            'added_at': file_data['added_at'],
            'size_kb': len(file_data['content']) / 1024
        }
    
    def get_file_content(self, file_id: str, line_start: Optional[int] = None, 
                        line_end: Optional[int] = None) -> Optional[str]:
        """Get full or partial file content"""
        if file_id not in self.session_files:
            return None
        
        content = self.session_files[file_id]['content']
        
        if line_start is not None or line_end is not None:
            lines = content.split('\n')
            start = (line_start - 1) if line_start else 0
            end = line_end if line_end else len(lines)
            return '\n'.join(lines[start:end])
        
        return content
    
    def list_files(self) -> List[Dict[str, Any]]:
        """List all session files with summaries"""
        return [
            {
                'file_id': fid,
                **(self.get_file_summary(fid) or {})
            }
            for fid in self.session_files
        ]
    
    def remove_file(self, file_id: str) -> bool:
        """Remove a file from session memory"""
        if file_id in self.session_files:
            filename = self.session_files[file_id]['filename']
            del self.session_files[file_id]
            self.logger.system(f"Removed session file: {filename}")
            return True
        return False
    
    def clear_all(self):
        """Clear all session files"""
        count = len(self.session_files)
        self.session_files.clear()
        if count > 0:
            self.logger.system(f"Cleared {count} session file(s)")
    
    def _generate_file_id(self, filepath: str) -> str:
        """Generate unique file ID from filepath"""
        import hashlib
        return hashlib.md5(filepath.encode()).hexdigest()[:12]
    
    def get_context_for_query(self, query: str, max_lines: int = 200) -> str:
        """
        Get formatted context for AI query
        
        Args:
            query: User query
            max_lines: Maximum lines to include in context
            
        Returns:
            Formatted context string
        """
        if not self.session_files:
            return ""
        
        # If no query, provide file summaries
        if not query or not query.strip():
            context_lines = ["## SESSION FILES (Available Reference Documents)"]
            for fid, file_data in self.session_files.items():
                summary = self.get_file_summary(fid)
                if not summary:
                    # Fallback to file_data if summary is missing
                    summary = {
                        'filename': file_data.get('filename', Path(fid).name),
                        'file_type': file_data.get('file_type', 'unknown'),
                        'line_count': file_data.get('line_count', 0),
                        'sections': len(file_data.get('sections', []))
                    }
                context_lines.append(f"\n**{summary['filename']}** ({summary['file_type']})")
                context_lines.append(f"  - {summary['line_count']} lines, {summary['sections']} sections")
            return "\n".join(context_lines)
        
        # Search for relevant sections
        results = self.search(query, top_k=10)
        
        if not results:
            # No relevant results, provide file summaries
            context_lines = ["## SESSION FILES (No specific matches, available files:)"]
            for fid, file_data in self.session_files.items():
                summary = self.get_file_summary(fid)
                if not summary:
                    summary = {
                        'filename': file_data.get('filename', Path(fid).name),
                        'file_type': file_data.get('file_type', 'unknown'),
                        'line_count': file_data.get('line_count', 0),
                        'sections': len(file_data.get('sections', []))
                    }
                context_lines.append(f"\n**{summary['filename']}** ({summary['file_type']})")
                context_lines.append(f"  - {summary['line_count']} lines, {summary['sections']} sections")
            return "\n".join(context_lines)
        
        # Format relevant results
        context_lines = ["## RELEVANT CODE/DOCUMENTATION (From Session Files)"]
        total_lines = 0
        
        for result in results:
            # Add section header
            context_lines.append(f"\n### {result['filename']} - {result['section_name']}")
            context_lines.append(f"*Lines {result['line_start']}-{result['line_end']} (relevance: {result['score']})*")
            context_lines.append("```")
            
            # [Changed] Content is already truncated to 1000 chars by search()
            # Add additional line limit for extremely long single-line content
            section_content = result['content']
            section_lines = section_content.split('\n')
            lines_to_add = min(len(section_lines), max_lines - total_lines)
            
            context_lines.extend(section_lines[:lines_to_add])
            context_lines.append("```")
            
            total_lines += lines_to_add
            
            if total_lines >= max_lines:
                context_lines.append("\n*[Additional content truncated to save context space]*")
                break
        
        return "\n".join(context_lines)
    
    # ========================================================================
    # STATISTICS (For GUI)
    # ========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get session file statistics"""
        total_size = sum(len(fd['content']) for fd in self.session_files.values())
        total_sections = sum(len(fd['sections']) for fd in self.session_files.values())
        
        return {
            'file_count': len(self.session_files),
            'total_size_kb': total_size / 1024,
            'total_sections': total_sections,
            'files': self.list_files()
        }