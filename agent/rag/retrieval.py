"""Document retrieval using BM25 for RAG."""

from pathlib import Path
from typing import List, Dict, Any
from rank_bm25 import BM25Okapi
import re


class DocumentChunk:
    """Represents a chunk of a document."""
    
    def __init__(self, id: str, content: str, source: str, score: float = 0.0):
        self.id = id
        self.content = content
        self.source = source
        self.score = score
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "source": self.source,
            "score": self.score
        }


class DocumentRetriever:
    """BM25-based document retriever."""
    
    def __init__(self, docs_dir: str = "docs"):
        self.docs_dir = Path(docs_dir)
        self.chunks: List[DocumentChunk] = []
        self.bm25 = None
        self._load_and_chunk_documents()
    
    def _load_and_chunk_documents(self):
        """Load all markdown files and chunk them."""
        if not self.docs_dir.exists():
            raise FileNotFoundError(f"Documents directory not found: {self.docs_dir}")
        
        for doc_path in self.docs_dir.glob("*.md"):
            self._chunk_document(doc_path)
        
        # Build BM25 index
        if self.chunks:
            tokenized_chunks = [self._tokenize(chunk.content) for chunk in self.chunks]
            self.bm25 = BM25Okapi(tokenized_chunks)
    
    def _chunk_document(self, doc_path: Path):
        """Chunk a single document by paragraphs/sections."""
        content = doc_path.read_text(encoding='utf-8')
        source = doc_path.stem  # filename without extension
        
        # Split by double newlines (paragraphs) or headers
        sections = re.split(r'\n\n+|\n(?=#)', content)
        
        chunk_id = 0
        for section in sections:
            section = section.strip()
            if section and len(section) > 20:  # Skip very short sections
                chunk = DocumentChunk(
                    id=f"{source}::chunk{chunk_id}",
                    content=section,
                    source=source
                )
                self.chunks.append(chunk)
                chunk_id += 1
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization for BM25."""
        # Lowercase and split on non-alphanumeric
        tokens = re.findall(r'\w+', text.lower())
        return tokens
    
    def retrieve(self, query: str, top_k: int = 3) -> List[DocumentChunk]:
        """
        Retrieve top-k most relevant chunks for a query.
        
        Args:
            query: Search query
            top_k: Number of chunks to return
            
        Returns:
            List of DocumentChunk with scores
        """
        if not self.chunks or not self.bm25:
            return []
        
        tokenized_query = self._tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)
        
        # Get top-k indices
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        
        # Create result chunks with scores
        results = []
        for idx in top_indices:
            chunk = self.chunks[idx]
            results.append(DocumentChunk(
                id=chunk.id,
                content=chunk.content,
                source=chunk.source,
                score=float(scores[idx])
            ))
        
        return results
    
    def get_chunk_by_id(self, chunk_id: str) -> DocumentChunk:
        """Get a specific chunk by ID."""
        for chunk in self.chunks:
            if chunk.id == chunk_id:
                return chunk
        return None