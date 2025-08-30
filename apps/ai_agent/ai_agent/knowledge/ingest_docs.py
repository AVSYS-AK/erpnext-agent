# -*- coding: utf-8 -*-
from __future__ import annotations
import os, re, ast, argparse
from pathlib import Path
from typing import List, Tuple, Dict, Any
from tqdm import tqdm
from markdown_it import MarkdownIt
from .rag_store import RAGStore, KBConfig, _hash_id

md = MarkdownIt()

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

def _chunk(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    parts = []
    i = 0
    n = len(text)
    while i < n:
        parts.append(text[i:i+size])
        i += size - overlap
    return parts

def _markdown_chunks(path: Path) -> List[Tuple[str, Dict[str, Any]]]:
    raw = _read_text(path)
    # simple: strip code fences to reduce noise
    stripped = re.sub(r"```.*?```", "", raw, flags=re.S)
    chunks = _chunk(stripped)
    out = []
    for idx, ch in enumerate(chunks):
        meta = {"source": str(path), "type":"md", "chunk": idx}
        out.append((ch, meta))
    return out

def _python_doc_chunks(path: Path) -> List[Tuple[str, Dict[str, Any]]]:
    raw = _read_text(path)
    try:
        tree = ast.parse(raw)
    except Exception:
        return []
    chunks = []
    # module docstring
    if (doc := ast.get_docstring(tree)):
        chunks.append((doc, {"source": str(path), "type":"py_doc", "symbol":"__module__"}))
    # functions & classes
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = getattr(node, "name", "?")
            doc = ast.get_docstring(node)
            if doc:
                text = f"{name}:\n{doc}"
                chunks.append((text, {"source": str(path), "type":"py_doc", "symbol": name}))
    # chunk if long
    out = []
    for idx, (txt, meta) in enumerate(chunks):
        for j, ch in enumerate(_chunk(txt)):
            m = dict(meta); m["chunk"] = j
            out.append((ch, m))
    return out

def gather_files(root_paths: List[str]) -> List[Path]:
    exts = {".md",".mdx",".markdown",".py"}
    files: List[Path] = []
    for rp in root_paths:
        rp = os.path.expanduser(rp)
        for p in Path(rp).rglob("*"):
            if p.suffix.lower() in exts and p.is_file():
                files.append(p)
    return files

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--paths", nargs="+", required=True, help="Folders containing Frappe/ERPNext docs or code")
    ap.add_argument("--kb-path", default=os.environ.get("AI_AGENT_KB_PATH", "~/.ai_agent_kb"))
    ap.add_argument("--collection", default="frappe_docs")
    args = ap.parse_args()

    cfg = KBConfig(path=os.path.expanduser(args.kb_path), collection=args.collection)
    store = RAGStore(cfg)
    files = gather_files(args.paths)

    print(f"Index path: {cfg.path} | collection: {cfg.collection}")
    print(f"Found {len(files)} files. Ingesting ...")

    docs = []
    for f in tqdm(files):
        chunks = _markdown_chunks(f) if f.suffix.lower() in {".md",".mdx",".markdown"} else _python_doc_chunks(f)
        for text, meta in chunks:
            doc_id = _hash_id(f"{meta['source']}::{meta.get('symbol','')}::{meta['chunk']}")
            docs.append((doc_id, text, meta))
        # Upsert in batches to keep memory low
        if len(docs) > 500:
            store.upsert(docs); docs = []
    if docs:
        store.upsert(docs)
    print("Done.")

if __name__ == "__main__":
    main()
