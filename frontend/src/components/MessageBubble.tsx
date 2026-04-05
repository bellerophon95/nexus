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
  Loader2,
  Fingerprint,
  FileSearch,
  MessageSquare,
  ShieldQuestion
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { API_BASE_URL } from "@/lib/constants";
import { getAuthHeaders } from "@/lib/auth";

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
    // Deep Metrics
    judge_correctness?: number;
    judge_completeness?: number;
    judge_conciseness?: number;
    judge_citation_quality?: number;
    ragas_context_precision?: number;
    ragas_answer_relevancy?: number;
  };
  agentSteps?: {
    agent: string;
    tool: string;
    status: "running" | "completed" | "error";
  }[];
  onCitationClick?: (id: number) => void;
  onFeedback?: (messageId: string, score: number) => void;
  onTriggerEval?: (messageId: string) => void;
  onPromote?: (messageId: string) => void;
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
  onTriggerEval,
  onPromote,
  onSelect,
  isSelected
}: MessageBubbleProps) {
  const isUser = role.toLowerCase() === "user";
  const [showTrace, setShowTrace] = React.useState(false);
  const [showAudit, setShowAudit] = React.useState(false);
  const [evalLogs, setEvalLogs] = React.useState<any[]>([]);
  const [isLoadingAudit, setIsLoadingAudit] = React.useState(false);
  const [isPromoting, setIsPromoting] = React.useState(false);
  const [isPromoted, setIsPromoted] = React.useState(false);
  const [isEvalTriggered, setIsEvalTriggered] = React.useState(false);

  const fetchAuditLogs = async () => {
    if (!messageId || evalLogs.length > 0) {
      setShowAudit(!showAudit);
      return;
    }

    setIsLoadingAudit(true);
    setShowAudit(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/evaluation/logs/${messageId}`, {
        headers: getAuthHeaders()
      });
      if (response.ok) {
        const data = await response.json();
        setEvalLogs(data);
      }
    } catch (err) {
      console.error("Failed to fetch audit logs:", err);
    } finally {
      setIsLoadingAudit(false);
    }
  };

  const handlePromote = async () => {
    if (!messageId || isPromoted) return;
    setIsPromoting(true);
    try {
       const response = await fetch(`${API_BASE_URL}/api/evaluation/golden`, {
         method: 'POST',
         headers: {
           ...getAuthHeaders(),
           'Content-Type': 'application/json'
         },
         body: JSON.stringify({ message_id: messageId, tier: "Production Feed" })
       });
       if (response.ok) {
         setIsPromoted(true);
         onPromote?.(messageId);
         // Reset after 3s
         setTimeout(() => setIsPromoted(false), 3000);
       }
    } catch (err) {
      console.error("Failed to promote to golden set:", err);
    } finally {
      setIsPromoting(false);
    }
  };

  const handleTriggerEval = async () => {
    if (!messageId || isEvalTriggered) return;
    setIsEvalTriggered(true);
    try {
      if (onTriggerEval) {
        onTriggerEval(messageId);
      } else {
        // Fallback direct call if prop not provided
        const response = await fetch(`${API_BASE_URL}/api/evaluation/trigger`, {
          method: 'POST',
          headers: {
            ...getAuthHeaders(),
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ message_id: messageId })
        });
        if (!response.ok) throw new Error("Failed to trigger eval");
      }
      // Reset after 3s
      setTimeout(() => setIsEvalTriggered(false), 3000);
    } catch (err) {
      console.error("Failed to trigger eval:", err);
      setIsEvalTriggered(false);
    }
  };

  // Helper to format scores
  const formatScore = (score?: number) => {
    if (score === undefined || score === null) return "N/A";
    return `${(score * 100).toFixed(0)}%`;
  };

  const formatRawScore = (score?: number) => {
    if (score === undefined || score === null) return "N/A";
    return `${score.toFixed(1)}/5`;
  };

  const getScoreColor = (score?: number) => {
    if (score === undefined || score === null) return "text-slate-500";
    if (score > 4 || score > 0.8) return "text-emerald-400";
    if (score > 2.5 || score > 0.5) return "text-yellow-400";
    return "text-rose-400";
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

              {/* Feedback & Tools */}
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

                  <button
                    onClick={() => handlePromote()}
                    disabled={isPromoting || isPromoted}
                    className={cn(
                      "flex items-center gap-1.5 px-2 py-1 rounded-md text-[9px] font-black uppercase tracking-tighter transition-all ml-2",
                      isPromoted 
                        ? "bg-emerald-500/20 border-emerald-500/30 text-emerald-400"
                        : "bg-amber-500/10 border-amber-500/20 text-amber-400 hover:bg-amber-500/20"
                    )}
                  >
                    {isPromoting ? <Loader2 className="h-2.5 w-2.5 animate-spin" /> : 
                     isPromoted ? <ShieldCheck className="h-2.5 w-2.5" /> :
                     <Target className="h-2.5 w-2.5" />}
                    {isPromoted ? "Promoted" : "Promote to Golden"}
                  </button>

                  <button
                    onClick={() => handleTriggerEval()}
                    disabled={isEvalTriggered}
                    className={cn(
                      "flex items-center gap-1.5 px-2 py-1 rounded-md text-[9px] font-black uppercase tracking-tighter transition-all ml-1",
                      isEvalTriggered
                        ? "bg-emerald-500/20 border-emerald-500/30 text-emerald-400"
                        : "bg-blue-500/10 border-blue-500/20 text-blue-400 hover:bg-blue-500/20"
                    )}
                  >
                    {isEvalTriggered ? <ShieldCheck className="h-2.5 w-2.5" /> : <Activity className="h-2.5 w-2.5" />}
                    {isEvalTriggered ? "Triggered" : "Deep Eval"}
                  </button>

                  <button
                    onClick={fetchAuditLogs}
                    className={cn(
                      "flex items-center gap-1.5 px-2 py-1 rounded-md text-[9px] font-black uppercase tracking-tighter transition-all ml-1",
                      showAudit 
                        ? "bg-purple-500/20 text-purple-400 ring-1 ring-purple-500/30" 
                        : "bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-slate-200"
                    )}
                  >
                    <FileSearch className="h-2.5 w-2.5" />
                    Audit Log
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

                {/* LLM Judge Expanded metrics */}
                {metrics.judge_correctness !== undefined && (
                  <div className="flex flex-col gap-2 p-2 rounded-lg bg-slate-950/30 col-span-2 border border-blue-500/10">
                    <div className="flex items-center gap-2 mb-1">
                      <ShieldCheck className={cn("h-3 w-3", getScoreColor(metrics.judge_correctness))} />
                      <span className="text-[9px] uppercase font-black tracking-widest text-slate-500">LLM Judge Cluster</span>
                    </div>
                    <div className="grid grid-cols-2 gap-y-2 gap-x-4">
                       <div className="flex items-center justify-between">
                         <span className="text-[9px] font-bold text-slate-500 uppercase">Correctness</span>
                         <span className={cn("text-[10px] font-mono font-black", getScoreColor(metrics.judge_correctness))}>
                           {formatRawScore(metrics.judge_correctness)}
                         </span>
                       </div>
                       <div className="flex items-center justify-between">
                         <span className="text-[9px] font-bold text-slate-500 uppercase">Completeness</span>
                         <span className={cn("text-[10px] font-mono font-black", getScoreColor(metrics.judge_completeness))}>
                           {formatRawScore(metrics.judge_completeness)}
                         </span>
                       </div>
                       <div className="flex items-center justify-between">
                         <span className="text-[9px] font-bold text-slate-500 uppercase">Conciseness</span>
                         <span className={cn("text-[10px] font-mono font-black", getScoreColor(metrics.judge_conciseness))}>
                           {formatRawScore(metrics.judge_conciseness)}
                         </span>
                       </div>
                       <div className="flex items-center justify-between border-l border-slate-800 pl-4">
                         <span className="text-[9px] font-bold text-slate-500 uppercase">Citation Q</span>
                         <span className={cn("text-[10px] font-mono font-black", getScoreColor(metrics.judge_citation_quality))}>
                           {formatRawScore(metrics.judge_citation_quality)}
                         </span>
                       </div>
                    </div>
                  </div>
                )}

                {/* RAG Scrutiny */}
                {metrics.ragas_context_precision !== undefined && (
                   <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-slate-950/30 col-span-2 border border-emerald-500/10">
                    <Fingerprint className={cn("h-3 w-3", getScoreColor(metrics.ragas_context_precision))} />
                    <div className="flex flex-col flex-1">
                      <span className="text-[9px] uppercase font-bold text-slate-600 leading-none italic">Scientific (Ragas)</span>
                      <div className="flex items-center justify-between">
                         <span className={cn("text-[11px] font-mono font-black", getScoreColor(metrics.ragas_context_precision))}>
                           CONTEXT PREC: {formatScore(metrics.ragas_context_precision)}
                         </span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Audit Log Content */}
            {showAudit && (
              <div className="mt-2 space-y-3 p-4 rounded-xl bg-slate-950/60 border border-slate-800/80 backdrop-blur-xl animate-in fade-in slide-in-from-top-4 duration-500">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                     <ShieldQuestion className="h-4 w-4 text-purple-400" />
                     <span className="text-[11px] font-black uppercase tracking-widest text-slate-100 italic">Audit Reasoning Cluster</span>
                  </div>
                  {isLoadingAudit && <Loader2 className="h-3 w-3 animate-spin text-purple-400" />}
                </div>

                {evalLogs.length === 0 && !isLoadingAudit ? (
                  <div className="p-8 text-center border border-dashed border-slate-800 rounded-lg">
                    <MessageSquare className="h-6 w-6 text-slate-700 mx-auto mb-2" />
                    <p className="text-[10px] text-slate-500 italic">No deep reasoning logs found for this turn yet. Run 'Deep Eval' to generate them.</p>
                  </div>
                ) : (
                  <div className="space-y-4 max-h-[300px] overflow-y-auto pr-2 no-scrollbar">
                    {evalLogs.map((log, idx) => (
                      <div key={idx} className="relative pl-4 border-l-2 border-purple-500/30 py-1">
                        <div className="flex items-center gap-2 mb-1.5">
                           <Badge variant="outline" className="text-[9px] font-black uppercase bg-purple-500/10 border-purple-500/30 text-purple-400 py-0 h-4">
                             {log.evaluator === 'llm_judge' ? 'LLM JUDGE' : 'SCIENTIFIC (RAGAS)'}
                           </Badge>
                           <span className="text-[9px] text-slate-500 font-mono">
                             {new Date(log.created_at).toLocaleTimeString()}
                           </span>
                        </div>
                        <p className="text-[13px] leading-relaxed text-slate-300 font-medium whitespace-pre-wrap selection:bg-purple-500/30">
                          {log.reasoning || "No detailed reasoning provided."}
                        </p>
                        {log.unsupported_claims && log.unsupported_claims.length > 0 && (
                          <div className="mt-3 space-y-1.5">
                             <span className="text-[10px] font-bold text-rose-400 uppercase tracking-widest flex items-center gap-1.5">
                               <AlertTriangle className="h-3 w-3" /> Hallucination Candidates
                             </span>
                             <ul className="text-[11px] text-rose-300/70 space-y-1 italic bg-rose-500/5 p-2 rounded-lg border border-rose-500/10">
                                {log.unsupported_claims.map((claim: string, i: number) => (
                                  <li key={i}>• {claim}</li>
                                ))}
                             </ul>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
