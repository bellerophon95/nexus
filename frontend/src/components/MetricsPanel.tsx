import React from "react";
import { 
  Zap, 
  ShieldCheck, 
  AlertTriangle, 
  Timer, 
  Coins, 
  Activity,
  BarChart3,
  TrendingDown,
  TrendingUp,
  Fingerprint
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

export interface ChatMetrics {
  hallucinationScore?: number; // 0-1
  relevanceScore?: number; // 0-1
  guardrailStatus: "passed" | "warning" | "failed";
  tier: "direct" | "rag" | "agentic" | "general" | "initializing";
  latency: number; // ms
  cost: number; // USD
  tokens: number;
  // Deep Metrics (Async)
  judge_correctness?: number; // 1-5
  judge_completeness?: number; // 1-5
  judge_conciseness?: number; // 1-5
  ragas_context_precision?: number; // 0-1
  ragas_answer_relevancy?: number; // 0-1
}

interface MetricsPanelProps {
  metrics: ChatMetrics | null;
  isLoading?: boolean;
}

export function MetricsPanel({ metrics, isLoading }: MetricsPanelProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 p-4 border-t border-slate-700 bg-slate-900/60 backdrop-blur-lg">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="flex items-start gap-2.5 animate-pulse">
            <div className="mt-0.5 rounded-lg bg-slate-800/80 p-1.5 h-8 w-8" />
            <div className="space-y-1.5 flex-1">
              <div className="h-2 w-16 bg-slate-800 rounded" />
              <div className="h-3 w-12 bg-slate-700/50 rounded" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (!metrics) {
    return (
      <div className="flex flex-col items-center justify-center p-8 text-center border-t border-slate-800 bg-slate-900/40 backdrop-blur-md">
        <Activity className="h-6 w-6 text-slate-700 mb-2" />
        <p className="text-xs text-slate-500 italic">No real-time metrics available</p>
      </div>
    );
  }

  const getScoreColor = (score: number) => {
    if (score > 4 || score > 0.8) return "text-emerald-400";
    if (score > 2.5 || score > 0.5) return "text-yellow-400";
    return "text-rose-400";
  };

  const formatRawScore = (score?: number) => {
    if (score === undefined || score === null) return "N/A";
    return `${score.toFixed(1)}/5`;
  };

  const getGuardrailBadge = (status: string) => {
    switch (status) {
      case "passed":
        return <Badge className="bg-emerald-500/10 text-emerald-400 border-emerald-500/30 font-bold tracking-wider">PASSED</Badge>;
      case "warning":
        return <Badge className="bg-yellow-500/10 text-yellow-400 border-yellow-500/30 font-bold tracking-wider">WARNING</Badge>;
      case "failed":
        return <Badge className="bg-rose-500/10 text-rose-400 border-rose-500/30 font-bold tracking-wider">FAILED</Badge>;
      default:
        return <Badge className="bg-rose-500/10 text-rose-400 border-rose-500/30 font-bold tracking-wider">FAILED</Badge>;
    }
  };

  return (
    <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 p-4 border-t border-slate-700 bg-slate-900/60 backdrop-blur-lg">
      <MetricItem 
        icon={<Fingerprint className="h-4 w-4" />} 
        label="Faithfulness" 
        value={
          typeof metrics.hallucinationScore === 'number'
            ? `${((1 - metrics.hallucinationScore) * 100).toFixed(0)}%`
            : metrics.tier === 'general'
            ? "General KB"
            : "Eval N/A"
        }
        color={
          typeof metrics.hallucinationScore === 'number'
            ? getScoreColor(1 - metrics.hallucinationScore)
            : "text-slate-500"
        }
      />

      <MetricItem 
        icon={<BarChart3 className="h-4 w-4" />} 
        label="Relevance" 
        value={
          typeof metrics.relevanceScore === 'number'
            ? `${(metrics.relevanceScore * 100).toFixed(0)}%`
            : metrics.tier === 'general'
            ? "General KB"
            : "Eval N/A"
        }
        color={
          typeof metrics.relevanceScore === 'number'
            ? getScoreColor(metrics.relevanceScore)
            : "text-slate-500"
        }
      />
      
      <MetricItem 
        icon={<ShieldCheck className="h-4 w-4" />} 
        label="Guardrails" 
        value={getGuardrailBadge(metrics.guardrailStatus)}
      />

      <MetricItem 
        icon={<Zap className="h-4 w-4" />} 
        label="Tier" 
        value={metrics.tier.toUpperCase()}
        color="text-blue-400"
      />

      {metrics.judge_correctness !== undefined && (
        <MetricItem 
          icon={<ShieldCheck className="h-4 w-4" />} 
          label="Correctness" 
          value={formatRawScore(metrics.judge_correctness)}
          color={getScoreColor(metrics.judge_correctness)}
        />
      )}

      {metrics.ragas_context_precision !== undefined && (
        <MetricItem 
          icon={<Activity className="h-4 w-4" />} 
          label="RAG Context" 
          value={`${(metrics.ragas_context_precision * 100).toFixed(0)}%`}
          color={getScoreColor(metrics.ragas_context_precision)}
        />
      )}

      <MetricItem 
        icon={<Timer className="h-4 w-4" />} 
        label="Latency" 
        value={`${metrics.latency.toFixed(0)} ms`}
        color="text-slate-200"
      />
    </div>
  );
}

function MetricItem({ icon, label, value, color }: { icon: React.ReactNode, label: string, value: React.ReactNode, color?: string }) {
  return (
    <div className="flex items-start gap-2.5">
      <div className="mt-0.5 rounded-lg bg-slate-800/50 p-1.5 text-slate-400">
        {icon}
      </div>
      <div className="space-y-0.5 overflow-hidden">
        <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">{label}</p>
        <div className={cn("text-xs font-semibold tabular-nums", color || "text-slate-200")}>
          {value}
        </div>
      </div>
    </div>
  );
}
