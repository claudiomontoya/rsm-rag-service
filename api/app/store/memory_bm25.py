from __future__ import annotations
import re
from typing import List, Dict, Any
from rank_bm25 import BM25Okapi

class InMemoryBM25:
    """In-memory BM25 index for keyword search."""
    
    def __init__(self):
        self.documents: List[Dict[str, Any]] = []
        self.tokenized_docs: List[List[str]] = []
        self.bm25: BM25Okapi | None = None
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization."""
        words = re.findall(r'\b\w+\b', text.lower())
        return words
    
    def add_documents(self, texts: List[str], metadata: List[Dict[str, Any]] = None) -> None:
        """Add documents to BM25 index."""
        if metadata is None:
            metadata = [{"page": i+1} for i in range(len(texts))]
        
        for text, meta in zip(texts, metadata):
            doc = {"text": text, **meta}
            self.documents.append(doc)
            self.tokenized_docs.append(self._tokenize(text))

        if self.tokenized_docs:
            self.bm25 = BM25Okapi(self.tokenized_docs)
    
    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search documents using BM25."""
        if not self.bm25 or not self.documents:
            return []
        
        tokenized_query = self._tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        
        results = []
        for idx in top_indices:
            if scores[idx] > 0: 
                doc = self.documents[idx].copy()
                doc["score"] = float(scores[idx])
                results.append(doc)
        
        return results
    
    def clear(self) -> None:
        """Clear the index."""
        self.documents.clear()
        self.tokenized_docs.clear()
        self.bm25 = None

bm25_index = InMemoryBM25()