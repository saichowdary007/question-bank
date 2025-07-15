"use client";

import { useState } from "react";
import { ShimmerButton } from "@/components/ui/shimmer-button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { Toast, ToastTitle, ToastDescription } from "@/components/ui/toast";

interface UploadSectionProps {
  setProcessingState: (state: "idle" | "processing" | "complete" | "error") => void;
  setLogs: (logs: any[]) => void;
  processingState: "idle" | "processing" | "complete" | "error";
  resetSession: () => void;
}

const UploadSection = ({ setProcessingState, setLogs, processingState, resetSession }: UploadSectionProps) => {
  const [file, setFile] = useState<File | null>(null);
  // Grade (1-10) and Subject dropdown defaults
  const [className, setClassName] = useState("Select Grade");
  const [subject, setSubject] = useState("Select Subject");
  const [chapter, setChapter] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState({ title: "", description: "" });

  // Track the upload-in-progress state separately from the long-running backend processing
  const [isUploading, setIsUploading] = useState(false);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      if (selectedFile.type !== "application/pdf") {
        setError("Please select a PDF file.");
        setFile(null);
        e.target.value = "";
        return;
      }
      
      // Reset session when new file is selected
      resetSession();
      
      setFile(selectedFile);
      setError(null);
    }
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!file) {
      setError("Please select a file to upload.");
      return;
    }
    setError(null);
    setLogs([]);
    // 1. Mark that backend will continue processing (used for log viewer)
    setProcessingState("processing");
    // 2. Disable the form only while the upload request is in flight
    setIsUploading(true);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("class_name", className);
    formData.append("subject", subject);
    formData.append("chapter", chapter);

    try {
      const backendBase = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
      const response = await fetch(`${backendBase}/upload-pdf/`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: "Upload failed" }));
        throw new Error(errorData.detail || "Upload failed");
      }
      
      setToastMessage({
        title: "Success",
        description: "File uploaded successfully. Processing started."
      });
      setShowToast(true);
      // The log stream will set the state to "complete"
      // Clear the local file so the same file can be selected again if desired
      setFile(null);
    } catch (err: any) {
      setError(err.message);
      setProcessingState("error");
      setToastMessage({
        title: "Error",
        description: err.message
      });
      setShowToast(true);
    }
    // Re-enable the form regardless of success or failure
    setIsUploading(false);
  };

  // Disable inputs only while the upload request is in progress
  const isDisabled = isUploading;

  return (
    <>
      <div className="p-4 border rounded-lg">
        <h2 className="text-xl font-bold mb-4 text-foreground">Upload Document</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid w-full max-w-sm items-center gap-1.5">
            <Label htmlFor="pdf-file">PDF File</Label>
            <Input 
              id="pdf-file" 
              type="file" 
              onChange={handleFileChange} 
              accept=".pdf" 
              disabled={isDisabled}
              aria-describedby={error ? "file-error" : undefined}
            />
            {error && (
              <p id="file-error" className="text-sm text-destructive mt-1">
                {error}
              </p>
            )}
          </div>
          <div className="grid w-full max-w-sm items-center gap-1.5">
            <Label htmlFor="class-name">Grade</Label>
            <select
              id="class-name"
              value={className}
              onChange={(e) => setClassName(e.target.value)}
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={isDisabled}
              required
            >
              <option value="1">1st Grade</option>
              <option value="2">2nd Grade</option>
              <option value="3">3rd Grade</option>
              <option value="4">4th Grade</option>
              <option value="5">5th Grade</option>
              <option value="6">6th Grade</option>
              <option value="7">7th Grade</option>
              <option value="8">8th Grade</option>
              <option value="9">9th Grade</option>
              <option value="10">10th Grade</option>
            </select>
          </div>
          <div className="grid w-full max-w-sm items-center gap-1.5">
            <Label htmlFor="subject">Subject</Label>
            <select
              id="subject"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={isDisabled}
              required
            >
              <option value="Math">Math</option>
              <option value="Science">Science</option>
              <option value="Social">Social</option>
            </select>
          </div>
          <div className="grid w-full max-w-sm items-center gap-1.5">
            <Label htmlFor="chapter">Chapter</Label>
            <Input 
              id="chapter" 
              type="text" 
              value={chapter} 
              onChange={(e) => setChapter(e.target.value)} 
              disabled={isDisabled}
              required
            />
          </div>
          
          <ShimmerButton 
            type="submit" 
            className="shadow-2xl w-full" 
            disabled={isDisabled}
          >
            <span className="whitespace-pre-wrap text-center text-sm font-medium leading-none tracking-tight text-white dark:from-white dark:to-slate-900/10 lg:text-lg flex items-center justify-center gap-2">
              {isDisabled ? (
                <>
                  <Spinner size="sm" />
                  Uploading...
                </>
              ) : (
                "Upload to S3 Bucket"
              )}
            </span>
          </ShimmerButton>
        </form>
      </div>

      {showToast && (
        <Toast
          variant={error ? "destructive" : "default"}
          onOpenChange={(open: boolean) => !open && setShowToast(false)}
        >
          <ToastTitle>{toastMessage.title}</ToastTitle>
          <ToastDescription>{toastMessage.description}</ToastDescription>
        </Toast>
      )}
    </>
  );
};

export default UploadSection; 