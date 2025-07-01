"use client";

import { useState, useEffect } from "react";
import { ShimmerButton } from "@/components/ui/shimmer-button";
import { Toast, ToastTitle, ToastDescription } from "@/components/ui/toast";
import { Spinner } from "@/components/ui/spinner";

interface DownloadSectionProps {
  processingState: "idle" | "processing" | "complete" | "error";
  resetSession: () => void;
}

const DownloadSection = ({ processingState, resetSession }: DownloadSectionProps) => {
  const [isReady, setIsReady] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState({ title: "", description: "" });
  const [serverShutdown, setServerShutdown] = useState(false);

  useEffect(() => {
    if (processingState === "processing" || processingState === "idle") {
      const interval = setInterval(async () => {
        try {
          const response = await fetch("http://localhost:8000/processing-status");
          if (!response.ok) {
            // Server is likely down
            setServerShutdown(true);
            clearInterval(interval);
            return;
          }

          const data = await response.json();
          setServerShutdown(false); // Server is up

          if (data.status === "complete") {
            setIsReady(true);
            clearInterval(interval);
          } else if (data.status === "idle") {
            // If server is idle, it might have been restarted. Stop polling.
             if(processingState === "processing") { // Only show shutdown if we were actively processing
                setServerShutdown(true);
             }
             clearInterval(interval);
          }
        } catch (error) {
          setServerShutdown(true);
          clearInterval(interval);
        }
      }, 3000); // Poll every 3 seconds

      return () => clearInterval(interval);
    }
  }, [processingState]);

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const response = await fetch("http://localhost:8000/questions");
      if (!response.ok) {
        setToastMessage({
          title: "Server Down",
          description: "The server has shut down. Please restart it to begin a new session.",
        });
        setShowToast(true);
        setServerShutdown(true);
        throw new Error("Server has shut down");
      }
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "questions.json";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      setToastMessage({
        title: "Success",
        description: "Questions downloaded successfully."
      });
      setShowToast(true);
      
      // Reload the page to reset the state for the next session.
      setTimeout(() => {
        window.location.reload();
      }, 2000); // 2 second delay for user to see the success toast.
      
    } catch (error: any) {
      if (!serverShutdown) {
        setToastMessage({
          title: "Error",
          description: error.message || "Failed to download questions. The server may be offline."
        });
        setShowToast(true);
      }
    } finally {
      setDownloading(false);
    }
  };

  const isDisabled = !isReady || downloading;

  return (
    <>
      <div className="p-4 border rounded-lg">
        <h2 className="text-xl font-bold mb-4 text-foreground">Download Questions</h2>
        <div className="h-20 flex items-center">
          <ShimmerButton
            className="shadow-2xl"
            onClick={handleDownload}
            disabled={isDisabled}
          >
            <span className="whitespace-pre-wrap text-center text-sm font-medium leading-none tracking-tight text-white dark:from-white dark:to-slate-900/10 lg:text-lg flex items-center justify-center gap-2">
              {downloading ? (
                <>
                  <Spinner size="sm" />
                  Downloading...
                </>
              ) : (
                "Download Questions"
              )}
            </span>
          </ShimmerButton>
        </div>
        {!isReady && processingState === "processing" && (
          <p className="text-sm text-muted-foreground mt-2">
            * Processing PDF... Download will be available shortly.
          </p>
        )}
        {isReady && !serverShutdown && (
           <p className="text-sm text-green-500 mt-2">
             ✅ Processing complete! Ready to download.
           </p>
        )}
        {serverShutdown && (
            <p className="text-sm text-red-500 mt-2">
                ⚠️ The server is offline or has finished its task. Please start the server to begin.
            </p>
        )}
      </div>

      {showToast && (
        <Toast
          variant={toastMessage.title.includes("Error") || toastMessage.title.includes("Down") ? "destructive" : "default"}
          onOpenChange={(open) => !open && setShowToast(false)}
        >
          <ToastTitle>{toastMessage.title}</ToastTitle>
          <ToastDescription>{toastMessage.description}</ToastDescription>
        </Toast>
      )}
    </>
  );
};

export default DownloadSection; 