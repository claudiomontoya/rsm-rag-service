from __future__ import annotations
import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from app.obs.logging_setup import get_logger

logger = get_logger(__name__)

@dataclass
class SemanticChunk:
    """Semantic chunk with metadata."""
    text: str
    title: Optional[str] = None
    section: Optional[str] = None
    page: Optional[int] = None
    chunk_index: int = 0
    word_count: int = 0
    metadata: Dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.word_count == 0:
            self.word_count = len(self.text.split())

class SemanticChunker:
    """Advanced semantic chunking with title bubbling."""
    
    def __init__(
        self,
        chunk_size: int = 800,
        chunk_overlap: int = 200,
        respect_boundaries: bool = True,
        enable_title_bubbling: bool = True
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.respect_boundaries = respect_boundaries
        self.enable_title_bubbling = enable_title_bubbling
        
        # Patterns for different content types
        self.html_title_pattern = re.compile(r'<h([1-6])[^>]*>(.*?)</h[1-6]>', re.IGNORECASE)
        self.md_title_pattern = re.compile(r'^(#{1,6})\s+(.+?)$', re.MULTILINE)
        self.sentence_boundary = re.compile(r'(?<=[.!?])\s+')
        self.paragraph_boundary = re.compile(r'\n\s*\n')
    
    def chunk_text(self, text: str, document_type: str = "text") -> List[SemanticChunk]:
        """Main chunking method with semantic awareness."""
        
        logger.info(f"Starting semantic chunking", 
                   text_length=len(text), 
                   document_type=document_type)
        
        if document_type == "html":
            return self._chunk_html(text)
        elif document_type == "markdown":
            return self._chunk_markdown(text)
        else:
            return self._chunk_plain_text(text)
    
    def _chunk_html(self, html: str) -> List[SemanticChunk]:
        """Chunk HTML content with title bubbling."""
        
        # Extract title hierarchy
        titles = self._extract_html_titles(html)
        
        # Clean HTML but preserve structure markers
        cleaned = self._clean_html_preserve_structure(html)
        
        # Split by sections if titles found
        if titles and self.enable_title_bubbling:
            return self._chunk_by_sections(cleaned, titles)
        else:
            return self._chunk_plain_text(cleaned)
    
    def _chunk_markdown(self, markdown: str) -> List[SemanticChunk]:
        """Chunk Markdown content with title bubbling."""
        
        # Extract title hierarchy
        titles = self._extract_markdown_titles(markdown)
        
        # Clean markdown but preserve structure
        cleaned = self._clean_markdown_preserve_structure(markdown)
        
        # Split by sections if titles found
        if titles and self.enable_title_bubbling:
            return self._chunk_by_sections(cleaned, titles)
        else:
            return self._chunk_plain_text(cleaned)
    
    def _chunk_plain_text(self, text: str) -> List[SemanticChunk]:
        """Chunk plain text with sentence/paragraph awareness."""
        
        if self.respect_boundaries:
            # Try paragraph-aware chunking first
            paragraphs = self.paragraph_boundary.split(text)
            if len(paragraphs) > 1:
                return self._chunk_by_paragraphs(paragraphs)
        
        # Fall back to sentence-aware chunking
        return self._chunk_by_sentences(text)
    
    def _extract_html_titles(self, html: str) -> List[Tuple[int, str, int]]:
        """Extract HTML titles with their positions and levels."""
        titles = []
        for match in self.html_title_pattern.finditer(html):
            level = int(match.group(1))
            title_text = re.sub(r'<[^>]+>', '', match.group(2)).strip()
            position = match.start()
            titles.append((level, title_text, position))
        return sorted(titles, key=lambda x: x[2])  # Sort by position
    
    def _extract_markdown_titles(self, markdown: str) -> List[Tuple[int, str, int]]:
        """Extract Markdown titles with their positions and levels."""
        titles = []
        for match in self.md_title_pattern.finditer(markdown):
            level = len(match.group(1))  # Count # characters
            title_text = match.group(2).strip()
            position = match.start()
            titles.append((level, title_text, position))
        return sorted(titles, key=lambda x: x[2])  # Sort by position
    
    def _clean_html_preserve_structure(self, html: str) -> str:
        """Clean HTML while preserving structural information."""
        # Replace headers with marked text
        html = self.html_title_pattern.sub(r'[TITLE_L\1] \2 [/TITLE]', html)
        
        # Remove other tags
        html = re.sub(r'<script.*?>.*?</script>', '', html, flags=re.DOTALL)
        html = re.sub(r'<style.*?>.*?</style>', '', html, flags=re.DOTALL)
        html = re.sub(r'<[^>]+>', ' ', html)
        
        # Clean up whitespace
        html = re.sub(r'\s+', ' ', html)
        
        return html.strip()
    
    def _clean_markdown_preserve_structure(self, markdown: str) -> str:
        """Clean Markdown while preserving structural information."""
        # Replace headers with marked text
        markdown = self.md_title_pattern.sub(r'[TITLE_L\1] \2 [/TITLE]', markdown)
        
        # Clean other markdown syntax
        markdown = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', markdown)  # Links
        markdown = re.sub(r'`{1,3}[^`]+`{1,3}', ' ', markdown)  # Code
        markdown = re.sub(r'[*_]{1,3}([^*_]+)[*_]{1,3}', r'\1', markdown)  # Emphasis
        
        # Clean up whitespace
        markdown = re.sub(r'\s+', ' ', markdown)
        
        return markdown.strip()
    
    def _chunk_by_sections(self, text: str, titles: List[Tuple[int, str, int]]) -> List[SemanticChunk]:
        """Chunk text by sections defined by titles."""
        chunks = []
        
        # Find title markers in cleaned text
        title_positions = []
        for level, title, _ in titles:
            pattern = rf'\[TITLE_L{level}\]\s*{re.escape(title)}\s*\[/TITLE\]'
            match = re.search(pattern, text)
            if match:
                title_positions.append((match.start(), match.end(), level, title))
        
        title_positions.sort()  # Sort by position in cleaned text
        
        # Create sections
        sections = []
        for i, (start, end, level, title) in enumerate(title_positions):
            section_start = end  # Start after title
            section_end = title_positions[i + 1][0] if i + 1 < len(title_positions) else len(text)
            
            section_text = text[section_start:section_end].strip()
            if section_text:
                sections.append((title, level, section_text))
        
        # If no clear sections, add all text
        if not sections:
            sections = [(None, 0, text)]
        
        # Chunk each section
        chunk_index = 0
        for section_title, section_level, section_text in sections:
            # Build title hierarchy for bubbling
            current_titles = []
            if self.enable_title_bubbling:
                # Find all parent titles
                for level, title, _ in titles:
                    if level <= section_level:
                        current_titles.append(title)
                if section_title and section_title not in current_titles:
                    current_titles.append(section_title)
            
            # Chunk the section text
            section_chunks = self._chunk_text_simple(section_text)
            
            for chunk_text in section_chunks:
                # Add title context if bubbling enabled
                if self.enable_title_bubbling and current_titles:
                    title_context = " > ".join(current_titles[-2:])  # Last 2 levels
                    enhanced_text = f"[Context: {title_context}]\n\n{chunk_text}"
                else:
                    enhanced_text = chunk_text
                
                chunks.append(SemanticChunk(
                    text=enhanced_text,
                    title=section_title,
                    section=" > ".join(current_titles) if current_titles else None,
                    chunk_index=chunk_index,
                    metadata={
                        "section_level": section_level,
                        "has_title_context": self.enable_title_bubbling and bool(current_titles)
                    }
                ))
                chunk_index += 1
        
        logger.info(f"Semantic chunking completed", 
                   chunks_created=len(chunks),
                   sections_found=len(sections))
        
        return chunks
    
    def _chunk_by_paragraphs(self, paragraphs: List[str]) -> List[SemanticChunk]:
        """Chunk by combining paragraphs up to size limit."""
        chunks = []
        current_chunk = []
        current_size = 0
        chunk_index = 0
        
        for paragraph in paragraphs:
            para_words = len(paragraph.split())
            
            if current_size + para_words > self.chunk_size and current_chunk:
                # Create chunk from accumulated paragraphs
                chunk_text = "\n\n".join(current_chunk)
                chunks.append(SemanticChunk(
                    text=chunk_text,
                    chunk_index=chunk_index,
                    word_count=current_size
                ))
                chunk_index += 1
                
                # Start new chunk with overlap
                if self.chunk_overlap > 0:
                    overlap_text = chunk_text[-self.chunk_overlap:]
                    current_chunk = [overlap_text, paragraph]
                    current_size = len(overlap_text.split()) + para_words
                else:
                    current_chunk = [paragraph]
                    current_size = para_words
            else:
                current_chunk.append(paragraph)
                current_size += para_words
        
        # Add final chunk
        if current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            chunks.append(SemanticChunk(
                text=chunk_text,
                chunk_index=chunk_index,
                word_count=current_size
            ))
        
        return chunks
    
    def _chunk_by_sentences(self, text: str) -> List[SemanticChunk]:
        """Chunk by combining sentences up to size limit."""
        sentences = self.sentence_boundary.split(text)
        chunks = []
        current_chunk = []
        current_size = 0
        chunk_index = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            sent_words = len(sentence.split())
            
            if current_size + sent_words > self.chunk_size and current_chunk:
                # Create chunk
                chunk_text = " ".join(current_chunk)
                chunks.append(SemanticChunk(
                    text=chunk_text,
                    chunk_index=chunk_index,
                    word_count=current_size
                ))
                chunk_index += 1
                
                # Start new chunk with overlap
                if self.chunk_overlap > 0 and len(current_chunk) > 1:
                    overlap_sentences = current_chunk[-2:]  # Last 2 sentences
                    overlap_size = sum(len(s.split()) for s in overlap_sentences)
                    current_chunk = overlap_sentences + [sentence]
                    current_size = overlap_size + sent_words
                else:
                    current_chunk = [sentence]
                    current_size = sent_words
            else:
                current_chunk.append(sentence)
                current_size += sent_words
        
        # Add final chunk
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            chunks.append(SemanticChunk(
                text=chunk_text,
                chunk_index=chunk_index,
                word_count=current_size
            ))
        
        return chunks
    
    def _chunk_text_simple(self, text: str) -> List[str]:
        """Simple text chunking for section content."""
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), self.chunk_size - self.chunk_overlap):
            chunk_words = words[i:i + self.chunk_size]
            chunks.append(" ".join(chunk_words))
        
        return chunks

# Global semantic chunker instance
semantic_chunker = SemanticChunker(
    chunk_size=800,
    chunk_overlap=200,
    respect_boundaries=True,
    enable_title_bubbling=True
)