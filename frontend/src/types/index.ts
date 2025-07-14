export interface FileMetadata {
  id: string
  name: string
  size: number
  type: string
  lastModified: number
  uploadedAt: Date
  status: 'pending' | 'uploading' | 'processing' | 'completed' | 'error'
  progress?: number
  error?: string
  downloadUrl?: string
}

export interface LogEntry {
  id: string
  timestamp: string
  level: 'info' | 'warning' | 'error' | 'success'
  message: string
  metadata?: Record<string, any>
}

export interface FileUploadProps {
  maxSize: number
  acceptedTypes: string[]
  onUpload: (files: File[]) => Promise<void>
  multiple?: boolean
  disabled?: boolean
}

export interface LogViewerProps {
  wsEndpoint: string
  bufferSize?: number
  autoReconnect?: boolean
  className?: string
}

export interface DownloadProps {
  fileId: string
  metadata: FileMetadata
  onDownload?: (fileId: string) => void
}

export interface UploadProgress {
  fileId: string
  progress: number
  status: FileMetadata['status']
  error?: string
}

export interface WebSocketMessage {
  type: 'log' | 'progress' | 'status'
  data: LogEntry | UploadProgress | any
}