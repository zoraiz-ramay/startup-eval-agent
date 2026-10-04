"""Semantic + word search over siemens_tools.csv, for the two places that shortlist tools.

Both the fit stage and the Empower pillar show the model a shortlist of the 2,923-row catalog, and
both used to build it from word overlap alone. Measured on Wandelbots (robot programming and
simulation), the 20 tools Empower was shown left out Tecnomatix, Process Simulate, Plant Simulation,
SIMIT and PLCSIM Advanced — Siemens' own simulation and virtual-commissioning tools — while
including an IEC 62443 certification and a cybersecurity service that shared the word "industrial".
A model cannot recommend a tool it never sees.

So the shortlist is now a reciprocal-rank fusion of two rankings:
- semantic: each tool's text embedded ONCE into data/tool_index/ (scripts/build_tool_index.py), the
  startup embedded once per run, ranked by cosine similarity — "robot programming" now finds
  "virtual commissioning of robotic processes";
- words: the existing overlap scores, so an exact product name the startup mentions still ranks.

When the provider cannot embed, the index is missing, or it was built for a different catalog or
model, the ranking is words alone and ``method`` says so — never silently.

The same machinery indexes the Xcelerator sellers (data/xcelerator_index/), for Connect's question
"is this offering already in the ecosystem?", and every department's stated needs from the
requirements workbook (data/needs_index/), so Collaborate puts the needs a startup actually answers
in front of the model first — Mobility states 33, and word overlap picked the 15 it was shown.
A catalog is told apart by its ``name``; one without a name is the tools catalog.
"""
from __future__ import annotations

import json
import logging
import os
import pathlib
import threading

from .config import BASE_DIR

log = logging.getLogger(__name__)

INDEX_DIR = pathlib.Path(os.getenv("TOOL_INDEX_DIR", str(pathlib.Path(BASE_DIR) / "tool_index")))
XCELERATOR_INDEX_DIR = pathlib.Path(os.getenv("XCELERATOR_INDEX_DIR", str(pathlib.Path(BASE_DIR) / "xcelerator_index")))
NEEDS_INDEX_DIR = pathlib.Path(os.getenv("NEEDS_INDEX_DIR", str(pathlib.Path(BASE_DIR) / "needs_index")))
SEMANTIC_DEPTH = 200          # how far down the semantic ranking fusion looks
RRF_K = 60                    # the usual reciprocal-rank-fusion constant: dampens the very top ranks
# Only the top of each ranking takes part in fusion. Fused over full depth, a generic tool high on
# words and at #150 semantically ("Rapidminer") collected two scores and outranked a strong
# semantic-only match: Process Simulate (#6) and Tecnomatix (#11) still missed Wandelbots' top 20.
# Measured by scripts/compare_tool_retrieval.py on the 4 stored companies with concepts: depth 20
# beat words on all four (mean recall 85% vs 64%, noise 9.2 vs 11.5 of 20); depth 40 mostly tied.
FUSE_DEPTH = int(os.getenv("TOOL_FUSE_DEPTH", "20"))
_lock = threading.Lock()
_loaded: dict = {}            # (catalog, checksum, model, dims) -> Index


def tool_text(entry: dict) -> str:
    """What is embedded for one tool: everything a reviewer would read to judge it."""
    return " | ".join(str(entry.get(k) or "").strip() for k in ("name", "category", "division", "description")
                      if str(entry.get(k) or "").strip())


def seller_text(entry: dict) -> str:
    """What is embedded for one Xcelerator seller: what it offers, to which industries, on which topics."""
    parts = [entry.get("name"), "; ".join(entry.get("industries") or []), "; ".join(entry.get("topics") or []),
             entry.get("description")]
    return " | ".join(str(p).strip() for p in parts if str(p or "").strip())


def need_text(entry: dict) -> str:
    """What is embedded for one stated need: whose it is, what it is, what it means, its keywords."""
    parts = [entry.get("department"), entry.get("category"), entry.get("capability"), entry.get("description"),
             "; ".join(entry.get("keywords") or [])]
    return " | ".join(str(p).strip() for p in parts if str(p or "").strip())


def _kind(catalog: dict) -> str:
    name = catalog.get("name")
    return name if name in ("xcelerator", "department_needs_index") else "siemens_tools"


def _text_for(catalog: dict):
    return {"xcelerator": seller_text, "department_needs_index": need_text}.get(_kind(catalog), tool_text)


def _missing_reason(catalog: dict) -> str:
    return {"xcelerator": "no Xcelerator index for this workbook — run scripts/build_tool_index.py --catalog xcelerator",
            "department_needs_index": "no needs index for this workbook — run scripts/build_tool_index.py --catalog needs",
            }.get(_kind(catalog), "no tool index for this catalog — run scripts/build_tool_index.py")


