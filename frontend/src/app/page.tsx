"use client";

import React, { useState } from "react";
import { 
  Plus, 
  MessageSquare, 
  Settings, 
  Search, 
  PanelRightClose,
  ChevronRight,
  Sparkles,
  GitBranch,
  ShieldCheck,
  Zap,
  Library,
  Layers,
  LayoutDashboard
} from "lucide-react";
import { ChatInterface, Message } from "@/components/ChatInterface";
import { AgentActivity, AgentStep } from "@/components/AgentActivity";
import { CitationCard } from "@/components/CitationCard";
import { MetricsPanel, ChatMetrics } from "@/components/MetricsPanel";
import { KnowledgeHub } from "@/components/KnowledgeHub";
import { SidebarHistory } from "@/components/SidebarHistory";

import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { API_BASE_URL } from "@/lib/constants";
import { getOrCreateSessionId, handleAccessParams, getAuthHeaders } from "@/lib/auth";
import { useEffect } from "react";

export default function Home() {
  const [activeTab, setActiveTab] = useState<"chat" | "library" | "settings">("chat");
  const [citations, setCitations] = useState<any[]>([]);
  const [agentSteps, setAgentSteps] = useState<AgentStep[]>([]);
  const [metrics, setMetrics] = useState<ChatMetrics | null>(null);
  const [isMetricsLoading, setIsMetricsLoading] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [initialMessages, setInitialMessages] = useState<Message[]>([]);
  const [refreshHistoryTrigger, setRefreshHistoryTrigger] = useState(0);
  const [sessionId, setSessionId] = useState<string>("");
  const [accessTier, setAccessTier] = useState<string>("visitor");
  const [selectedSkills, setSelectedSkills] = useState<string[]>([]);

  const toggleSkill = (skillId: string) => {
    setSelectedSkills(prev => 
      prev.includes(skillId) 
        ? prev.filter(id => id !== skillId) 
        : [...prev, skillId]
    );
  };

  useEffect(() => {
    // 1. Initialize session and handle access params once on mount
    handleAccessParams();
    const sid = getOrCreateSessionId(); 
    setSessionId(sid);
    
    const tier = typeof window !== 'undefined' ? localStorage.getItem('nexus_access_tier') || 'visitor' : 'visitor';
    setAccessTier(tier);
  }, []);

  const handleAgentStep = (stepData: any) => {
    // If we already have this tool/step, update it instead of adding a new one
    setAgentSteps((prev) => {
      const existingIdx = prev.findIndex(s => s.tool === stepData.tool && s.agent === stepData.agent);
      if (existingIdx !== -1) {
        const updated = [...prev];
        updated[existingIdx] = {
          ...updated[existingIdx],
          status: stepData.status || "completed"
        };
        return updated;
      }
      
      const newStep: AgentStep = {
        id: Math.random().toString(36).substr(2, 9),
        agent: stepData.agent || "System",
        tool: stepData.tool || "Processing...",
        status: stepData.status || "completed",
        timestamp: new Date(),
      };
      return [newStep, ...prev];
    });
  };

  const handleActivity = (activityData: any) => {
    const newStep: AgentStep = {
      id: Math.random().toString(36).substr(2, 9),
      agent: activityData.node || "Agent",
      node: activityData.node,
      tool: activityData.status || "Thinking...",
      status: activityData.status_type || "running",
      timestamp: new Date(),
    };

    setAgentSteps((prev) => {
      // Find latest step for this node
      const existingIdx = prev.findIndex(s => s.node === newStep.node);
      
      if (existingIdx !== -1) {
        const updated = [...prev];
        // If it was already completed, don't revert to running unless it's a new task
        // For simplicity: replace the first occurrence of this node's activity
        updated[existingIdx] = {
          ...updated[existingIdx],
          tool: newStep.tool,
          status: newStep.status,
          timestamp: newStep.timestamp
        };
        return updated;
      }
      
      return [newStep, ...prev];
    });
  };

  const clearState = () => {
    setCitations([]);
    setAgentSteps([]);
  };

  const handleSelectConversation = async (id: string) => {
    setConversationId(id);
    clearState();
    try {
      const response = await fetch(`${API_BASE_URL}/api/history/conversations/${id}/messages`, {
        headers: getAuthHeaders()
      });
      const data = await response.json();
      setInitialMessages(data.messages || []);
      setActiveTab("chat");
    } catch (err) {
      console.error("Failed to load conversation:", err);
    }
  };

  const handleNewChat = () => {
    setConversationId(null);
    setInitialMessages([]);
    clearState();
    setActiveTab("chat");
  };

  return (
    <main className="flex h-screen w-full flex-row overflow-hidden bg-slate-950 text-slate-200">
      {/* ── Left Sidebar: Context / Menu ── */}
      <aside className={cn(
        "flex flex-col border-r border-slate-800 bg-slate-900/40 backdrop-blur-xl transition-all duration-300",
        isSidebarOpen ? "w-72" : "w-16"
      )}>
        <div className="flex h-16 items-center border-b border-slate-800 px-4">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-lg bg-blue-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
               <Zap className="h-5 w-5 text-white fill-white" />
            </div>
            {isSidebarOpen && <span className="text-lg font-black tracking-tight text-white uppercase italic">Nexus AI</span>}
          </div>
        </div>

        <nav className="flex-1 space-y-1 p-2 overflow-y-auto">
          <SidebarItem 
            icon={<LayoutDashboard className="h-4 w-4" />} 
            label="Dashboard" 
            isActive={activeTab === "chat"} 
            onClick={() => setActiveTab("chat")}
            isOpen={isSidebarOpen}
            badge={selectedSkills.length > 0 ? selectedSkills.length : undefined}
          />
          <SidebarItem 
             icon={<Library className="h-4 w-4" />} 
             label="Knowledge Base" 
             isActive={activeTab === "library"} 
             onClick={() => setActiveTab("library")}
             isOpen={isSidebarOpen}
             badge={selectedSkills.length > 0 ? selectedSkills.length : undefined}
          />

          {isSidebarOpen && (
            <div className="pt-6 pb-2 px-3">
              <span className="text-[10px] font-bold uppercase tracking-widest text-slate-500 italic">Configuration</span>
            </div>
          )}
          
          <SidebarItem 
            icon={<Settings className="h-4 w-4" />} 
            label="System Settings" 
            isActive={activeTab === "settings"} 
            onClick={() => setActiveTab("settings")}
            isOpen={isSidebarOpen}
          />

          {isSidebarOpen && activeTab === "chat" && (
            <div className="flex-1 mt-4 overflow-hidden">
               <SidebarHistory 
                 currentConversationId={conversationId}
                 onSelectConversation={handleSelectConversation}
                 onNewChat={handleNewChat}
                 isOpen={isSidebarOpen}
                 refreshTrigger={refreshHistoryTrigger}
               />
            </div>
          )}
        </nav>

        {/* Sidebar Footer: Researcher & Memory */}
        <div className="border-t border-slate-800 bg-slate-900/60 backdrop-blur-md">
          {isSidebarOpen && (
            <div className="p-3 border-b border-slate-800/50">
              <div className="flex items-center gap-3 px-2">
                <div className="h-7 w-7 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-[10px] font-black text-white italic shadow-lg shadow-blue-500/10">
                  RS
                </div>
                <div className="flex flex-col overflow-hidden">
                   <span className="text-[11px] font-bold text-slate-200 leading-tight truncate">
                     Researcher
                   </span>
                   <span className="text-[9px] text-slate-500 font-medium tracking-tight truncate">
                     ID: #{sessionId.slice(0, 8)}
                   </span>
                </div>
              </div>
            </div>
          )}
          
          <div className="p-4">
            {isSidebarOpen ? (
                <div className="rounded-xl bg-blue-500/5 p-3 border border-blue-500/10 transition-all hover:bg-blue-500/10 group">
                   <p className="text-[10px] text-slate-500 font-bold uppercase mb-2 flex items-center gap-2">
                     <span className="h-1 w-1 rounded-full bg-emerald-500 animate-pulse"></span>
                     Memory Status
                   </p>
                   <div className="flex justify-between text-[10px] mb-1">
                      <span className="text-slate-400">Semantic Cache</span>
                      <span className="text-emerald-400 font-bold tracking-tight">OPTIMIZED</span>
                   </div>
                   <div className="h-1 w-full bg-slate-800 rounded-full overflow-hidden">
                      <div className="h-full bg-gradient-to-r from-blue-600 to-emerald-500 transition-all duration-1000" style={{ width: '12%' }}></div>
                   </div>
                </div>
            ) : (
                <div className="flex justify-center py-2">
                   <ShieldCheck className="h-5 w-5 text-emerald-500" />
                </div>
            )}
          </div>
        </div>
      </aside>

      {/* ── Main Chat / Component View ── */}
      <section className="flex flex-1 flex-col relative overflow-hidden">
        {activeTab === "chat" ? (
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
                    onConversationCreated={(id) => {
                      setConversationId(id);
                      setRefreshHistoryTrigger(prev => prev + 1);
                    }}
                    onAgentStep={handleAgentStep}
                    onActivity={handleActivity}
                    onCitationsUpdate={(c) => {
                      setCitations(c);
                    }}
                    onMetricsUpdate={(m) => {
                      setMetrics(m);
                      setIsMetricsLoading(false);
                    }}
                    onLoadingStart={() => {
                      setMetrics(null);
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
                       {citations.length === 0 ? (
                         <div className="rounded-xl border border-dashed border-slate-800 p-8 text-center bg-slate-900/40">
                            <Layers className="h-6 w-6 text-slate-700 mx-auto mb-2" />
                            <p className="text-[10px] text-slate-500 italic max-w-xs mx-auto">
                              Metadata for synthesized claims will appear here once aswer generation is complete
                            </p>
                         </div>
                       ) : (
                         citations.map((cit) => (
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
                          <AgentActivity steps={agentSteps} />
                       </div>
                    </div>
                  </div>
               </aside>
            </div>
            
            <MetricsPanel metrics={metrics} isLoading={isMetricsLoading} />
          </div>
        ) : activeTab === "library" ? (
          <KnowledgeHub 
            selectedSkills={selectedSkills} 
            onToggleSkill={toggleSkill} 
          />
        ) : (
          <div className="flex h-full flex-col items-center justify-center space-y-4 text-center">
            <Settings className="h-12 w-12 text-slate-800 animate-pulse" />
            <h2 className="text-2xl font-bold text-slate-300 tracking-tight">System Settings</h2>
            <p className="text-slate-500 max-w-sm italic">Core orchestration parameters and model configurations will be managed here in the next milestone.</p>
            <Button onClick={() => setActiveTab("chat")} variant="link" className="text-blue-400 mt-4">Return to Dashboard</Button>
          </div>
        )}
      </section>
    </main>
  );
}

function SidebarItem({ icon, label, isActive, onClick, isOpen, badge }: { icon: React.ReactNode, label: string, isActive: boolean, onClick: () => void, isOpen: boolean, badge?: number }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex w-full items-center gap-3 rounded-lg px-3 py-2 transition-all",
        isActive 
          ? "bg-blue-600/10 text-white shadow-sm ring-1 ring-blue-500/20" 
          : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200",
        !isOpen && "justify-center px-0"
      )}
    >
      <div className={cn(
        "flex shrink-0 items-center justify-center transition-all",
        isActive && "text-blue-400"
      )}>
        {icon}
      </div>
      {isOpen && <span className="text-[13px] font-medium tracking-tight whitespace-nowrap">{label}</span>}
      {isOpen && badge !== undefined && (
        <span className="ml-auto flex h-4 w-4 items-center justify-center rounded-full bg-blue-600 text-[10px] font-bold text-white shadow-lg shadow-blue-500/20">
          {badge}
        </span>
      )}
      {isOpen && isActive && badge === undefined && <ChevronRight className="ml-auto h-3 w-3 text-blue-500/50" />}
    </button>
  );
}
