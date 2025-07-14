import React, { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Copy, Trash2, Pause, Play, Download } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn, formatTimestamp, throttle } from '@/lib/utils'
import { LogViewerProps, LogEntry, WebSocketMessage } from '@/types'

const LogViewer: React.FC<LogViewerProps> = ({
  wsEndpoint,
  bufferSize = 1000,
  autoReconnect = true,
  className,
}) => {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const [isPaused, setIsPaused] = useState(false)
  const [autoScroll, setAutoScroll] = useState(true)
  const [connectionAttempts, setConnectionAttempts] = useState(0)
  
  const wsRef = useRef<WebSocket | null>(null)
  const logContainerRef = useRef<HTMLDivElement>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>()

  const scrollToBottom = useCallback(() => {
    if (autoScroll && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight
    }
  }, [autoScroll])

  const throttledScrollToBottom = useCallback(
    throttle(scrollToBottom, 100),
    [scrollToBottom]
  )

  const addLog = useCallback((newLog: LogEntry) => {
    if (isPaused) return
    
    setLogs(prev => {
      const updated = [...prev, newLog]
      // Keep buffer size manageable
      if (updated.length > bufferSize) {
        return updated.slice(-bufferSize)
      }
      return updated
    })
    
    throttledScrollToBottom()
  }, [isPaused, bufferSize, throttledScrollToBottom])

  const connectWebSocket = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return
    }

    try {
      const ws = new WebSocket(wsEndpoint)
      wsRef.current = ws

      ws.onopen = () => {
        console.log('WebSocket connected')
        setIsConnected(true)
        setConnectionAttempts(0)
        
        addLog({
          id: `connection-${Date.now()}`,
          timestamp: new Date().toISOString(),
          level: 'success',
          message: 'Connected to log stream',
        })
      }

      ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data)
          
          if (message.type === 'log') {
            const logEntry = message.data as LogEntry
            addLog({
              ...logEntry,
              id: logEntry.id || `log-${Date.now()}-${Math.random()}`,
            })
          }
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error)
          addLog({
            id: `error-${Date.now()}`,
            timestamp: new Date().toISOString(),
            level: 'error',
            message: `Failed to parse message: ${event.data}`,
          })
        }
      }

      ws.onclose = (event) => {
        console.log('WebSocket disconnected:', event.code, event.reason)
        setIsConnected(false)
        
        addLog({
          id: `disconnection-${Date.now()}`,
          timestamp: new Date().toISOString(),
          level: 'warning',
          message: `Disconnected from log stream (${event.code})`,
        })

        // Auto-reconnect logic
        if (autoReconnect && connectionAttempts < 5) {
          const delay = Math.min(1000 * Math.pow(2, connectionAttempts), 30000)
          setConnectionAttempts(prev => prev + 1)
          
          addLog({
            id: `reconnect-${Date.now()}`,
            timestamp: new Date().toISOString(),
            level: 'info',
            message: `Reconnecting in ${delay / 1000}s... (attempt ${connectionAttempts + 1}/5)`,
          })

          reconnectTimeoutRef.current = setTimeout(() => {
            connectWebSocket()
          }, delay)
        }
      }

      ws.onerror = (error) => {
        console.error('WebSocket error:', error)
        addLog({
          id: `ws-error-${Date.now()}`,
          timestamp: new Date().toISOString(),
          level: 'error',
          message: 'WebSocket connection error',
        })
      }
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error)
      addLog({
        id: `connection-error-${Date.now()}`,
        timestamp: new Date().toISOString(),
        level: 'error',
        message: 'Failed to establish WebSocket connection',
      })
    }
  }, [wsEndpoint, autoReconnect, connectionAttempts, addLog])

  useEffect(() => {
    connectWebSocket()

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [connectWebSocket])

  const handleScroll = useCallback(() => {
    if (!logContainerRef.current) return
    
    const { scrollTop, scrollHeight, clientHeight } = logContainerRef.current
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 10
    
    if (autoScroll !== isAtBottom) {
      setAutoScroll(isAtBottom)
    }
  }, [autoScroll])

  const copyLogs = useCallback(() => {
    const logText = logs
      .map(log => `[${formatTimestamp(log.timestamp)}] ${log.level.toUpperCase()}: ${log.message}`)
      .join('\n')
    
    navigator.clipboard.writeText(logText).then(() => {
      addLog({
        id: `copy-${Date.now()}`,
        timestamp: new Date().toISOString(),
        level: 'info',
        message: `Copied ${logs.length} log entries to clipboard`,
      })
    }).catch(() => {
      addLog({
        id: `copy-error-${Date.now()}`,
        timestamp: new Date().toISOString(),
        level: 'error',
        message: 'Failed to copy logs to clipboard',
      })
    })
  }, [logs, addLog])

  const clearLogs = useCallback(() => {
    setLogs([])
    addLog({
      id: `clear-${Date.now()}`,
      timestamp: new Date().toISOString(),
      level: 'info',
      message: 'Log history cleared',
    })
  }, [addLog])

  const downloadLogs = useCallback(() => {
    const logText = logs
      .map(log => `[${formatTimestamp(log.timestamp)}] ${log.level.toUpperCase()}: ${log.message}`)
      .join('\n')
    
    const blob = new Blob([logText], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `logs-${new Date().toISOString().split('T')[0]}.txt`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }, [logs])

  const getLogLevelColor = (level: LogEntry['level']) => {
    switch (level) {
      case 'error':
        return 'text-red-400'
      case 'warning':
        return 'text-yellow-400'
      case 'success':
        return 'text-green-400'
      case 'info':
      default:
        return 'text-blue-400'
    }
  }

  const getLogLevelBg = (level: LogEntry['level']) => {
    switch (level) {
      case 'error':
        return 'bg-red-500/10 border-red-500/20'
      case 'warning':
        return 'bg-yellow-500/10 border-yellow-500/20'
      case 'success':
        return 'bg-green-500/10 border-green-500/20'
      case 'info':
      default:
        return 'bg-blue-500/10 border-blue-500/20'
    }
  }

  return (
    <div className={cn("flex flex-col bg-card border rounded-lg", className)}>
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold">Log Viewer</h3>
          <div className={cn(
            "w-2 h-2 rounded-full",
            isConnected ? "bg-green-500 animate-pulse" : "bg-red-500"
          )} />
          <span className="text-xs text-muted-foreground">
            {isConnected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
        
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setIsPaused(!isPaused)}
            className="h-8 w-8"
            aria-label={isPaused ? 'Resume logging' : 'Pause logging'}
          >
            {isPaused ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}
          </Button>
          
          <Button
            variant="ghost"
            size="icon"
            onClick={copyLogs}
            className="h-8 w-8"
            disabled={logs.length === 0}
            aria-label="Copy logs to clipboard"
          >
            <Copy className="h-4 w-4" />
          </Button>
          
          <Button
            variant="ghost"
            size="icon"
            onClick={downloadLogs}
            className="h-8 w-8"
            disabled={logs.length === 0}
            aria-label="Download logs"
          >
            <Download className="h-4 w-4" />
          </Button>
          
          <Button
            variant="ghost"
            size="icon"
            onClick={clearLogs}
            className="h-8 w-8"
            disabled={logs.length === 0}
            aria-label="Clear logs"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Log Container */}
      <div
        ref={logContainerRef}
        className="flex-1 h-[400px] overflow-y-auto p-4 space-y-1 font-mono text-sm"
        onScroll={handleScroll}
      >
        <AnimatePresence initial={false}>
          {logs.map((log, index) => (
            <motion.div
              key={log.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.2 }}
              className={cn(
                "log-entry p-2 rounded border-l-2 transition-colors",
                getLogLevelBg(log.level)
              )}
            >
              <div className="flex items-start gap-2">
                <span className="text-xs text-muted-foreground whitespace-nowrap">
                  {formatTimestamp(log.timestamp)}
                </span>
                <span className={cn(
                  "text-xs font-medium uppercase tracking-wide whitespace-nowrap",
                  getLogLevelColor(log.level)
                )}>
                  {log.level}
                </span>
                <span className="flex-1 break-words">
                  {log.message}
                </span>
              </div>
              
              {log.metadata && (
                <div className="mt-1 pl-16 text-xs text-muted-foreground">
                  <pre className="whitespace-pre-wrap">
                    {JSON.stringify(log.metadata, null, 2)}
                  </pre>
                </div>
              )}
            </motion.div>
          ))}
        </AnimatePresence>
        
        {logs.length === 0 && (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            <p>No logs yet. Waiting for data...</p>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between p-2 border-t text-xs text-muted-foreground">
        <span>{logs.length} entries</span>
        <div className="flex items-center gap-2">
          {isPaused && (
            <span className="text-yellow-500">⏸ Paused</span>
          )}
          {!autoScroll && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setAutoScroll(true)
                scrollToBottom()
              }}
              className="h-6 px-2 text-xs"
            >
              Scroll to bottom
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}

export default LogViewer