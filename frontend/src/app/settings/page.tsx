"use client";

import React from "react";
import { Settings } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";

export default function SettingsPage() {
  const router = useRouter();

  return (
    <div className="flex h-full flex-col items-center justify-center space-y-4 text-center">
      <Settings className="h-12 w-12 text-slate-800 animate-pulse" />
      <h2 className="text-2xl font-bold text-slate-300 tracking-tight">System Settings</h2>
      <p className="text-slate-500 max-w-sm italic">Core orchestration parameters and model configurations will be managed here in the next milestone.</p>
      <Button onClick={() => router.push("/chat")} variant="link" className="text-blue-400 mt-4">Return to Dashboard</Button>
    </div>
  );
}
