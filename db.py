from pymongo import MongoClient
import json
from datetime import datetime
from bson import ObjectId

client = MongoClient("mongodb://localhost:27017/")
db = client["question_bank"]
collection = db["questions"]

def save_question(data: dict):
    collection.insert_one(data)

def get_all_questions():
    return list(collection.find({}, {"question": 1, "_id": 0}))

# NEW: utility to export current questions collection to a JSON file so that
# the generated questions can be stored outside the database when requested.

def export_questions_to_json(file_path: str = "questions.json"):
    """Dump all questions in the MongoDB collection to ``file_path`` in a
    structured JSON format that matches the existing schema.

    The function converts MongoDB ``ObjectId`` values to strings so that the
    resulting file is valid JSON.
    """
    questions = list(collection.find())

    # Convert ObjectId instances to plain strings for JSON serialisation.
    for q in questions:
        if "_id" in q:
            q["_id"] = str(q["_id"])

    payload = {
        "exported_at": datetime.utcnow().isoformat(),
        "total_questions": len(questions),
        "questions": questions,
    }

    with open(file_path, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2, ensure_ascii=False)