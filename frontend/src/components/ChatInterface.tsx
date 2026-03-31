import React, { useState, useRef, useEffect } from "react";
import { Send, Loader2, Sparkles, User, StopCircle, Settings2, Sliders, Info } from "lucide-react";
import { 
  Dialog, 
  DialogContent, 
  DialogHeader, 
  DialogTitle, 
  DialogTrigger,
  DialogDescription
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MessageBubble } from "./MessageBubble";
import { cn } from "@/lib/utils";
import { API_BASE_URL } from "@/lib/constants";
import { getAuthHeaders, getOrCreateSessionId } from "@/lib/auth";

export interface AgentStep {
  agent: string;
  tool: string;
  status: "running" | "completed" | "error";
}

export interface Message {
  id?: string;
  role: "user" | "assistant";
  content: string;
  citations?: any[];
  feedback?: number;
  metrics?: {
    latency?: number;
    tokens?: number;
    cost?: number;
    hallucinationScore?: number;
    relevanceScore?: number;
    guardrailStatus?: string;
    tier?: string;
  };
  agentSteps?: AgentStep[];
}

interface ChatInterfaceProps {
  onMessageReceived?: (message: Message) => void;
  onCitationsUpdate?: (citations: any[]) => void;
  onAgentStep?: (step: any) => void;
  onActivity?: (activity: any) => void;
  onMetricsUpdate?: (metrics: any) => void;
  onLoadingStart?: () => void;
  conversationId?: string | null;
  initialMessages?: Message[];
  onConversationCreated?: (id: string) => void;
}

