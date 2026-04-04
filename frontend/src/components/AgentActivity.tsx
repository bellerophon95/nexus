import React from "react";
import { Terminal, Search, Binary, CheckCircle2, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export interface AgentStep {
  id: string;
  agent: string;
  node?: string; // New field from graph
  tool: string;
  status: "running" | "completed" | "error";
  timestamp: Date;
  rationale?: string;
}

interface AgentActivityProps {
  steps: AgentStep[];
}

export function AgentActivity({ steps }: AgentActivityProps) {
  return (
    <div className="flex flex-col bg-slate-900/40 p-4 backdrop-blur-md rounded-xl">
      <div className="mb-4 flex items-center gap-2 text-slate-200">
        <Terminal className="h-4 w-4 text-blue-400" />
        <span className="text-sm font-semibold tracking-tight uppercase">Agent activity</span>
      </div>

      <div className="flex flex-col gap-3">
        {steps.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <Search className="h-6 w-6 text-slate-700 mb-2 opacity-50" />
            <p className="text-xs text-slate-500 italic">Ready for research queries</p>
          </div>
        ) : (
          steps.map((step) => (
            <div
              key={step.id}
              className={cn(
                "group relative flex items-start gap-3 rounded-lg border border-slate-800 p-3 transition-all",
                step.status === "running" ? "border-blue-500/30 bg-blue-500/5" : "bg-slate-800/20"
              )}
            >
              <div
                className={cn(
                  "flex h-6 w-6 shrink-0 items-center justify-center rounded border shadow-sm",
                  step.status === "running" ? "border-blue-400/50 bg-blue-400/10 text-blue-400" : 
                  step.status === "completed" ? "border-emerald-400/50 bg-emerald-400/10 text-emerald-400" :
                  "border-rose-400/50 bg-rose-400/10 text-rose-400"
                )}
              >
                {step.status === "running" ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : step.status === "completed" ? (
                  <CheckCircle2 className="h-3 w-3" />
                ) : (
                  <Search className="h-3 w-3" />
                )}
              </div>

              <div className="flex-1 space-y-2 overflow-hidden">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-bold uppercase tracking-widest text-slate-500">
                      {step.agent}
                    </span>
                    <span className="text-[8px] text-slate-600">
                      {step.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                    </span>
                  </div>
                </div>
                
                <div className="space-y-1.5">
                  <p className="text-xs font-semibold text-slate-200">
                    {step.tool}
                  </p>
                  
                  {step.rationale && (
                    <div className="rounded-md bg-slate-900/50 p-2 border border-slate-800/50">
                      <p className="text-[10px] font-bold text-blue-400/80 uppercase tracking-tighter mb-1 select-none">Rationale</p>
                      <p className="text-[11px] leading-relaxed text-slate-400 italic">
                        {step.rationale}
                      </p>
                    </div>
                  )}
                </div>
              </div>

              {step.status === "running" && (
                <div className="absolute top-0 right-0 p-1">
                   <div className="h-1 w-1 animate-ping rounded-full bg-blue-400"></div>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
