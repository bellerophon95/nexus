import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { 
  User, 
  Sparkles, 
  ThumbsUp, 
  ThumbsDown, 
  Activity, 
  Zap, 
  ShieldCheck, 
  ShieldAlert,
  ChevronDown,
  BarChart3,
  Target,
  AlertTriangle,
  Loader2
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

interface MessageBubbleProps {
  role: "user" | "assistant";
  content: string;
  messageId?: string;
  feedback?: number; // 1, -1, or 0
  metrics?: {
    latency?: number;
    tokens?: number;
    cost?: number;
    hallucinationScore?: number;
    relevanceScore?: number;
    guardrailStatus?: string;
    tier?: string;
  };
  agentSteps?: {
    agent: string;
    tool: string;
    status: "running" | "completed" | "error";
  }[];
  onCitationClick?: (id: number) => void;
  onFeedback?: (messageId: string, score: number) => void;
  onSelect?: () => void;
  isSelected?: boolean;
}

export function MessageBubble({ 
  role, 
  content, 
  messageId, 
  feedback = 0,
  metrics,
  agentSteps,
  onCitationClick, 
  onFeedback,
  onSelect,
  isSelected
}: MessageBubbleProps) {
  const isUser = role.toLowerCase() === "user";
  const [showTrace, setShowTrace] = React.useState(false);

  // Helper to format scores
  const formatScore = (score?: number) => {
    if (score === undefined || score === null) return "N/A";
    return `${(score * 100).toFixed(0)}%`;
  };

  return (
    <div
      onClick={onSelect}
      className={cn(
        "group mb-8 flex w-full max-w-3xl gap-4 cursor-pointer transition-all duration-300",
        isUser ? "ml-auto flex-row-reverse" : "mr-auto",
        isSelected && !isUser && "scale-[1.02] -translate-y-1"
      )}
    >
      <div
        className={cn(
          "flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border-2 shadow-sm transition-all duration-300",
          isUser
            ? "border-blue-600/50 bg-blue-600/20 text-blue-400 group-hover:scale-110"
            : "border-emerald-500/30 bg-emerald-500/10 text-emerald-400 group-hover:scale-110"
        )}
      >
        {isUser ? <User className="h-5 w-5" /> : <Sparkles className="h-5 w-5" />}
      </div>

      <div
        className={cn(
          "relative flex-1 space-y-3",
          isUser ? "items-end" : "items-start"
        )}
      >
        {/* Process Map (Visual Graph Steps) */}
        {!isUser && agentSteps && agentSteps.length > 0 && (
          <div className="flex flex-col gap-2 mb-2">
             <div className="flex items-center gap-2 mb-1">
                <div className="flex h-4 w-4 items-center justify-center rounded bg-blue-500/20 text-blue-400">
                  <Activity className="h-2.5 w-2.5" />
                </div>
                <span className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Agent Flow</span>
             </div>
             <div className="flex flex-wrap gap-2">
                {agentSteps.map((step, idx) => {
                  const isRunning = step.status === "running";
                  const isCompleted = step.status === "completed";
                  const isError = step.status === "error";

                  return (
                    <div 
                      key={idx}
                      className={cn(
                        "flex items-center gap-2 px-3 py-1.5 rounded-lg border text-[11px] font-bold transition-all duration-300",
                        isRunning ? "bg-blue-500/10 border-blue-500/40 text-blue-400 animate-pulse" :
                        isCompleted ? "bg-emerald-500/5 border-emerald-500/20 text-emerald-500/70" :
                        isError ? "bg-rose-500/10 border-rose-500/40 text-rose-400" :
                        "bg-slate-800/40 border-slate-700/50 text-slate-500"
                      )}
                    >
                      {isRunning && <Loader2 className="h-3 w-3 animate-spin" />}
                      {isCompleted && <ShieldCheck className="h-3 w-3" />}
                      {isError && <ShieldAlert className="h-3 w-3" />}
                      <span className="opacity-60">{step.agent}:</span>
                      <span>{step.tool}</span>
                    </div>
                  );
                })}
             </div>
          </div>
        )}

        <div
          className={cn(
            "inline-block rounded-2xl px-5 py-3 shadow-lg transition-all duration-300",
            isUser
              ? "bg-gradient-to-br from-blue-600 to-blue-700 text-white"
              : cn(
                  "bg-slate-900/80 text-slate-100 backdrop-blur-xl border border-slate-800/50 hover:border-blue-500/30",
                  isSelected && "border-blue-500/50 bg-blue-500/5 shadow-blue-500/10 ring-1 ring-blue-500/20"
                )
          )}
        >
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              p: ({ node, ...props }) => <p className="mb-3 last:mb-0 leading-relaxed text-[15px] font-medium" {...props} />,
              code: ({ node, ...props }) => (
                <code className="rounded bg-slate-950/80 px-1.5 py-0.5 font-mono text-[13px] text-blue-400 border border-slate-800" {...props} />
              ),
              strong: ({ node, ...props }) => <strong className="font-bold text-blue-300" {...props} />,
              text: ({ node, ...props }: any) => {
                const text = props.children;
                if (typeof text === 'string' && text.includes('[Source')) {
                  const parts = text.split(/(\[Source \d+\])/g);
                  return (
                    <>
                      {parts.map((part, i) => {
                        const match = part.match(/\[Source (\d+)\]/);
                        if (match) {
                          const id = parseInt(match[1]);
                          return (
                            <button
                              key={i}
                              onClick={() => onCitationClick?.(id)}
                              className="mx-1 inline-flex items-center gap-1 rounded bg-blue-500/10 px-2 py-0.5 text-[11px] font-black text-blue-400 border border-blue-500/30 hover:bg-blue-500/20 active:scale-95 transition-all"
                            >
                              CIT {id}
                            </button>
                          );
                        }
                        return part;
                      })}
                    </>
                  );
                }
                return text;
              }
            }}
          >
            {content}
          </ReactMarkdown>
        </div>

        {/* Observability & Meta Row */}
        {!isUser && (
          <div className="flex flex-col gap-2 pt-1">
            <div className="flex items-center gap-3">
              {metrics && (
                <button 
                  onClick={() => setShowTrace(!showTrace)}
                  className={cn(
                    "flex items-center gap-1.5 px-2 py-1 rounded-md text-[10px] font-black uppercase tracking-widest transition-all",
                    showTrace 
                      ? "bg-blue-500/20 text-blue-400 ring-1 ring-blue-500/30" 
                      : "text-slate-500 hover:text-slate-300 hover:bg-slate-800"
                  )}
                >
                  <Activity className="h-3 w-3" />
                  Trace Details
                  <ChevronDown className={cn("h-3 w-3 transition-transform", showTrace && "rotate-180")} />
                </button>
              )}

              {/* Guardrail Status */}
              {metrics?.guardrailStatus && (
                <div className="flex items-center gap-1">
                  {metrics.guardrailStatus === "passed" ? (
                    <Badge variant="outline" className="h-5 px-1.5 gap-1 border-emerald-500/20 bg-emerald-500/5 text-emerald-500/70 text-[9px] font-bold uppercase tracking-tighter">
                      <ShieldCheck className="h-2.5 w-2.5" /> Safety Passed
                    </Badge>
                  ) : (
                    <Badge variant="outline" className="h-5 px-1.5 gap-1 border-rose-500/20 bg-rose-500/5 text-rose-500/70 text-[9px] font-bold uppercase tracking-tighter">
                      <ShieldAlert className="h-2.5 w-2.5" /> Guard Altered
                    </Badge>
                  )}
                </div>
              )}

              {/* Feedback */}
              {messageId && (
                <div className="flex items-center gap-1 ml-auto opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={() => onFeedback?.(messageId, 1)}
                    className={cn(
                      "p-1 rounded-md transition-all hover:bg-emerald-500/10",
                      feedback === 1 ? "text-emerald-400" : "text-slate-600 hover:text-emerald-500/50"
                    )}
                  >
                    <ThumbsUp className="h-3 w-3" />
                  </button>
                  <button
                    onClick={() => onFeedback?.(messageId, -1)}
                    className={cn(
                      "p-1 rounded-md transition-all hover:bg-rose-500/10",
                      feedback === -1 ? "text-rose-400" : "text-slate-600 hover:text-rose-500/50"
                    )}
                  >
                    <ThumbsDown className="h-3 w-3" />
                  </button>
                </div>
              )}
            </div>

            {/* Trace Content */}
            {showTrace && metrics && (
              <div className="grid grid-cols-2 gap-2 p-3 rounded-xl bg-slate-900/40 border border-slate-800/50 backdrop-blur-md animate-in fade-in slide-in-from-top-2 duration-300">
                {/* Latency */}
                <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-slate-950/30">
                  <Zap className="h-3 w-3 text-amber-400" />
                  <div className="flex flex-col">
                    <span className="text-[9px] uppercase font-bold text-slate-600 leading-none">Latency</span>
                    <span className="text-[11px] font-mono font-bold text-slate-300">{metrics.latency?.toFixed(0)}<span className="text-[9px] ml-0.5 opacity-50">ms</span></span>
                  </div>
                </div>

                {/* Tokens/Cost */}
                <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-slate-950/30">
                  <BarChart3 className="h-3 w-3 text-blue-400" />
                  <div className="flex flex-col">
                    <span className="text-[9px] uppercase font-bold text-slate-600 leading-none">Usage</span>
                    <span className="text-[11px] font-mono font-bold text-slate-300">{metrics.tokens}<span className="text-[9px] ml-0.5 opacity-50">tkns</span></span>
                  </div>
                </div>

                {/* Faithfulness */}
                <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-slate-950/30">
                  {metrics.hallucinationScore !== undefined && (metrics.hallucinationScore > 0.3) ? 
                    <AlertTriangle className="h-3 w-3 text-rose-400" /> : 
                    <Target className="h-3 w-3 text-emerald-400" />
                  }
                  <div className="flex flex-col">
                    <span className="text-[9px] uppercase font-bold text-slate-600 leading-none">Grounding</span>
                    <span className={cn(
                      "text-[11px] font-mono font-bold",
                      metrics.hallucinationScore !== undefined && metrics.hallucinationScore > 0.3 ? "text-rose-400" : "text-emerald-400"
                    )}>
                      {formatScore(1 - (metrics.hallucinationScore || 0))}
                    </span>
                  </div>
                </div>

                {/* Relevance */}
                <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-slate-950/30">
                  <Activity className="h-3 w-3 text-purple-400" />
                  <div className="flex flex-col">
                    <span className="text-[9px] uppercase font-bold text-slate-600 leading-none">Relevance</span>
                    <span className="text-[11px] font-mono font-bold text-slate-200">{formatScore(metrics.relevanceScore)}</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
