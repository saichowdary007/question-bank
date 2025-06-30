#!/usr/bin/env python3
"""
Enhanced Log Viewer for Question Bank Processing
Monitor your PDF processing with beautiful real-time visualization
"""

import time
import os
import sys
from datetime import datetime
from typing import Dict, List, Deque
import re
from collections import deque

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich.progress import Progress, BarColumn, TextColumn
from rich.table import Table

import argparse

console = Console()

class LogViewer:
    def __init__(self, log_file: str = "app.log"):
        self.log_file = log_file
        self.stats = {
            'pages_processed': 0,
            'total_pages': 0,
            'questions_generated': 0,
            'questions_saved': 0,
            'questions_skipped': 0,
            'errors': 0,
            'start_time': None,
            'current_phase': 'Waiting...'
        }
        self.recent_logs: Deque[str] = deque(maxlen=100) # Keep last 100 log lines
        
    def _create_header(self) -> Panel:
        """Create the header panel."""
        title = Text("QUESTION BANK PROCESSOR", justify="center", style="bold magenta")
        subtitle = Text("Real-time Log Monitor", justify="center", style="cyan")
        header_text = Text("\n").join([title, subtitle])
        return Panel(header_text, border_style="blue")

    def _create_stats_panel(self) -> Panel:
        """Create the statistics panel."""
        elapsed = ""
        if self.stats['start_time']:
            elapsed_seconds = time.time() - self.stats['start_time']
            minutes, seconds = divmod(elapsed_seconds, 60)
            elapsed = f"{int(minutes):02d}:{int(seconds):02d}"

        stats_grid = Table.grid(expand=True)
        stats_grid.add_column(ratio=1)
        stats_grid.add_column(ratio=1)

        stats_grid.add_row(
            Text(f"Current Phase: {self.stats['current_phase']}", style="cyan"),
            Text(f"Elapsed Time: {elapsed}", style="bold gray50", justify="right")
        )

        progress = self.stats['pages_processed']
        total = self.stats['total_pages'] if self.stats['total_pages'] > 0 else 1
        
        progress_bar = Progress(
            TextColumn("[bold green]{task.description}"),
            BarColumn(bar_width=None),
            TextColumn("[bold green]{task.percentage:>3.0f}% ({task.completed}/{task.total})"),
            expand=True
        )
        progress_task = progress_bar.add_task("Pages", total=total)
        progress_bar.update(progress_task, completed=progress)

        stats_grid.add_row(progress_bar, "")
        
        stats_grid.add_row(
            Text(f"Questions Generated: {self.stats['questions_generated']}", style="magenta"),
            Text(f"Questions Saved: {self.stats['questions_saved']}", style="cyan")
        )
        stats_grid.add_row(
            Text(f"Questions Skipped: {self.stats['questions_skipped']}", style="yellow"),
            Text(f"Errors: {self.stats['errors']}", style="bold red")
        )

        return Panel(stats_grid, title="[bold blue]Statistics", border_style="blue")

    def _create_log_panel(self) -> Panel:
        """Create the recent logs panel."""
        log_text = Text("\n".join(self.colorize_log_line(line) for line in list(self.recent_logs)[-15:]))
        return Panel(log_text, title="[bold blue]Recent Activity", border_style="blue", height=15)

    def colorize_log_line(self, line: str) -> str:
        """Add rich markup to log lines based on their content."""
        line = line.strip()
        if "ERROR" in line:
            return f"[red]{line}[/red]"
        elif "WARNING" in line:
            return f"[yellow]{line}[/yellow]"
        elif any(emoji in line for emoji in ["✅", "🎉", "✨"]):
            return f"[green]{line}[/green]"
        elif any(emoji in line for emoji in ["🔄", "⚡", "🧠"]):
            return f"[cyan]{line}[/cyan]"
        elif any(emoji in line for emoji in ["📁", "📄", "💾", "📤"]):
            return f"[magenta]{line}[/magenta]"
        elif "⏱️" in line:
            return f"[yellow3]{line}[/yellow3]"
        elif "⏭️" in line:
            return f"[gray50]{line}[/gray50]"
        else:
            return line
            
    def update_stats_from_log(self, logs: List[str]):
        """Update statistics by parsing recent logs."""
        # Use a temporary running total for questions generated in this batch
        # to avoid double counting if logs are processed slowly.
        new_questions_generated = 0

        for line in logs:
            if "Extracted" in line and "pages from PDF" in line:
                 match = re.search(r'Extracted (\d+) pages', line)
                 if match:
                    self.stats['total_pages'] = int(match.group(1))

            if "Pages processed:" in line:
                match = re.search(r'(\d+)/(\d+)', line)
                if match:
                    self.stats['pages_processed'] = int(match.group(1))
                    if self.stats['total_pages'] == 1: # If total_pages is default
                        self.stats['total_pages'] = int(match.group(2))

            if "MCQs generated" in line:
                match = re.search(r'(\d+) MCQs generated', line)
                if match:
                    new_questions_generated += int(match.group(1))
                    
            if "Saved question:" in line:
                self.stats['questions_saved'] += 1
            if "Skipped similar question:" in line:
                self.stats['questions_skipped'] += 1
            if "ERROR" in line:
                self.stats['errors'] += 1
                
            # Update current phase
            if "STARTING PDF PROCESSING" in line:
                self.stats['current_phase'] = "🚀 Starting"
                self.stats['start_time'] = time.time()
                # Reset stats for a new run
                for key in ['pages_processed', 'questions_generated', 'questions_saved', 'questions_skipped', 'errors', 'total_pages']:
                    self.stats[key] = 0

            elif "EXTRACTING PAGES" in line:
                self.stats['current_phase'] = "📄 Extracting Pages"
            elif "GENERATING QUESTIONS" in line:
                self.stats['current_phase'] = "🧠 Generating Questions"
            elif "SAVING QUESTIONS" in line:
                self.stats['current_phase'] = "💾 Saving Questions"
            elif "EXPORTING RESULTS" in line:
                self.stats['current_phase'] = "📤 Exporting"
            elif "PROCESSING COMPLETE" in line:
                self.stats['current_phase'] = "🎉 Complete"
        
        # This logic is tricky. The logs provide a per-page count, not a running total.
        # A better approach would be to get the total from the logs if possible.
        # For now, we accumulate.
        if "Generating Questions" in self.stats['current_phase']:
            self.stats['questions_generated'] += new_questions_generated


    def _generate_layout(self) -> Layout:
        """Generate the main layout."""
        layout = Layout()
        layout.split_column(
            Layout(self._create_header(), name="header", size=5),
            Layout(ratio=1, name="main")
        )
        layout["main"].split_row(
            Layout(self._create_stats_panel(), name="stats", ratio=2),
            Layout(self._create_log_panel(), name="logs", ratio=3)
        )
        return layout

    def monitor_logs(self, refresh_interval: float = 0.5):
        """Monitor the log file in real-time using rich.Live."""
        last_position = 0
        
        with Live(
                self._generate_layout(),
                screen=True,                 # use alternate screen so the header isn’t duplicated
                redirect_stderr=False,
                transient=True,
                refresh_per_second=max(1, int(1 / refresh_interval)),
        ) as live:
            try:
                while True:
                    if not os.path.exists(self.log_file):
                        # Display a waiting message
                        waiting_text = Text(f"Waiting for log file: {self.log_file}...", justify="center", style="yellow")
                        live.update(Panel(waiting_text, title="Waiting", border_style="red"))
                        time.sleep(refresh_interval)
                        continue
                    
                    try:
                        with open(self.log_file, 'r', encoding='utf-8') as f:
                            # If file has been truncated (new process started), reset
                            current_size = os.fstat(f.fileno()).st_size
                            if current_size < last_position:
                                last_position = 0
                            
                            f.seek(last_position)
                            new_lines = f.readlines()
                            last_position = f.tell()
                            
                        if new_lines:
                            stripped_lines = [line.strip() for line in new_lines if line.strip()]
                            self.recent_logs.extend(stripped_lines)
                            self.update_stats_from_log(stripped_lines)
                        
                        live.update(self._generate_layout())
                        
                    except Exception:
                        # In case of file reading errors, just skip this iteration
                        pass
                        
            except KeyboardInterrupt:
                # Exit gracefully on Ctrl+C
                pass

def parse_args():
    """Parse command‑line arguments."""
    parser = argparse.ArgumentParser(description="Real‑time log viewer")
    parser.add_argument("--log", default="app.log", help="Path to the log file")
    parser.add_argument("--refresh", type=float, default=0.5,
                        help="Screen refresh interval in seconds (default: 0.5)")
    return parser.parse_args()

def main():
    """Entrypoint invoked from the CLI."""
    args = parse_args()

    viewer = LogViewer(log_file=args.log)
    try:
        console.clear()
        console.print(
            f"[bold green]🚀 Starting Real‑time Log Viewer for[/bold green] "
            f"[bold cyan]{args.log}[/bold cyan]"
        )
        console.print("[yellow]Press Ctrl+C to exit.[/yellow]")
        time.sleep(1.0)
        viewer.monitor_logs(refresh_interval=args.refresh)
    except Exception as e:
        console.print(f"[bold red]An unexpected error occurred: {e}[/bold red]")
    finally:
        console.print("\n[bold yellow]👋 Log monitor stopped.[/bold yellow]")

if __name__ == "__main__":
    main() 