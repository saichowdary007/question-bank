from sentence_transformers import SentenceTransformer, util

model = SentenceTransformer('all-MiniLM-L6-v2')

def is_similar(new_question, existing_questions, threshold=0.85):
    new_emb = model.encode(new_question, convert_to_tensor=True)
    for q in existing_questions:
        old_emb = model.encode(q, convert_to_tensor=True)
        if util.cos_sim(new_emb, old_emb).item() > threshold:
            return True
    return False