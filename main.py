from fastapi import FastAPI, Request, WebSocket, Body, UploadFile, File, Form
from fastapi.responses import FileResponse, PlainTextResponse, JSONResponse
from starlette.middleware.cors import CORSMiddleware
import os, shutil, json, asyncio, re, aiohttp  # type: ignore
from pdf_utils import extract_pages_from_pdf
from llm_ollama import call_ollama_mistral_async, OLLAMA_URL, OLLAMA_REQUEST_TIMEOUT
from db import (
    save_question,
    get_all_questions,
    export_questions_to_json_subset,
    delete_all_questions,
)
from deduplication import is_similar_fast, model as dedup_model
import logging
from datetime import datetime
import time
from typing import List, Literal
import signal
import subprocess
import threading
from fastapi.responses import StreamingResponse
import torch
from processor import PDFProcessor
from s3_service import S3Service

# FastAPI shutdown hook – ensures the shared aiohttp session from llm_ollama
# is gracefully closed so the event loop can exit cleanly.
from llm_ollama import close_async_session

def _slugify(value: str) -> str:
    """
    Normalizes string, converts to lowercase, removes non-alpha characters,
    and converts spaces to hyphens.
    """
    return re.sub(r'[^a-z0-9_]+', '-', value.lower()).strip('-')

app = FastAPI()

# Global state for processing status
ProcessingStatus = Literal["idle", "processing", "complete", "error"]
processing_status: ProcessingStatus = "idle"

origins = [
    "http://localhost",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Accept", "Accept-Encoding", "Content-Type", "Origin", "Authorization", "Cache-Control"],
    expose_headers=["Content-Type", "Content-Length"]
)

CONCURRENT_REQUESTS = int(os.getenv("CONCURRENT_REQUESTS", "4"))

# ---------------------------------------------------------------------------
# Logging – console (colored) *and* file (JSON lines for downstream ingestion)
# ---------------------------------------------------------------------------

