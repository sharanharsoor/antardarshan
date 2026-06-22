"use client";

import { useParams } from "next/navigation";
import { AskPageCore } from "@/components/ask/AskPageCore";

/**
 * Persistent conversation page — /ask/c/{uuid}
 * Loads an existing conversation from Supabase and enables continuing it.
 * Also handles shared (read-only) conversations for recipients.
 */
export default function ConversationPage() {
  const params = useParams();
  const conversationId = params.id as string;

  return <AskPageCore conversationId={conversationId} />;
}
