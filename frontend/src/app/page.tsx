"use client";

import { useState, useEffect } from "react";
import UploadSection from "@/components/upload-section";
import DownloadSection from "@/components/download-section";
import LogViewer from "@/components/log-viewer";

interface Log {
  level: "INFO" | "WARNING" | "ERROR" | "DEBUG" | "CRITICAL";
  message: string;
  timestamp: string;
}

interface Stats {
  pages_processed: number;
  questions_generated: number;
  questions_saved: number;
  questions_skipped: number;
  errors: number;
  start_time: number | null;
  current_phase: string;
  progress: number;
  total_pages: number;
}

export default function Home() {
  const [processingState, setProcessingState] = useState<"idle" | "processing" | "complete" | "error">("idle");
  const [logs, setLogs] = useState<Log[]>([]);
  const [stats, setStats] = useState<Stats>({
    pages_processed: 0,
    questions_generated: 0,
    questions_saved: 0,
    questions_skipped: 0,
    errors: 0,
    start_time: null,
    current_phase: 'Waiting...',
    progress: 0,
    total_pages: 0,
  });

  useEffect(() => {
    // Reset the backend state when the component mounts
    const resetBackendState = async () => {
      try {
        await fetch("http://localhost:8000/reset", { method: "POST" });
        console.log("Backend state reset.");
      } catch (error) {
        console.error("Failed to reset backend state:", error);
      }
    };
    resetBackendState();
  }, []);

  useEffect(() => {
    if (logs.length === 0) {
        setStats({
            pages_processed: 0,
            questions_generated: 0,
            questions_saved: 0,
            questions_skipped: 0,
            errors: 0,
            start_time: null,
            current_phase: 'Waiting...',
            progress: 0,
            total_pages: 0,
        });
        return;
    }

    const newStats = logs.reduce((acc, log) => {
        if (!acc.start_time && log.message.includes("STARTING PDF PROCESSING")) {
            acc.start_time = Date.now();
        }
        if (log.message.includes("Extracted") && log.message.includes("pages from PDF")) {
            const match = log.message.match(/Extracted (\d+) pages/);
            if (match) acc.total_pages = parseInt(match[1]);
        }
        const pageMatch = log.message.match(/Page (\d+) completed/);
        if (pageMatch) {
            acc.pages_processed = Math.max(acc.pages_processed, parseInt(pageMatch[1]));
        }
        if (log.message.includes("MCQs generated")) {
            const match = log.message.match(/(\d+) MCQs generated/);
            if (match) acc.questions_generated += parseInt(match[1]);
        }
        if (log.message.includes("Saved question:")) acc.questions_saved += 1;
        if (log.message.includes("Skipped similar question:")) acc.questions_skipped += 1;
        if (log.level === "ERROR") acc.errors += 1;
        
        if (log.message.includes("STARTING PDF PROCESSING")) acc.current_phase = "🚀 Starting";
        else if (log.message.includes("EXTRACTING PAGES")) acc.current_phase = "📄 Extracting Pages";
        else if (log.message.includes("GENERATING QUESTIONS")) acc.current_phase = "🧠 Generating Questions";
        else if (log.message.includes("SAVING QUESTIONS")) acc.current_phase = "💾 Saving Questions";
        else if (log.message.includes("EXPORTING RESULTS")) acc.current_phase = "📤 Exporting";
        else if (log.message.includes("PROCESSING COMPLETE")) acc.current_phase = "🎉 Complete";

        return acc;
    }, { ...stats, pages_processed: 0, questions_generated: 0, questions_saved: 0, questions_skipped: 0, errors: 0 });

    if (newStats.total_pages > 0) {
        newStats.progress = Math.round((newStats.pages_processed / newStats.total_pages) * 100);
    }

    setStats(newStats);
  }, [logs]);

  useEffect(() => {
    if (processingState !== "processing") return;

    const eventSource = new EventSource("http://localhost:8000/logs/");
    setLogs([]); // Clear previous logs

    eventSource.onmessage = (event) => {
      try {
        const eventData = JSON.parse(event.data);
        const rawLine = eventData.line;

        if (!rawLine) return;

        const logMatch = rawLine.match(/(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - (\w+) - (.+)/);
        
        let logData: Log;

        if (logMatch) {
            const [, timestamp, level, message] = logMatch;
            logData = { 
              timestamp, 
              level: level.toUpperCase() as Log['level'], 
              message: message.trim() 
            };
        } else {
            // Handle non-matching lines (e.g., separators, headers) as INFO
            logData = { 
              timestamp: new Date().toISOString(), 
              level: "INFO", 
              message: rawLine 
            };
        }
        
        setLogs((prevLogs) => [...prevLogs, logData]);
        
        if (logData.message && (logData.message.includes("PROCESSING COMPLETE") || logData.message.includes("Question Bank Processor session complete"))) {
          setProcessingState("complete");
          eventSource.close();
        }
      } catch (error) {
        console.error("Failed to parse log data:", event.data, error);
      }
    };

    eventSource.onerror = (err) => {
      console.error("EventSource error, closing connection:", err);
      eventSource.close();
      // Optionally, you could try to reconnect or show an error to the user
      if (processingState === "processing") {
        setProcessingState("error"); 
      }
    };

    return () => {
      eventSource.close();
    };
  }, [processingState]);

  const elapsed = stats.start_time ? `${String(Math.floor((Date.now() - stats.start_time) / 60000)).padStart(2, '0')}:${String(Math.floor(((Date.now() - stats.start_time) / 1000) % 60)).padStart(2, '0')}` : "00:00";

  return (
    <main className="flex flex-col h-screen bg-gray-900 text-white font-sans">
      {/* Main container */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Rail */}
        <div className="w-full md:w-[30%] flex-shrink-0 flex flex-col gap-4 p-4 border-r border-gray-700">
          <UploadSection 
            setProcessingState={setProcessingState} 
            setLogs={setLogs}
            processingState={processingState}
          />
          <DownloadSection processingState={processingState} />
        </div>

        {/* Right Rail */}
        <div className="flex-1 flex flex-col">
          {/* Header */}
          <div className="p-4 border-b border-gray-700">
            <h1 className="text-2xl font-bold text-pink-500">Question Bank Processor</h1>
            <p className="text-sm text-gray-400">Real-time Log Monitor</p>
          </div>
          
          {/* Stats Panel */}
          <div className="p-4 border-b border-gray-700">
             <h2 className="text-lg font-semibold text-blue-400 mb-2">STATISTICS</h2>
             <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
                <div><span className="font-semibold text-cyan-400">Phase:</span> {stats.current_phase}</div>
                <div><span className="font-semibold text-green-400">Pages:</span> {stats.pages_processed} / {stats.total_pages}</div>
                <div><span className="font-semibold text-magenta-400">Generated:</span> {stats.questions_generated}</div>
                <div><span className="font-semibold text-yellow-400">Skipped:</span> {stats.questions_skipped}</div>
                <div><span className="font-semibold text-cyan-400">Saved:</span> {stats.questions_saved}</div>
                <div><span className="font-semibold text-red-400">Errors:</span> {stats.errors}</div>
                <div><span className="font-semibold text-gray-400">Time:</span> {elapsed}</div>
             </div>
             { stats.total_pages > 0 && 
                <div className="mt-4">
                    <div className="w-full bg-gray-700 rounded-full h-2.5">
                        <div className="bg-blue-500 h-2.5 rounded-full" style={{ width: `${stats.progress}%` }}></div>
                    </div>
                </div>
             }
          </div>

          {/* Log Viewer (Recent Activity) */}
          <div className="flex-1 flex flex-col overflow-y-auto">
             <h2 className="text-lg font-semibold text-blue-400 p-4 sticky top-0 bg-gray-900 z-10">RECENT ACTIVITY</h2>
             <div className="flex-1 p-4 pt-0">
                <LogViewer logs={logs} />
             </div>
          </div>
        </div>
      </div>
    </main>
  );
}