class JsonFormatter(logging.Formatter):
    """Simple JSON log formatter producing one-line JSON objects."""

    def format(self, record):  # type: ignore[override]
        import json  # local import avoids polluting top-level namespace

        base = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
        }
        if record.exc_info:
            base["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(base, ensure_ascii=False)


# Configure root logger programmatically to support mixed formatters
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Console handler (colored human-friendly)
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
root_logger.addHandler(console_handler)

# File handler (structured JSON)
file_handler = logging.FileHandler("app.log", encoding="utf-8")
file_handler.setFormatter(JsonFormatter())
root_logger.addHandler(file_handler)

# Replace default handler in earlier code reference
logging.getLogger().handlers = [console_handler, file_handler]

def log_separator(title: str = "", char: str = "=", length: int = 80):
    """Create a visual separator in logs."""
    if title:
        padding = (length - len(title) - 2) // 2
        separator = char * padding + f" {title} " + char * padding
        if len(separator) < length:
            separator += char
    else:
        separator = char * length
    
    logging.info(separator)

def log_progress_bar(current: int, total: int, prefix: str = "Progress", bar_length: int = 40):
    """Create a visual progress bar in logs."""
    if total == 0:
        return
    
    progress = current / total
    filled_length = int(bar_length * progress)
    bar = "█" * filled_length + "░" * (bar_length - filled_length)
    percentage = progress * 100
    
    logging.info(f"{prefix}: [{bar}] {current}/{total} ({percentage:.1f}%)")

def log_timing(start_time: float, operation: str):
    """Log timing information for operations."""
    elapsed = time.time() - start_time
    minutes, seconds = divmod(elapsed, 60)
    if minutes > 0:
        time_str = f"{int(minutes)}m {seconds:.1f}s"
    else:
        time_str = f"{seconds:.1f}s"
    
    logging.info(f"⏱️  {operation} completed in {time_str}")

def shutdown_all_servers():
    """Automatically shutdown all related server processes after completion."""
    logging.info("🔄 Initiating automatic server shutdown...")
    
    # Get the current process group ID
    current_pgid = os.getpgid(0)
    
    # Kill related processes
    processes_to_kill = [
        "uvicorn",
        "run_server",
        "log_viewer"
    ]
    
    killed_count = 0
    for process_name in processes_to_kill:
        try:
            # Use pkill with SIGTERM and process group
            result = subprocess.run(
                ["pkill", "-TERM", "-f", process_name], 
                capture_output=True, 
                text=True
            )
            if result.returncode == 0:
                killed_count += 1
                logging.info(f"✅ Stopped {process_name} processes")
            else:
                logging.info(f"ℹ️  No {process_name} processes found")
                
            # Double-check with SIGKILL after a short delay
            time.sleep(0.5)
            subprocess.run(["pkill", "-KILL", "-f", process_name], capture_output=True)
            
        except Exception as e:
            logging.warning(f"⚠️  Could not stop {process_name}: {e}")
    
    if killed_count > 0:
        logging.info(f"🎯 Successfully stopped {killed_count} server processes")
    else:
        logging.info("ℹ️  No additional server processes to stop")
    
    # Ensure this process and its children are terminated
    try:
        os.killpg(current_pgid, signal.SIGTERM)
    except:
        os._exit(0)  # Force exit if killpg fails

def delayed_shutdown():
    """Perform shutdown after a short delay to ensure response is sent."""
    time.sleep(2)  # Give time for HTTP response to be sent
    
    log_separator("🛑 AUTOMATIC SHUTDOWN INITIATED", "═")
    logging.info("💤 Waiting 3 seconds before shutdown...")
    time.sleep(3)
    
    shutdown_all_servers()
    
    logging.info("👋 All servers stopped successfully!")
    logging.info("🎉 Question Bank Processor session complete!")
    log_separator("", "═")
    
    # Final shutdown
    time.sleep(1)
    os._exit(0)  # Force exit the entire process

UPLOAD_DIR = "temp_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

LOG_FILE_PATH = "app.log"

pdf_processor: PDFProcessor | None = None

@app.on_event("startup")
def _start_pdf_processor():
    """Launch the SQS polling worker in a background thread (only if configured)."""
    global pdf_processor
    
    # Check if SQS is configured for production use
    sqs_queue_url = os.getenv("SQS_QUEUE_URL", "").strip()
    
    if not sqs_queue_url:
        logging.info("🔧 SQS_QUEUE_URL not configured – falling back to direct S3 polling mode")

        # Start a background thread that continuously scans the bucket for
        # *incoming/* PDFs and processes them one-by-one.
        try:
            pdf_processor = PDFProcessor(require_queue=False)
            threading.Thread(target=pdf_processor.scan_bucket_and_process_forever, daemon=True).start()
            logging.info("🚀 PDFProcessor S3 polling thread started (bucket=%s)", pdf_processor.bucket_name)
        except Exception as exc:
            logging.warning("⚠️  Could not start S3 polling processor: %s – running in manual mode", exc)
        return
    
    try:
        pdf_processor = PDFProcessor()
        threading.Thread(target=pdf_processor.poll_and_process_forever, daemon=True).start()
        logging.info("🚀 PDFProcessor background thread started (queue=%s)", pdf_processor.queue_url)
    except Exception as exc:
        logging.warning("⚠️  Could not start PDFProcessor: %s - running in local mode", exc)
        logging.info("📝 API endpoints will still be available for manual file uploads")


# ---------------------------------------------------------------------------
# Shutdown – close shared HTTP resources
# ---------------------------------------------------------------------------


@app.on_event("shutdown")
async def _shutdown_async_resources() -> None:
    """Gracefully close any global async resources before process exit."""
    await close_async_session()


@app.get("/health")
async def health():
    """Simple liveness probe for container orchestrators (Docker, K8s etc.)."""
    return {"status": "ok"}


@app.get("/status")
async def runtime_status():
    """Return basic queue metrics to aid monitoring/alerting."""
    if pdf_processor is None:
        return {"status": "initialising"}

    if not pdf_processor.queue_url:
        # Running in direct S3 polling mode – no SQS metrics available
        return {"status": "s3-polling", "bucket": pdf_processor.bucket_name}

    attrs = pdf_processor.sqs.get_queue_attributes(pdf_processor.queue_url)
    return {
        "queue_url": pdf_processor.queue_url,
        "queue_depth": attrs.get("ApproximateNumberOfMessages"),
        "inflight": attrs.get("ApproximateNumberOfMessagesNotVisible"),
    }

@app.get("/logs/")
async def stream_logs(request: Request, from_end: bool = False):
    """Stream server logs as Server-Sent Events (SSE).

    Args:
        request: Starlette request instance (used to detect client disconnects).
        from_end: If *True*, the stream starts at the **current** end of the log
            file instead of replaying the entire file. This is useful for
            consecutive processing sessions where the client only cares about
            **new** log lines.
    """

    # Determine the starting offset **outside** the generator to avoid reopening
    # the file just to seek to its current length on every iteration.
    start_position = 0
    if from_end and os.path.exists(LOG_FILE_PATH):
        # Seek to the end of the file so we only stream *new* log lines.
        with open(LOG_FILE_PATH, "rb") as f:
            f.seek(0, os.SEEK_END)
            start_position = f.tell()

    async def log_generator():
        # Track how many bytes we've already read.
        last_position = start_position
        
        # Create the log file if it doesn't exist to prevent initial errors.
        if not os.path.exists(LOG_FILE_PATH):
            open(LOG_FILE_PATH, "a").close()

        try:
            while True:
                if await request.is_disconnected():
                    logging.info("Client disconnected from log stream.")
                    break
                
                with open(LOG_FILE_PATH, 'r', encoding='utf-8') as f:
                    f.seek(last_position)
                    new_content = f.read()
                    last_position = f.tell()

                if new_content:
                    for line in new_content.strip().split('\n'):
                        if line.strip():
                             # Send raw line to frontend for parsing
                             data = {"line": line.strip()}
                             yield f"data: {json.dumps(data)}\n\n"
                
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            logging.info("Log streaming cancelled by server.")
        except Exception as e:
            logging.error(f"Error in log stream generator: {e}")

    return StreamingResponse(
        log_generator(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
            "X-Accel-Buffering": "no"
        }
    )

@app.get("/questions")
async def get_questions():
    file_path = "questions.json"
    if os.path.exists(file_path):
        return FileResponse(path=file_path, filename="questions.json", media_type='application/json')
    return {"error": "questions.json not found"}

@app.get("/processing-status")
async def get_processing_status():
    """Returns the current status of PDF processing."""
    global processing_status
    if processing_status == "complete" and not os.path.exists("questions.json"):
        processing_status = "idle"
    return {"status": processing_status}

@app.post("/reset")
async def reset_state():
    """Resets the server state."""
    global processing_status
    processing_status = "idle"
    
    # Delete old questions file if it exists
    if os.path.exists("questions.json"):
        os.remove("questions.json")
        logging.info("🗑️  Previous questions file removed.")
        
    return {"status": "reset"}

# ------------------------------
# Deprecated endpoints removed
# ------------------------------

@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    await websocket.accept()
    last_position = 0
    
    try:
        while True:
            with open(LOG_FILE_PATH, 'r', encoding='utf-8') as f:
                f.seek(last_position)
                new_content = f.read()
                last_position = f.tell()

            if new_content:
                for line in new_content.strip().split('\n'):
                    if line.strip():
                        log_match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - (\w+) - (.+)', line)
                        if log_match:
                            timestamp, level, message = log_match.groups()
                            data = {
                                "type": "log",
                                "timestamp": timestamp,
                                "level": level,
                                "message": message.strip()
                            }
                            await websocket.send_json(data)
            
            await asyncio.sleep(0.5)  # Poll every 500ms
    except Exception as e:
        logging.error(f"WebSocket error: {e}")
    finally:
        try:
            await websocket.close()
        except:
            pass

# -------------------------------------------------------------
# 🔄 Replaced: Proxy to native Ollama /api/generate (JSON in ➜ JSON out)
# -------------------------------------------------------------

@app.post("/ask-plain")
async def proxy_ollama_generate(payload: dict = Body(...)):
    """Forward JSON payload directly to the running Ollama server and return its native JSON response.

    Example payload expected (same as Ollama):
        {
          "model": "mistral",
          "prompt": "hello",
          "stream": false
        }
    """

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                OLLAMA_URL,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=OLLAMA_REQUEST_TIMEOUT),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

