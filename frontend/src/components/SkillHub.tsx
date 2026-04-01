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

interface Skill {
  id: string;
  metadata: {
    name: string;
    description: string;
    category?: string;
  };
  path: string;
}

export function SkillHub() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [bundles, setBundles] = useState<Record<string, string[]>>({});
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedSkills, setSelectedSkills] = useState<Set<string>>(new Set());
  const [activeBundle, setActiveBundle] = useState<string | null>(null);

  useEffect(() => {
    const fetchSkills = async () => {
      try {
        const response = await fetch("/api/skills/index");
        const data = await response.json();
        setSkills(data.skills);
        setBundles(data.bundles);
      } catch (error) {
        console.error("Failed to fetch skills:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchSkills();
  }, []);

  const toggleSkill = (id: string) => {
    const newSelected = new Set(selectedSkills);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedSkills(newSelected);
    setActiveBundle(null);
  };

  const applyBundle = (bundleName: string) => {
    const bundleSkillIds = bundles[bundleName] || [];
    setSelectedSkills(new Set(bundleSkillIds));
    setActiveBundle(bundleName);
  };

  const filteredSkills = skills.filter(skill => 
    skill.metadata.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    skill.id.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="flex h-full flex-col bg-slate-950/50">
      {/* Skill Hub Navigation */}
      <div className="border-b border-slate-800/60 bg-slate-900/40 p-6">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-amber-600/20 flex items-center justify-center border border-amber-500/30 shadow-lg shadow-amber-500/10">
              <Zap className="h-6 w-6 text-amber-400 fill-amber-400/20" />
            </div>
            <div>
              <h2 className="text-xl font-black text-white italic tracking-tight uppercase">Skill Hub</h2>
              <p className="text-[10px] text-slate-500 font-bold uppercase tracking-widest leading-none">Capability Orchestration Layer</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Badge variant="outline" className="bg-amber-500/10 text-amber-400 border-amber-500/20 px-3 py-1">
              {selectedSkills.size} Skills Active
            </Badge>
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
              className="h-11 w-full rounded-xl border border-slate-800 bg-slate-900/50 pl-10 pr-4 text-sm text-slate-200 placeholder-slate-600 outline-none ring-amber-500/20 focus:ring-2 transition-all"
            />
          </div>

          <div className="flex flex-wrap gap-2">
             <span className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mr-2 self-center">Bundles:</span>
             {Object.keys(bundles).map(bundleName => (
               <Button
                key={bundleName}
                variant="ghost"
                size="sm"
                onClick={() => applyBundle(bundleName)}
                className={`h-7 rounded-full text-[10px] uppercase tracking-wider font-bold border px-3 transition-all ${
                  activeBundle === bundleName 
                  ? "bg-amber-500/20 border-amber-500/40 text-amber-400" 
                  : "bg-slate-900/40 border-slate-800 text-slate-400 hover:text-slate-200"
                }`}
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
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-amber-500/30 border-t-amber-500" />
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredSkills.map((skill) => (
              <Card 
                key={skill.id}
                onClick={() => toggleSkill(skill.id)}
                className={`group relative overflow-hidden p-4 cursor-pointer transition-all border-slate-800 hover:border-amber-500/40 bg-slate-900/30 hover:bg-slate-900/50 ${
                  selectedSkills.has(skill.id) ? "ring-1 ring-amber-500/50 border-amber-500/40" : ""
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className={`p-2 rounded-lg transition-colors ${
                    selectedSkills.has(skill.id) ? "bg-amber-500/20 text-amber-400" : "bg-slate-800 text-slate-500 group-hover:text-slate-300"
                  }`}>
                    <Cpu className="h-5 w-5" />
                  </div>
                  {selectedSkills.has(skill.id) ? (
                    <CheckCircle2 className="h-5 w-5 text-amber-500 shadow-lg" />
                  ) : (
                    <Circle className="h-5 w-5 text-slate-800 group-hover:text-slate-700" />
                  )}
                </div>

                <div className="mt-3">
                  <h3 className="font-bold text-sm text-slate-200 group-hover:text-white transition-colors uppercase tracking-tight">
                    {skill.metadata.name || skill.id}
                  </h3>
                  <p className="mt-1 text-[11px] text-slate-500 line-clamp-2 leading-relaxed">
                    {skill.metadata.description || "No description provided."}
                  </p>
                </div>

                {/* Categories / Badges if available */}
                <div className="mt-4 flex items-center justify-between">
                   <div className="flex gap-2">
                     <Badge variant="ghost" className="h-5 text-[9px] uppercase font-black bg-slate-950/50 text-slate-600 border-none px-2 tracking-tighter">
                       v1.0
                     </Badge>
                   </div>
                   <Button variant="ghost" size="icon" className="h-6 w-6 text-slate-700 hover:text-amber-400 transition-colors">
                     <Info className="h-4 w-4" />
                   </Button>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Footer Info */}
      <div className="border-t border-slate-800/60 bg-slate-900/20 p-4 px-6 flex items-center justify-between overflow-hidden relative">
        <div className="flex items-center gap-4 text-[10px] text-slate-500 font-bold uppercase tracking-widest">
          <div className="flex items-center gap-1.5">
            <div className="h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />
            Orchestrator Online
          </div>
          <div className="flex items-center gap-1.5">
             <Package className="h-3 w-3" />
             Antigravity Library V2.4
          </div>
        </div>
        <a 
          href="https://github.com/sickn33/antigravity-awesome-skills" 
          target="_blank" 
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 text-[10px] text-slate-400 hover:text-amber-400 transition-colors font-bold uppercase tracking-widest"
        >
          Source Registry
          <ExternalLink className="h-3 w-3" />
        </a>
      </div>
    </div>
  );
}
