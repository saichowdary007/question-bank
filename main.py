from fastapi import FastAPI, File, UploadFile, Form, Request
import os, shutil, json, asyncio, re
from pdf_utils import extract_pages_from_pdf
from llm_ollama import call_ollama_mistral_async
from db import save_question, get_all_questions
from deduplication import is_similar
import logging
from datetime import datetime
import time
from typing import List
import signal
import subprocess
import threading
from fastapi.responses import StreamingResponse

app = FastAPI()

CONCURRENT_REQUESTS = 4

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
    
    # Kill related processes
    processes_to_kill = [
        "uvicorn",
        "run_server",
        "log_viewer"
    ]
    
    killed_count = 0
    for process_name in processes_to_kill:
        try:
            # Use pkill to terminate processes
            result = subprocess.run(
                ["pkill", "-f", process_name], 
                capture_output=True, 
                text=True
            )
            if result.returncode == 0:
                killed_count += 1
                logging.info(f"✅ Stopped {process_name} processes")
            else:
                logging.info(f"ℹ️  No {process_name} processes found")
        except Exception as e:
            logging.warning(f"⚠️  Could not stop {process_name}: {e}")
    
    if killed_count > 0:
        logging.info(f"🎯 Successfully stopped {killed_count} server processes")
    else:
        logging.info("ℹ️  No additional server processes to stop")

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
async def stream_logs(request: Request):
    async def log_generator():
        last_position = 0
        try:
            while True:
                if await request.is_disconnected():
                    break
                
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
                                 yield f"data: {json.dumps(data)}\n\n"
                
                await asyncio.sleep(0.5)  # Poll every 500ms
        except asyncio.CancelledError:
            pass

    return StreamingResponse(log_generator(), media_type="text/event-stream")

@app.post("/upload-pdf/")
async def upload_pdf(
    file: UploadFile = File(...),
    class_name: str = Form(...),
    subject: str = Form(...),
    chapter: str = Form(...)
):
    overall_start_time = time.time()
    
    log_separator("🚀 STARTING PDF PROCESSING", "═")
    logging.info(f"📁 Processing file: {file.filename}")
    logging.info(f"📚 Class: {class_name} | Subject: {subject} | Chapter: {chapter}")
    
    # Save file
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
                
            if is_similar(q_obj["question"], existing_qs):
                questions_skipped += 1
                logging.info(f"⏭️  Skipped similar question: {q_obj['question'][:50]}...")
                continue

            saved_question = {
                "class": class_name,
                "subject": subject,
                "chapter": chapter,
                **q_obj,
            }
            save_question(saved_question)
            existing_qs.append(q_obj["question"])
            new_questions.append(saved_question)
            questions_saved += 1
            
            if questions_saved % 5 == 0:  # Log every 5th saved question
                log_progress_bar(questions_saved, total_questions_processed, "💾 Questions saved")
            
            logging.info(f"✅ Saved question: {q_obj['question'][:80]}...")

    log_timing(save_start_time, "Database operations")
    
    # Convert MongoDB ObjectIds to strings for JSON serialisation
    log_separator("📤 EXPORTING RESULTS", "─")
    export_start_time = time.time()
    
    serialisable_questions = []
    for q in new_questions:
        q_copy = q.copy()
        if "_id" in q_copy:
            q_copy["_id"] = str(q_copy["_id"])
        serialisable_questions.append(q_copy)

    # Export questions to JSON
    with open("questions.json", "w", encoding="utf-8") as fp:
        json.dump({
            "exported_at": datetime.utcnow().isoformat(),
            "total_questions": len(serialisable_questions),
            "questions": serialisable_questions,
        }, fp, indent=2, ensure_ascii=False)

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

    # 🎯 NEW: Automatic shutdown after completion
    logging.info("🚀 Initiating automatic shutdown sequence...")
    
    # Start shutdown in background thread to not block the HTTP response
    shutdown_thread = threading.Thread(target=delayed_shutdown, daemon=True)
    shutdown_thread.start()

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