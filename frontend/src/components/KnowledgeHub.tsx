"use client";

import React, { useState } from "react";
import { 
  Plus, 
  Library,
  Layers,
  Search,
  Upload,
  Zap
} from "lucide-react";
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

  const handleUploadSuccess = () => {
    // Increment trigger to refresh DocumentLibrary
    setRefreshTrigger(prev => prev + 1);
    // Optionally close the modal after a short delay
    setTimeout(() => {
      setIsUploadModalOpen(false);
    }, 2000);
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
              <UploadPanel onUploadSuccess={handleUploadSuccess} showTitle={false} />
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
