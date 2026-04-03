import React, { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, File, X, CheckCircle2, AlertCircle, Loader2, Lock, Globe } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { API_BASE_URL } from "@/lib/constants";
import { getAuthHeaders } from "@/lib/auth";

interface UploadPanelProps {
  onUploadSuccess?: (docId: string, chunks: number) => void;
  onTaskCreated?: (taskId: string) => void;
  showTitle?: boolean;
}

export function UploadPanel({ onUploadSuccess, onTaskCreated, showTitle = true }: UploadPanelProps) {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<"idle" | "uploading" | "success" | "error">("idle");
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState("");
  const [isPersonal, setIsPersonal] = useState(true);

  const onDrop = useCallback((acceptedFiles: File[], fileRejections: any[]) => {
    if (fileRejections.length > 0) {
      setStatus("error");
      const rejection = fileRejections[0];
      if (rejection.errors[0]?.code === "file-too-large") {
        setMessage("File too large. Max limit is 5MB for the Free Tier.");
      } else {
        setMessage(rejection.errors[0]?.message || "File rejected.");
      }
      return;
    }

    if (acceptedFiles.length > 0) {
      setFile(acceptedFiles[0]);
      setStatus("idle");
      setMessage("");
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
      "text/html": [".html"],
      "text/plain": [".txt"],
      "text/csv": [".csv"],
    },
    maxSize: 5 * 1024 * 1024, // 5MB
    multiple: false,
  });


  const handleUpload = async () => {
    if (!file) return;

    setStatus("uploading");
    setProgress(0);
    setMessage("Uploading file...");
    
    const formData = new FormData();
    formData.append("file", file);
    formData.append("is_personal", String(isPersonal));

    try {
      const response = await fetch(`${API_BASE_URL}/api/ingest/`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: formData,
      });

      if (!response.ok) {
        if (response.status === 413) {
           throw new Error("File too large for the current system limits (Max 5MB).");
        }
        
        try {
          const errorData = await response.json();
          throw new Error(errorData.detail || `Upload failed: ${response.statusText}`);
        } catch (e) {
          throw new Error(`Upload failed: ${response.statusText}`);
        }
      }

      const result = await response.json();
      
      // Notify parent immediately that the task has been created
      if (onTaskCreated) {
        onTaskCreated(result.task_id);
      }
      
      // We no longer poll here; the parent (KnowledgeHub) handles it
      setStatus("success");
      setMessage("Upload successful! Ingestion protocol initiated.");
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Ingestion failed");
    }
  };

  const reset = () => {
    setFile(null);
    setStatus("idle");
    setMessage("");
    setProgress(0);
  };

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-6 backdrop-blur-md shadow-xl overflow-hidden">
      {showTitle && (
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-200">Ingest Document</h3>
          {file && (
            <button onClick={reset} className="text-slate-500 hover:text-slate-300 transition-colors">
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      )}

      {!file ? (
        <div
          {...getRootProps()}
          className={cn(
            "group flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-800 py-10 transition-colors hover:border-blue-500/50 hover:bg-blue-500/5",
            isDragActive && "border-blue-500 bg-blue-500/10"
          )}
        >
          <input {...getInputProps()} />
          <Upload className={cn(
            "h-10 w-10 text-slate-600 transition-colors group-hover:text-blue-500",
            isDragActive && "text-blue-500"
          )} />
          <p className="mt-4 text-xs font-medium text-slate-400 group-hover:text-slate-300">
            {isDragActive ? "Drop the file here" : "Drag & drop PDF, DOCX, TXT, CSV, or HTML"}
          </p>
          <p className="mt-1 text-[10px] text-slate-600">Max size: 5MB (Free Tier Optimization)</p>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center gap-3 rounded-lg bg-slate-800/50 p-3">
            <div className="rounded bg-blue-500/10 p-2">
              <File className="h-5 w-5 text-blue-400" />
            </div>
            <div className="flex-1 overflow-hidden">
              <p className="text-xs font-medium text-slate-200 truncate">{file.name}</p>
              <p className="text-[10px] text-slate-500">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
            </div>
          </div>

          {status === "idle" && (
            <div className="flex items-center justify-between rounded-lg bg-slate-800/30 p-3 border border-slate-700/50">
              <div className="flex items-center gap-3">
                <div className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-full transition-colors",
                  isPersonal ? "bg-amber-500/10 text-amber-500" : "bg-emerald-500/10 text-emerald-500"
                )}>
                  {isPersonal ? <Lock className="h-4 w-4" /> : <Globe className="h-4 w-4" />}
                </div>
                <div>
                  <p className="text-[11px] font-bold text-slate-200">
                    {isPersonal ? "Personal Knowledge" : "Shared Library"}
                  </p>
                  <p className="text-[9px] text-slate-500 leading-tight">
                    {isPersonal ? "Only you can see this" : "Available to everybody"}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsPersonal(!isPersonal)}
                className={cn(
                  "relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none",
                  isPersonal ? "bg-slate-700" : "bg-emerald-600"
                )}
              >
                <span
                  className={cn(
                    "pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out",
                    isPersonal ? "translate-x-0" : "translate-x-4"
                  )}
                />
              </button>
            </div>
          )}

          {status === "uploading" && (
            <div className="space-y-2">
              <div className="flex justify-between text-[10px]">
                <span className="text-slate-400 italic">Extracting semantic chunks...</span>
                <span className="text-blue-400 font-bold">{progress}%</span>
              </div>
              <div className="h-1.5 w-full rounded-full bg-slate-800 overflow-hidden">
                <div 
                  className="h-full bg-blue-500 transition-all duration-300" 
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
          )}

          {status === "success" && (
            <div className="flex items-center gap-2 text-xs font-medium text-emerald-400 animate-in fade-in zoom-in duration-300">
              <CheckCircle2 className="h-4 w-4" />
              <span>{message}</span>
            </div>
          )}

          {status === "error" && (
            <div className="flex items-center gap-2 text-xs font-medium text-rose-400 animate-in fade-in zoom-in duration-300">
              <AlertCircle className="h-4 w-4" />
              <span>{message}</span>
            </div>
          )}

          <div className="flex gap-2 pt-2">
            {status === "idle" && (
              <Button 
                onClick={handleUpload} 
                className="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold"
              >
                Start Ingestion
              </Button>
            )}
            
            {status === "success" && (
              <Button 
                onClick={reset} 
                variant="outline"
                className="w-full border-slate-700 text-slate-300 hover:bg-slate-800"
              >
                Upload Another
              </Button>
            )}

            {status === "error" && (
              <Button 
                onClick={handleUpload} 
                className="w-full bg-rose-600 hover:bg-rose-500 text-white"
              >
                Retry
              </Button>
            )}

            {status === "uploading" && (
               <Button disabled className="w-full bg-slate-800 text-slate-500">
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Processing...
               </Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
