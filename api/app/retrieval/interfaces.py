from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class Retriever(ABC):
    """Base interface for all retrieval strategies."""
    
    @abstractmethod
    async def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant documents."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return retriever name."""
        pass