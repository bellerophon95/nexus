"use client";

import React, { useState } from "react";
import { 
  Plus, 
  Library,
  Layers,
  Search,
  Upload,
  Zap,
  Clock,
  CheckCircle2,
  AlertCircle
} from "lucide-react";
import { IngestionTask } from "@/lib/types";
import { API_BASE_URL } from "@/lib/constants";
import { getAuthHeaders } from "@/lib/auth";
import { DocumentLibrary } from "@/components/DocumentLibrary";
import { UploadPanel } from "@/components/UploadPanel";
import { SkillHub } from "@/components/SkillHub";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogDescription,
} from "@/components/ui/dialog";

interface KnowledgeHubProps {
  selectedSkills: string[];
  onToggleSkill: (skillId: string) => void;
}

export function KnowledgeHub({ selectedSkills, onToggleSkill }: KnowledgeHubProps) {
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState<"documents" | "skills">("documents");
  const [activeTasks, setActiveTasks] = useState<IngestionTask[]>([]);

  // Fetch initial active tasks on mount
  React.useEffect(() => {
    const fetchActiveTasks = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/ingest/active`, {
          headers: getAuthHeaders(),
        });
        if (response.ok) {
          const tasks = await response.json();
          if (tasks.length > 0) {
            setActiveTasks(tasks);
          }
        }
      } catch (err) {
        console.error("Failed to fetch initial active tasks:", err);
      }
    };
    fetchActiveTasks();
  }, []);

  // Polling for active tasks
  React.useEffect(() => {
    // If no tasks, do nothing
    if (activeTasks.length === 0) return;

    // Check if any tasks actually need polling
    const stillActive = activeTasks.filter(t => t.status === "pending" || t.status === "processing");
    if (stillActive.length === 0) return;

    const pollInterval = setInterval(async () => {
      const updatedTasks = [...activeTasks];
      let hasChanges = false;
      let needsRefresh = false;

      await Promise.all(stillActive.map(async (task) => {
        try {
          const response = await fetch(`${API_BASE_URL}/api/ingest/status/${task.id}`, {
            headers: getAuthHeaders(),
          });
          
          if (response.ok) {
            const data: IngestionTask = await response.json();
            const idx = updatedTasks.findIndex(t => t.id === task.id);
            if (idx !== -1) {
              // Only update if something changed
              if (updatedTasks[idx].status !== data.status || updatedTasks[idx].progress !== data.progress) {
                updatedTasks[idx] = { ...updatedTasks[idx], ...data };
                hasChanges = true;
              }
              
              if (data.status === "completed" || data.status === "skipped") {
                needsRefresh = true;
                // Linger for 3 seconds before removing
                setTimeout(() => {
                  setActiveTasks(prev => prev.filter(t => t.id !== task.id));
                }, 3000);
              }
            }
          }
        } catch (err) {
          console.error(`Failed to poll task ${task.id}:`, err);
        }
      }));

      if (hasChanges) {
        setActiveTasks(updatedTasks);
      }
      if (needsRefresh) {
        setRefreshTrigger(prev => prev + 1);
      }
    }, 2000);

    return () => clearInterval(pollInterval);
  }, [activeTasks]);

  const handleUploadSuccess = () => {
    // Increment trigger to refresh DocumentLibrary when a task actually completes
    setRefreshTrigger(prev => prev + 1);
  };

  const handleTaskCreated = (taskId: string) => {
    // Add to active tasks with initial state
    const newTask: IngestionTask = {
      id: taskId,
      status: "pending",
      progress: 0,
      message: "Syncing with ingestion worker...",
      created_at: new Date().toISOString(),
    };
    setActiveTasks(prev => [newTask, ...prev]);
    
    // Close the modal immediately
    setIsUploadModalOpen(false);
    console.log(`Ingestion task created: ${taskId}`);
  };

  const handleDismissTask = (taskId: string) => {
    setActiveTasks(prev => prev.filter(t => t.id !== taskId));
  };

  return (
    <div className="flex flex-1 flex-col overflow-hidden bg-slate-950">
      {/* Knowledge Hub Header */}
      <header className="flex h-20 items-center justify-between border-b border-slate-800/60 bg-slate-900/10 px-8 backdrop-blur-md">
        <div className="flex items-center gap-4">
          <div className="h-10 w-10 rounded-xl bg-blue-600/20 flex items-center justify-center border border-blue-500/30 shadow-lg shadow-blue-500/10">
            <Library className="h-6 w-6 text-blue-400" />
          </div>
          <div>
            <h1 className="text-xl font-black text-white italic tracking-tight uppercase">Intelligence Hub</h1>
            <p className="text-[10px] text-slate-500 font-bold uppercase tracking-widest leading-none">Capability & Grounding Layer</p>
          </div>
        </div>

        <div className="flex items-center gap-6">
          {/* Tab Selector */}
          <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as any)} className="w-[300px]">
             <TabsList className="grid w-full grid-cols-2 bg-slate-800/40 border border-slate-700/50 p-1 h-10 rounded-xl">
               <TabsTrigger value="documents" className="rounded-lg text-[10px] uppercase font-bold tracking-widest data-[state=active]:bg-blue-600 data-[state=active]:text-white transition-all">
                 <Library className="h-3 w-3 mr-2" />
                 Documents
               </TabsTrigger>
               <TabsTrigger value="skills" className="rounded-lg text-[10px] uppercase font-bold tracking-widest data-[state=active]:bg-amber-600 data-[state=active]:text-white transition-all">
                 <Zap className="h-3 w-3 mr-2" />
                 Skills
               </TabsTrigger>
             </TabsList>
          </Tabs>
          {/* Search Bar */}
          <div className="relative hidden md:block">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
            <input 
              type="text" 
              placeholder="Filter knowledge..." 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-10 w-64 rounded-xl border border-slate-800 bg-slate-900/50 pl-10 pr-4 text-xs text-slate-200 placeholder-slate-600 outline-none ring-blue-500/20 focus:ring-2 transition-all shadow-inner"
            />
          </div>

          <Separator orientation="vertical" className="h-8 bg-slate-800/60 hidden md:block" />

          <Dialog open={isUploadModalOpen} onOpenChange={setIsUploadModalOpen}>
            <DialogTrigger
              render={
                <Button className="bg-blue-600 hover:bg-blue-500 text-white font-bold gap-2 shadow-lg shadow-blue-500/20 px-6 h-10">
                  <Plus className="h-4 w-4" />
                  Add Document
                </Button>
              }
            />
            <DialogContent className="sm:max-w-xl bg-slate-950 border-slate-800 text-slate-200">
            <DialogHeader>
              <DialogTitle className="text-xl font-bold text-white italic">Ingest Intelligence</DialogTitle>
              <DialogDescription className="text-slate-500">
                Upload research papers or documentation to ground your agents with verified facts.
              </DialogDescription>
            </DialogHeader>
            <div className="py-4">
              <UploadPanel 
                onUploadSuccess={handleUploadSuccess} 
                onTaskCreated={handleTaskCreated}
                showTitle={false} 
              />
            </div>
          </DialogContent>
        </Dialog>
        </div>
      </header>

      {/* Library Section */}
      <div className="flex-1 overflow-y-auto no-scrollbar">
        {activeTab === "documents" ? (
          <DocumentLibrary 
            refreshTrigger={refreshTrigger} 
            searchQuery={searchQuery}
            showTitle={false} 
            activeTasks={activeTasks}
            onDismissTask={handleDismissTask}
          />
        ) : (
          <SkillHub 
            selectedSkills={selectedSkills}
            onToggleSkill={onToggleSkill}
          />
        )}
      </div>
    </div>
  );
}
