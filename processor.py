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


class PDFProcessor:  # noqa: R0902 – keep attributes explicit for clarity
    """High-level orchestrator that pulls messages and processes PDFs one-by-one."""

    def __init__(
        self,
        s3_service: S3Service | None = None,
        queue_service: QueueService | None = None,
        bucket_name: str | None = None,
        queue_url: str | None = None,
    ) -> None:
        self.s3 = s3_service or S3Service()
        self.sqs = queue_service or QueueService()
        self.bucket_name = bucket_name or S3_BUCKET_NAME
        self.queue_url = queue_url or SQS_QUEUE_URL

        # CloudWatch client for custom metrics (optional local usage)
        self.cloudwatch = boto3.client("cloudwatch", region_name=self.s3.region_name)

        if not self.queue_url:
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
        completed_key = key.replace("incoming/", "completed/")
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
                pages = extract_pages_from_pdf(str(local_pdf))
                logging.info("📄 Extracted %d pages", len(pages))

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
                        self._persist_question(q_obj)

                elapsed = time.time() - start_time
                logging.info("✅ Finished processing in %.1fs", elapsed)

                # Move to completed
                self.s3.move_file(bucket, processing_key, completed_key)
                logging.info("🎉 Moved to %s", completed_key)

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
        if isinstance(raw_options, list):
            option_map = {k: v for k, v in zip(["a", "b", "c", "d"], raw_options)}
        elif isinstance(raw_options, dict):
            option_map = {k.lower(): v for k, v in raw_options.items()}
        else:
            option_map = {}

        answer_raw = str(q_obj.get("answer", "")).strip().upper()
        if answer_raw in ["A", "B", "C", "D"]:
            correct_key = answer_raw.lower()
        else:
            correct_key = "a"

        saved_question = {
            "question_type": "single_choice",
            "question_name": question_text,
            "correct_answer": correct_key,
            "options": option_map,
            "__v": 0,
        }
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

    return f"""You are an intelligent educational assistant.\n\nRead the following page excerpt from a school book (Grades 1–10) and identify its main concepts.\nGenerate between 3 and 5 multiple-choice questions (MCQs) that test understanding of those concepts.\n\nRules:\n1. Provide 3 to 5 questions total.\n2. Each question must stem directly from the provided text.\n3. Do not repeat or rephrase existing questions within the same list.\n4. Give exactly 4 answer options labelled A–D in an array.\n5. Clearly indicate the correct answer for each question using the same letter (e.g., \"A\").\n6. Return ONLY a valid JSON array of objects in the form:\n\n[\n  {{\"question\": \"...\", \"options\": [\"A\", \"B\", \"C\", \"D\"], \"answer\": \"A\"}},\n  ...\n]\n\nText:\n\"\n{page_text}\n\"\n""" 