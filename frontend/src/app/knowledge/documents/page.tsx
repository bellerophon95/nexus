"use client";

import { KnowledgeHub } from "@/components/KnowledgeHub";
import { useAppContext } from "@/context/AppContext";

export default function DocumentsPage() {
  const { selectedSkills, toggleSkill } = useAppContext();
  return <KnowledgeHub selectedSkills={selectedSkills} onToggleSkill={toggleSkill} initialTab="documents" showTabs={false} />;
}
