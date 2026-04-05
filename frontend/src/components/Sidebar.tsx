"use client";

import React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { 
  Plus, 
  Settings, 
  Library,
  LayoutDashboard,
  Zap,
  ChevronRight,
  ShieldCheck
} from "lucide-react";
import { cn } from "@/lib/utils";
import { SidebarHistory } from "@/components/SidebarHistory";
import { useAppContext } from "@/context/AppContext";

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { isSidebarOpen, selectedSkills, sessionId, refreshHistoryTrigger } = useAppContext();

  const isChatActive = pathname.startsWith("/chat") || pathname === "/";
  const isDocumentsActive = pathname === "/knowledge/documents";
  const isSkillsActive = pathname === "/knowledge/skills";
  const isSettingsActive = pathname === "/settings";

  const handleNewChat = () => {
    router.push("/chat");
  };

  const handleSelectConversation = (id: string) => {
    router.push(`/chat/${id}`);
  };

  return (
    <aside className={cn(
      "flex flex-col border-r border-slate-800 bg-slate-900/40 backdrop-blur-xl transition-all duration-300",
      isSidebarOpen ? "w-72" : "w-16"
    )}>
      <div className="flex h-16 items-center border-b border-slate-800 px-4">
        <Link href="/" className="flex items-center gap-3 hover:opacity-80 transition-opacity">
          <div className="h-8 w-8 rounded-lg bg-blue-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
             <Zap className="h-5 w-5 text-white fill-white" />
          </div>
          {isSidebarOpen && <span className="text-lg font-black tracking-tight text-white uppercase italic">Nexus AI</span>}
        </Link>
      </div>

      <nav className="flex-1 space-y-1 p-2 overflow-y-auto">
        <SidebarItem 
          href="/chat"
          icon={<LayoutDashboard className="h-4 w-4" />} 
          label="Dashboard" 
          isActive={isChatActive} 
          isOpen={isSidebarOpen}
          badge={selectedSkills.length > 0 ? selectedSkills.length : undefined}
        />

        <SidebarItem 
          href="/evaluation"
          icon={<ShieldCheck className="h-4 w-4" />} 
          label="Monitoring" 
          isActive={pathname === "/evaluation"} 
          isOpen={isSidebarOpen}
        />
        
        {isSidebarOpen && (
          <div className="pt-6 pb-2 px-3">
            <span className="text-[10px] font-bold uppercase tracking-widest text-slate-500 italic">Knowledge Base</span>
          </div>
        )}

        <SidebarItem 
           href="/knowledge/documents"
           icon={<Library className="h-4 w-4" />} 
           label="Document Library" 
           isActive={isDocumentsActive} 
           isOpen={isSidebarOpen}
        />
        <SidebarItem 
           href="/knowledge/skills"
           icon={<Zap className="h-4 w-4" />} 
           label="Skill Hub" 
           isActive={isSkillsActive} 
           isOpen={isSidebarOpen}
        />

        {isSidebarOpen && (
          <div className="pt-6 pb-2 px-3">
            <span className="text-[10px] font-bold uppercase tracking-widest text-slate-500 italic">Configuration</span>
          </div>
        )}
        
        <SidebarItem 
          href="/settings"
          icon={<Settings className="h-4 w-4" />} 
          label="System Settings" 
          isActive={isSettingsActive} 
          isOpen={isSidebarOpen}
        />

        {isSidebarOpen && isChatActive && (
          <div className="flex-1 mt-4 overflow-hidden outline-none">
             <SidebarHistory 
               currentConversationId={pathname.startsWith("/chat/") ? pathname.split("/").pop()! : null}
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
  );
}

function SidebarItem({ href, icon, label, isActive, isOpen, badge }: { href: string, icon: React.ReactNode, label: string, isActive: boolean, isOpen: boolean, badge?: number }) {
  return (
    <Link
      href={href}
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
    </Link>
  );
}
