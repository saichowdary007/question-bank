import React, { useCallback, useState, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Upload, File, X, CheckCircle, AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { cn, formatBytes } from '@/lib/utils'
import { FileUploadProps, FileMetadata } from '@/types'

const FileUpload: React.FC<FileUploadProps> = ({
  maxSize,
  acceptedTypes,
  onUpload,
  multiple = true,
  disabled = false,
}) => {
  const [isDragActive, setIsDragActive] = useState(false)
  const [files, setFiles] = useState<FileMetadata[]>([])
  const [isUploading, setIsUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const validateFile = useCallback((file: File): string | null => {
    if (file.size > maxSize) {
      return `File size exceeds ${formatBytes(maxSize)}`
    }
    
    const fileExtension = '.' + file.name.split('.').pop()?.toLowerCase()
    if (!acceptedTypes.includes(fileExtension) && !acceptedTypes.includes(file.type)) {
      return `File type not supported. Accepted types: ${acceptedTypes.join(', ')}`
    }
    
    return null
  }, [maxSize, acceptedTypes])

  const processFiles = useCallback((fileList: FileList) => {
    const newFiles: FileMetadata[] = []
    
    Array.from(fileList).forEach((file) => {
      const error = validateFile(file)
      const fileMetadata: FileMetadata = {
        id: `${file.name}-${Date.now()}-${Math.random()}`,
        name: file.name,
        size: file.size,
        type: file.type,
        lastModified: file.lastModified,
        uploadedAt: new Date(),
        status: error ? 'error' : 'pending',
        progress: 0,
        error: error || undefined,
      }
      newFiles.push(fileMetadata)
    })

    setFiles(prev => multiple ? [...prev, ...newFiles] : newFiles)
    
    // Start upload for valid files
    const validFiles = Array.from(fileList).filter((_, index) => !newFiles[index].error)
    if (validFiles.length > 0) {
      handleUpload(validFiles, newFiles.filter(f => !f.error))
    }
  }, [validateFile, multiple])

  const handleUpload = useCallback(async (filesToUpload: File[], fileMetadata: FileMetadata[]) => {
    setIsUploading(true)
    
    try {
      // Update status to uploading
      setFiles(prev => prev.map(f => 
        fileMetadata.some(fm => fm.id === f.id) 
          ? { ...f, status: 'uploading' as const, progress: 0 }
          : f
      ))

      // Simulate upload progress
      const progressInterval = setInterval(() => {
        setFiles(prev => prev.map(f => {
          if (fileMetadata.some(fm => fm.id === f.id) && f.status === 'uploading') {
            const newProgress = Math.min((f.progress || 0) + Math.random() * 20, 95)
            return { ...f, progress: newProgress }
          }
          return f
        }))
      }, 500)

      await onUpload(filesToUpload)
      
      clearInterval(progressInterval)
      
      // Mark as completed
      setFiles(prev => prev.map(f => 
        fileMetadata.some(fm => fm.id === f.id)
          ? { ...f, status: 'completed' as const, progress: 100 }
          : f
      ))
    } catch (error) {
      setFiles(prev => prev.map(f => 
        fileMetadata.some(fm => fm.id === f.id)
          ? { 
              ...f, 
              status: 'error' as const, 
              error: error instanceof Error ? error.message : 'Upload failed' 
            }
          : f
      ))
    } finally {
      setIsUploading(false)
    }
  }, [onUpload])

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (!disabled) {
      setIsDragActive(true)
    }
  }, [disabled])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragActive(false)
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragActive(false)
    
    if (disabled) return
    
    const { files: droppedFiles } = e.dataTransfer
    if (droppedFiles && droppedFiles.length > 0) {
      processFiles(droppedFiles)
    }
  }, [disabled, processFiles])

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const { files: selectedFiles } = e.target
    if (selectedFiles && selectedFiles.length > 0) {
      processFiles(selectedFiles)
    }
    // Reset input value to allow selecting the same file again
    e.target.value = ''
  }, [processFiles])

  const removeFile = useCallback((fileId: string) => {
    setFiles(prev => prev.filter(f => f.id !== fileId))
  }, [])

  const openFileDialog = useCallback(() => {
    if (!disabled) {
      fileInputRef.current?.click()
    }
  }, [disabled])

  const getStatusIcon = (status: FileMetadata['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case 'error':
        return <AlertCircle className="h-4 w-4 text-red-500" />
      case 'uploading':
      case 'processing':
        return <div className="h-4 w-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      default:
        return <File className="h-4 w-4 text-muted-foreground" />
    }
  }

  return (
    <div className="w-full space-y-4">
      {/* Upload Zone */}
      <motion.div
        className={cn(
          "relative border-2 border-dashed rounded-lg transition-all duration-300 cursor-pointer",
          "hover:border-primary/50 hover:bg-primary/5",
          isDragActive && "drag-active",
          disabled && "opacity-50 cursor-not-allowed",
          "h-[200px] w-full max-w-[300px] mx-auto"
        )}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onClick={openFileDialog}
        whileHover={!disabled ? { scale: 1.02 } : {}}
        whileTap={!disabled ? { scale: 0.98 } : {}}
      >
        <div className="absolute inset-0 flex flex-col items-center justify-center p-6 text-center">
          <motion.div
            animate={isDragActive ? { scale: 1.1 } : { scale: 1 }}
            transition={{ duration: 0.2 }}
          >
            <Upload className="h-12 w-12 text-muted-foreground mb-4" />
          </motion.div>
          
          <div className="space-y-2">
            <p className="text-sm font-medium">
              {isDragActive ? 'Drop files here' : 'Drag & drop files here'}
            </p>
            <p className="text-xs text-muted-foreground">
              or click to browse
            </p>
            <p className="text-xs text-muted-foreground">
              Max size: {formatBytes(maxSize)}
            </p>
            <p className="text-xs text-muted-foreground">
              Supported: {acceptedTypes.join(', ')}
            </p>
          </div>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          multiple={multiple}
          accept={acceptedTypes.join(',')}
          onChange={handleFileSelect}
          className="hidden"
          disabled={disabled}
          aria-label="File upload input"
        />
      </motion.div>

      {/* File List */}
      <AnimatePresence>
        {files.length > 0 && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="space-y-2"
          >
            <h3 className="text-sm font-medium">Files ({files.length})</h3>
            <div className="space-y-2 max-h-60 overflow-y-auto">
              {files.map((file) => (
                <motion.div
                  key={file.id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 20 }}
                  className="flex items-center gap-3 p-3 bg-card rounded-lg border"
                >
                  <div className="flex-shrink-0">
                    {getStatusIcon(file.status)}
                  </div>
                  
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{file.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {formatBytes(file.size)}
                    </p>
                    
                    {file.status === 'uploading' && (
                      <div className="mt-2">
                        <Progress value={file.progress || 0} className="h-1" />
                        <p className="text-xs text-muted-foreground mt-1">
                          {Math.round(file.progress || 0)}%
                        </p>
                      </div>
                    )}
                    
                    {file.error && (
                      <p className="text-xs text-red-500 mt-1">{file.error}</p>
                    )}
                  </div>
                  
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={(e) => {
                      e.stopPropagation()
                      removeFile(file.id)
                    }}
                    className="flex-shrink-0 h-8 w-8"
                    aria-label={`Remove ${file.name}`}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </motion.div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Upload Button */}
      {files.some(f => f.status === 'pending') && (
        <Button
          onClick={() => {
            const pendingFiles = files.filter(f => f.status === 'pending')
            // This would need to be implemented based on your file handling logic
          }}
          disabled={isUploading}
          className="w-full"
          variant="magic"
        >
          {isUploading ? 'Uploading...' : `Upload ${files.filter(f => f.status === 'pending').length} file(s)`}
        </Button>
      )}
    </div>
  )
}

export default FileUpload