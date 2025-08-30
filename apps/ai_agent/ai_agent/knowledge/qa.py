from __future__ import annotations
import os
from typing import Dict, Any, List

try:
    import frappe
except Exception:
    frappe = None

from .rag_store import RAGStore, KBConfig
from ..llm_client import LLMClient

SYS_PROMPT = (
    "You are an ERPNext/Frappe expert. Answer concisely using ONLY the provided context. "
    "If the answer is not clearly in the context, say 'I don't know'. "
    "Prefer steps and exact ERPNext/Frappe terms when possible."
)

def _kb_path() -> str:
    # Prefer explicit env from caller (api.ask sets this). Else site path. Else local default.
    p = os.environ.get("AI_AGENT_KB_PATH")
    if not p and frappe:
        p = frappe.get_site_path("private", "files", "ai_kb")
    if not p:
        p = "./erp.local/private/files/ai_kb"
    os.makedirs(p, exist_ok=True)
    return p

def answer_question(question: str, top_k: int = 6) -> Dict[str, Any]:
    store = RAGStore(KBConfig(path=_kb_path()))
    hits = store.query(question, k=int(top_k))
    if not hits:
        return {"answer": "I don't know.", "sources": []}

    # Build compact context
    sources: List[str] = []
    ctx_parts: List[str] = []
    for h in hits:
        src = h.get("source", "")
        if src and src not in sources:
            sources.append(src)
        snippet = h.get("text", "")
        ctx_parts.append(f"[{src}] {snippet}")

    context = "\n\n".join(ctx_parts)
    # Keep context bounded for small local models
    if len(context) > 8000:
        context = context[:8000]

    user_prompt = f"Question: {question}\n\nContext:\n{context}\n\nAnswer:"
    llm = LLMClient()
    try:
        answer = llm.complete(system=SYS_PROMPT, user=user_prompt, streaming=False)
    except Exception:
        # Fallback: return the best snippet if LLM not reachable
        answer = hits[0].get("text", "")[:600]

    return {"answer": answer, "sources": sources[:top_k]}
