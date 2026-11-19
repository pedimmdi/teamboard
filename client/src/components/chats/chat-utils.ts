import type { ChatMessage } from "@/lib/api";

export function mergeChatMessages(current: ChatMessage[], incoming: ChatMessage[]) {
  const messages = new Map(current.map((message) => [message.id, message]));
  for (const message of incoming) messages.set(message.id, message);
  return [...messages.values()].sort((left, right) =>
    left.created_at.localeCompare(right.created_at) || left.id.localeCompare(right.id));
}

export function validateChatFiles(files: File[]) {
  if (files.length > 5) return "Attach at most five files.";
  if (files.some((file) => file.size === 0 || file.size > 5 * 1024 * 1024)) return "Each file must be nonempty and at most 5 MB.";
  if (files.reduce((size, file) => size + file.size, 0) > 20 * 1024 * 1024) return "Attachments must total at most 20 MB.";
  if (files.some((file) => !/\.(txt|png|jpe?g)$/i.test(file.name))) return "Choose TXT, PNG or JPEG files.";
  return "";
}
