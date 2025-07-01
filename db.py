from pymongo import MongoClient
import json
import os
from datetime import datetime
from bson import ObjectId
import re
import hashlib
import random
import shutil

client = MongoClient(os.environ.get("MONGODB_URI", "mongodb://localhost:27017/"))
db = client["question_bank"]
collection = db["questions"]

OPTION_KEYS = [
    "a",
    "b",
    "c",
    "d",
]

def save_question(data: dict):
    """Insert a question document and return the newly created ``ObjectId``.

    The original implementation discarded the inserted ID, but returning it
    allows callers to keep track of questions created in a specific processing
    session without altering any external behaviour.
    """
    result = collection.insert_one(data)
    return result.inserted_id

def get_all_questions():
    return list(collection.find({}, {"question": 1, "_id": 0}))

def _convert_question_for_export(q: dict) -> dict:
    """Convert a Mongo document into the required questions.json schema."""
    # Helper to strip leading/trailing option markers like "A)", "(A)", "A." etc.
    def _clean_option_text(text: str) -> str:
        if not isinstance(text, str):
            return str(text)
        # Remove leading markers (e.g., "A) ", "A. ")
        text = re.sub(r"^\s*[A-D]\s*[\)\.:]\s*", "", text)
        # Remove trailing markers (e.g., " (A)")
        text = re.sub(r"\s*[\(\[]?[A-D][\)\]]?\s*$", "", text)
        return text.strip()

    # Fetch the raw options from DB entry (could be list or dict)
    raw_options = q.get("options", [])
    raw_options_list = list(raw_options.values()) if isinstance(raw_options, dict) else list(raw_options)

    # If options are packed into a single string (e.g., "A) ... B) ... C) ... D) ...") OR only one
    # of the four slots is non-empty and contains all markers, split it into four.
    if raw_options_list:
        needs_split = False
        combined_str = None

        if len(raw_options_list) == 1 and isinstance(raw_options_list[0], str):
            combined_str = raw_options_list[0]
            needs_split = True
        elif len(raw_options_list) == 4:
            non_empty = [opt for opt in raw_options_list if isinstance(opt, str) and opt.strip()]
            if len(non_empty) == 1:
                combined_str = non_empty[0]
                needs_split = True

        if needs_split and combined_str and re.search(r"[A-D]\s*[\)\.:]", combined_str):
            split_candidate = re.sub(r"\s*[A-D]\s*[\)\.:]\s*", "|", combined_str)
            parts = [p.strip() for p in split_candidate.split("|") if p.strip()]
            if len(parts) == 4:
                raw_options_list = parts

    # Ensure exactly four options
    while len(raw_options_list) < 4:
        raw_options_list.append("")
    raw_options_list = raw_options_list[:4]

    # Clean markers like (A) / A. etc. from each option
    cleaned_options = [_clean_option_text(opt) for opt in raw_options_list]

    # Determine the text of the correct answer before shuffling
    answer_letter = str(q.get("answer") or q.get("correct_answer") or "").strip().upper()
    answer_index = ord(answer_letter) - ord("A") if answer_letter in ["A", "B", "C", "D"] else 0
    correct_answer_text = _clean_option_text(raw_options_list[answer_index])

    # Deterministically shuffle options to distribute correct answers across keys
    seed = int(hashlib.md5(q.get("question", "").encode()).hexdigest(), 16)
    rnd = random.Random(seed)
    shuffled_options = cleaned_options.copy()
    rnd.shuffle(shuffled_options)

    # Re-map correct answer key after shuffling
    try:
        new_correct_index = shuffled_options.index(correct_answer_text)
    except ValueError:
        # Fallback: if not found, default to first option
        new_correct_index = 0

    options_dict = {k: v for k, v in zip(OPTION_KEYS, shuffled_options)}
    correct_key = OPTION_KEYS[new_correct_index]

    return {
        "_id": {"$oid": str(q.get("_id"))},
        "question_type": "single_choice",
        "question_name": q.get("question", ""),
        "correct_answer": correct_key,
        "options": options_dict,
        "__v": 0,
    }

def export_questions_to_json(file_path: str = "questions.json"):
    """Dump all questions in the MongoDB collection to ``file_path`` in the new
    JSON schema required by the frontend export.
    """
    # Safeguard: If file_path exists as a directory, remove it
    if os.path.exists(file_path) and os.path.isdir(file_path):
        shutil.rmtree(file_path)
        print(f"Warning: Removed directory '{file_path}' to create export file")
    
    questions = list(collection.find())

    transformed = [_convert_question_for_export(q) for q in questions]

    payload = {
        "exported_at": datetime.utcnow().isoformat(),
        "total_questions": len(transformed),
        "questions": transformed,
    }

    with open(file_path, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2, ensure_ascii=False)

def delete_all_questions():
    """Deletes all documents from the questions collection."""
    result = collection.delete_many({})
    return result.deleted_count

# ----------------------------------------------------------------------------------
# Export helpers
# ----------------------------------------------------------------------------------

def export_questions_to_json_subset(questions, file_path: str = "questions.json"):
    """Export *only* the provided ``questions`` list to ``file_path``.

    This helper is identical to :pyfunc:`export_questions_to_json` but operates on
    an in-memory collection instead of pulling the full database. It is useful
    for generating a session-scoped export without affecting existing logic.
    """
    # Safeguard: If file_path exists as a directory, remove it
    if os.path.exists(file_path) and os.path.isdir(file_path):
        shutil.rmtree(file_path)
        print(f"Warning: Removed directory '{file_path}' to create export file")

    transformed = [_convert_question_for_export(q) for q in questions]

    payload = {
        "exported_at": datetime.utcnow().isoformat(),
        "total_questions": len(transformed),
        "questions": transformed,
    }

    with open(file_path, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2, ensure_ascii=False)