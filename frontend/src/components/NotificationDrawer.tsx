"use client";

import React, { useEffect, useState, useRef } from "react";
import { 
  Bell, 
  CheckCircle2, 
  Clock, 
  AlertCircle, 
  ChevronRight,
  Loader2,
  FileText,
  X
} from "lucide-react";
import { 
  Drawer, 
  DrawerContent, 
  DrawerHeader, 
  DrawerTitle, 
  DrawerTrigger,
  DrawerClose
} from "@/components/ui/drawer";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { supabase } from "@/lib/supabaseClient";
import { cn } from "@/lib/utils";

export interface IngestionTask {
  id: string;
  status: "pending" | "processing" | "completed" | "error";
  progress: number;
  message: string;
  created_at: string;
  document_id?: string;
  metadata?: any;
}

export function NotificationDrawer() {
  const [tasks, setTasks] = useState<IngestionTask[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const prevTasksCount = useRef(0);

  useEffect(() => {
    // 1. Initial Fetch
    const fetchTasks = async () => {
      const { data, error } = await supabase
        .from("ingestion_tasks")
        .select("*")
        .order("created_at", { ascending: false })
        .limit(10);
      
      if (data) {
        setTasks(data);
        prevTasksCount.current = data.length;
      }
    };

    fetchTasks();

    // 2. Realtime Subscription
    const channel = supabase
      .channel("ingestion_tasks_realtime")
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "ingestion_tasks" },
        (payload) => {
          if (payload.eventType === "INSERT") {
            const newTask = payload.new as IngestionTask;
            setTasks((prev) => [newTask, ...prev].slice(0, 10));
            if (!isOpen) setUnreadCount((c) => c + 1);
          } else if (payload.eventType === "UPDATE") {
            const updatedTask = payload.new as IngestionTask;
            setTasks((prev) => 
              prev.map((t) => (t.id === updatedTask.id ? updatedTask : t))
            );
            // If it just completed, trigger a small notification hint if drawer is closed
            if (updatedTask.status === "completed" && !isOpen) {
               setUnreadCount((c) => c + 1);
            }
          }
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [isOpen]);

  const handleOpenChange = (open: boolean) => {
    setIsOpen(open);
    if (open) setUnreadCount(0);
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "completed": return <CheckCircle2 className="h-4 w-4 text-emerald-500" />;
      case "error": return <AlertCircle className="h-4 w-4 text-rose-500" />;
      case "processing": return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />;
      default: return <Clock className="h-4 w-4 text-slate-500" />;
    }
  };

  return (
    <Drawer open={isOpen} onOpenChange={handleOpenChange}>
      <DrawerTrigger asChild>
        <Button variant="ghost" size="icon" className="relative text-slate-400 hover:text-white hover:bg-slate-800/50">
          <Bell className="h-5 w-5" />
          {unreadCount > 0 && (
            <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-blue-600 text-[10px] font-bold text-white ring-2 ring-slate-950 animate-bounce">
              {unreadCount}
            </span>
          )}
        </Button>
      </DrawerTrigger>
      <DrawerContent className="bg-slate-900/95 border-slate-800 text-slate-200 backdrop-blur-xl">
        <div className="mx-auto w-full max-w-lg">
          <DrawerHeader className="flex flex-row items-center justify-between border-b border-slate-800/50 pb-4">
            <div>
              <DrawerTitle className="text-xl font-bold tracking-tight text-white flex items-center gap-2 italic uppercase">
                <Zap className="h-5 w-5 text-blue-500 fill-blue-500" />
                Ingestion Pipeline
              </DrawerTitle>
              <p className="text-xs text-slate-500 font-medium">Real-time background processing status</p>
            </div>
            <DrawerClose asChild>
                <Button variant="ghost" size="icon" className="text-slate-500 hover:text-white">
                    <X className="h-4 w-4" />
                </Button>
            </DrawerClose>
          </DrawerHeader>

          <div className="p-4 space-y-4 h-[60vh] overflow-y-auto no-scrollbar">
            {tasks.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center space-y-4">
                <div className="h-12 w-12 rounded-full bg-slate-800/50 flex items-center justify-center">
                  <FileText className="h-6 w-6 text-slate-600" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-400">No active tasks</p>
                  <p className="text-[10px] text-slate-500 italic max-w-[200px]">Upload a document to see the automated enrichment pipeline in action.</p>
                </div>
              </div>
            ) : (
              tasks.map((task) => (
                <div 
                  key={task.id} 
                  className={cn(
                    "group relative overflow-hidden rounded-xl border p-4 transition-all duration-300",
                    task.status === "completed" 
                      ? "bg-emerald-500/5 border-emerald-500/10 hover:bg-emerald-500/10" 
                      : task.status === "error"
                      ? "bg-rose-500/5 border-rose-500/10 hover:bg-rose-500/10"
                      : "bg-blue-500/5 border-blue-500/10 hover:bg-blue-500/10"
                  )}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-start gap-3">
                      <div className={cn(
                        "mt-0.5 rounded-lg p-2 flex items-center justify-center",
                        task.status === "completed" ? "bg-emerald-500/10" : "bg-blue-500/10"
                      )}>
                         <FileText className={cn(
                           "h-4 w-4",
                           task.status === "completed" ? "text-emerald-400" : "text-blue-400"
                         )} />
                      </div>
                      <div>
                        <h4 className="text-sm font-bold text-slate-100 truncate max-w-[240px]">
                          {task.metadata?.title || "Active Ingestion"}
                        </h4>
                        <div className="flex items-center gap-2 mt-1">
                          {getStatusIcon(task.status)}
                          <span className={cn(
                            "text-[10px] font-bold uppercase tracking-wider",
                            task.status === "completed" ? "text-emerald-500" : "text-blue-400"
                          )}>
                            {task.status}
                          </span>
                        </div>
                      </div>
                    </div>
                    <Badge variant="outline" className="bg-slate-950/50 border-slate-800 text-[9px] font-mono text-slate-500">
                       {new Date(task.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </Badge>
                  </div>

                  <p className="text-[11px] text-slate-400 mb-3 leading-relaxed">
                    {task.message || "Initializing background processor..."}
                  </p>

                  {task.status === "processing" && (
                    <div className="space-y-1.5">
                       <div className="flex justify-between text-[9px] font-bold">
                          <span className="text-blue-400 uppercase tracking-tighter">Hyper-segmentation in progress</span>
                          <span className="text-blue-500">{Math.round(task.progress)}%</span>
                       </div>
                       <Progress value={task.progress} className="h-1 bg-slate-800 overflow-hidden">
                          <div className="h-full bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.5)]" />
                       </Progress>
                    </div>
                  )}

                  {task.status === "completed" && (
                    <div className="flex items-center justify-between pt-2 mt-2 border-t border-emerald-500/5">
                       <span className="text-[9px] text-emerald-500/60 font-medium italic">Entities & Semantic nodes indexed</span>
                       <Button variant="ghost" size="sm" className="h-6 text-[10px] text-emerald-400 hover:text-emerald-300 hover:bg-emerald-500/10 px-2 rounded-md">
                          View Details <ChevronRight className="h-3 w-3 ml-1" />
                       </Button>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </DrawerContent>
    </Drawer>
  );
}

// Support components (Zap)
function Zap({ className }: { className?: string }) {
  return (
    <svg 
      xmlns="http://www.w3.org/2000/svg" 
      viewBox="0 0 24 24" 
      fill="none" 
      stroke="currentColor" 
      strokeWidth="2" 
      strokeLinecap="round" 
      strokeLinejoin="round" 
      className={className}
    >
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  );
}
