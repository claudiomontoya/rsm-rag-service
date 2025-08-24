from __future__ import annotations
import fitz  # PyMuPDF
import httpx
import magic
from typing import List, Dict, Optional
from app.obs.logging_setup import get_logger
from app.obs.decorators import traced

logger = get_logger(__name__)

class PDFExtractor:
    """PDF content extraction with error handling."""
    
    @traced("pdf_extract_from_bytes")
    def extract_from_bytes(self, pdf_bytes: bytes) -> str:
        """Extract text from PDF bytes."""
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            text_content = []
            
            for page_num in range(len(doc)):
                try:
                    page = doc.load_page(page_num)
                    text = page.get_text()
                    
                    if text.strip():
                        # Add page marker for chunking
                        text_content.append(f"[PAGE {page_num + 1}]\n{text}")
                        
                except Exception as e:
                    logger.warning(f"Failed to extract page {page_num + 1}: {e}")
                    continue
            
            doc.close()
            
            if not text_content:
                raise ValueError("No text content found in PDF")
            
            full_text = "\n\n".join(text_content)
            logger.info(f"PDF extracted successfully", 
                       pages=len(text_content), 
                       text_length=len(full_text))
            
            return full_text
            
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            raise ValueError(f"Failed to extract PDF content: {str(e)}")
    
    @traced("pdf_fetch_and_extract")
    async def fetch_and_extract(self, url: str) -> str:
        """Fetch PDF from URL and extract text."""
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(60.0),
                follow_redirects=True
            ) as client:
                
                logger.info(f"Fetching PDF from URL", url=url)
                response = await client.get(url)
                response.raise_for_status()
                
                # Verify content type
                content_type = response.headers.get("content-type", "")
                if not content_type.startswith("application/pdf"):
                    # Try to detect with magic
                    file_type = magic.from_buffer(response.content[:1024], mime=True)
                    if file_type != "application/pdf":
                        raise ValueError(f"URL does not contain PDF content: {content_type}")
                
                logger.info(f"PDF downloaded successfully", 
                           url=url, 
                           size_bytes=len(response.content))
                
                return self.extract_from_bytes(response.content)
                
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching PDF", url=url, error=str(e))
            raise
        except Exception as e:
            logger.error(f"Failed to fetch and extract PDF", url=url, error=str(e))
            raise
    
    def validate_pdf_content(self, content: str) -> str:
        """Validate and clean PDF content."""
        if not content or len(content.strip()) < 100:
            raise ValueError("PDF content too short or empty")
        
        # Basic cleaning
        content = content.replace('\x00', '')  # Remove null bytes
        content = content.replace('\r\n', '\n')  # Normalize line endings
        
        return content.strip()

# Global PDF extractor instance
pdf_extractor = PDFExtractor()