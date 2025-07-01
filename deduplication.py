from sentence_transformers import SentenceTransformer, util
try:
    import torch  # Added for tensor operations
except ImportError:  # pragma: no cover
    torch = None  # type: ignore

model = SentenceTransformer('all-MiniLM-L6-v2')

def is_similar(new_question, existing_questions, threshold=0.85):
    new_emb = model.encode(new_question, convert_to_tensor=True)
    for q in existing_questions:
        old_emb = model.encode(q, convert_to_tensor=True)
        if util.cos_sim(new_emb, old_emb).item() > threshold:
            return True
    return False

def encode_questions(questions):
    """Encode a list of questions and return a 2-D tensor (n_questions × embedding_dim)."""
    if not questions:
        # Return an empty 2-D tensor with 0 rows and the correct embedding dimension (384 for MiniLM).
        return torch.empty((0, model.get_sentence_embedding_dimension()))
    return model.encode(questions, convert_to_tensor=True)

def is_similar_fast(new_question_emb, existing_embs, threshold=0.85):
    """Fast duplicate detection using *pre-computed* embeddings.

    Args:
        new_question_emb: 1-D tensor embedding of the new question.
        existing_embs: 2-D tensor containing embeddings of existing questions.
        threshold: Cosine similarity threshold to consider two questions duplicates.

    Returns:
        True if the new question is similar to **any** existing question, else False.
    """
    # Short-circuit if we have no existing embeddings yet.
    if existing_embs is None or existing_embs.shape[0] == 0:
        return False

    # Compute cosine similarities in a single vectorised operation.
    cos_scores = util.cos_sim(new_question_emb, existing_embs)
    return bool((cos_scores > threshold).any().item())