from fastapi import FastAPI, File, UploadFile, Form, Request, WebSocket
from fastapi.responses import FileResponse
from starlette.middleware.cors import CORSMiddleware
import os, shutil, json, asyncio, re
from pdf_utils import extract_pages_from_pdf
from llm_ollama import call_ollama_mistral_async
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

app = FastAPI()

# Global state for processing status
ProcessingStatus = Literal["idle", "processing", "complete", "error"]
processing_status: ProcessingStatus = "idle"

origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:3003",  # Added to allow frontend on port 3003
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

# Enhanced logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()  # Also log to console for real-time viewing
    ]
)

# Create a custom formatter for console output with colors
class ColoredFormatter(logging.Formatter):
    """Custom formatter adding colors to different log levels."""
    
    # Color codes
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
        'RESET': '\033[0m'      # Reset
    }
    
    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        record.levelname = f"{log_color}{record.levelname}{self.COLORS['RESET']}"
        return super().format(record)

# Apply colored formatter to console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(ColoredFormatter('%(asctime)s - %(levelname)s - %(message)s'))
logging.getLogger().handlers[1] = console_handler

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

@app.post("/upload-pdf/")
async def upload_pdf(
    file: UploadFile = File(...),
    class_name: str = Form(...),
    subject: str = Form(...),
    chapter: str = Form(...)
):
    global processing_status
    
    # Reset state at the beginning of an upload
    processing_status = "processing"
    
    # Clean up previous exports to ensure a fresh start
    if os.path.exists("questions.json"):
         try:
             os.remove("questions.json")
             logging.info("🗑️  Removed previous questions.json export")
         except Exception as e:
             logging.warning(f"⚠️  Could not delete questions.json: {e}")
    
    """Start a brand-new processing session.

    This function now orchestrates the entire workflow from PDF upload to question
    generation, deduplication, and final export.
    """
    
    # --- 1. INITIAL SETUP & CLEANUP ---
    log_separator("🚀 INITIATING NEW PROCESSING SESSION", "═")
    
    overall_start_time = time.time()
    
    # Ensure the upload directory exists
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    # Save uploaded file
    file_start_time = time.time()
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    log_timing(file_start_time, "File upload and save")
    
    # Extract pages
    log_separator("📄 EXTRACTING PAGES FROM PDF", "─")
    extract_start_time = time.time()
    pages = extract_pages_from_pdf(file_path)
    log_timing(extract_start_time, "Page extraction")
    
    logging.info(f"📊 Extracted {len(pages)} pages from PDF")
    
    existing_qs = [q["question"] for q in get_all_questions()]
    # Pre-compute embeddings for existing questions once to reduce repeated encoding overhead
    existing_embs = (
        dedup_model.encode(existing_qs, convert_to_tensor=True) if existing_qs else None
    )
    new_questions = []
    
    logging.info(f"🗃️  Found {len(existing_qs)} existing questions in database")
    
    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)

    async def process_page(page_text: str, page_num: int):
        """Generates questions for a single page, respecting the semaphore."""
        page_start_time = time.time()
        
        async with semaphore:
            logging.info(f"🔄 Processing page {page_num}/{len(pages)} - Requesting MCQs...")
            
            prompt = f'''You are an intelligent educational assistant.

Read the following page excerpt from a school book (Grades 1–10) and identify its main concepts.
Generate between 3 and 5 multiple-choice questions (MCQs) that test understanding of those concepts.

Rules:
1. Provide 3 to 5 questions total.
2. Each question must stem directly from the provided text.
3. Do not repeat or rephrase existing questions within the same list.
4. Give exactly 4 answer options labelled A–D in an array.
5. Clearly indicate the correct answer for each question using the same letter (e.g., "A").
6. Return ONLY a valid JSON array of objects in the form:

[
  {{"question": "...", "options": ["A", "B", "C", "D"], "answer": "A"}},
  ...
]

Text:
"""
{page_text}
"""
'''
            try:
                response = await call_ollama_mistral_async(prompt)
                data = json.loads(response)
                
                if isinstance(data, dict) and "questions" in data:
                    questions_list = data["questions"]
                else:
                    questions_list = data
                
                if not isinstance(questions_list, list):
                    raise ValueError("Expected a list of questions in JSON output")
                
                page_elapsed = time.time() - page_start_time
                logging.info(f"✅ Page {page_num} completed: {len(questions_list)} MCQs generated in {page_elapsed:.1f}s")
                log_progress_bar(page_num, len(pages), "📖 Pages processed")
                
                return questions_list
            except Exception as e:
                logging.error(f"❌ Error processing page {page_num}: {e}")
                return []

    # Create and run all page-processing tasks concurrently
    log_separator("🧠 GENERATING QUESTIONS WITH AI", "─")
    processing_start_time = time.time()
    
    logging.info(f"⚡ Starting concurrent processing with {CONCURRENT_REQUESTS} workers")
    
    tasks = [process_page(page, i + 1) for i, page in enumerate(pages) if page.strip()]
    results_from_pages = await asyncio.gather(*tasks)

    log_timing(processing_start_time, "AI question generation")
    
    # Process results and save to database
    log_separator("💾 SAVING QUESTIONS TO DATABASE", "─")
    save_start_time = time.time()
    
    total_questions_processed = 0
    questions_saved = 0
    questions_skipped = 0
    
    for page_idx, questions_list in enumerate(results_from_pages):
        for q_obj in questions_list:
            total_questions_processed += 1
            
            if not q_obj or "question" not in q_obj:
                questions_skipped += 1
                continue
                
            # Replace duplicate check with fast embedding-based comparison
            new_emb = dedup_model.encode(q_obj["question"], convert_to_tensor=True)
            if is_similar_fast(new_emb, existing_embs):
                questions_skipped += 1
                logging.info(f"⏭️  Skipped similar question: {q_obj['question'][:50]}...")
                continue

            saved_question = {
                "class": class_name,
                "subject": subject,
                "chapter": chapter,
                **q_obj,
            }
            # Insert and track the newly created question
            inserted_id = save_question(saved_question)
            saved_question["_id"] = inserted_id
            existing_qs.append(q_obj["question"])
            new_questions.append(saved_question)
            questions_saved += 1
            
            if questions_saved % 5 == 0:  # Log every 5th saved question
                log_progress_bar(questions_saved, total_questions_processed, "💾 Questions saved")
            
            logging.info(f"✅ Saved question: {q_obj['question'][:80]}...")

            # Update cached embeddings incrementally
            if existing_embs is None:
                existing_embs = new_emb.unsqueeze(0)
            else:
                existing_embs = torch.cat((existing_embs, new_emb.unsqueeze(0)), dim=0)

    log_timing(save_start_time, "Database operations")
    
    # Export *only* the questions created during this processing session
    log_separator("📤 EXPORTING RESULTS", "─")
    export_start_time = time.time()
    export_questions_to_json_subset(new_questions, "questions.json")
    log_timing(export_start_time, "Results export")
    
    # Final summary
    log_separator("🎉 PROCESSING COMPLETE", "═")
    log_timing(overall_start_time, "Total processing time")
    
    logging.info(f"📊 SUMMARY:")
    logging.info(f"   📄 Pages processed: {len(pages)}")
    logging.info(f"   🔢 Total questions generated: {total_questions_processed}")
    logging.info(f"   💾 Questions saved: {questions_saved}")
    logging.info(f"   ⏭️  Questions skipped (duplicates): {questions_skipped}")
    logging.info(f"   📁 Results exported to: questions.json")
    
    log_separator("", "═")

    processing_status = "complete"

    # 🎯 NEW: Automatic shutdown after completion
    # logging.info("🚀 Initiating automatic shutdown sequence...")
    
    # # Start shutdown in background thread to not block the HTTP response
    # shutdown_thread = threading.Thread(target=delayed_shutdown, daemon=True)
    # shutdown_thread.start()

    return {
        "status": "completed",
        "message": "PDF processed successfully! Servers will shutdown automatically in 5 seconds.",
        "summary": {
            "pages_processed": len(pages),
            "questions_generated": total_questions_processed,
            "questions_saved": questions_saved,
            "questions_skipped": questions_skipped,
            "output_file": "questions.json"
        }
    }

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