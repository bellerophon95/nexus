import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { User, Sparkles, Code, ThumbsUp, ThumbsDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

interface MessageBubbleProps {
  role: "user" | "assistant";
  content: string;
  messageId?: string;
  feedback?: number; // 1, -1, or 0
  onCitationClick?: (id: number) => void;
  onFeedback?: (messageId: string, score: number) => void;
}

export function MessageBubble({ 
  role, 
  content, 
  messageId, 
  feedback = 0,
  onCitationClick, 
  onFeedback 
}: MessageBubbleProps) {
  const isUser = role === "user";

  return (
    <div
      className={cn(
        "group mb-6 flex w-full max-w-3xl gap-4",
        isUser ? "ml-auto flex-row-reverse" : "mr-auto"
      )}
    >
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border",
          isUser
            ? "border-blue-500/50 bg-blue-500/10 text-blue-400"
            : "border-emerald-500/50 bg-emerald-500/10 text-emerald-400"
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Sparkles className="h-4 w-4" />}
      </div>

      <div
        className={cn(
          "relative flex-1 overflow-hidden px-1 pt-1",
          isUser ? "text-right" : "text-left"
        )}
      >
        <div
          className={cn(
            "inline-block rounded-2xl px-4 py-2 shadow-sm",
            isUser
              ? "bg-blue-600 text-white"
              : "bg-slate-800/80 text-slate-100 backdrop-blur-sm border border-slate-700/50"
          )}
        >
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              p: ({ node, ...props }) => <p className="mb-2 last:mb-0 leading-relaxed text-sm" {...props} />,
              code: ({ node, ...props }) => (
                <code className="rounded bg-slate-900/50 px-1 font-mono text-xs text-blue-300" {...props} />
              ),
              strong: ({ node, ...props }) => <strong className="font-semibold text-blue-200" {...props} />,
              // Special handling for citations: [Source N]
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
                              className="mx-1 inline-flex items-center gap-0.5 rounded border border-blue-500/30 bg-blue-500/10 px-1.5 py-0.5 text-[10px] font-bold text-blue-400 transition-colors hover:bg-blue-500/20"
                            >
                              REF {id}
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

        {/* Feedback Actions for Assistant */}
        {!isUser && messageId && (
          <div className="mt-2 flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              onClick={() => onFeedback?.(messageId, 1)}
              className={cn(
                "p-1.5 rounded-lg border transition-all hover:scale-105 active:scale-95",
                feedback === 1 
                  ? "bg-emerald-500/20 border-emerald-500/50 text-emerald-400 shadow-[0_0_10px_rgba(16,185,129,0.2)]" 
                  : "bg-slate-800/40 border-slate-700/50 text-slate-500 hover:text-emerald-400 hover:border-emerald-500/30"
              )}
              title="Helpful"
            >
              <ThumbsUp className="h-3 w-3" />
            </button>
            <button
              onClick={() => onFeedback?.(messageId, -1)}
              className={cn(
                "p-1.5 rounded-lg border transition-all hover:scale-105 active:scale-95",
                feedback === -1 
                  ? "bg-rose-500/20 border-rose-500/50 text-rose-400 shadow-[0_0_10px_rgba(244,63,94,0.2)]" 
                  : "bg-slate-800/40 border-slate-700/50 text-slate-500 hover:text-rose-400 hover:border-rose-500/30"
              )}
              title="Not helpful"
            >
              <ThumbsDown className="h-3 w-3" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
