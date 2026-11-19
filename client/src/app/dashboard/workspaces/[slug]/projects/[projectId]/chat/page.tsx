"use client";

import ChatsView from "@/components/chats/chats-view";
import { useWorkspace } from "../../../workspace-context";
import { useProjectContext } from "../project-context";

export default function ChatsPage() {
  const { slug } = useWorkspace();
  const { project } = useProjectContext();
  return <ChatsView slug={slug} projectId={project.id} />;
}
