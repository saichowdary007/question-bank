"""Event-driven PDF processing orchestrator.

This module glues together AWS S3 + SQS with the existing question-generation
pipeline (``pdf_utils``, ``llm_ollama``, ``deduplication``, ``db``).

The class is intentionally *self-contained* so we can later import it from
``main.py`` or run it as a standalone worker script.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict
import re  # Added for option text normalisation

# Step-0: lightweight timing helper for micro-metrics
from utils import timing

from deduplication import is_similar_fast, model as dedup_model
from llm_ollama import call_ollama_mistral
from pdf_utils import extract_pages_from_pdf
from db import save_question, get_all_questions, upsert_processing_state

from s3_service import S3Service
from queue_service import QueueService

# AWS & DB helpers
import boto3
from datetime import datetime

# -----------------------------------------------------------------------------
# Configuration via environment variables (sane defaults for dev)
# -----------------------------------------------------------------------------

S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "pdf-question-bank")
SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL", "")
PROCESSING_TIMEOUT = int(os.getenv("PROCESSING_TIMEOUT", "900"))  # seconds
CONCURRENT_REQUESTS = int(os.getenv("CONCURRENT_REQUESTS", "1"))  # placeholder

# After imports and configuration, insert the mapping constants

# -----------------------------------------------------------------------------
# Grade and subject code mappings for MongoDB storage
# -----------------------------------------------------------------------------

# Map various frontend / path representations to canonical grade codes
GRADE_CODE_MAP: dict[str, str] = {
    # Kindergarten
    "kinder-garten": "K1",
    "kinder garten": "K1",
    "kindergarten": "K1",
    "kg": "K1",
    "0": "K1",
    # Grades 1 – 10
    **{str(i): f"G{i}" for i in range(1, 11)},
}

# Map subject names to canonical codes
SUBJECT_CODE_MAP: dict[str, str] = {
    "english": "ENG",
    "math": "MAT",
    "maths": "MAT",
    "science": "SCI",
    "social": "SOC",
}


class PDFProcessor:  # noqa: R0902 – keep attributes explicit for clarity
    """High-level orchestrator that pulls messages and processes PDFs one-by-one."""

    def __init__(
        self,
        s3_service: S3Service | None = None,
        queue_service: QueueService | None = None,
        bucket_name: str | None = None,
        queue_url: str | None = None,
        require_queue: bool = True,
    ) -> None:
        self.s3 = s3_service or S3Service()
        self.sqs = queue_service or QueueService()
        self.bucket_name = bucket_name or S3_BUCKET_NAME
        self.queue_url = queue_url or SQS_QUEUE_URL

        # CloudWatch client for custom metrics (optional local usage)
        self.cloudwatch = boto3.client("cloudwatch", region_name=self.s3.region_name)

        # Require an SQS queue only when the processor is intended to run in
        # *event-driven* mode. For simple “scan bucket for PDFs” workflows we
        # allow instantiation without a queue.
        if require_queue and not self.queue_url:
            raise ValueError("SQS_QUEUE_URL environment variable must be set")

        # Cache existing questions + embeddings once per processor lifetime
        self._existing_questions: list[str] = [
            q.get("question") or q.get("question_name")
            for q in get_all_questions()
            if (q.get("question") or q.get("question_name"))
        ]
        self._existing_embs = (
            dedup_model.encode(self._existing_questions, convert_to_tensor=True)
            if self._existing_questions
            else None
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def poll_and_process_forever(self) -> None:  # blocking loop
        logging.info("📡 Starting SQS polling loop (queue=%s)", self.queue_url)
        while True:
            messages = self.sqs.receive_messages(
                self.queue_url, max_messages=1, wait_time_seconds=20, visibility_timeout=PROCESSING_TIMEOUT
            )
            if not messages:
                continue  # long-poll again

            for msg in messages:
                receipt_handle = msg["ReceiptHandle"]
                try:
                    self._process_queue_message(msg)
                    # Delete only on success
                    self.sqs.delete_message(self.queue_url, receipt_handle)
                except Exception as exc:  # pragma: no cover
                    logging.exception("❌ Error processing message: %s", exc)
                    # Let the message return to the queue (handled by DLQ after N attempts)

    def scan_bucket_and_process_forever(
        self,
        prefix: str = "incoming/",
        poll_interval: int = 10,
    ) -> None:
        """Continuously scan *prefix* in the configured S3 bucket and process
        each discovered PDF until none remain. Intended for simple setups
        without SQS where users upload PDFs directly to S3.
        """

        logging.info(
            "🛰️  Starting S3 polling loop (bucket=%s, prefix=%s)",
            self.bucket_name,
            prefix,
        )

        while True:
            # List *only* incoming PDFs so we don’t repeatedly touch files that
            # were already moved to *processing/* or *completed/*.
            keys = [
                k
                for k in self.s3.list_files(self.bucket_name, prefix=prefix)
                if k.lower().endswith(".pdf")
            ]

            if not keys:
                # Nothing to do – back-off before the next poll
                time.sleep(poll_interval)
                continue

            for key in keys:
                try:
                    self._process_pdf(self.bucket_name, key)
                except Exception as exc:  # pragma: no cover
                    logging.exception("❌ Error processing %s: %s", key, exc)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _process_queue_message(self, message: Dict[str, Any]) -> None:
        """Parse S3 event style message and trigger PDF processing."""
        body = message.get("Body")
        if not body:
            logging.warning("Received message without body – skipping")
            return

        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            logging.warning("Message body is not valid JSON (%s) – skipping", exc)
            return

        # Support plain *event* or wrapper (e.g. eventBridge → SQS)
        record = (payload.get("Records") or [payload])[0]
        s3_info = record.get("s3", {})
        bucket = s3_info.get("bucket", {}).get("name", self.bucket_name)
        key = s3_info.get("object", {}).get("key")
        size = s3_info.get("object", {}).get("size")
        if not key:
            logging.warning("S3 key not found in message – skipping")
            return

        logging.info("📝 Received task for s3://%s/%s", bucket, key)

        # Persist *incoming* state before actual processing starts
        upsert_processing_state(
            key,
            "queued",
            bucket=bucket,
            size=size,
            queued_at=datetime.utcnow().isoformat(),
        )

        self._process_pdf(bucket, key)

    def _process_pdf(self, bucket: str, key: str) -> None:
        """Download, generate questions, store in DB, and move file through lifecycle."""

        # Derive lifecycle keys
        processing_key = key.replace("incoming/", "processing/")
        completed_key = key.replace("incoming/", "archived/")
        failed_key = key.replace("incoming/", "failed/")

        # Move → processing so other workers do not pick it up again
        self.s3.move_file(bucket, key, processing_key)
        logging.info("🚚 Moved to %s", processing_key)

        upsert_processing_state(key, "processing", processing_started_at=datetime.utcnow().isoformat())

        with tempfile.TemporaryDirectory() as tmpdir:
            local_pdf = Path(tmpdir) / Path(processing_key).name
            # Download
            self.s3.download_file(bucket, processing_key, str(local_pdf))
            logging.info("⬇️  Downloaded %s", local_pdf)

            try:
                start_time = time.time()
                # --- Page extraction ---------------------------------------------------
                with timing("Page extraction"):
                    pages = extract_pages_from_pdf(str(local_pdf))
                logging.info("📄 Extracted %d pages", len(pages))

                # Extract metadata from the original S3 key (incoming/<grade>/<subject>/<topic>/...)
                parts = key.split("/")
                grade_meta = parts[1] if len(parts) > 1 else None
                subject_meta = parts[2] if len(parts) > 2 else None
                topic_meta = parts[3] if len(parts) > 3 else None

                for page_num, page_text in enumerate(pages, start=1):
                    prompt = _build_prompt(page_text)
                    response_text = call_ollama_mistral(prompt)
                    try:
                        q_objects = json.loads(response_text)
                    except json.JSONDecodeError:
                        logging.warning("Page %d returned non-JSON – skipping", page_num)
                        continue

                    if isinstance(q_objects, dict) and "questions" in q_objects:
                        q_objects = q_objects["questions"]

                    if not isinstance(q_objects, list):
                        logging.warning("Unexpected response format on page %d – skipping", page_num)
                        continue

                    for q_obj in q_objects:
                        # Attach metadata so it is persisted alongside the question
                        if grade_meta:
                            q_obj["grade"] = grade_meta
                        if subject_meta:
                            q_obj["subject"] = subject_meta
                        if topic_meta:
                            q_obj["topic"] = topic_meta
                        self._persist_question(q_obj)

                elapsed = time.time() - start_time
                logging.info("✅ Finished processing in %.1fs", elapsed)

                # Move to archived – keep the PDF for storage
                self.s3.move_file(bucket, processing_key, completed_key)
                logging.info("🎉 Archived to %s", completed_key)

                upsert_processing_state(
                    key,
                    "completed",
                    completed_at=datetime.utcnow().isoformat(),
                )

                self._publish_metric("ProcessedPDF", 1)

            except Exception as exc:
                logging.exception("❌ Error during PDF processing: %s", exc)
                # Move to failed on any exception
                self.s3.move_file(bucket, processing_key, failed_key)
                logging.info("📦 Moved to %s", failed_key)

                upsert_processing_state(
                    key,
                    "failed",
                    failed_at=datetime.utcnow().isoformat(),
                    error=str(exc),
                )

                self._publish_metric("FailedPDF", 1)

    # ------------------------------------------------------------------
    # Question helpers
    # ------------------------------------------------------------------

    def _persist_question(self, q_obj: Dict[str, Any]) -> None:
        """Deduplicate and persist a single question payload."""
        question_text: str | None = q_obj.get("question") or q_obj.get("question_name")
        if not question_text:
            return  # skip malformed

        # Duplicate detection (fast embeddings)
        new_emb = dedup_model.encode(question_text, convert_to_tensor=True)
        if is_similar_fast(new_emb, self._existing_embs):
            logging.debug("Duplicate question skipped: %.60s", question_text)
            return

        # Normalize options
        raw_options = q_obj.get("options", [])

        def _strip_label(txt: str) -> str:
            """Remove leading labels like 'A)', 'B.', etc. and trim."""
            if not isinstance(txt, str):
                return txt  # bail out early for non-strings
            return re.sub(r"^\s*[A-Da-d][).]\s*", "", txt).strip()

        option_map: dict[str, str] = {}

        # Case 1 – LLM returned a plain list → map directly to a–d after cleaning
        if isinstance(raw_options, list):
            cleaned = [_strip_label(opt) for opt in raw_options if isinstance(opt, str)]
            option_map = {k: v for k, v in zip(["a", "b", "c", "d"], cleaned)}

        # Case 2 – LLM returned a dict
        elif isinstance(raw_options, dict):
            temp_map = {k.lower(): v for k, v in raw_options.items()}

            # Occasionally the model puts *all* options inside the first key (usually 'a').
            # Detect this by checking for only one key and presence of markers like 'B)' within
            # the value, then split the string accordingly.
            if len(temp_map) == 1:
                combined_val = list(temp_map.values())[0]
                if isinstance(combined_val, str) and any(f"{ch})" in combined_val for ch in "BCD"):
                    # Ensure we have an 'A)' marker to simplify splitting logic
                    candidate = combined_val if "A)" in combined_val[:3] else f"A) {combined_val}"
                    parts = re.split(r"\s*[A-D]\)\s*", candidate)
                    parts = [p.strip(" ,") for p in parts if p.strip()]
                    option_map = {k: _strip_label(v) for k, v in zip(["a", "b", "c", "d"], parts)}
                else:
                    option_map = {list(temp_map.keys())[0]: _strip_label(combined_val)}
            else:
                option_map = {k: _strip_label(v) if isinstance(v, str) else v for k, v in temp_map.items()}

        # Fallback – unexpected structure
        else:
            option_map = {}

        answer_raw = str(q_obj.get("answer", "")).strip().upper()
        if answer_raw in ["A", "B", "C", "D"]:
            correct_key = answer_raw.lower()
        else:
            correct_key = "a"

        # Build the document with metadata keys first (if present) so they
        # appear right after the automatically added ``_id`` field in MongoDB.
        saved_question = {}

        # Insert contextual metadata in deterministic order
        for field in ("grade", "subject", "topic"):
            raw_val = q_obj.get(field)
            if raw_val is None:
                continue

            # Normalise and translate grade/subject values to their canonical
            # codes expected in MongoDB. Any value that does not have an
            # explicit mapping falls back to the original input so we do not
            # inadvertently drop information.
            if field == "grade":
                key = str(raw_val).strip().lower()
                saved_val = GRADE_CODE_MAP.get(key, raw_val)
            elif field == "subject":
                key = str(raw_val).strip().lower()
                saved_val = SUBJECT_CODE_MAP.get(key, raw_val)
            else:
                saved_val = raw_val

            saved_question[field] = saved_val

        # Insert the core question fields *after* metadata so the final
        # document order is: _id, grade, subject, topic, question_type, ...
        saved_question.update({
            "question_type": "single_choice",
            "question_name": question_text,
            "correct_answer": correct_key,
            "options": option_map,
            "__v": 0,
        })

        save_question(saved_question)
        # Extend local cache for later duplicate detection
        self._existing_questions.append(question_text)
        if self._existing_embs is not None:
            self._existing_embs = dedup_model.encode(
                self._existing_questions, convert_to_tensor=True
            )

    # -----------------------------------------------------------------------------
    # CloudWatch helper
    # -----------------------------------------------------------------------------

    def _publish_metric(self, name: str, value: int) -> None:
        """Send a custom metric datapoint to CloudWatch (best-effort)."""
        try:
            self.cloudwatch.put_metric_data(
                Namespace="PDFQuestionBank",
                MetricData=[
                    {
                        "MetricName": name,
                        "Value": value,
                        "Unit": "Count",
                    }
                ],
            )
        except Exception:  # pragma: no cover – network errors in local dev
            logging.debug("Could not publish CloudWatch metric %s", name)


# -----------------------------------------------------------------------------
# Helper – prompt builder (kept minimal on purpose)
# -----------------------------------------------------------------------------

def _build_prompt(page_text: str) -> str:
    """Return the system prompt used for MCQ generation."""

    return f"""You are an intelligent educational assistant.\n\nRead the following page excerpt from a school book (Grades 1–10) and identify its main educational concepts.\n\n**CONTENT VALIDATION FIRST:**\n- If the text is empty, contains only page numbers, headers, footers, navigation elements, or lacks substantive educational content (less than 20 meaningful words), return: []\n- If the text is fragmented, corrupted, or incomprehensible, return: []\n\n**QUESTION GENERATION RULES:**\nOnly if content contains clear educational concepts:\n1. Generate 3-5 multiple-choice questions testing comprehension of main concepts\n2. Each question MUST be based on specific information in the text\n3. Do not generate questions about page numbers, headers, formatting, or information not in the text\n4. Each question must have exactly 4 options labeled A-D\n5. Only one option should be clearly correct\n6. Return ONLY valid JSON array format:\n\n[\n  {{\"question\": \"...\", \"options\": [\"A\", \"B\", \"C\", \"D\"], \"answer\": \"A\"}},\n  ...\n]\n\nText:\n\"\n{page_text}\n\"\n"""