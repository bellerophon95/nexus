"use client";

import { use } from "react";
import { ChatDashboard } from "@/components/ChatDashboard";

export default function ConversationPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <ChatDashboard initialConversationId={id} />;
}
