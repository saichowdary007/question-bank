"use client";

import { useEffect, useRef } from "react";
import styles from './log-viewer.module.css';
import 'xterm/css/xterm.css';

interface Log {
  level: "INFO" | "WARNING" | "ERROR" | "DEBUG" | "CRITICAL";
  message: string;
  timestamp: string;
}

interface LogViewerProps {
  logs: Log[];
}

const LogViewer = ({ logs }: LogViewerProps) => {
  const terminalRef = useRef<HTMLDivElement>(null);
  const term = useRef<any>(null);
  const lastLogIndex = useRef<number>(0);
  const userScrolledUp = useRef<boolean>(false);

  useEffect(() => {
    let isMounted = true;
    const initializeTerminal = async () => {
      if (!terminalRef.current || term.current) return;
      
      const { Terminal } = await import('xterm');
      
      if (!isMounted) return;

      term.current = new Terminal({
        convertEol: true,
        fontSize: 14,
        fontFamily: 'Menlo, Monaco, "Courier New", monospace',
        scrollback: 2000,
        theme: {
          background: '#131313', // A slightly different dark background
          foreground: '#d0d0d0',
        },
        cursorBlink: false,
      });

      term.current.open(terminalRef.current);

      // Handle user scrolling
      term.current.onScroll(() => {
        const buffer = term.current.buffer.active;
        // The viewport is at the bottom if the viewport Y is equal to the base Y
        const atBottom = buffer.viewportY === buffer.baseY;
        userScrolledUp.current = !atBottom;
      });
    };

    initializeTerminal();
    
    return () => { isMounted = false; };
  }, []);

  useEffect(() => {
    if (!term.current || logs.length === lastLogIndex.current) return;

    const newLogs = logs.slice(lastLogIndex.current);
    
    newLogs.forEach(log => {
        if(term.current) {
            // Simple coloring for different log levels
            let color = '\x1b[37m'; // white
            if(log.level === 'ERROR') color = '\x1b[31m'; // red
            if(log.level === 'WARNING') color = '\x1b[33m'; // yellow
            if(log.message.includes("PROCESSING COMPLETE")) color = '\x1b[32;1m'; // bright green

            term.current.writeln(`${color}${log.message}\x1b[0m`);
        }
    });

    lastLogIndex.current = logs.length;
    
    if (term.current && !userScrolledUp.current) {
      term.current.scrollToBottom();
    }
  }, [logs]);

  return (
    <div className={styles.logViewerContainer}>
      <div ref={terminalRef} className={styles.terminal}></div>
    </div>
  );
};

export default LogViewer; 