export function ChatInterface({ 
  onMessageReceived, 
  onCitationsUpdate, 
  onAgentStep,
  onActivity,
  onMetricsUpdate,
  onLoadingStart,
  conversationId: initialConvId,
  initialMessages = [],
  onConversationCreated
}: ChatInterfaceProps) {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>(initialMessages);
  const [conversationId, setConversationId] = useState<string | null>(initialConvId || null);
  const [isLoading, setIsLoading] = useState(false);
  
  // Tuning parameters
  const [matchThreshold, setMatchThreshold] = useState(0.2);
  const [rerank, setRerank] = useState(true);
  const [maxIterations, setMaxIterations] = useState(3);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (initialConvId !== conversationId) {
      setConversationId(initialConvId || null);
    }
  }, [initialConvId]);

  useEffect(() => {
    if (initialMessages.length > 0) {
      // Normalize history from DB (snake_case) to Frontend (camelCase)
      const normalized = initialMessages.map(msg => ({
        ...msg,
        agentSteps: msg.agentSteps || (msg as any).agent_steps,
        citations: msg.citations || (msg as any).citations
      }));
      setMessages(normalized);
      
      // Auto-populate the sidebar with the latest assistant message's logic/citations
      const lastAssistant = [...normalized].reverse().find(m => m.role === "assistant");
      if (lastAssistant) {
        if (lastAssistant.citations) onCitationsUpdate?.(lastAssistant.citations);
        if (lastAssistant.agentSteps) {
            // We need to pass them one by one or as a batch
            lastAssistant.agentSteps.forEach((step: AgentStep) => onAgentStep?.(step));
        }
        if (lastAssistant.metrics) onMetricsUpdate?.(lastAssistant.metrics);
      }
    } else if (!initialConvId) {
      setMessages([]);
    }
  }, [initialMessages, initialConvId]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = { role: "user", content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);
    onLoadingStart?.();

    const assistantMessage: Message = { role: "assistant", content: "" };
    setMessages((prev) => [...prev, assistantMessage]);

    // Close any existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    // Connect to SSE endpoint (Uses API_BASE_URL for production compatibility)
    // Note: SSE (EventSource) doesn't support custom headers, 
    // so we pass user_id as a query param.
    const userId = getOrCreateSessionId();
    let url = `${API_BASE_URL}/api/query?q=${encodeURIComponent(input)}&match_threshold=${matchThreshold}&rerank=${rerank}&user_id=${userId}`;
    if (conversationId) {
      url += `&conversation_id=${conversationId}`;
    }
    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    eventSource.onerror = (err) => {
        console.error("SSE Connection Error:", err);
        setIsLoading(false);
        setMessages(prev => [
            ...prev.slice(0, -1),
            { role: "assistant", content: "⚠️ The Nexus backend is currently experiencing connection issues. Please try again in a few moments." }
        ]);
        eventSource.close();
    };

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.type === "token") {
          setMessages((prev) => {
            const lastMessage = prev[prev.length - 1];
            if (lastMessage && lastMessage.role === "assistant") {
              const updatedMessage = {
                ...lastMessage,
                content: lastMessage.content + data.content
              };
              return [...prev.slice(0, -1), updatedMessage];
            }
            return prev;
          });
        } else if (data.type === "agent_step") {
          onAgentStep?.(data);
          setMessages((prev) => {
            const newMessages = [...prev];
            const last = newMessages[newMessages.length - 1];
            if (last && last.role === "assistant") {
              const steps = last.agentSteps || [];
              const existingIdx = steps.findIndex(s => s.agent === data.agent && s.tool === data.tool);
              if (existingIdx > -1) {
                steps[existingIdx] = { agent: data.agent, tool: data.tool, status: data.status };
              } else {
                steps.push({ agent: data.agent, tool: data.tool, status: data.status });
              }
              last.agentSteps = [...steps];
            }
            return newMessages;
          });
        } else if (data.type === "activity") {
          onActivity?.(data);
        } else if (data.type === "metrics") {
          onMetricsUpdate?.(data);
          setMessages((prev) => {
            const newMessages = [...prev];
            const lastMessage = newMessages[newMessages.length - 1];
            if (lastMessage && lastMessage.role === "assistant") {
              lastMessage.metrics = data;
            }
            return newMessages;
          });
        } else if (data.type === "done") {
          if (data.citations) {
            onCitationsUpdate?.(data.citations);
          }
          
          if (data.conversation_id && !conversationId) {
            setConversationId(data.conversation_id);
            onConversationCreated?.(data.conversation_id);
          }

          if (data.message_id) {
            setMessages((prev) => {
              const newMessages = [...prev];
              const last = newMessages[newMessages.length - 1];
              if (last && last.role === "assistant") {
                last.id = data.message_id;
              }
              return newMessages;
            });
          }

          setIsLoading(false);
          eventSource.close();
        } else if (data.type === "error") {
          setMessages((prev) => {
            const newMessages = [...prev];
            const lastMessage = newMessages[newMessages.length - 1];
            if (lastMessage) {
              lastMessage.content = `Error: ${data.message}`;
            }
            return newMessages;
          });
          setIsLoading(false);
          eventSource.close();
        }
      } catch (err) {
        console.error("Error parsing SSE data:", err);
      }
    };

    eventSource.onerror = (err) => {
      console.error("SSE Connection Error. Status:", eventSource.readyState, "Event:", err);
      setIsLoading(false);
      eventSource.close();
    };
  };

  const handleFeedback = async (messageId: string, score: number) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/messages/${messageId}/feedback`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          ...getAuthHeaders()
        },
        body: JSON.stringify({ score })
      });
      
      if (response.ok) {
        setMessages((prev) => prev.map(msg => 
          msg.id === messageId ? { ...msg, feedback: score } : msg
        ));
      }
    } catch (err) {
      console.error("Failed to submit feedback:", err);
    }
  };

  const handleStop = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-full flex-col bg-slate-950/20 backdrop-blur-sm">
      {/* Search & Agent Tuning Header */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-slate-800/50 bg-slate-900/20">
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="bg-blue-500/10 text-blue-400 border-blue-500/20 text-[10px] font-bold tracking-tighter uppercase px-1.5 h-5">
            Nexus v0.1.0
          </Badge>
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-widest">Multi-Agent Lab</span>
        </div>
        
        <Dialog>
          <DialogTrigger 
            render={
              <Button variant="ghost" size="sm" className="h-8 gap-2 text-slate-400 hover:text-blue-400 hover:bg-blue-500/10 rounded-lg transition-all active:scale-95">
                <Settings2 className="h-3.5 w-3.5" />
                <span className="text-[11px] font-bold uppercase tracking-wider">Tune Engine</span>
              </Button>
            }
          />
          <DialogContent className="bg-slate-900 border-slate-800 text-slate-200 sm:max-w-[400px] shadow-2xl backdrop-blur-xl">
            <DialogHeader>
              <div className="flex items-center gap-2 mb-1">
                <Sliders className="h-4 w-4 text-blue-400" />
                <DialogTitle className="text-lg font-bold tracking-tight text-slate-100">Engine Tuning</DialogTitle>
              </div>
              <DialogDescription className="text-slate-500 text-xs italic">
                Calibrate the retrieval sensitivity and agentic reasoning depth for this session.
              </DialogDescription>
            </DialogHeader>
            
            <div className="space-y-6 py-6">
              {/* Threshold Setting */}
              <div className="space-y-3">
                <div className="flex justify-between items-end">
                  <label className="text-[11px] font-bold uppercase tracking-widest text-slate-400 flex items-center gap-1.5">
                    Retrieval Sensitivity
                    <Info className="h-3 w-3 opacity-50" />
                  </label>
                  <span className="text-xs font-mono text-blue-400 font-bold bg-blue-500/10 px-1.5 py-0.5 rounded border border-blue-500/20">
                    {matchThreshold.toFixed(2)}
                  </span>
                </div>
                <input 
                  type="range" 
                  min="0.05" 
                  max="0.9" 
                  step="0.05" 
                  value={matchThreshold} 
                  onChange={(e) => setMatchThreshold(parseFloat(e.target.value))}
                  className="w-full h-1.5 appearance-none bg-slate-800 rounded-lg cursor-pointer accent-blue-500 hover:accent-blue-400 transition-all"
                />
                <div className="flex justify-between text-[10px] text-slate-600 font-medium">
                  <span className="italic">Broad (Recall)</span>
                  <span className="italic">Strict (Precision)</span>
                </div>
              </div>

              <Separator className="bg-slate-800/50" />

              {/* Reranking Toggle */}
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <label className="text-[11px] font-bold uppercase tracking-widest text-slate-400">Deep Reranking</label>
                  <p className="text-[10px] text-slate-600">Apply Cross-Encoder for precision.</p>
                </div>
                <button 
                  onClick={() => setRerank(!rerank)}
                  className={cn(
                    "relative h-5 w-10 shrink-0 cursor-pointer rounded-full transition-colors duration-200 ease-in-out focus:outline-none",
                    rerank ? "bg-blue-600" : "bg-slate-700"
                  )}
                >
                  <span className={cn(
                    "pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out",
                    rerank ? "translate-x-5" : "translate-x-1"
                  )} />
                </button>
              </div>

              <Separator className="bg-slate-800/50" />

              {/* Max Iterations */}
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <label className="text-[11px] font-bold uppercase tracking-widest text-slate-400">Reasoning Depth</label>
                  <p className="text-[10px] text-slate-600">Max agentic search loops.</p>
                </div>
                <div className="flex items-center gap-3">
                   <button 
                    onClick={() => setMaxIterations(Math.max(1, maxIterations - 1))}
                    className="h-7 w-7 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-400 hover:bg-slate-700 transition-all"
                   >-</button>
                   <span className="text-xs font-bold text-slate-200 min-w-[12px] text-center">{maxIterations}</span>
                   <button 
                    onClick={() => setMaxIterations(Math.min(10, maxIterations + 1))}
                    className="h-7 w-7 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-400 hover:bg-slate-700 transition-all"
                   >+</button>
                </div>
              </div>
            </div>

            <div className="rounded-lg bg-blue-500/5 border border-blue-500/10 p-3 mt-2">
              <div className="flex gap-2">
                <Sparkles className="h-4 w-4 text-blue-400 shrink-0 mt-0.5" />
                <p className="text-[10px] leading-relaxed text-slate-400 italic">
                  <b>Advice:</b> Lower thresholds (0.10) are better for complex, multi-hop research, while higher values (0.4+) are safer for factual extraction from clean PDF text.
                </p>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto px-4 pt-4 no-scrollbar">
        <div className="mx-auto max-w-3xl space-y-6 pb-20">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-10 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-600/10 border border-blue-500/30 text-blue-500 mb-4 animate-pulse">
                <Sparkles className="h-6 w-6" />
              </div>
              <h2 className="text-xl font-bold text-slate-200">Welcome to Project Nexus</h2>
              <p className="mt-2 text-sm text-slate-500 max-w-xs">
                Ask anything about your research documents. I'll search across the knowledge base and synthesize an answer.
              </p>
            </div>
          ) : (
            messages.map((msg, idx) => (
              <MessageBubble 
                key={idx} 
                role={msg.role} 
                content={msg.content} 
                messageId={msg.id}
                feedback={msg.feedback}
                metrics={msg.metrics}
                agentSteps={msg.agentSteps}
                onCitationClick={(id: string | number) => {
                   document.getElementById(`citation-${id}`)?.scrollIntoView({ behavior: 'smooth' });
                }}
                onFeedback={handleFeedback}
              />
            ))
          )}
          {isLoading && messages[messages.length - 1].content === "" && (
            <div className="flex items-center gap-3 text-slate-400">
               <Loader2 className="h-4 w-4 animate-spin text-blue-400" />
               <span className="text-xs italic tracking-wide">Orchestrating search agents...</span>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      <div className="p-4 bg-gradient-to-t from-slate-950/80 to-transparent">
        <div className="mx-auto max-w-3xl relative">
          <div className="absolute -top-12 left-0 right-0 h-10 bg-gradient-to-t from-slate-950 to-transparent pointer-events-none"></div>
          <div className="flex items-center gap-2 rounded-2xl border border-slate-700 bg-slate-900/60 p-2 pl-4 pr-1.5 backdrop-blur-md shadow-lg transition-all focus-within:border-blue-500/50 focus-within:ring-2 focus-within:ring-blue-500/20">
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSend()}
              placeholder="Ask a question..."
              className="flex-1 border-none bg-transparent text-sm text-slate-200 focus-visible:ring-0 placeholder:text-slate-500"
            />
            {isLoading ? (
              <Button 
                onClick={handleStop}
                variant="ghost"
                className="h-9 w-9 bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 rounded-xl"
              >
                <StopCircle className="h-4 w-4" />
              </Button>
            ) : (
              <Button 
                onClick={handleSend}
                className="h-9 w-9 bg-blue-600 hover:bg-blue-500 text-white rounded-xl shadow-md transition-all active:scale-95"
                disabled={!input.trim()}
              >
                <Send className="h-4 w-4" />
              </Button>
            )}
          </div>
          <p className="mt-2 text-[10px] text-center text-slate-600 font-medium">
             Press <kbd className="rounded bg-slate-800 px-1 py-0.5 text-[9px]">Enter</kbd> to send • Nexus v0.1.0
          </p>
        </div>
      </div>
    </div>
  );
}
