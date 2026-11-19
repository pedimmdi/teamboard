"use client";

import ChatsView from "@/components/chats/chats-view";
import { useWorkspace } from "../workspace-context";

export default function ChatsPage() {
  const { slug } = useWorkspace();
  return <ChatsView slug={slug} />;
}
