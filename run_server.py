#!/usr/bin/env python3
"""
Question Bank Processor - Enhanced Startup Script
Launch the FastAPI server with beautiful logging and monitoring
"""

import os
import sys
import time
import subprocess
from pathlib import Path

class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    PURPLE = '\033[35m'
    GRAY = '\033[90m'
    YELLOW = '\033[93m'
    RESET = '\033[0m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'

def print_banner():
    """Print the application banner."""
    print(f"{Colors.BOLD}{Colors.HEADER}")
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 25 + "QUESTION BANK PROCESSOR" + " " * 30 + "║")
    print("║" + " " * 20 + "Enhanced Logging & Monitoring System" + " " * 23 + "║")
    print("╚" + "═" * 78 + "╝")
    print(f"{Colors.ENDC}")

def print_instructions():
    """Print usage instructions."""
    print(f"{Colors.BOLD}{Colors.OKCYAN}")
    print("📋 ENHANCED FEATURES:")
    print(f"{Colors.ENDC}")
    print(f"  {Colors.OKGREEN}🎨 Colored console output{Colors.ENDC}")
    print(f"  {Colors.OKGREEN}📊 Real-time progress bars{Colors.ENDC}")
    print(f"  {Colors.OKGREEN}⏱️  Detailed timing information{Colors.ENDC}")
    print(f"  {Colors.OKGREEN}📈 Visual statistics dashboard{Colors.ENDC}")
    print(f"  {Colors.OKGREEN}🔍 Enhanced error tracking{Colors.ENDC}")
    
    print(f"\n{Colors.BOLD}{Colors.WARNING}")
    print("🚀 HOW TO USE:")
    print(f"{Colors.ENDC}")
    print(f"  {Colors.OKCYAN}1. Server will start on http://localhost:8000{Colors.ENDC}")
    print(f"  {Colors.OKCYAN}2. Open another terminal and run: python log_viewer.py{Colors.ENDC}")
    print(f"  {Colors.OKCYAN}3. Upload a PDF via the API endpoint{Colors.ENDC}")
    print(f"  {Colors.OKCYAN}4. Watch the beautiful real-time logs!{Colors.ENDC}")
    
    print(f"\n{Colors.BOLD}{Colors.OKBLUE}")
    print("📊 MONITORING OPTIONS:")
    print(f"{Colors.ENDC}")
    print(f"  {Colors.PURPLE}• Basic logs: tail -f app.log{Colors.ENDC}")
    print(f"  {Colors.PURPLE}• Enhanced viewer: python log_viewer.py{Colors.ENDC}")
    print(f"  {Colors.PURPLE}• Fast refresh: python log_viewer.py --refresh 0.5{Colors.ENDC}")

def check_dependencies():
    """Check if required files exist."""
    required_files = ['main.py', 'llm_ollama.py', 'pdf_utils.py', 'db.py', 'deduplication.py']
    missing_files = []
    
    for file in required_files:
        if not Path(file).exists():
            missing_files.append(file)
    
    if missing_files:
        print(f"{Colors.FAIL}❌ Missing required files: {', '.join(missing_files)}{Colors.ENDC}")
        return False
    
    print(f"{Colors.OKGREEN}✅ All required files found{Colors.ENDC}")
    return True

def check_ollama():
    """Check if Ollama is running."""
    try:
        import requests
        ollama_host = os.getenv("OLLAMA_HOST", "localhost")
        response = requests.get(f"http://{ollama_host}:11434/api/tags", timeout=5)
        if response.status_code == 200:
            print(f"{Colors.OKGREEN}✅ Ollama is running and accessible{Colors.ENDC}")
            return True
    except:
        pass
    
    print(f"{Colors.WARNING}⚠️  Warning: Ollama might not be running on localhost:11434{Colors.ENDC}")
    print(f"{Colors.GRAY}   Make sure to start Ollama before processing PDFs{Colors.ENDC}")
    return False

def print_startup_info():
    """Print beautiful startup information and instructions."""
    
    
    print(f"\n{Colors.YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.RESET}")
    print(f"{Colors.GREEN}🎊 Ready to transform your PDFs into beautiful question banks! 🎊{Colors.RESET}")
    print(f"{Colors.YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.RESET}\n")

def main():
    """Main function to start the server."""
    print_banner()
    
    print(f"{Colors.BOLD}{Colors.OKCYAN}🔍 SYSTEM CHECK{Colors.ENDC}")
    print("─" * 40)
    
    # Check dependencies
    if not check_dependencies():
        print(f"{Colors.FAIL}❌ System check failed. Please ensure all files are present.{Colors.ENDC}")
        sys.exit(1)
    
    # Check Ollama
    check_ollama()
    
    # Check if log viewer is available
    if Path("log_viewer.py").exists():
        print(f"{Colors.OKGREEN}✅ Enhanced log viewer available{Colors.ENDC}")
    else:
        print(f"{Colors.WARNING}⚠️  Log viewer not found{Colors.ENDC}")
    
    print()
    print_startup_info()
    
    print(f"\n{Colors.BOLD}{Colors.OKGREEN}")
    print("🚀 STARTING SERVER...")
    print(f"{Colors.ENDC}")
    print("─" * 40)
    
    # Start the server
    try:
        # Clear any existing log file for a fresh start
        if Path("app.log").exists():
            backup_name = f"app_backup_{int(time.time())}.log"
            Path("app.log").rename(backup_name)
            print(f"{Colors.GRAY}📁 Previous log backed up as: {backup_name}{Colors.ENDC}")
        
        print(f"{Colors.OKCYAN}🌐 Server starting at http://localhost:8000{Colors.ENDC}")
        print(f"{Colors.GRAY}📄 API docs available at http://localhost:8000/docs{Colors.ENDC}")
        print(f"{Colors.GRAY}💾 Logs will be written to: app.log{Colors.ENDC}")
        print()
        print(f"{Colors.BOLD}{Colors.WARNING}💡 TIP: Open another terminal and run 'python log_viewer.py' for real-time monitoring{Colors.ENDC}")
        print(f"{Colors.BOLD}{Colors.GREEN}🎯 NEW: Servers will auto-shutdown after PDF processing completes!{Colors.ENDC}")
        print("─" * 80)
        print()
        
        # Start the FastAPI server
        cmd = [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
        print(f"{Colors.GRAY}Running: {' '.join(cmd)}{Colors.ENDC}")
        subprocess.run(cmd)
        
    except KeyboardInterrupt:
        print(f"\n{Colors.OKCYAN}👋 Server stopped gracefully{Colors.ENDC}")
    except Exception as e:
        print(f"\n{Colors.FAIL}❌ Error starting server: {e}{Colors.ENDC}")
        sys.exit(1)

if __name__ == "__main__":
    main() 