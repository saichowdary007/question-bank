from dotenv import load_dotenv
load_dotenv()  # reads .env into os.environ
from pymongo import MongoClient
import json
import os
from datetime import datetime
from bson import ObjectId
import re
import hashlib
import random
import shutil

#
# Initialize MongoDB client using either MONGODB_URI or MONGO_URI environment variable
mongo_uri = os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URI")
if not mongo_uri:
    raise RuntimeError("Environment variable MONGODB_URI or MONGO_URI must be set")
client = MongoClient(mongo_uri)
db = client["question_bank"]
collection = db["questions"]
process_collection = db["processing_state"]


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
    """Return all questions, projecting both legacy and new question text fields."""
    return list(collection.find({}, {"question": 1, "question_name": 1, "_id": 0}))

def _convert_question_for_export(q: dict) -> dict:
    """Convert a Mongo document into the required questions.json schema."""
    # ---------- Fast-path for already normalised documents ----------
    # If the document already contains the modern schema keys and an
    # options mapping with exactly the expected keys (a–d), we can skip
    # all further transformation logic. This prevents the exporter from
    # re-shuffling or modifying questions that were re-imported from a
    # previously exported *questions.json* file, ensuring idempotency.
    if (
        {"question_type", "question_name", "correct_answer", "options"}.issubset(q.keys())
        and isinstance(q.get("options"), dict)
        and set(q["options"].keys()) == set(OPTION_KEYS)
    ):
        return {
            "_id": {"$oid": str(q.get("_id"))},
            "grade": q.get("grade"),
            "subject": q.get("subject"),
            "topic": q.get("topic") or q.get("chapter"),
            "question_type": q["question_type"],
            "question_name": q["question_name"],
            "correct_answer": q["correct_answer"],
            "options": q["options"],
            "__v": q.get("__v", 0),
        }

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

    # Support both legacy ("question") and new ("question_name") field names
    question_text = q.get("question") or q.get("question_name") or ""

    # Deterministically shuffle options to distribute correct answers across keys
    seed = int(hashlib.md5(question_text.encode()).hexdigest(), 16)
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
        "grade": q.get("grade"),
        "subject": q.get("subject"),
        "topic": q.get("topic") or q.get("chapter"),
        "question_type": "single_choice",
        "question_name": question_text,
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


def upsert_processing_state(key: str, status: str, **metadata):
    """Create or update a processing-status record for the given S3 object ``key``.

    The document _id equals the S3 *object key* which is unique in the bucket.
    Additional metadata such as timestamps, file size or error details can be
    provided via ``**metadata``.
    """
    from datetime import datetime  # local import to avoid polluting global ns

    update = {
        "status": status,
        **metadata,
        "updated_at": datetime.utcnow(),
    }
    # Preserve original creation timestamp on subsequent updates
    process_collection.update_one(
        {"_id": key},
        {
            "$set": update,
            "$setOnInsert": {"created_at": datetime.utcnow()},
        },
        upsert=True,
    )