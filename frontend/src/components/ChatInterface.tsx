import React, { useState, useRef, useEffect } from "react";
import { Send, Loader2, Sparkles, User, StopCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MessageBubble } from "./MessageBubble";
import { cn } from "@/lib/utils";
import { API_BASE_URL } from "@/lib/constants";

export interface Message {
  id?: string;
  role: "user" | "assistant";
  content: string;
  citations?: any[];
  feedback?: number;
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
      setMessages(initialMessages);
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
    let url = `${API_BASE_URL}/api/query?q=${encodeURIComponent(input)}`;
    if (conversationId) {
      url += `&conversation_id=${conversationId}`;
    }
    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

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
        } else if (data.type === "activity") {
          onActivity?.(data);
        } else if (data.type === "metrics") {
          onMetricsUpdate?.(data);
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
        headers: { "Content-Type": "application/json" },
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
                onCitationClick={(id) => {
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
