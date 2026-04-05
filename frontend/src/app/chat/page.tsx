"use client";

import { use } from "react";
import { ChatDashboard } from "@/components/ChatDashboard";

export default function ChatPage({ searchParams }: { searchParams: Promise<{ threadId?: string }> }) {
  const params = use(searchParams);
  const threadId = params.threadId || null;
  return <ChatDashboard initialConversationId={threadId} />;
}
