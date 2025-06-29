#!/usr/bin/env python3
"""
Enhanced Log Viewer for Question Bank Processing
Monitor your PDF processing with beautiful real-time visualization
"""

import time
import os
import sys
from datetime import datetime
from typing import Dict, List
import re

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
    
    # Additional colors
    PURPLE = '\033[35m'
    YELLOW = '\033[33m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    GRAY = '\033[90m'

class LogViewer:
    def __init__(self, log_file: str = "app.log"):
        self.log_file = log_file
        self.stats = {
            'pages_processed': 0,
            'questions_generated': 0,
            'questions_saved': 0,
            'questions_skipped': 0,
            'errors': 0,
            'start_time': None,
            'current_phase': 'Waiting...'
        }
        self.phases = [
            "🚀 Starting PDF Processing",
            "📄 Extracting Pages",
            "🧠 Generating Questions",
            "💾 Saving to Database", 
            "📤 Exporting Results",
            "🎉 Complete"
        ]
        
    def clear_screen(self):
        """Clear the terminal screen."""
        os.system('cls' if os.name == 'nt' else 'clear')
        
    def print_header(self):
        """Print the application header."""
        print(f"{Colors.BOLD}{Colors.HEADER}")
        print("╔" + "═" * 78 + "╗")
        print("║" + " " * 25 + "QUESTION BANK PROCESSOR" + " " * 30 + "║")
        print("║" + " " * 23 + "Real-time Log Monitor" + " " * 32 + "║")
        print("╚" + "═" * 78 + "╝")
        print(f"{Colors.ENDC}")
        
    def print_stats_panel(self):
        """Print the current statistics panel."""
        elapsed = ""
        if self.stats['start_time']:
            elapsed_seconds = time.time() - self.stats['start_time']
            minutes, seconds = divmod(elapsed_seconds, 60)
            elapsed = f"{int(minutes):02d}:{int(seconds):02d}"
        
        print(f"{Colors.BOLD}{Colors.OKBLUE}")
        print("┌─ STATISTICS " + "─" * 66 + "┐")
        print(f"│ {Colors.OKCYAN}Current Phase:{Colors.ENDC}{Colors.BOLD} {self.stats['current_phase']:<50} {Colors.OKBLUE}│")
        print(f"│ {Colors.OKGREEN}Pages Processed:{Colors.ENDC}{Colors.BOLD} {self.stats['pages_processed']:<20} {Colors.PURPLE}Questions Generated:{Colors.ENDC}{Colors.BOLD} {self.stats['questions_generated']:<15} {Colors.OKBLUE}│")
        print(f"│ {Colors.OKCYAN}Questions Saved:{Colors.ENDC}{Colors.BOLD} {self.stats['questions_saved']:<20} {Colors.WARNING}Questions Skipped:{Colors.ENDC}{Colors.BOLD} {self.stats['questions_skipped']:<16} {Colors.OKBLUE}│")
        print(f"│ {Colors.FAIL}Errors:{Colors.ENDC}{Colors.BOLD} {self.stats['errors']:<30} {Colors.GRAY}Elapsed Time:{Colors.ENDC}{Colors.BOLD} {elapsed:<20} {Colors.OKBLUE}│")
        print("└" + "─" * 78 + "┘")
        print(f"{Colors.ENDC}")
        
    def print_progress_bar(self, current: int, total: int, label: str = "Progress", width: int = 50):
        """Print a visual progress bar."""
        if total == 0:
            return
            
        progress = min(current / total, 1.0)
        filled = int(width * progress)
        bar = "█" * filled + "░" * (width - filled)
        percentage = progress * 100
        
        print(f"{Colors.BOLD}{Colors.OKGREEN}{label}: {Colors.ENDC}", end="")
        print(f"{Colors.OKCYAN}[{bar}]{Colors.ENDC} ", end="")
        print(f"{Colors.BOLD}{percentage:6.1f}% ({current}/{total}){Colors.ENDC}")
        
    def print_recent_logs(self, logs: List[str], max_lines: int = 15):
        """Print recent log entries with color coding."""
        print(f"{Colors.BOLD}{Colors.OKBLUE}")
        print("┌─ RECENT ACTIVITY " + "─" * 61 + "┐")
        print(f"{Colors.ENDC}")
        
        for log_line in logs[-max_lines:]:
            colored_line = self.colorize_log_line(log_line)
            # Truncate long lines
            if len(log_line) > 76:
                colored_line = colored_line[:73] + "..."
            print(f"│ {colored_line:<76} │")
            
        print(f"{Colors.BOLD}{Colors.OKBLUE}")
        print("└" + "─" * 78 + "┘")
        print(f"{Colors.ENDC}")
        
    def colorize_log_line(self, line: str) -> str:
        """Add colors to log lines based on their content."""
        if "ERROR" in line:
            return f"{Colors.FAIL}{line}{Colors.ENDC}"
        elif "WARNING" in line:
            return f"{Colors.WARNING}{line}{Colors.ENDC}"
        elif any(emoji in line for emoji in ["✅", "🎉", "✨"]):
            return f"{Colors.OKGREEN}{line}{Colors.ENDC}"
        elif any(emoji in line for emoji in ["🔄", "⚡", "🧠"]):
            return f"{Colors.OKCYAN}{line}{Colors.ENDC}"
        elif any(emoji in line for emoji in ["📁", "📄", "💾", "📤"]):
            return f"{Colors.PURPLE}{line}{Colors.ENDC}"
        elif "⏱️" in line:
            return f"{Colors.YELLOW}{line}{Colors.ENDC}"
        elif "⏭️" in line:
            return f"{Colors.GRAY}{line}{Colors.ENDC}"
        else:
            return line
            
    def update_stats_from_log(self, logs: List[str]):
        """Update statistics by parsing recent logs."""
        for line in logs:
            # Count pages processed
            if "Page" in line and "completed" in line:
                try:
                    match = re.search(r'Page (\d+)', line)
                    if match:
                        page_num = int(match.group(1))
                        self.stats['pages_processed'] = max(self.stats['pages_processed'], page_num)
                except:
                    pass
                    
            # Count questions
            if "MCQs generated" in line:
                try:
                    match = re.search(r'(\d+) MCQs generated', line)
                    if match:
                        self.stats['questions_generated'] += int(match.group(1))
                except:
                    pass
                    
            if "Saved question:" in line:
                self.stats['questions_saved'] += 1
                
            if "Skipped similar question:" in line:
                self.stats['questions_skipped'] += 1
                
            if "ERROR" in line:
                self.stats['errors'] += 1
                
            # Update current phase
            if "STARTING PDF PROCESSING" in line:
                self.stats['current_phase'] = "🚀 Starting PDF Processing"
                self.stats['start_time'] = time.time()
            elif "EXTRACTING PAGES" in line:
                self.stats['current_phase'] = "📄 Extracting Pages from PDF"
            elif "GENERATING QUESTIONS" in line:
                self.stats['current_phase'] = "🧠 Generating Questions with AI"
            elif "SAVING QUESTIONS" in line:
                self.stats['current_phase'] = "💾 Saving Questions to Database"
            elif "EXPORTING RESULTS" in line:
                self.stats['current_phase'] = "📤 Exporting Results"
            elif "PROCESSING COMPLETE" in line:
                self.stats['current_phase'] = "🎉 Processing Complete!"
                
    def print_footer(self):
        """Print the footer with instructions."""
        print(f"{Colors.GRAY}")
        print("─" * 80)
        print("Press Ctrl+C to exit the log viewer")
        print(f"Monitoring: {self.log_file}")
        print(f"{Colors.ENDC}")
        
    def monitor_logs(self, refresh_interval: float = 2.0):
        """Monitor the log file in real-time."""
        logs = []
        last_position = 0
        
        try:
            while True:
                try:
                    # Check if log file exists
                    if not os.path.exists(self.log_file):
                        self.clear_screen()
                        self.print_header()
                        print(f"\n{Colors.WARNING}Waiting for log file: {self.log_file}{Colors.ENDC}")
                        print(f"{Colors.GRAY}Start your PDF processing to see logs...{Colors.ENDC}")
                        time.sleep(refresh_interval)
                        continue
                    
                    # Read new log entries
                    with open(self.log_file, 'r', encoding='utf-8') as f:
                        f.seek(last_position)
                        new_lines = f.readlines()
                        last_position = f.tell()
                        
                    # Add new lines to our log buffer
                    for line in new_lines:
                        line = line.strip()
                        if line:
                            logs.append(line)
                            
                    # Update statistics
                    if new_lines:
                        self.update_stats_from_log(new_lines)
                    
                    # Refresh display
                    self.clear_screen()
                    self.print_header()
                    self.print_stats_panel()
                    
                    # Show progress bars if we have data
                    if self.stats['pages_processed'] > 0:
                        # Estimate total pages (this could be improved with actual page count)
                        estimated_total = max(self.stats['pages_processed'], 10)
                        self.print_progress_bar(
                            self.stats['pages_processed'], 
                            estimated_total, 
                            "📖 Pages Processed"
                        )
                        
                    if self.stats['questions_generated'] > 0:
                        print()  # Add spacing
                        
                    self.print_recent_logs(logs)
                    self.print_footer()
                    
                except FileNotFoundError:
                    pass
                except Exception as e:
                    print(f"{Colors.FAIL}Error reading log file: {e}{Colors.ENDC}")
                    
                time.sleep(refresh_interval)
                
        except KeyboardInterrupt:
            print(f"\n{Colors.OKCYAN}Log viewer stopped.{Colors.ENDC}")
            sys.exit(0)

def main():
    """Main function to run the log viewer."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Real-time log viewer for Question Bank Processor")
    parser.add_argument(
        "--log-file", 
        default="app.log", 
        help="Path to the log file to monitor (default: app.log)"
    )
    parser.add_argument(
        "--refresh", 
        type=float, 
        default=1.0, 
        help="Refresh interval in seconds (default: 1.0)"
    )
    
    args = parser.parse_args()
    
    viewer = LogViewer(args.log_file)
    print(f"{Colors.BOLD}{Colors.OKGREEN}")
    print("🚀 Starting Real-time Log Viewer...")
    print(f"📁 Monitoring: {args.log_file}")
    print(f"🔄 Refresh rate: {args.refresh}s")
    print(f"{Colors.ENDC}")
    time.sleep(2)
    
    viewer.monitor_logs(args.refresh)

if __name__ == "__main__":
    main() 