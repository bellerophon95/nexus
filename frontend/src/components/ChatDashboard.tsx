"use client";

import React, { useState, useEffect } from "react";
import { 
  PanelRightClose,
  Library,
  Layers
} from "lucide-react";
import { ChatInterface, Message } from "@/components/ChatInterface";
import { AgentActivity, AgentStep } from "@/components/AgentActivity";
import { CitationCard } from "@/components/CitationCard";
import { MetricsPanel, ChatMetrics } from "@/components/MetricsPanel";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { API_BASE_URL } from "@/lib/constants";
import { getAuthHeaders } from "@/lib/auth";
import { useAppContext } from "@/context/AppContext";

interface ChatDashboardProps {
  initialConversationId?: string | null;
}

export function ChatDashboard({ initialConversationId = null }: ChatDashboardProps) {
  const { isSidebarOpen, setIsSidebarOpen, triggerHistoryRefresh } = useAppContext();
  
  const [conversationId, setConversationId] = useState<string | null>(initialConversationId);
  const [initialMessages, setInitialMessages] = useState<Message[]>([]);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null);
  const [selectedCitations, setSelectedCitations] = useState<any[]>([]);
  const [selectedAgentSteps, setSelectedAgentSteps] = useState<AgentStep[]>([]);
  const [selectedMetrics, setSelectedMetrics] = useState<ChatMetrics | null>(null);
  const [isMetricsLoading, setIsMetricsLoading] = useState(false);

  // Load history when conversationId changes (from props)
  useEffect(() => {
    if (initialConversationId) {
      loadConversation(initialConversationId);
    } else {
      setConversationId(null);
      setInitialMessages([]);
      clearState();
    }
  }, [initialConversationId]);

  const loadConversation = async (id: string) => {
    setIsHistoryLoading(true);
    setConversationId(id);
    clearState();
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/history/conversations/${id}/messages`, {
        headers: getAuthHeaders()
      });
      const data = await response.json();
      
      const normalized = (data.messages || []).map((msg: any) => ({
        ...msg,
        agentSteps: msg.agentSteps || msg.agent_steps,
        citations: msg.citations || msg.citations
      }));

      setInitialMessages(normalized);
    } catch (err) {
      console.error("Failed to load conversation:", err);
    } finally {
      setIsHistoryLoading(false);
    }
  };

  const handleActivityUpdate = (data: any) => {
     // Simplified implementation for now, re-using logic from original page.tsx
     setSelectedAgentSteps((prev) => {
        const agentName = data.agent || data.node || "Nexus";
        const toolName = data.tool || data.status || "Thinking...";
        const statusValue = (data.status === "completed" || data.status_type === "completed" ? "completed" : "running") as any;
        const rationale = data.rationale;
        
        const existingIdx = prev.findIndex(s => s.agent === agentName && s.tool === toolName);
        
        if (existingIdx !== -1) {
          const nextSteps = [...prev];
          nextSteps[existingIdx] = {
            ...nextSteps[existingIdx],
            status: statusValue,
            rationale: rationale || nextSteps[existingIdx].rationale
          };
          return nextSteps;
        }
        
        return [...prev, {
          id: Math.random().toString(36).substring(2, 11),
          agent: agentName,
          tool: toolName,
          status: statusValue,
          timestamp: new Date(),
          rationale: rationale,
        } as AgentStep];
      });
  };

  const clearState = () => {
    setSelectedCitations([]);
    setSelectedAgentSteps([]);
    setSelectedMetrics(null);
    setSelectedMessageId(null);
  };

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <header className="flex h-16 items-center justify-between border-b border-slate-800 bg-slate-900/20 px-6 backdrop-blur-sm">
         <div className="flex items-center gap-3">
            <div className="flex -space-x-2">
               <div className="h-6 w-6 rounded-full border-2 border-slate-950 bg-blue-500"></div>
               <div className="h-6 w-6 rounded-full border-2 border-slate-950 bg-emerald-500"></div>
               <div className="h-6 w-6 rounded-full border-2 border-slate-950 bg-rose-500"></div>
            </div>
            <span className="text-sm font-semibold text-slate-100">Nexus AI Intelligent Grounding Layer</span>
         </div>
         <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => setIsSidebarOpen(!isSidebarOpen)} className="text-slate-400 hover:text-white">
               <PanelRightClose className={cn("h-4 w-4 transition-transform", !isSidebarOpen && "rotate-180")} />
            </Button>
         </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
         <div className="flex-1 overflow-hidden">
            <ChatInterface 
              conversationId={conversationId}
              initialMessages={initialMessages}
              isLoadingHistory={isHistoryLoading}
              selectedMessageId={selectedMessageId}
              onConversationCreated={(id) => {
                setConversationId(id);
                triggerHistoryRefresh();
              }}
              onMessageSelect={(msg: Message) => {
                setSelectedMessageId(msg.id || null);
                setSelectedCitations(msg.citations || []);
                const mappedSteps = (msg.agentSteps || []).map((step: any, i: number) => ({
                  id: step.id || `${msg.id}-${i}`,
                  agent: step.agent || "Agent",
                  tool: step.tool || "Processing...",
                  status: step.status || "completed",
                  timestamp: step.timestamp ? new Date(step.timestamp) : new Date(),
                  rationale: step.rationale
                }));
                setSelectedAgentSteps(mappedSteps as AgentStep[]);
                setSelectedMetrics(msg.metrics as any);
              }}
              onAgentStep={handleActivityUpdate}
              onActivity={handleActivityUpdate}
              onCitationsUpdate={(c) => {
                setSelectedCitations(c);
              }}
              onMetricsUpdate={(m) => {
                setSelectedMetrics(m);
                setIsMetricsLoading(false);
              }}
              onLoadingStart={() => {
                setSelectedMetrics(null);
                setIsMetricsLoading(true);
                clearState();
              }}
            />
         </div>
         
         {/* Right Side: Citations / Steps */}
         <aside className="hidden xl:flex w-80 flex-col border-l border-slate-800 bg-slate-900/10 h-full overflow-hidden">
            <div className="flex-1 overflow-y-auto no-scrollbar scroll-smooth">
              <div className="p-4 space-y-4 pb-24">
                 <div className="flex items-center gap-2 text-slate-100 mb-2">
                    <Library className="h-4 w-4 text-blue-400" />
                    <span className="text-sm font-bold uppercase tracking-tight">Citations & Logic</span>
                 </div>
                 {selectedCitations.length === 0 ? (
                   <div className="rounded-xl border border-dashed border-slate-800 p-8 text-center bg-slate-900/40">
                      <Layers className="h-6 w-6 text-slate-700 mx-auto mb-2" />
                       <p className="text-[10px] text-slate-500 italic max-w-xs mx-auto">
                          Metadata for synthesized claims will appear here once answer generation is complete
                       </p>
                   </div>
                 ) : (
                   selectedCitations.map((cit) => (
                     <div key={cit.id} id={`citation-${cit.id}`}>
                        <CitationCard 
                          id={cit.id} 
                          title={cit.title}
                          header={cit.header} 
                          text={cit.text} 
                          metadata={cit.metadata}
                        />
                     </div>
                   ))
                 )}
                 
                 <Separator className="bg-slate-800 my-4" />
                 <div className="rounded-xl overflow-hidden shadow-2xl">
                     <AgentActivity steps={selectedAgentSteps} />
                  </div>
              </div>
            </div>
         </aside>
      </div>
      
      <MetricsPanel metrics={selectedMetrics} isLoading={isMetricsLoading} />
    </div>
  );
}
