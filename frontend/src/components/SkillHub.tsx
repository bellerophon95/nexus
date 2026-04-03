"use client";

import React, { useState, useEffect } from "react";
import { 
  Zap, 
  Search, 
  Cpu, 
  CheckCircle2, 
  Circle,
  Package,
  Layers,
  Info,
  ExternalLink,
  ChevronRight
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { API_BASE_URL } from "@/lib/constants";
import { cn } from "@/lib/utils";

interface Skill {
  id: string;
  name: string;
  description: string;
  role?: string;
  expertise?: string[];
  category?: string;
  path: string;
}

interface SkillHubProps {
  selectedSkills: string[];
  onToggleSkill: (skillId: string) => void;
}

export function SkillHub({ selectedSkills, onToggleSkill }: SkillHubProps) {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [bundles, setBundles] = useState<Record<string, string[]>>({});
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeBundle, setActiveBundle] = useState<string | null>(null);

  useEffect(() => {
    const fetchSkills = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/skills/index`);
        const data = await response.json();
        setSkills(data.skills || []);
        setBundles(data.bundles || {});
      } catch (error) {
        console.error("Failed to fetch skills:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchSkills();
  }, []);

  const selectBundle = (bundleName: string) => {
    setActiveBundle(bundleName);
    const bundleSkillIds = bundles[bundleName] || [];
    bundleSkillIds.forEach(id => {
      if (!selectedSkills.includes(id)) {
        onToggleSkill(id);
      }
    });
  };

  const filteredSkills = skills.filter(skill => 
    skill.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    skill.id.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="flex h-full flex-col bg-slate-950/50">
      {/* Skill Hub Navigation */}
      <div className="border-b border-slate-800/60 bg-slate-900/40 p-6">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-blue-600/20 flex items-center justify-center border border-blue-500/30 shadow-lg shadow-blue-500/10">
              <Zap className="h-6 w-6 text-blue-400 fill-blue-400/20" />
            </div>
            <div>
              <h2 className="text-xl font-black text-white italic tracking-tight uppercase">Skill Hub</h2>
              <p className="text-[10px] text-slate-500 font-bold uppercase tracking-widest leading-none mt-1">Capability Orchestration Layer</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-3 bg-slate-900/60 border border-slate-800 px-4 py-1.5 rounded-full shadow-inner">
               <div className="flex h-2 w-2 rounded-full bg-blue-500 animate-pulse"></div>
               <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">{selectedSkills.length} Skills Active</span>
            </div>
          </div>
        </div>

        {/* Search and Quick Filters */}
        <div className="flex flex-col gap-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
            <input 
              type="text" 
              placeholder="Search agent capabilities..." 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-11 w-full rounded-xl border border-slate-800 bg-slate-900/50 pl-10 pr-4 text-sm text-slate-200 placeholder-slate-600 outline-none ring-blue-500/20 focus:ring-2 transition-all"
            />
          </div>

          <div className="flex flex-wrap gap-2">
             <span className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mr-2 self-center italic">Quick Bundles:</span>
             {Object.keys(bundles).map(bundleName => (
               <Button
                key={bundleName}
                variant="ghost"
                size="sm"
                onClick={() => selectBundle(bundleName)}
                className={cn(
                  "h-7 rounded-full text-[10px] uppercase tracking-wider font-bold border px-3 transition-all",
                  activeBundle === bundleName 
                    ? "bg-blue-600 border-blue-500 text-white shadow-lg shadow-blue-500/20" 
                    : "bg-slate-900/40 border-slate-800 text-slate-400 hover:text-slate-200"
                )}
               >
                 {bundleName}
               </Button>
             ))}
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-6 no-scrollbar">
        {loading ? (
          <div className="flex h-full items-center justify-center">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-blue-500/30 border-t-blue-500" />
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredSkills.map((skill) => {
              const isActive = selectedSkills.includes(skill.id);
              return (
                <Card 
                  key={skill.id} 
                  className={cn(
                    "relative group overflow-hidden border-slate-800 bg-slate-900/40 transition-all cursor-pointer hover:border-blue-500/50",
                    isActive && "border-blue-500/50 bg-blue-500/5 ring-1 ring-blue-500/20"
                  )}
                  onClick={() => onToggleSkill(skill.id)}
                >
                  <div className="p-5 flex flex-col h-full uppercase italic">
                    <div className="flex justify-between items-start mb-3">
                       <div className={cn(
                         "p-2 rounded-lg transition-colors",
                         isActive ? "bg-blue-600 text-white" : "bg-slate-800 text-slate-400 group-hover:text-blue-400"
                       )}>
                         <Zap className="h-4 w-4" />
                       </div>
                       {isActive ? (
                         <CheckCircle2 className="h-4 w-4 text-blue-500" />
                       ) : (
                         <Circle className="h-4 w-4 text-slate-700 group-hover:text-slate-500" />
                       )}
                    </div>
                    
                    <h3 className="font-bold text-sm text-slate-100 group-hover:text-white transition-colors tracking-tight line-clamp-1 mb-1">
                      {skill.name}
                    </h3>
                    <p className="text-[10px] text-slate-500 font-medium leading-relaxed line-clamp-3 mb-4">
                      {skill.description}
                    </p>

                    <div className="mt-auto flex items-center justify-between border-t border-slate-800/50 pt-4">
                       <div className="flex gap-2">
                         <Badge variant="outline" className="h-5 text-[8px] uppercase font-black bg-slate-950/50 text-slate-500 border-slate-800 px-2 tracking-tighter">
                           V2.4
                         </Badge>
                       </div>
                       <Button variant="ghost" size="icon" className="h-6 w-6 text-slate-700 hover:text-blue-400 transition-colors">
                         <Info className="h-4 w-4" />
                       </Button>
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </div>

      {/* Footer Info */}
      <div className="border-t border-slate-800/60 bg-slate-900/20 p-4 px-6 flex items-center justify-between overflow-hidden relative">
        <div className="flex items-center gap-4 text-[10px] text-slate-500 font-bold uppercase tracking-widest">
          <div className="flex items-center gap-1.5">
            <div className="h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />
            Skill Orchestrator Ready
          </div>
          <div className="flex items-center gap-1.5">
             <Package className="h-3 w-3" />
             Nexus SDK v1.2
          </div>
        </div>
        <a 
          href="https://github.com/sickn33/nexus-awesome-skills" 
          target="_blank" 
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 text-[10px] text-slate-400 hover:text-blue-400 transition-colors font-bold uppercase tracking-widest"
        >
          Source Registry
          <ExternalLink className="h-3 w-3" />
        </a>
      </div>
    </div>
  );
}