# ---------------------------------------------------------------------------
# 📤 File upload endpoint – Frontend ➜ Backend ➜ S3 ➜ Processor
# ---------------------------------------------------------------------------


@app.post("/api/upload")
async def upload_file(
    grade: str = Form(...),
    subject: str = Form(...),
    topic: str = Form(...),
    file: UploadFile = File(...),
):
    """
    This endpoint receives a file and its metadata, saves it to a temporary location,
    and then queues it for processing.

    The metadata includes *grade*, *subject*, and *topic* information and store it in S3 under the **incoming/** prefix so
    that the processor can use it to enrich the question bank data.
    The S3 key will be:
        incoming/<grade>/<subject>/<topic>/<original_filename>

    """
    try:
        # Create a slug for the grade, subject, and topic
        grade_slug = _slugify(grade)
        subject_slug = _slugify(subject)
        topic_slug = _slugify(topic)
        s3_key = f"incoming/{grade_slug}/{subject_slug}/{topic_slug}/{file.filename}"

        bucket_name = os.getenv("S3_BUCKET_NAME", "pdf-question-bank")

        # Save the uploaded file to a temporary location
        temp_file_path = f"temp_uploads/{file.filename}"
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Upload the file object directly to S3
        s3 = S3Service()
        s3.upload_file(temp_file_path, bucket_name, s3_key)

        logging.info("📤 Uploaded %s to s3://%s/%s", file.filename, bucket_name, s3_key)
        return {"detail": "File uploaded", "key": s3_key}
    except Exception as exc:  # pragma: no cover – network/IO errors in dev env
        logging.exception("❌ Failed to upload PDF to S3: %s", exc)
        return JSONResponse(status_code=500, content={"detail": f"Upload failed: {exc}"})