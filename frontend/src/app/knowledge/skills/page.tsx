"use client";

import { KnowledgeHub } from "@/components/KnowledgeHub";
import { useAppContext } from "@/context/AppContext";

export default function SkillsPage() {
  const { selectedSkills, toggleSkill } = useAppContext();
  return <KnowledgeHub selectedSkills={selectedSkills} onToggleSkill={toggleSkill} initialTab="skills" showTabs={false} />;
}
