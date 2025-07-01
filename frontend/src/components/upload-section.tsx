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
  const [className, setClassName] = useState("7");
  const [subject, setSubject] = useState("Science");
  const [chapter, setChapter] = useState("Chapter 1");
  const [error, setError] = useState<string | null>(null);
  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState({ title: "", description: "" });

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
    setProcessingState("processing");

    const formData = new FormData();
    formData.append("file", file);
    formData.append("class_name", className);
    formData.append("subject", subject);
    formData.append("chapter", chapter);

    try {
      const response = await fetch("http://localhost:8000/upload-pdf/", {
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
    } catch (err: any) {
      setError(err.message);
      setProcessingState("error");
      setToastMessage({
        title: "Error",
        description: err.message
      });
      setShowToast(true);
    }
  };

  const isDisabled = processingState === "processing";

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
            <Label htmlFor="class-name">Class</Label>
            <Input 
              id="class-name" 
              type="text" 
              value={className} 
              onChange={(e) => setClassName(e.target.value)} 
              disabled={isDisabled}
              required
            />
          </div>
          <div className="grid w-full max-w-sm items-center gap-1.5">
            <Label htmlFor="subject">Subject</Label>
            <Input 
              id="subject" 
              type="text" 
              value={subject} 
              onChange={(e) => setSubject(e.target.value)} 
              disabled={isDisabled}
              required
            />
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
                  Processing...
                </>
              ) : (
                "Generate Questions"
              )}
            </span>
          </ShimmerButton>
        </form>
      </div>

      {showToast && (
        <Toast
          variant={error ? "destructive" : "default"}
          onOpenChange={(open) => !open && setShowToast(false)}
        >
          <ToastTitle>{toastMessage.title}</ToastTitle>
          <ToastDescription>{toastMessage.description}</ToastDescription>
        </Toast>
      )}
    </>
  );
};

export default UploadSection; 