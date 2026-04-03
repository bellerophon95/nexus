"use client";

import React, { useEffect, useState } from "react";
import { 
  FileText, 
  Trash2, 
  RefreshCw, 
  Calendar, 
  Layers, 
  FileCode, 
  FilePieChart,
  Search,
  ExternalLink,
  Globe,
  Lock,
  MessageSquareText,
  ShieldCheck,
  AlertTriangle,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Clock
} from "lucide-react";
import { IngestionTask } from "@/lib/types";
import { Progress } from "@/components/ui/progress";
import { format } from "date-fns";
import { 
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { API_BASE_URL } from "@/lib/constants";

interface Document {
  id: string;
  title: string;
  doc_type: string;
  chunk_count: number;
  created_at: string;
  is_personal: boolean;
  description: string | null;
}

interface DocumentLibraryProps {
  refreshTrigger?: number;
  searchQuery?: string;
  showTitle?: boolean;
  activeTasks?: IngestionTask[];
  onDismissTask?: (taskId: string) => void;
}

export function DocumentLibrary({ refreshTrigger, searchQuery = "", showTitle = true, activeTasks = [], onDismissTask }: DocumentLibraryProps) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [sharingId, setSharingId] = useState<string | null>(null);
  const [isSharing, setIsSharing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchDocuments = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/documents/`);
      if (!response.ok) throw new Error("Failed to fetch documents");
      const data = await response.json();
      setDocuments(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const deleteDocument = async (id: string) => {
    setDeletingId(id);
    try {
      const response = await fetch(`${API_BASE_URL}/api/documents/${id}`, {
        method: "DELETE",
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to delete document");
      }
      
      setDocuments(prev => prev.filter(doc => doc.id !== id));
    } catch (err: any) {
      console.error("Delete error:", err);
      alert(`Error deleting document: ${err.message}`);
    } finally {
      setDeletingId(null);
    }
  };

  const shareDocument = async (id: string) => {
    setIsSharing(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/documents/${id}/share`, {
        method: "POST",
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to share document");
      }
      
      setDocuments(prev => prev.map(doc => 
        doc.id === id ? { ...doc, is_personal: false } : doc
      ));
      setSharingId(null);
    } catch (err: any) {
      console.error("Share error:", err);
      alert(`Error sharing document: ${err.message}`);
    } finally {
      setIsSharing(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, [refreshTrigger]);

  const getDocIcon = (type: string) => {
    const t = type.toLowerCase();
    if (t.includes("pdf")) return <FilePieChart className="h-5 w-5 text-rose-400" />;
    if (t.includes("csv") || t.includes("excel")) return <FileCode className="h-5 w-5 text-emerald-400" />;
    if (t.includes("txt") || t.includes("md")) return <FileText className="h-5 w-5 text-blue-400" />;
    return <FileText className="h-5 w-5 text-slate-400" />;
  };

  if (isLoading && documents.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center space-y-4">
        <RefreshCw className="h-8 w-8 animate-spin text-blue-500 opacity-50" />
        <p className="text-sm text-slate-500 font-medium tracking-wide uppercase">Syncing Library...</p>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col p-8 max-w-6xl mx-auto w-full">
      {showTitle && (
        <div className="flex items-center justify-between mb-8">
          <div>
            <h2 className="text-3xl font-extrabold text-slate-100 tracking-tight flex items-center gap-3">
              <Layers className="h-8 w-8 text-blue-500" />
              Document Library
            </h2>
            <p className="text-slate-500 mt-1 text-sm font-medium">Manage your knowledge base and vector embeddings.</p>
          </div>
          <Button 
            variant="outline" 
            onClick={fetchDocuments}
            className="border-slate-800 bg-slate-900/50 hover:bg-slate-800 text-slate-300 gap-2 border shadow-xl backdrop-blur-md"
          >
            <RefreshCw className={cn("h-4 w-4", isLoading && "animate-spin")} />
            Refresh
          </Button>
        </div>
      )}

      {/* Filtered Documents + Active Tasks Combined */}
      {(() => {
        const filteredDocs = documents.filter(doc => 
          doc.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
          doc.doc_type.toLowerCase().includes(searchQuery.toLowerCase()) ||
          (doc.description || "").toLowerCase().includes(searchQuery.toLowerCase())
        );

        const totalItems = activeTasks.length + filteredDocs.length;

        if (totalItems === 0) {
          return (
            <div className="flex flex-1 flex-col items-center justify-center rounded-3xl border border-dashed border-slate-800 bg-slate-900/40 p-12 text-center shadow-inner">
              <div className="bg-slate-800/50 p-4 rounded-full mb-4">
                <Search className="h-10 w-10 text-slate-700" />
              </div>
              <h3 className="text-lg font-bold text-slate-300">
                {searchQuery ? "No matching knowledge" : "No documents found"}
              </h3>
              <p className="text-slate-500 max-w-xs mx-auto mt-2 text-sm italic">
                {searchQuery 
                  ? `We couldn't find anything matching "${searchQuery}" in your grounding layer.` 
                  : "Your library is empty. Upload your first PDF or text file to start building your AI knowledge base."}
              </p>
            </div>
          );
        }

        return (
          <div className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/30 backdrop-blur-xl shadow-2xl">
            <table className="w-full text-left border-collapse">
              <thead className="bg-slate-800/50 text-[10px] font-bold uppercase tracking-widest text-slate-400">
                <tr>
                  <th className="px-6 py-4">Document</th>
                  <th className="px-6 py-4">Status / Summary</th>
                  <th className="px-6 py-4">Chunks</th>
                  <th className="px-6 py-4">Timestamp</th>
                  <th className="px-6 py-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50">
                {/* Render Active Tasks First */}
                {activeTasks.map((task) => (
                  <tr key={task.id} className="bg-blue-500/5 border-l-2 border-l-blue-500/50 animate-pulse-subtle">
                    <td className="px-6 py-5">
                      <div className="flex items-center gap-4">
                        <div className="bg-blue-500/20 p-2.5 rounded-lg border border-blue-500/30 shadow-[0_0_15px_rgba(59,130,246,0.1)]">
                          <Loader2 className="h-5 w-5 text-blue-400 animate-spin" />
                        </div>
                        <div>
                          <p className="font-bold text-blue-400 text-sm truncate max-w-[200px]">
                            {task.filename || "Ingesting Source..."}
                          </p>
                          <span className="inline-flex items-center gap-1 mt-1 rounded bg-blue-500/10 px-1.5 py-0.5 text-[8px] font-black text-blue-500 border border-blue-500/20 uppercase tracking-tighter">
                            Active Sync
                          </span>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-5 min-w-[300px]">
                      <div className="space-y-2">
                        <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-widest">
                          <span className={cn(
                            "truncate max-w-[240px]",
                            task.status === "error" ? "text-rose-400 font-bold" : "text-blue-400/80"
                          )}>
                            {task.status === "error" 
                              ? `Sync Error: ${task.message || "Extraction failed"}` 
                              : task.message || "Processing..."}
                          </span>
                          <span className="text-blue-400 ml-2">{Math.round(task.progress)}%</span>
                        </div>
                        <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-slate-800/50 border border-slate-700/30">
                          <div 
                            className={cn(
                              "h-full transition-all duration-500 ease-out shadow-[0_0_10px_rgba(59,130,246,0.5)]",
                              task.status === "error" ? "bg-rose-500 shadow-rose-500/50" : "bg-blue-500"
                            )}
                            style={{ width: `${task.progress}%` }}
                          />
                          <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent animate-shimmer" />
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-5">
                      <span className="text-[10px] text-slate-600 font-bold tracking-widest italic uppercase">
                        {task.status === "error" ? "Stalled" : "Calculating..."}
                      </span>
                    </td>
                    <td className="px-6 py-5">
                      <div className="flex items-center gap-2 text-xs text-blue-400 font-bold tracking-tighter animate-pulse">
                         <Clock className="h-3 w-3" />
                         LIVE
                      </div>
                    </td>
                    <td className="px-6 py-5 text-right">
                      {onDismissTask && (
                        <div className="flex justify-end items-center gap-2">
                           {task.status === "error" && (
                             <span className="text-[10px] text-rose-500 font-black uppercase tracking-tighter mr-2">
                               FAILED
                             </span>
                           )}
                          <Button 
                            variant="ghost" 
                            size="sm" 
                            onClick={() => onDismissTask(task.id)}
                            className={cn(
                              "h-8 px-3 rounded-lg flex items-center gap-2 transition-all",
                              task.status === "error" 
                                ? "bg-rose-500/10 text-rose-500 hover:bg-rose-500 hover:text-white border border-rose-500/20" 
                                : "text-slate-500 hover:text-slate-300 hover:bg-slate-800"
                            )}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                            <span className="text-[10px] font-bold uppercase tracking-widest">
                              {task.status === "error" ? "Dismiss" : "Cancel"}
                            </span>
                          </Button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}

                {/* Render Existing Documents */}
                {filteredDocs.map((doc) => (
                  <tr key={doc.id} className="group hover:bg-blue-500/5 transition-colors">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-4">
                        <div className="bg-slate-800/50 p-2.5 rounded-lg border border-slate-700/50 shadow-sm group-hover:border-blue-500/30 transition-all">
                          {getDocIcon(doc.doc_type)}
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <p className="font-semibold text-slate-200 text-sm group-hover:text-blue-400 transition-colors truncate max-w-[200px]">
                              {doc.title}
                            </p>
                            {doc.is_personal ? (
                              <span className="flex items-center gap-1 rounded bg-amber-500/10 px-1.5 py-0.5 text-[9px] font-bold text-amber-500 border border-amber-500/20">
                                <Lock className="h-2.5 w-2.5" />
                                PERSONAL
                              </span>
                            ) : (
                              <span className="flex items-center gap-1 rounded bg-emerald-500/10 px-1.5 py-0.5 text-[9px] font-bold text-emerald-500 border border-emerald-500/20">
                                <ShieldCheck className="h-2.5 w-2.5" />
                                SHARED
                              </span>
                            )}
                          </div>
                          <p className="text-[10px] text-slate-500 uppercase tracking-tight font-bold opacity-60">
                            {doc.doc_type}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 max-w-[300px]">
                      <div className="flex items-start gap-2">
                        <MessageSquareText className="h-3 w-3 text-slate-600 mt-0.5 shrink-0" />
                        <p className="text-[11px] text-slate-400 leading-normal line-clamp-2 italic">
                          {doc.description || "Synthesizing description..."}
                        </p>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <span className="rounded-full bg-blue-500/10 px-2.5 py-0.5 text-[10px] font-bold text-blue-400 border border-blue-500/20">
                          {doc.chunk_count}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-xs text-slate-400">
                      <div className="flex items-center gap-2 font-medium opacity-80">
                        <Calendar className="h-3 w-3" />
                        {format(new Date(doc.created_at), "MMM d, HH:mm")}
                      </div>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        {doc.is_personal && (
                          <AlertDialog open={sharingId === doc.id} onOpenChange={(open: boolean) => !open && setSharingId(null)}>
                            <AlertDialogTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => setSharingId(doc.id)}
                                className="h-8 w-8 rounded-full text-slate-500 hover:text-emerald-400 hover:bg-emerald-400/10"
                                title="Share to Library"
                              >
                                <Globe className="h-4 w-4" />
                              </Button>
                            </AlertDialogTrigger>
                            <AlertDialogContent className="bg-slate-900 border-slate-800">
                              <AlertDialogHeader>
                                <AlertDialogTitle className="text-slate-100 flex items-center gap-2">
                                  <AlertTriangle className="h-5 w-5 text-amber-500" />
                                  Share Document?
                                </AlertDialogTitle>
                                <AlertDialogDescription className="text-slate-400">
                                  This will make <span className="font-bold text-slate-200">"{doc.title}"</span> available to everybody in the Shared Library. 
                                  <br /><br />
                                  <span className="text-amber-500/80 text-xs font-medium">
                                    This action is irreversible and will allow others to query this data.
                                  </span>
                                </AlertDialogDescription>
                              </AlertDialogHeader>
                              <AlertDialogFooter>
                                <AlertDialogCancel className="bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700">Cancel</AlertDialogCancel>
                                <AlertDialogAction 
                                  onClick={() => shareDocument(doc.id)}
                                  className="bg-emerald-600 hover:bg-emerald-500 text-white"
                                  disabled={isSharing}
                                >
                                  {isSharing ? <RefreshCw className="h-4 w-4 animate-spin mr-2" /> : null}
                                  Share Irreversibly
                                </AlertDialogAction>
                              </AlertDialogFooter>
                            </AlertDialogContent>
                          </AlertDialog>
                        )}
                        
                        <Button
                          variant="ghost"
                          size="icon"
                          disabled={deletingId === doc.id}
                          onClick={() => deleteDocument(doc.id)}
                          className={cn(
                            "h-8 w-8 rounded-full transition-all duration-300",
                            deletingId === doc.id 
                              ? "bg-rose-500/20 text-rose-500" 
                              : "text-slate-500 hover:text-rose-400 hover:bg-rose-400/10"
                          )}
                          title="Delete Document"
                        >
                          {deletingId === doc.id ? (
                            <RefreshCw className="h-4 w-4 animate-spin" />
                          ) : (
                            <Trash2 className="h-4 w-4" />
                          )}
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })()}
    </div>
  );
}
