import { AskPageCore } from "@/components/ask/AskPageCore";

/**
 * /ask — new conversation entry point.
 * Redirects to /ask/c/{uuid} once a conversation is created (for logged-in users).
 * Anonymous users get sessionStorage-backed in-memory conversation.
 */
export default function AskPage() {
  return <AskPageCore />;
}
