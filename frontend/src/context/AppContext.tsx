"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import { getOrCreateSessionId, handleAccessParams } from "@/lib/auth";

interface AppContextType {
  isSidebarOpen: boolean;
  setIsSidebarOpen: (open: boolean) => void;
  selectedSkills: string[];
  toggleSkill: (skillId: string) => void;
  sessionId: string;
  accessTier: string;
  refreshHistoryTrigger: number;
  triggerHistoryRefresh: () => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export function AppContextProvider({ children }: { children: React.ReactNode }) {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [selectedSkills, setSelectedSkills] = useState<string[]>([]);
  const [sessionId, setSessionId] = useState<string>("");
  const [accessTier, setAccessTier] = useState<string>("visitor");
  const [refreshHistoryTrigger, setRefreshHistoryTrigger] = useState(0);

  const triggerHistoryRefresh = () => setRefreshHistoryTrigger(prev => prev + 1);

  useEffect(() => {
    handleAccessParams();
    const sid = getOrCreateSessionId();
    setSessionId(sid);

    const tier = typeof window !== "undefined" ? localStorage.getItem("nexus_access_tier") || "visitor" : "visitor";
    setAccessTier(tier);
  }, []);

  const toggleSkill = (skillId: string) => {
    setSelectedSkills((prev) =>
      prev.includes(skillId) ? prev.filter((id) => id !== skillId) : [...prev, skillId]
    );
  };

  return (
    <AppContext.Provider
      value={{
        isSidebarOpen,
        setIsSidebarOpen,
        selectedSkills,
        toggleSkill,
        sessionId,
        accessTier,
        refreshHistoryTrigger,
        triggerHistoryRefresh
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useAppContext() {
  const context = useContext(AppContext);
  if (context === undefined) {
    throw new Error("useAppContext must be used within an AppContextProvider");
  }
  return context;
}
