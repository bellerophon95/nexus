"use client";

import { ChatDashboard } from "@/components/ChatDashboard";

export default function ChatPage({ searchParams }: { searchParams: { threadId?: string } }) {
  const threadId = searchParams.threadId || null;
  return <ChatDashboard initialConversationId={threadId} />;
}
