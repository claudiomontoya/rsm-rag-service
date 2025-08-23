from __future__ import annotations
import re
from typing import List

def strip_html(text: str) -> str:
    """Remove HTML tags from markup."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def strip_markdown(text: str) -> str:
    """Simplistic markdown cleaner."""
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"`{1,3}[^`]+`{1,3}", " ", text)
    text = re.sub(r"[*_#>-]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def simple_word_split(text: str, chunk_size: int = 500) -> List[str]:
    """Split text into chunks by word count."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
    return chunks if chunks else [""]