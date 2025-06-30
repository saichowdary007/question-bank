import React, { useState, useCallback } from 'react'
import { motion } from 'framer-motion'
import { Download, FileText, CheckCircle, AlertCircle, Clock } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { cn, formatBytes, formatTimestamp } from '@/lib/utils'
import { DownloadProps, FileMetadata } from '@/types'

const DownloadManager: React.FC<DownloadProps> = ({
  fileId,
  metadata,
  onDownload,
}) => {
  const [downloadProgress, setDownloadProgress] = useState(0)
  const [isDownloading, setIsDownloading] = useState(false)
  const [downloadError, setDownloadError] = useState<string | null>(null)

  const handleDownload = useCallback(async () => {
    if (isDownloading || !metadata.downloadUrl) return

    setIsDownloading(true)
    setDownloadError(null)
    setDownloadProgress(0)

    try {
      // Simulate download progress
      const progressInterval = setInterval(() => {
        setDownloadProgress(prev => {
          const newProgress = prev + Math.random() * 15
          return newProgress >= 100 ? 100 : newProgress
        })
      }, 200)

      // Actual download logic would go here
      const response = await fetch(metadata.downloadUrl)
      
      if (!response.ok) {
        throw new Error(`Download failed: ${response.statusText}`)
      }

      const blob = await response.blob()
      
      // Create download link
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = metadata.name
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)

      clearInterval(progressInterval)
      setDownloadProgress(100)
      
      // Call optional callback
      onDownload?.(fileId)
      
      // Reset after a delay
      setTimeout(() => {
        setDownloadProgress(0)
        setIsDownloading(false)
      }, 2000)

    } catch (error) {
      setDownloadError(error instanceof Error ? error.message : 'Download failed')
      setIsDownloading(false)
      setDownloadProgress(0)
    }
  }, [isDownloading, metadata.downloadUrl, metadata.name, fileId, onDownload])

  const getStatusIcon = () => {
    switch (metadata.status) {
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case 'error':
        return <AlertCircle className="h-4 w-4 text-red-500" />
      case 'processing':
        return <Clock className="h-4 w-4 text-yellow-500" />
      default:
        return <FileText className="h-4 w-4 text-muted-foreground" />
    }
  }

  const getStatusColor = () => {
    switch (metadata.status) {
      case 'completed':
        return 'border-green-500/20 bg-green-500/5'
      case 'error':
        return 'border-red-500/20 bg-red-500/5'
      case 'processing':
        return 'border-yellow-500/20 bg-yellow-500/5'
      default:
        return 'border-border bg-card'
    }
  }

  const canDownload = metadata.status === 'completed' && metadata.downloadUrl && !isDownloading

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "p-4 rounded-lg border transition-all duration-300",
        getStatusColor()
      )}
    >
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 mt-1">
          {getStatusIcon()}
        </div>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <h4 className="font-medium truncate">{metadata.name}</h4>
              <div className="flex items-center gap-4 mt-1 text-xs text-muted-foreground">
                <span>{formatBytes(metadata.size)}</span>
                <span>{metadata.type}</span>
                <span>Uploaded {formatTimestamp(metadata.uploadedAt)}</span>
              </div>
            </div>
            
            <Button
              variant="magic"
              size="sm"
              onClick={handleDownload}
              disabled={!canDownload}
              className="flex-shrink-0"
              aria-label={`Download ${metadata.name}`}
            >
              <Download className="h-4 w-4 mr-2" />
              {isDownloading ? 'Downloading...' : 'Download'}
            </Button>
          </div>

          {/* Status Messages */}
          {metadata.status === 'processing' && (
            <div className="mt-2">
              <p className="text-sm text-yellow-600">Processing file...</p>
              {metadata.progress !== undefined && (
                <Progress value={metadata.progress} className="mt-1 h-1" />
              )}
            </div>
          )}

          {metadata.status === 'error' && metadata.error && (
            <div className="mt-2">
              <p className="text-sm text-red-600">{metadata.error}</p>
            </div>
          )}

          {/* Download Progress */}
          {isDownloading && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              className="mt-2"
            >
              <div className="flex items-center justify-between text-sm mb-1">
                <span>Downloading...</span>
                <span>{Math.round(downloadProgress)}%</span>
              </div>
              <Progress value={downloadProgress} className="h-2" />
            </motion.div>
          )}

          {/* Download Error */}
          {downloadError && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              className="mt-2"
            >
              <p className="text-sm text-red-600">{downloadError}</p>
              <Button
                variant="outline"
                size="sm"
                onClick={handleDownload}
                className="mt-1"
              >
                Retry Download
              </Button>
            </motion.div>
          )}

          {/* File Metadata */}
          {metadata.status === 'completed' && (
            <div className="mt-3 p-2 bg-muted/50 rounded text-xs">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <span className="font-medium">File ID:</span>
                  <span className="ml-1 font-mono">{fileId.slice(0, 8)}...</span>
                </div>
                <div>
                  <span className="font-medium">Status:</span>
                  <span className="ml-1 capitalize">{metadata.status}</span>
                </div>
                {metadata.lastModified && (
                  <div className="col-span-2">
                    <span className="font-medium">Modified:</span>
                    <span className="ml-1">{formatTimestamp(new Date(metadata.lastModified))}</span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  )
}

export default DownloadManager