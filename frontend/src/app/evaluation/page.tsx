"use client";

import React, { useEffect, useState } from "react";
import { 
  BarChart3, 
  Activity, 
  Zap, 
  ShieldCheck, 
  AlertTriangle, 
  Target, 
  History,
  Play,
  ArrowUpRight,
  TrendingDown,
  TrendingUp,
  Clock,
  Fingerprint
} from "lucide-react";
import { cn } from "@/lib/utils";
import { API_BASE_URL } from "@/lib/constants";
import { getAuthHeaders } from "@/lib/auth";
import { Badge } from "@/components/ui/badge";

interface EvalStats {
  avg_scores: Record<string, number>;
  total_evals_last_100: number;
}

interface EvalAlert {
  id: string;
  message_id: string;
  metric_name: string;
  metric_value: number;
  threshold: number;
  created_at: string;
  messages?: {
    content: string;
    conversation_id: string;
  };
}

export default function EvaluationDashboard() {
  const [stats, setStats] = useState<EvalStats | null>(null);
  const [alerts, setAlerts] = useState<EvalAlert[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRunningSuite, setIsRunningSuite] = useState(false);
  const [suiteStatus, setSuiteStatus] = useState<string | null>(null);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    setIsLoading(true);
    try {
      const [statsRes, alertsRes] = await Promise.all([
        fetch(`${API_BASE_URL}/api/evaluation/stats`, { headers: getAuthHeaders() }),
        fetch(`${API_BASE_URL}/api/evaluation/alerts`, { headers: getAuthHeaders() })
      ]);

      if (statsRes.ok && alertsRes.ok) {
        const statsData = await statsRes.json();
        const alertsData = await alertsRes.json();
        setStats(statsData);
        setAlerts(alertsData);
      }
    } catch (err) {
      console.error("Failed to fetch dashboard data:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRunSuite = async () => {
    setIsRunningSuite(true);
    setSuiteStatus("Initializing Suite...");
    try {
      const response = await fetch(`${API_BASE_URL}/api/evaluation/run-suite`, {
        method: 'POST',
        headers: getAuthHeaders()
      });
      if (response.ok) {
        setSuiteStatus("Suite Triggered Successfully");
        setTimeout(() => setSuiteStatus(null), 5000);
      }
    } catch (err) {
      console.error("Failed to run suite:", err);
      setSuiteStatus("Failed to start suite");
    } finally {
      setIsRunningSuite(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center bg-slate-950">
        <div className="flex flex-col items-center gap-4">
          <Activity className="h-10 w-10 animate-spin text-blue-500" />
          <p className="text-slate-500 font-black uppercase tracking-widest text-[10px]">Syncing Observability Data...</p>
        </div>
      </div>
    );
  }

  // Helper to format scores
  const getAvg = (name: string) => stats?.avg_scores[name] ?? 0;

  return (
    <div className="flex-1 overflow-y-auto bg-slate-950 p-8 scrollbar-hide">
      <div className="max-w-6xl mx-auto space-y-8 pb-12">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-black text-white uppercase italic tracking-tighter flex items-center gap-3">
              <ShieldCheck className="h-8 w-8 text-blue-500" />
              Evaluation <span className="text-blue-500/80">Observability</span>
            </h1>
            <p className="text-slate-500 font-medium text-sm mt-1">Real-time LLM performance tracking & threshold monitoring</p>
          </div>
          <div className="flex flex-col items-end gap-2">
            <button 
              onClick={handleRunSuite}
              disabled={isRunningSuite}
              className={cn(
                "flex items-center gap-2.5 px-6 py-3 rounded-xl font-black uppercase tracking-widest text-xs transition-all shadow-lg active:scale-95 disabled:opacity-50",
                suiteStatus?.includes("Success") ? "bg-emerald-600 text-white shadow-emerald-500/20" : "bg-blue-600 hover:bg-blue-500 text-white shadow-blue-500/20"
              )}
            >
              {isRunningSuite ? <Activity className="h-4 w-4 animate-spin" /> : 
               suiteStatus?.includes("Success") ? <ShieldCheck className="h-4 w-4" /> :
               <Play className="h-4 w-4 fill-white" />}
              {suiteStatus || "Run Golden Suite"}
            </button>
            {suiteStatus && (
               <span className="text-[9px] font-black uppercase tracking-widest text-blue-400 animate-pulse">Background Process Active</span>
            )}
          </div>
        </div>

        {/* Primary Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <StatCard 
            label="Avg Correctness" 
            value={`${(getAvg('judge_correctness') || (1 - getAvg('hallucinationScore')) * 5).toFixed(1)}/5`}
            icon={<ShieldCheck className="h-5 w-5 text-emerald-400" />}
            trend={<TrendingUp className="h-4 w-4 text-emerald-400" />}
            color="emerald"
          />
          <StatCard 
            label="Avg Completeness" 
            value={`${(getAvg('judge_completeness') || getAvg('relevanceScore') * 5).toFixed(1)}/5`}
            icon={<Target className="h-5 w-5 text-blue-400" />}
            trend={<TrendingUp className="h-4 w-4 text-emerald-400" />}
            color="blue"
          />
          <StatCard 
            label="Avg Citation Q" 
            value={`${(getAvg('judge_citation_quality') || 0).toFixed(1)}/5`}
            icon={<BarChart3 className="h-5 w-5 text-purple-400" />}
            trend={null}
            color="purple"
          />
          <StatCard 
            label="Violations" 
            value={alerts.length}
            icon={<AlertTriangle className="h-5 w-5 text-rose-400" />}
            trend={alerts.length > 5 ? <TrendingUp className="h-4 w-4 text-rose-400" /> : null}
            color="rose"
          />
        </div>

        {/* Secondary Detailed Metrics Segment */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
           <DetailedMetric 
             label="Response Latency" 
             value={`${getAvg('latency').toFixed(0)}ms`}
             subtext="Avg Turn-around"
             icon={<Zap className="h-4 w-4 text-amber-400" />}
           />
           <DetailedMetric 
             label="Conciseness" 
             value={(getAvg('judge_conciseness') || 0).toFixed(1)}
             subtext="Efficiency Score"
             icon={<Activity className="h-4 w-4 text-slate-400" />}
           />
           <DetailedMetric 
             label="Scientific Alpha" 
             value={`${(getAvg('ragas_context_precision') * 100).toFixed(1)}%`}
             subtext="Context Precision"
             icon={<Fingerprint className="h-4 w-4 text-blue-400" />}
           />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Alerts List */}
          <div className="lg:col-span-2 space-y-4">
            <h2 className="text-xs font-black uppercase tracking-[0.3em] text-slate-500 flex items-center gap-2">
              <AlertTriangle className="h-3 w-3" /> Recent Performance Alerts
            </h2>
            <div className="rounded-2xl border border-slate-800 bg-slate-900/40 backdrop-blur-xl overflow-hidden">
              {alerts.length === 0 ? (
                <div className="p-12 text-center">
                  <ShieldCheck className="h-10 w-10 text-slate-800 mx-auto mb-4" />
                  <p className="text-slate-500 font-medium">All systems within normal thresholds</p>
                </div>
              ) : (
                <div className="divide-y divide-slate-800">
                  {alerts.map((alert) => (
                    <div key={alert.id} className="p-4 flex items-center justify-between hover:bg-slate-800/30 transition-colors group">
                      <div className="flex items-center gap-4">
                        <div className="h-10 w-10 rounded-xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center">
                          <TrendingDown className="h-5 w-5 text-rose-400" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-[11px] font-black uppercase tracking-wider text-slate-100 italic">{alert.metric_name}</span>
                            <Badge variant="outline" className="text-[9px] border-rose-500/30 bg-rose-500/10 text-rose-400">Violation</Badge>
                          </div>
                          <p className="text-[10px] text-slate-500 mt-0.5">
                            Value: <span className="text-rose-400 font-mono">{(alert.metric_value * 100).toFixed(0)}%</span> (Threshold: {alert.threshold * 100}%)
                          </p>
                        </div>
                      </div>
                      <div className="flex flex-col items-end gap-1">
                        <span className="text-[9px] font-mono text-slate-600">{new Date(alert.created_at).toLocaleString()}</span>
                        <button className="text-[9px] font-black uppercase text-blue-400 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
                          View Turn <ArrowUpRight className="h-2 w-2" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Golden Dataset Health */}
          <div className="space-y-4">
             <h2 className="text-xs font-black uppercase tracking-[0.3em] text-slate-500 flex items-center gap-2">
              <Fingerprint className="h-3 w-3" /> Dataset Integrity
            </h2>
            <div className="rounded-2xl border border-slate-800 bg-slate-900/40 backdrop-blur-xl p-6 space-y-6">
                <div className="space-y-2">
                  <div className="flex justify-between items-end">
                    <span className="text-[10px] font-black uppercase text-slate-400">Golden Coverage</span>
                    <span className="text-lg font-black text-white italic">84%</span>
                  </div>
                  <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                    <div className="h-full bg-blue-500 w-[84%] shadow-[0_0_10px_rgba(59,130,246,0.5)]" />
                  </div>
                </div>

                <div className="space-y-3">
                   <div className="flex items-center justify-between p-3 rounded-xl bg-slate-950/40 border border-slate-800/50">
                      <div className="flex items-center gap-3">
                         <Target className="h-4 w-4 text-emerald-400" />
                        <span className="text-[10px] font-bold text-slate-300">Golden Samples</span>
                      </div>
                      <span className="text-xs font-mono font-black text-slate-100">124</span>
                   </div>
                   <div className="flex items-center justify-between p-3 rounded-xl bg-slate-950/40 border border-slate-800/50">
                      <div className="flex items-center gap-3">
                         <History className="h-4 w-4 text-blue-400" />
                        <span className="text-[10px] font-bold text-slate-300">Last Evaluation</span>
                      </div>
                      <span className="text-xs font-mono font-black text-slate-100">2h ago</span>
                   </div>
                   <div className="flex items-center justify-between p-3 rounded-xl bg-slate-950/40 border border-slate-800/50">
                      <div className="flex items-center gap-3">
                         <Clock className="h-4 w-4 text-amber-400" />
                        <span className="text-[10px] font-bold text-slate-300">Avg Eval Time</span>
                      </div>
                      <span className="text-xs font-mono font-black text-slate-100">42.1s</span>
                   </div>
                </div>

                <div className="pt-4 border-t border-slate-800/50">
                  <p className="text-[10px] text-slate-600 italic leading-relaxed">
                    Promotion of production turns to the golden set helps improve accuracy over time by providing more ground truth samples for evaluation.
                  </p>
                </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function DetailedMetric({ label, value, subtext, icon }: any) {
  return (
    <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/20 backdrop-blur-sm flex items-center gap-4 group hover:border-slate-700 transition-colors">
      <div className="p-2 rounded-lg bg-slate-950/50 border border-white/5 group-hover:scale-110 transition-transform">
        {icon}
      </div>
      <div>
        <p className="text-[10px] font-black uppercase tracking-widest text-slate-500">{label}</p>
        <div className="flex items-baseline gap-2">
          <h4 className="text-lg font-black text-white italic tracking-tighter">{value}</h4>
          <span className="text-[9px] text-slate-600 font-bold uppercase">{subtext}</span>
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, icon, trend, color }: any) {
  const colorMap: any = {
    emerald: "bg-emerald-500/5 border-emerald-500/20 text-emerald-400 shadow-emerald-500/5",
    blue: "bg-blue-500/5 border-blue-500/20 text-blue-400 shadow-blue-500/5",
    amber: "bg-amber-500/5 border-amber-500/20 text-amber-400 shadow-amber-500/5",
    rose: "bg-rose-500/5 border-rose-500/20 text-rose-400 shadow-rose-500/5",
  };

  return (
    <div className={cn(
      "p-5 rounded-2xl border transition-all duration-300 hover:scale-[1.02] shadow-xl",
      colorMap[color]
    )}>
      <div className="flex justify-between items-start mb-4">
        <div className="p-2 rounded-lg bg-slate-950/50 border border-white/5">
          {icon}
        </div>
        {trend}
      </div>
      <div>
        <p className="text-[10px] font-black uppercase tracking-[0.2em] opacity-60 mb-1">{label}</p>
        <h3 className="text-2xl font-black text-white italic tracking-tighter">{value}</h3>
      </div>
    </div>
  );
}
