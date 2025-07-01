#!/usr/bin/env python3
"""
Local Setup Script for Question Bank Processor
Ensures ollama is running and has the required models installed
"""

import subprocess
import sys
import time
import requests
import os
from pathlib import Path

class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_step(message):
    print(f"{Colors.BLUE}🔧 {message}...{Colors.ENDC}")

def print_success(message):
    print(f"{Colors.GREEN}✅ {message}{Colors.ENDC}")

def print_warning(message):
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.ENDC}")

def print_error(message):
    print(f"{Colors.RED}❌ {message}{Colors.ENDC}")

def check_ollama_running():
    """Check if Ollama is running locally."""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        return response.status_code == 200
    except:
        return False

def start_ollama():
    """Start Ollama if it's not running."""
    if check_ollama_running():
        print_success("Ollama is already running")
        return True
    
    print_step("Starting Ollama")
    try:
        # Try to start Ollama
        if sys.platform == "darwin":  # macOS
            subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:  # Linux/Windows
            subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Wait for Ollama to start
        for i in range(30):  # Wait up to 30 seconds
            if check_ollama_running():
                print_success("Ollama started successfully")
                return True
            time.sleep(1)
        
        print_error("Failed to start Ollama within 30 seconds")
        return False
    except FileNotFoundError:
        print_error("Ollama not found. Please install Ollama first: https://ollama.ai/")
        return False
    except Exception as e:
        print_error(f"Error starting Ollama: {e}")
        return False

def check_mistral_model():
    """Check if the mistral model is available."""
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
        return "mistral" in result.stdout
    except:
        return False

def install_mistral_model():
    """Install the mistral model."""
    if check_mistral_model():
        print_success("Mistral model is already installed")
        return True
    
    print_step("Installing mistral model (this may take a few minutes)")
    try:
        result = subprocess.run(["ollama", "pull", "mistral"], 
                              capture_output=False, text=True)
        if result.returncode == 0:
            print_success("Mistral model installed successfully")
            return True
        else:
            print_error("Failed to install mistral model")
            return False
    except Exception as e:
        print_error(f"Error installing mistral model: {e}")
        return False

def check_mongodb():
    """Check if MongoDB is accessible."""
    try:
        from pymongo import MongoClient
        client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=5000)
        client.server_info()
        print_success("MongoDB is accessible")
        return True
    except:
        print_warning("MongoDB not accessible at localhost:27017")
        print("  You can:")
        print("  1. Install MongoDB locally")
        print("  2. Use Docker: docker run -d -p 27017:27017 mongo:7")
        print("  3. Use MongoDB Atlas (cloud)")
        return False

def check_python_dependencies():
    """Check if required Python packages are installed."""
    try:
        import fastapi, uvicorn, pymongo, requests, aiohttp
        print_success("All Python dependencies are installed")
        return True
    except ImportError as e:
        print_error(f"Missing Python dependencies: {e}")
        print("Run: pip install -r requirements.txt")
        return False

def main():
    print(f"{Colors.BOLD}{Colors.BLUE}")
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║                    Question Bank Processor Setup                     ║")
    print("║                         Local Development                            ║")
    print("╚══════════════════════════════════════════════════════════════════════╝")
    print(f"{Colors.ENDC}")
    
    success = True
    
    # Check Python dependencies
    print_step("Checking Python dependencies")
    if not check_python_dependencies():
        success = False
    
    # Check and start Ollama
    print_step("Checking Ollama service")
    if not start_ollama():
        success = False
    
    # Install mistral model
    if success:
        print_step("Checking mistral model")
        if not install_mistral_model():
            success = False
    
    # Check MongoDB
    print_step("Checking MongoDB")
    check_mongodb()  # Not critical for setup
    
    print("\n" + "="*70)
    if success:
        print_success("Setup completed successfully!")
        print(f"\n{Colors.GREEN}You can now run:{Colors.ENDC}")
        print(f"  {Colors.YELLOW}python run_server.py{Colors.ENDC}")
        print(f"\n{Colors.GREEN}Or directly:{Colors.ENDC}")
        print(f"  {Colors.YELLOW}uvicorn main:app --host 0.0.0.0 --port 8000{Colors.ENDC}")
    else:
        print_error("Setup failed. Please resolve the issues above.")
        sys.exit(1)

if __name__ == "__main__":
    main() 