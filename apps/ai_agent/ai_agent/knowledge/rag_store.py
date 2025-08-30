from __future__ import annotations
import os, hashlib
from dataclasses import dataclass
from typing import List, Dict, Any
import chromadb
from chromadb.utils import embedding_functions

def _hash_id(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()

@dataclass
class KBConfig:
    path: str
    collection: str = "frappe_docs"
    model: str = "sentence-transformers/all-MiniLM-L6-v2"

class RAGStore:
    """
    Simple wrapper around Chroma PersistentClient.
    Works with chromadb>=1.0.20 (no 'ids' in include).
    """
    def __init__(self, cfg: KBConfig):
        self.cfg = cfg
        os.makedirs(cfg.path, exist_ok=True)
        self.client = chromadb.PersistentClient(path=cfg.path)
        self.ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=cfg.model)
        self.col = self.client.get_or_create_collection(
            name=cfg.collection,
            embedding_function=self.ef,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(self, batch: List[tuple[str, str, Dict[str, Any]]]) -> None:
        """
        batch: list of (id, text, metadata)
        """
        if not batch:
            return
        ids = [b[0] for b in batch]
        docs = [b[1] for b in batch]
        metas = [b[2] for b in batch]
        self.col.upsert(ids=ids, documents=docs, metadatas=metas)

    def query(self, text: str, k: int = 6) -> List[Dict[str, Any]]:
        """
        Returns flat hits: [{text, source, metadata, distance}, ...]
        """
        res = self.col.query(
            query_texts=[text],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]
        hits: List[Dict[str, Any]] = []
        for doc, meta, dist in zip(docs, metas, dists):
            hits.append({
                "text": doc,
                "source": meta.get("source", ""),
                "metadata": meta,
                "distance": float(dist),
            })
        return hits
