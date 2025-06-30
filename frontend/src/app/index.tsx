import React, { useState, useCallback } from 'react'
import Head from 'next/head'
import { motion } from 'framer-motion'
import { FileText, Activity, Download, Settings } from 'lucide-react'
import FileUpload from '@/components/FileUpload'
import LogViewer from '@/components/LogViewer'
import DownloadManager from '@/components/DownloadManager'
import { Button } from '@/components/ui/button'
import { FileMetadata } from '@/types'

const ACCEPTED_TYPES = ['.pdf', '.doc', '.docx', '.txt']
const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10MB

export default function Home() {
  const [files, setFiles] = useState<FileMetadata[]>([])
  const [activeTab, setActiveTab] = useState<'upload' | 'logs' | 'downloads'>('upload')
  const [logKey, setLogKey] = useState<number>(Date.now())

  const handleFileUpload = useCallback(async (uploadedFiles: File[]) => {
    console.log('Uploading files:', uploadedFiles)
    
    // Simulate file processing
    const newFiles: FileMetadata[] = uploadedFiles.map(file => ({
      id: `${file.name}-${Date.now()}-${Math.random()}`,
      name: file.name,
      size: file.size,
      type: file.type,
      lastModified: file.lastModified,
      uploadedAt: new Date(),
      status: 'processing',
      progress: 0,
      downloadUrl: `#download-${file.name}`, // Mock URL
    }))

    setFiles(prev => [...prev, ...newFiles])

    // Simulate processing completion
    setTimeout(() => {
      setFiles(prev => prev.map(f => 
        newFiles.some(nf => nf.id === f.id)
          ? { ...f, status: 'completed', progress: 100 }
          : f
      ))
    }, 3000)

    // Trigger a fresh LogViewer instance for the upcoming processing run
    setLogKey(Date.now())
  }, [])

  const handleDownload = useCallback((fileId: string) => {
    console.log('Downloaded file:', fileId)
  }, [])

  const tabs = [
    { id: 'upload', label: 'Upload Files', icon: FileText },
    { id: 'logs', label: 'Activity Logs', icon: Activity },
    { id: 'downloads', label: 'Downloads', icon: Download },
  ] as const

  return (
    <>
      <Head>
        <title>File Management Interface</title>
        <meta name="description" content="Modern file management with real-time logging" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
      </Head>

      <div className="min-h-screen bg-background">
        {/* Header */}
        <header className="border-b bg-card/50 backdrop-blur-sm sticky top-0 z-50">
          <div className="container mx-auto px-4 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="h-8 w-8 bg-primary rounded-lg flex items-center justify-center">
                  <FileText className="h-5 w-5 text-primary-foreground" />
                </div>
                <div>
                  <h1 className="text-xl font-bold">File Manager</h1>
                  <p className="text-sm text-muted-foreground">
                    Upload, process, and download files with real-time monitoring
                  </p>
                </div>
              </div>
              
              <Button variant="ghost" size="icon" aria-label="Settings">
                <Settings className="h-5 w-5" />
              </Button>
            </div>
          </div>
        </header>

        {/* Main Content */}
        <main className="container mx-auto px-4 py-8 max-w-7xl">
          {/* Tab Navigation */}
          <div className="flex flex-wrap gap-2 mb-8 p-1 bg-muted rounded-lg">
            {tabs.map((tab) => {
              const Icon = tab.icon
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`
                    flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all
                    min-h-[44px] relative overflow-hidden
                    ${activeTab === tab.id 
                      ? 'bg-background text-foreground shadow-sm' 
                      : 'text-muted-foreground hover:text-foreground hover:bg-background/50'
                    }
                  `}
                  aria-label={tab.label}
                >
                  <Icon className="h-4 w-4" />
                  <span className="hidden sm:inline">{tab.label}</span>
                  {activeTab === tab.id && (
                    <motion.div
                      layoutId="activeTab"
                      className="absolute inset-0 bg-background rounded-md -z-10"
                      transition={{ type: "spring", bounce: 0.2, duration: 0.6 }}
                    />
                  )}
                </button>
              )
            })}
          </div>

          {/* Tab Content */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Main Content Area */}
            <div className="lg:col-span-2">
              <motion.div
                key={activeTab}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
              >
                {activeTab === 'upload' && (
                  <div className="space-y-6">
                    <div>
                      <h2 className="text-2xl font-bold mb-2">Upload Files</h2>
                      <p className="text-muted-foreground">
                        Drag and drop files or click to browse. Supported formats: {ACCEPTED_TYPES.join(', ')}
                      </p>
                    </div>
                    
                    <FileUpload
                      maxSize={MAX_FILE_SIZE}
                      acceptedTypes={ACCEPTED_TYPES}
                      onUpload={handleFileUpload}
                      multiple={true}
                    />
                  </div>
                )}

                {activeTab === 'logs' && (
                  <div className="space-y-6">
                    <div>
                      <h2 className="text-2xl font-bold mb-2">Activity Logs</h2>
                      <p className="text-muted-foreground">
                        Real-time monitoring of file processing activities
                      </p>
                    </div>
                    
                    <LogViewer
                      wsEndpoint="ws://localhost:8000/logs/"
                      bufferSize={500}
                      autoReconnect={true}
                      key={logKey}
                    />
                  </div>
                )}

                {activeTab === 'downloads' && (
                  <div className="space-y-6">
                    <div>
                      <h2 className="text-2xl font-bold mb-2">Downloads</h2>
                      <p className="text-muted-foreground">
                        Manage and download your processed files
                      </p>
                    </div>
                    
                    <div className="space-y-4">
                      {files.length === 0 ? (
                        <div className="text-center py-12 text-muted-foreground">
                          <Download className="h-12 w-12 mx-auto mb-4 opacity-50" />
                          <p>No files available for download yet.</p>
                          <p className="text-sm">Upload some files to get started!</p>
                        </div>
                      ) : (
                        files.map((file) => (
                          <DownloadManager
                            key={file.id}
                            fileId={file.id}
                            metadata={file}
                            onDownload={handleDownload}
                          />
                        ))
                      )}
                    </div>
                  </div>
                )}
              </motion.div>
            </div>

            {/* Sidebar */}
            <div className="space-y-6">
              {/* Quick Stats */}
              <div className="bg-card border rounded-lg p-6">
                <h3 className="font-semibold mb-4">Quick Stats</h3>
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Total Files</span>
                    <span className="font-medium">{files.length}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Completed</span>
                    <span className="font-medium text-green-500">
                      {files.filter(f => f.status === 'completed').length}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Processing</span>
                    <span className="font-medium text-yellow-500">
                      {files.filter(f => f.status === 'processing').length}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Errors</span>
                    <span className="font-medium text-red-500">
                      {files.filter(f => f.status === 'error').length}
                    </span>
                  </div>
                </div>
              </div>

              {/* System Status */}
              <div className="bg-card border rounded-lg p-6">
                <h3 className="font-semibold mb-4">System Status</h3>
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">API Server</span>
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                      <span className="text-sm text-green-500">Online</span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">WebSocket</span>
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 bg-yellow-500 rounded-full" />
                      <span className="text-sm text-yellow-500">Connecting</span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Storage</span>
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 bg-green-500 rounded-full" />
                      <span className="text-sm text-green-500">Available</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Recent Activity (Mini Log) */}
              {activeTab !== 'logs' && (
                <div className="bg-card border rounded-lg p-6">
                  <h3 className="font-semibold mb-4">Recent Activity</h3>
                  <div className="space-y-2 text-sm">
                    <div className="flex items-center gap-2 text-muted-foreground">
                      <div className="w-1 h-1 bg-current rounded-full" />
                      <span>System initialized</span>
                    </div>
                    <div className="flex items-center gap-2 text-muted-foreground">
                      <div className="w-1 h-1 bg-current rounded-full" />
                      <span>Ready for file uploads</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </main>

        {/* Footer */}
        <footer className="border-t bg-card/50 backdrop-blur-sm mt-16">
          <div className="container mx-auto px-4 py-6">
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
              <p className="text-sm text-muted-foreground">
                © 2024 File Management Interface. Built with Next.js & TypeScript.
              </p>
              <div className="flex items-center gap-4 text-sm text-muted-foreground">
                <span>v1.0.0</span>
                <span>•</span>
                <span>Status: Online</span>
              </div>
            </div>
          </div>
        </footer>
      </div>
    </>
  )
}