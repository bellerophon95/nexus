import React from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { FileText, BookOpen, Tag } from "lucide-react";

interface CitationCardProps {
  id: number;
  title?: string;
  header?: string;
  text: string;
  metadata?: any;
}

export function CitationCard({ id, title, header, text, metadata }: CitationCardProps) {
  // Use official title first, fall back to doc_type or 'Document'
  const displayTitle = title || metadata?.title || metadata?.doc_type || "Document";
  const topic = metadata?.topics?.[0] || "General";

  return (
    <Card className="mb-4 overflow-hidden border-slate-700 bg-slate-900/50 backdrop-blur-md transition-all hover:bg-slate-900/80 group">
      <CardHeader className="p-3 pb-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="flex items-center gap-1 border-blue-500/50 text-blue-400 bg-blue-500/5">
              <BookOpen className="h-3 w-3" />
              Source {id}
            </Badge>
          </div>
          <Badge variant="secondary" className="text-[10px] uppercase tracking-wider bg-slate-800 text-slate-400 border-none">
            {topic}
          </Badge>
        </div>
        <div className="mt-2 flex items-center gap-2">
           <FileText className="h-3 w-3 text-slate-500" />
           <span className="text-[11px] font-bold text-slate-400 uppercase tracking-tighter truncate max-w-[200px]">
              {displayTitle}
           </span>
        </div>
        <CardTitle className="mt-1 text-sm font-black text-slate-200 line-clamp-1 italic tracking-tight group-hover:text-white transition-colors">
          {header || `Reference Segment`}
        </CardTitle>
      </CardHeader>
      <CardContent className="p-3">
        <div className="relative">
          <div className="absolute -left-1 top-0 bottom-0 w-[2px] bg-blue-500/30 rounded-full" />
          <p className="text-xs leading-relaxed text-slate-400 pl-3 line-clamp-4 italic">
            "{text}"
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
