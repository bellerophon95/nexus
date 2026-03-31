import React, { useEffect, useState } from "react";
import { MessageSquare, Clock, Search, Plus, Trash2, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { Separator } from "@/components/ui/separator";
import { API_BASE_URL } from "@/lib/constants";
import { getAuthHeaders } from "@/lib/auth";

interface Conversation {
  id: string;
  title: string;
  updated_at: string;
}

interface SidebarHistoryProps {
  currentConversationId: string | null;
  onSelectConversation: (id: string) => void;
  onNewChat: () => void;
  isOpen: boolean;
  refreshTrigger?: number;
}

export function SidebarHistory({ 
  currentConversationId, 
  onSelectConversation, 
  onNewChat,
  isOpen,
  refreshTrigger = 0
}: SidebarHistoryProps) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const fetchConversations = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/conversations`, {
        headers: getAuthHeaders()
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      setConversations(data.conversations || []);
    } catch (err) {
      console.error("Failed to fetch conversations:", err);
      // Gracefully handle error state
      setConversations([]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchConversations();
  }, [refreshTrigger]);

  const filteredConversations = conversations.filter(c => 
    c.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/conversations/${id}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      });
      
      if (response.ok) {
        setConversations(prev => prev.filter(c => c.id !== id));
        if (id === currentConversationId) {
          onNewChat();
        }
      } else {
        const error = await response.json();
        alert(`Failed to delete: ${error.detail || 'Unknown error'}`);
      }
    } catch (err) {
      console.error("Delete failed:", err);
      alert("Network error while deleting thread.");
    }
  };

  if (!isOpen) return null;

  return (
    <div className="flex flex-col h-full overflow-hidden animate-in fade-in slide-in-from-left-4 duration-300">
      <div className="p-3">
        <button
          onClick={onNewChat}
          className="flex w-full items-center gap-2 rounded-xl bg-blue-600 px-3 py-2.5 text-xs font-bold text-white shadow-lg shadow-blue-500/20 transition-all hover:bg-blue-500 hover:scale-[1.02] active:scale-95"
        >
          <Plus className="h-4 w-4" />
          <span>New Nexus Thread</span>
        </button>
      </div>

      <div className="px-3 mb-2">
        <div className="relative group">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-500 transition-colors group-focus-within:text-blue-400" />
          <input
            type="text"
            placeholder="Search threads..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-lg border border-slate-800 bg-slate-950/50 py-2 pl-8 pr-3 text-[11px] text-slate-200 placeholder:text-slate-600 focus:border-blue-500/50 focus:outline-none focus:ring-1 focus:ring-blue-500/20 transition-all"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-2 space-y-1 no-scrollbar">
        <div className="pt-2 pb-1 px-3">
          <span className="text-[10px] font-bold uppercase tracking-widest text-slate-500 italic">Recent Threads</span>
        </div>

        {isLoading && conversations.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-8 space-y-2 opacity-50">
             <Clock className="h-5 w-5 text-slate-600 animate-spin" />
             <span className="text-[10px] text-slate-500 font-medium tracking-tight">Syncing history...</span>
          </div>
        ) : filteredConversations.length === 0 ? (
          <div className="p-6 text-center">
             <p className="text-[10px] text-slate-600 italic">No threads found</p>
          </div>
        ) : (
          filteredConversations.map((conv) => (
            <div
              key={conv.id}
              onClick={() => onSelectConversation(conv.id)}
              className={cn(
                "group flex w-full flex-col gap-1 rounded-lg px-3 py-2 text-left transition-all relative overflow-hidden cursor-pointer",
                currentConversationId === conv.id
                  ? "bg-slate-800 text-white ring-1 ring-slate-700/50"
                  : "text-slate-400 hover:bg-slate-800/40 hover:text-slate-200"
              )}
            >
              <div className="flex items-center justify-between w-full">
                <span className="text-[12px] font-medium leading-tight truncate pr-6">
                  {conv.title}
                </span>
                <div className="flex items-center gap-1">
                   <button
                     onClick={(e) => handleDelete(e, conv.id)}
                     className="p-1.5 rounded-md hover:bg-red-500/20 hover:text-red-400 transition-all opacity-0 group-hover:opacity-100 focus:opacity-100"
                     title="Delete Thread"
                   >
                     <Trash2 className="h-3 w-3" />
                   </button>
                   <ChevronRight className={cn(
                     "h-3 w-3 transition-transform duration-300 opacity-0 group-hover:opacity-100",
                     currentConversationId === conv.id && "text-blue-500 opacity-100"
                   )} />
                </div>
              </div>
              <div className="flex items-center gap-1.5 text-[9px] text-slate-500 font-medium">
                <Clock className="h-2.5 w-2.5" />
                <span>{new Date(conv.updated_at).toLocaleDateString()}</span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