class Index:
    def __init__(self, names: list[str], vectors, meta: dict):
        self.names = names                      # catalog names, in vector-row order
        self.row = {n.casefold(): i for i, n in enumerate(names)}
        self.vectors = vectors                  # numpy float32, rows L2-normalised
        self.meta = meta

    def rank(self, query) -> list[str]:
        """Catalog names, most similar first (the top SEMANTIC_DEPTH)."""
        import numpy as np
        scores = self.vectors @ query
        top = np.argsort(-scores)[:SEMANTIC_DEPTH]
        return [self.names[i] for i in top]


def _dir(catalog: dict) -> pathlib.Path:
    return {"xcelerator": XCELERATOR_INDEX_DIR, "department_needs_index": NEEDS_INDEX_DIR}.get(_kind(catalog), INDEX_DIR)


def _paths(catalog: dict):
    d = _dir(catalog)
    return d / "vectors.npy", d / "meta.json"


def load_index(catalog: dict, model: str, dims: int) -> Index | None:
    """The stored index, if it was built for exactly this catalog, model and size."""
    if not catalog.get("available") or not model:
        return None
    key = (catalog.get("checksum"), model, dims)
    with _lock:
        if (_kind(catalog), *key) in _loaded:
            return _loaded[(_kind(catalog), *key)]
        vec_path, meta_path = _paths(catalog)
        if not vec_path.exists() or not meta_path.exists():
            return None
        try:
            import numpy as np
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if (meta.get("checksum"), meta.get("model"), meta.get("dims")) != key:
                return None
            vectors = np.load(vec_path).astype("float32")
            index = Index(meta["names"], vectors, meta)
        except Exception:
            log.warning("[tool_search] index unreadable; using word matching", exc_info=True)
            return None
        _loaded[(_kind(catalog), *key)] = index
        return index


def build_index(catalog: dict, llm, batch: int = 100) -> Index:
    """Embed every catalog entry and store the index. Run by scripts/build_tool_index.py."""
    import numpy as np
    model, dims = llm.embedding_model(), _dims()
    if not model:
        raise RuntimeError("this provider has no embedding model (set EMBEDDING_MODEL)")
    entries = catalog["entries"]
    rows = []
    for start in range(0, len(entries), batch):
        chunk = entries[start:start + batch]
        vectors = llm.embed([_text_for(catalog)(e) for e in chunk], dims=dims, cache=False)
        if vectors is None or len(vectors) != len(chunk):
            raise RuntimeError(f"embedding failed at entry {start}: {llm.last_error}")
        rows.extend(vectors)
        log.info("[tool_search] embedded %d/%d", min(start + batch, len(entries)), len(entries))
    matrix = _normalise(np.asarray(rows, dtype="float32"))
    _dir(catalog).mkdir(parents=True, exist_ok=True)
    vec_path, meta_path = _paths(catalog)
    np.save(vec_path, matrix.astype("float16"))
    meta = {"model": model, "dims": dims, "checksum": catalog["checksum"], "count": len(entries),
            "names": [e["name"] for e in entries]}
    meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    with _lock:
        _loaded.clear()
    return Index(meta["names"], matrix, meta)


def _dims() -> int:
    from .llm import EMBEDDING_DIMS
    return EMBEDDING_DIMS


def _normalise(matrix):
    import numpy as np
    norms = np.linalg.norm(matrix, axis=-1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def semantic_ranking(query_text: str, catalog: dict, llm) -> tuple[list[str] | None, str]:
    """(catalog names by similarity, "") or (None, why word matching is used instead)."""
    if llm is None or not getattr(llm, "available", False):
        return None, "no model configured"
    try:
        model = llm.embedding_model() if callable(getattr(type(llm), "embedding_model", None)) else ""
    except Exception:                                     # noqa: BLE001 — a client that cannot say
        model = ""
    if not model:
        return None, "this provider has no embedding model"
    index = load_index(catalog, model, _dims())
    if index is None:
        return None, _missing_reason(catalog)
    text = str(query_text or "").strip()[:4000]
    if not text:
        return None, "nothing to describe the startup with"
    vectors = llm.embed([text], dims=_dims())
    if not vectors:
        return None, "the embedding call failed"
    import numpy as np
    return index.rank(_normalise(np.asarray(vectors[0], dtype="float32"))), ""


def fuse(word_ranked: list[str], semantic_ranked: list[str] | None, limit: int) -> list[str]:
    """Reciprocal-rank fusion of the two rankings (names), best first. Words alone without semantics."""
    if not semantic_ranked:
        return word_ranked[:limit]
    score: dict = {}
    keep: dict = {}
    for ranking in (word_ranked, semantic_ranked):
        for rank, name in enumerate(ranking[:FUSE_DEPTH]):
            key = name.casefold()
            keep.setdefault(key, name)
            score[key] = score.get(key, 0.0) + 1.0 / (RRF_K + rank + 1)
    return [keep[k] for k in sorted(score, key=lambda k: -score[k])][:limit]
