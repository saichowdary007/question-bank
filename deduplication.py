# deduplication.py  – drop-in replacement with backward compatibility
from __future__ import annotations

import os
import torch
from sentence_transformers import SentenceTransformer, util

# ───────────────────────────────────────────────────────────────
# 0 · CONFIG
# ───────────────────────────────────────────────────────────────
MODEL_NAME: str = "all-MiniLM-L6-v2"
SIM_THRESHOLD: float = float(os.getenv("SIM_THRESHOLD", 0.85))

# Pick the fastest device that exists → cuda ▸ mps ▸ cpu
DEVICE: str = (
    "cuda"
    if torch.cuda.is_available()
    else "mps"
    if torch.backends.mps.is_available()
    else "cpu"
)

# Optional speed boost on PyTorch ≥ 2.1
_compile = torch.compile if hasattr(torch, "compile") else (lambda m: m)
model = _compile(SentenceTransformer(MODEL_NAME, device=DEVICE))
EMB_DIM: int = model.get_sentence_embedding_dimension()  # should be 384

# ───────────────────────────────────────────────────────────────
# 1 · ENCODING UTILITY
# ───────────────────────────────────────────────────────────────
@torch.inference_mode()
def encode(sentences: list[str] | str) -> torch.Tensor:
    """
    Encode a single sentence or batch of sentences into a tensor of
    shape (n, EMB_DIM).  Automatically normalises embeddings.
    """
    if isinstance(sentences, str):
        sentences = [sentences]

    return model.encode(
        sentences,
        batch_size=64,           # adjust per GPU/CPU RAM
        convert_to_tensor=True,
        device=DEVICE,           # stay on-device; no extra copies
        normalize_embeddings=True,
    )

# ───────────────────────────────────────────────────────────────
# 2 · FAST DUPLICATE CHECK
# ───────────────────────────────────────────────────────────────
def is_similar_fast(
    new_q,                         # ⇢ str *or* torch.Tensor (embedding)
    existing_embs: torch.Tensor,
    threshold: float = SIM_THRESHOLD,
) -> bool:
    """
    Return True if *new_q* is semantically similar to any row in
    *existing_embs* (cosine ≥ threshold).

    * new_q may be:
        · str  – will be encoded on the fly, or
        · torch.Tensor – pre-computed embedding of shape (d) or (1 × d)
    * existing_embs is a 2-D float tensor with shape (N × d).
    """

    # Nothing to compare with
    if existing_embs.numel() == 0:
        return False

    # ── Accept both raw strings and ready embeddings ────────────
    if torch.is_tensor(new_q):
        new_emb = new_q
        # Ensure shape (1 × d) for 0-D or 1-D input tensors
        if new_emb.ndim == 0:
            new_emb = new_emb.unsqueeze(0)
        elif new_emb.ndim == 1:
            new_emb = new_emb.unsqueeze(0)
    else:
        new_emb = encode(new_q)           # shape (1 × d)

    # Single vectorised cosine-similarity call (GPU-friendly)
    return bool((util.cos_sim(new_emb, existing_embs) > threshold).any())

# ───────────────────────────────────────────────────────────────
# 3 · BULK INITIALISER
# ───────────────────────────────────────────────────────────────
def build_embedding_cache(questions: list[str]) -> torch.Tensor:
    """Encode an entire question list into a (N × d) tensor cache."""
    return encode(questions)

# ───────────────────────────────────────────────────────────────
# 4 · LEGACY API SHIM
# ───────────────────────────────────────────────────────────────
def encode_questions(questions: list[str] | str) -> torch.Tensor:
    """
    Back-compat wrapper — older modules imported `encode_questions`.
    Simply forwards to the new `encode` helper.
    """
    return encode(questions)