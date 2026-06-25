"use client";

import { useState, useEffect, useRef, useCallback, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  Send, RotateCcw, ThumbsUp, ThumbsDown, ExternalLink,
  Share2, PanelLeftOpen, PanelLeftClose, Check, Copy,
  ArrowUp, ArrowDown, MessageSquareQuote,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import { queryAIStream, getQuotaStatus, deleteSession, scriptureToSlug, type QueryResponse, type QuotaStatus } from "@/lib/api";
import { createClient } from "@/utils/supabase/client";
import { createConversation, loadConversation, shareConversation, getUserQuota, getConversationFeedback, type UserQuotaStatus } from "@/lib/conversations";
import { ConversationSidebar } from "./ConversationSidebar";
import type { User } from "@supabase/supabase-js";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const SESSION_MESSAGES_KEY = "antardarshan_messages";

interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: QueryResponse["citations"];
  mode?: string;
  traceId?: string | null;
  messageId?: string | null;
  model?: string | null;
  tokensUsed?: number | null;
  feedback?: 1 | -1 | null;
}

interface AskPageCoreProps {
  conversationId?: string; // undefined = new/anonymous, string = load existing
}

function AskPageCoreInner({ conversationId: propConversationId }: AskPageCoreProps) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const prefill = searchParams.get("prefill") ?? "";
  // ?draft= pre-fills the input but does NOT auto-submit (user adds their question first)
  const draft = searchParams.get("draft") ?? "";

  const [user, setUser] = useState<User | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  // Always start empty — sessionStorage is restored in useEffect after mount.
  // Reading sessionStorage in useState causes SSR/client hydration mismatch.
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState(draft || prefill);
  const [loading, setLoading] = useState(false);
  const [loadingConversation, setLoadingConversation] = useState(!!propConversationId);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(propConversationId ?? null);
  const [isShared, setIsShared] = useState(false);
  const [isReadOnly, setIsReadOnly] = useState(false);
  const [ownerUserId, setOwnerUserId] = useState<string | null>(null);
  const [quota, setQuota] = useState<QuotaStatus | null>(null);
  const [userQuota, setUserQuota] = useState<UserQuotaStatus | null>(null);
  // Default sidebar open on desktop (>768px), closed on mobile
  const [sidebarOpen, setSidebarOpen] = useState(
    typeof window !== "undefined" && window.innerWidth >= 768
  );
  const [copied, setCopied] = useState(false);
  const [copiedMsgIdx, setCopiedMsgIdx] = useState<number | null>(null);
  const [logContent, setLogContent] = useState<boolean>(false);
  // Pending feedback: user clicked thumbs but hasn't submitted comment yet
  const [feedbackPending, setFeedbackPending] = useState<{
    msgIdx: number; rating: 1 | -1; traceId?: string | null; messageId?: string | null;
  } | null>(null);
  const [feedbackComment, setFeedbackComment] = useState("");
  // Quote-and-ask: text selected inside an AI response — tracks text + toolbar position
  const [selectedResponseText, setSelectedResponseText] = useState<{
    text: string; x: number; y: number;
  } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const toggleLogContent = () => {
    setLogContent((prev) => {
      const next = !prev;
      localStorage.setItem("antardarshan_log_content", String(next));
      return next;
    });
  };

  const handleCopyResponse = (content: string, idx: number) => {
    navigator.clipboard.writeText(content).then(() => {
      setCopiedMsgIdx(idx);
      setTimeout(() => setCopiedMsgIdx(null), 2000);
    });
  };
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const [showScrollUp, setShowScrollUp] = useState(false);
  const autoSubmittedRef = useRef(false);

  // Get current user + access token for JWT-authenticated API calls.
  // When user resolves, also re-check isReadOnly in case the conversation
  // was loaded before auth completed (avoids re-fetching the conversation).
  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getSession().then(({ data }) => {
      const sessionUser = data.session?.user ?? null;
      setUser(sessionUser);
      setAccessToken(data.session?.access_token ?? null);
      if (sessionUser && window.innerWidth >= 768) setSidebarOpen(true);
      // Fetch per-user quota so the UI shows personal remaining count
      if (sessionUser) {
        getUserQuota().then(setUserQuota).catch(() => {});
      }
    });
    const { data: listener } = supabase.auth.onAuthStateChange((_e, session) => {
      const newUser = session?.user ?? null;
      setUser(newUser);
      setAccessToken(session?.access_token ?? null);
      if (newUser && window.innerWidth >= 768) setSidebarOpen(true);
      // On sign-out: clear conversation state so stale messages aren't visible
      if (!newUser) {
        setMessages([]);
        setConversationId(null);
        setSidebarOpen(false);
      }
    });
    return () => listener.subscription.unsubscribe();
  }, []);

  // Re-evaluate isReadOnly when auth resolves — fixes the race where
  // conversation loaded before auth completed and owner got stuck read-only.
  useEffect(() => {
    if (!isShared || ownerUserId === null) return;
    const shouldBeReadOnly = !(user?.id && user.id === ownerUserId);
    // Use setTimeout to avoid synchronous setState-in-effect lint violation
    const t = setTimeout(() => setIsReadOnly(shouldBeReadOnly), 0);
    return () => clearTimeout(t);
  }, [user?.id, isShared, ownerUserId]);

  // Restore client-side preferences on mount (avoids SSR hydration mismatch)
  useEffect(() => {
    const t = setTimeout(() => {
      try {
        // Session messages (anonymous conversations)
        if (!propConversationId && !prefill) {
          const saved = sessionStorage.getItem(SESSION_MESSAGES_KEY);
          if (saved) setMessages(JSON.parse(saved));
          const sid = sessionStorage.getItem("antardarshan_session_id");
          if (sid) setSessionId(sid);
        }
        // Content logging preference
        const logPref = localStorage.getItem("antardarshan_log_content");
        if (logPref !== null) setLogContent(logPref === "true");
      } catch { /* ignore */ }
    }, 0);
    return () => clearTimeout(t);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // runs once on mount only

  // Clear loadingConversation when there's no conversation to load
  useEffect(() => {
    if (!propConversationId) {
      const t = setTimeout(() => setLoadingConversation(false), 0);
      return () => clearTimeout(t);
    }
  }, [propConversationId]);

  // Load existing conversation from Supabase.
  // conversationLoadedRef prevents duplicate fetches within the same render cycle,
  // but resets when propConversationId changes (user navigates to different conversation).
  const conversationLoadedRef = useRef<string | null>(null);
  useEffect(() => {
    if (!propConversationId) return;
    if (conversationLoadedRef.current === propConversationId) return; // already loaded this one
    conversationLoadedRef.current = propConversationId;

    loadConversation(propConversationId)
      .catch(() => null)  // network failure → treat as not found, don't spin forever
      .then((data) => {
      if (!data) { setLoadingConversation(false); return; }

      const conv = data.conversation;
      setIsShared(conv.shared);
      setOwnerUserId(conv.user_id ?? null);
      const viewerIsOwner = !!user?.id && user.id === conv.user_id;
      setIsReadOnly(conv.shared && !viewerIsOwner);

      const msgs: Message[] = data.messages.map((m) => ({
        role: m.role as "user" | "assistant",
        content: m.content,
        citations: m.citations?.map((c: { scripture: string; chapter: number; verse: number; translator: string; readable?: boolean }) => ({
          ...c,
          readable: c.readable !== false,
        })) ?? undefined,
        mode: m.mode ?? undefined,
        messageId: m.role === "assistant" ? (m.id ?? null) : null,
        model: m.model ?? null,
        tokensUsed: m.tokens_used ?? null,
        feedback: null,  // will be populated below
      }));

      // Restore feedback ratings the user previously submitted for this conversation
      getConversationFeedback(propConversationId).then((feedbackMap) => {
        if (Object.keys(feedbackMap).length === 0) return;
        setMessages((prev) => prev.map((m) =>
          m.messageId && feedbackMap[m.messageId]
            ? { ...m, feedback: feedbackMap[m.messageId] }
            : m
        ));
      }).catch(() => {});

      setMessages(msgs);
      setLoadingConversation(false);
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [propConversationId]); // user?.id excluded intentionally — see comment above

  // Prefill handling: clear old session, auto-submit
  useEffect(() => {
    if (!prefill) return;
    sessionStorage.removeItem(SESSION_MESSAGES_KEY);
    sessionStorage.removeItem("antardarshan_session_id");

    if (!autoSubmittedRef.current) {
      autoSubmittedRef.current = true;
      setTimeout(() => {
        document.getElementById("ask-form")?.dispatchEvent(
          new Event("submit", { bubbles: true, cancelable: true })
        );
      }, 150);
    }
  }, [prefill]);

  // Persist to sessionStorage (for non-persisted conversations)
  useEffect(() => {
    if (!propConversationId && typeof window !== "undefined") {
      sessionStorage.setItem(SESSION_MESSAGES_KEY, JSON.stringify(messages));
    }
  }, [messages, propConversationId]);

  // Quota — fetch once on mount, then refresh after each query (event-driven, no polling loop)
  useEffect(() => {
    getQuotaStatus().then(setQuota).catch(() => {});
  }, []);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Select text in AI response → show floating "Ask about this" button near selection
  useEffect(() => {
    const handleMouseUp = () => {
      const selection = window.getSelection();
      if (!selection || selection.isCollapsed) {
        setSelectedResponseText(null);
        return;
      }
      const text = selection.toString().trim();
      if (text.length < 3) return;

      // Only trigger when the selection is inside the messages container
      const container = messagesContainerRef.current;
      if (!container) return;
      const range = selection.getRangeAt(0);
      const node = range.commonAncestorContainer.nodeType === Node.TEXT_NODE
        ? range.commonAncestorContainer.parentElement
        : range.commonAncestorContainer as Element;
      if (!container.contains(node)) return;

      // Position the button just above the selection
      const rect = range.getBoundingClientRect();
      setSelectedResponseText({ text, x: rect.left + rect.width / 2, y: rect.top - 6 });
    };

    // Auto-dismiss when selection is cleared (user clicks elsewhere)
    const handleSelectionChange = () => {
      const selection = window.getSelection();
      if (!selection || selection.isCollapsed) {
        setSelectedResponseText(null);
      }
    };

    document.addEventListener("mouseup", handleMouseUp);
    document.addEventListener("selectionchange", handleSelectionChange);
    return () => {
      document.removeEventListener("mouseup", handleMouseUp);
      document.removeEventListener("selectionchange", handleSelectionChange);
    };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const q = input.trim();
    if (!q || loading || isReadOnly) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setLoading(true);
    // Declare outside try so catch can reference it to replace the stale placeholder
    let streamingId = "";

    try {
      let convId = conversationId;
      if (!convId && user) {
        const conv = await createConversation();
        if (conv) {
          convId = conv.id;
          setConversationId(conv.id);
        }
      }

      // Use a stable UUID to identify the streaming placeholder — avoids stale-index bugs
      streamingId = `stream-${Date.now()}`;
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "", citations: [], mode: undefined, feedback: null,
          traceId: streamingId },  // reuse traceId as a temp stable key
      ]);

      let streamedContent = "";

      const response = await queryAIStream(
        q,
        sessionId || undefined,
        { conversation_id: convId ?? undefined, access_token: accessToken ?? undefined, log_content: logContent },
        (token) => {
          streamedContent += token;
          setMessages((prev) =>
            prev.map((m) =>
              m.traceId === streamingId ? { ...m, content: streamedContent } : m
            )
          );
        },
      );

      setSessionId(response.session_id);
      if (!propConversationId) {
        sessionStorage.setItem("antardarshan_session_id", response.session_id);
      }
      // Silently update the URL bar to the permanent conversation URL.
      // Use window.history.replaceState (not router.replace) so Next.js does NOT
      // remount the component — the stream stays alive, no page flash.
      if (convId && !propConversationId && typeof window !== "undefined") {
        window.history.replaceState({}, "", `/ask/c/${convId}`);
      }
      if (response.conversation_id && !conversationId) {
        setConversationId(response.conversation_id);
      }

      // Replace the placeholder with the finalized message + metadata
      setMessages((prev) =>
        prev.map((m) =>
          m.traceId === streamingId
            ? {
                role: "assistant",
                content: streamedContent,
                citations: response.citations,
                mode: response.mode,
                traceId: response.trace_id ?? null,
                messageId: response.message_id ?? null,
                model: response.model ?? null,
                tokensUsed: response.tokens_used ?? null,
                feedback: null,
              }
            : m
        )
      );
      // Notify sidebar to reload — backend auto-titles the conversation after persist_messages,
      // so by this point the title is in the DB and the sidebar can pick it up.
      window.dispatchEvent(new CustomEvent("conversation-updated"));
    } catch (err: unknown) {
      const status = (err as { status?: number })?.status;
      const detail = (err as { detail?: { error?: string; message?: string } })?.detail;
      let errorContent = "Could not reach the server. Please try again.";
      if (status === 429) {
        errorContent = detail?.error === "global_limit_reached"
          ? "The service has reached its daily query limit. Please come back tomorrow."
          : "You've used today's 50 personal queries. Come back tomorrow — the limit resets at midnight UTC.";
      }
      // Replace the stale placeholder (if it exists) rather than appending a second message
      setMessages((prev) => {
        const hasPlaceholder = prev.some((m) => m.traceId === streamingId);
        if (hasPlaceholder) {
          return prev.map((m) =>
            m.traceId === streamingId
              ? { role: "assistant" as const, content: errorContent, feedback: null }
              : m
          );
        }
        return [...prev, { role: "assistant" as const, content: errorContent, feedback: null }];
      });
    } finally {
      setLoading(false);
      // Refresh quota after each query — accurate without background polling
      getQuotaStatus().then(setQuota).catch(() => {});
      if (user) getUserQuota().then(setUserQuota).catch(() => {});
    }
  };

  const handleFeedbackClick = (msgIdx: number, rating: 1 | -1, traceId?: string | null, messageId?: string | null) => {
    // Optimistic: show the rating immediately
    setMessages((prev) => prev.map((m, i) => i === msgIdx ? { ...m, feedback: rating } : m));
    // Open comment box (optional — user can skip)
    setFeedbackPending({ msgIdx, rating, traceId, messageId });
    setFeedbackComment("");
  };

  const submitFeedback = async (comment: string) => {
    if (!feedbackPending) return;
    const { msgIdx, rating, traceId, messageId } = feedbackPending;
    setFeedbackPending(null);
    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`;
      await fetch(`${API_BASE}/api/feedback`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          trace_id: traceId,
          rating,
          comment: comment.trim() || null,
          mode: messages[msgIdx]?.mode,
          conversation_id: conversationId,
          message_id: messageId ?? null,
        }),
      });
    } catch { /* non-critical */ }
  };

  const handleQuoteAndAsk = useCallback(() => {
    if (!selectedResponseText) return;
    const quote = `> "${selectedResponseText.text.slice(0, 300)}"\n\n`;
    setInput((prev) => (prev ? `${prev}\n${quote}` : quote));
    setSelectedResponseText(null);
    window.getSelection()?.removeAllRanges();
    setTimeout(() => {
      inputRef.current?.focus();
      const len = inputRef.current?.value.length ?? 0;
      inputRef.current?.setSelectionRange(len, len);
    }, 50);
  }, [selectedResponseText]);

  const handleNewChat = useCallback(async () => {
    if (sessionId) await deleteSession(sessionId).catch(() => {});
    sessionStorage.removeItem("antardarshan_session_id");
    sessionStorage.removeItem(SESSION_MESSAGES_KEY);
    setSessionId(null);
    setMessages([]);
    setConversationId(null);
    router.push("/ask");
  }, [sessionId, router]);

  const handleShare = async () => {
    if (!conversationId) return;
    const url = await shareConversation(conversationId);
    if (url) {
      await navigator.clipboard.writeText(url);
      setIsShared(true);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (loadingConversation) {
    return (
      <div className="flex h-[calc(100vh-3.5rem)] items-center justify-center text-muted">
        <div className="flex gap-1">
          {[0, 150, 300].map((d) => (
            <span key={d} className="h-2 w-2 animate-bounce rounded-full bg-accent" style={{ animationDelay: `${d}ms` }} />
          ))}
        </div>
      </div>
    );
  }

  // Per-user exhaustion takes priority over global when logged in
  const isExhausted = userQuota
    ? !userQuota.per_user_allowed
    : quota?.status === "exhausted";

  return (
    <div className="fixed inset-0 top-14 flex bg-background">
      {/* Sidebar — only for logged-in users, toggleable */}
      {user && sidebarOpen && (
        <ConversationSidebar
          currentConversationId={conversationId ?? undefined}
          onNewChat={handleNewChat}
        />
      )}

      {/* Main chat area */}
      <div className="flex flex-1 flex-col min-w-0">
        {/* Top bar — sticky so it stays visible while scrolling the messages */}
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-border bg-background/95 backdrop-blur px-4 py-2 gap-2">
          <div className="flex items-center gap-2">
            {user && (
              <button
                onClick={() => setSidebarOpen((o) => !o)}
                className="rounded-md p-1.5 text-muted hover:bg-surface hover:text-foreground transition-colors"
                aria-label={sidebarOpen ? "Hide history" : "Show history"}
                title="Conversation history"
              >
                {sidebarOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeftOpen className="h-4 w-4" />}
              </button>
            )}
            <button
              onClick={handleNewChat}
              className="flex items-center gap-1 rounded-md px-3 py-1.5 text-sm text-muted hover:bg-surface hover:text-foreground transition-colors"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              New Chat
            </button>
          </div>

          <div className="flex items-center gap-3">
            {/* Share button */}
            {conversationId && user && (
              <button
                onClick={handleShare}
                className="flex items-center gap-1 text-xs text-muted hover:text-foreground transition-colors"
                title={isShared ? "Shared — click to copy link" : "Share this conversation"}
              >
                {copied ? <Check className="h-3.5 w-3.5 text-success" /> : <Share2 className="h-3.5 w-3.5" />}
                {copied ? "Copied!" : isShared ? "Shared" : "Share"}
              </button>
            )}

            {/* Content logging toggle — user controls whether Q&A goes to LangFuse */}
            <div className="relative group">
              <button
                onClick={toggleLogContent}
                className={`flex items-center gap-1 text-xs transition-colors ${
                  logContent ? "text-accent" : "text-muted hover:text-foreground"
                }`}
                aria-label={logContent ? "Disable response logging" : "Enable response logging"}
              >
                <span className="text-base leading-none">{logContent ? "🔒" : "🔓"}</span>
                <span className="hidden sm:inline">{logContent ? "Saving" : "Not saving"}</span>
              </button>
              {/* Tooltip */}
              <div className="pointer-events-none absolute right-0 top-full mt-2 w-72 rounded-lg bg-foreground px-3 py-2.5 text-[11px] text-background leading-snug opacity-0 group-hover:opacity-100 transition-opacity duration-150 z-50 shadow-lg space-y-1.5">
                <p>
                  {logContent
                    ? "🔒 Your questions and answers are being saved to help improve this service. Click to disable."
                    : "🔓 Questions and answers are NOT being saved to our analytics. Click to enable."}
                </p>
                <p className="opacity-70">
                  Your conversation history is always saved to your own account so you can refer back to it.
                </p>
                <p className="opacity-60 border-t border-background/20 pt-1.5">
                  🔐 We never store your personal details (name, email) alongside your questions. Your email is used only for login.
                </p>
              </div>
            </div>

            {/* Read-only badge */}
            {isReadOnly && (
              <span className="text-xs text-muted bg-surface rounded-md px-2 py-1">Read-only</span>
            )}

            {/* Quota indicator — personal count for logged-in users, global dot for anonymous */}
            {userQuota ? (
              <div className="flex items-center gap-2 text-xs text-muted"
                title={`${userQuota.per_user_used} of ${userQuota.per_user_limit} personal queries used today`}>
                <span className={`h-2.5 w-2.5 rounded-full ${
                  userQuota.per_user_remaining > 10 ? "bg-success" :
                  userQuota.per_user_remaining > 0 ? "bg-yellow-500" : "bg-error"
                }`} />
                <span className="hidden sm:inline">
                  {userQuota.per_user_remaining > 0
                    ? `${userQuota.per_user_remaining} of ${userQuota.per_user_limit} queries left`
                    : "Daily limit reached"}
                </span>
              </div>
            ) : quota && (
              <div className="flex items-center gap-2 text-sm text-muted" title={`${quota.queries_today} of ${quota.daily_limit} queries used today`}>
                <span className={`h-2.5 w-2.5 rounded-full ${
                  quota.status === "available" ? "bg-success" :
                  quota.status === "limited" ? "bg-yellow-500" : "bg-error"
                }`} />
                <span className="hidden sm:inline text-xs">
                  {isExhausted ? "Daily limit reached" : "Queries available"}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Messages */}
        <div
          className="flex-1 overflow-y-auto px-4 py-6"
          ref={messagesContainerRef}
          onScroll={(e) => setShowScrollUp(e.currentTarget.scrollTop > 300)}
        >
          <div className="mx-auto max-w-2xl space-y-6">
            {messages.length === 0 && (
              <div className="text-center py-16 text-muted">
                <p className="text-lg mb-2">Ask anything about Indian philosophy</p>
                <p className="text-sm">Citations from Gita, Upanishads, Dhammapada, Yoga Sutras &amp; more</p>
              </div>
            )}

            {messages.map((msg, i) => (
              <div key={i} className={msg.role === "user" ? "flex justify-end" : ""}>
                {msg.role === "user" ? (
                  <div className="max-w-[80%] rounded-2xl bg-accent/10 px-4 py-3 text-sm">
                    {msg.content}
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div className="prose prose-sm dark:prose-invert max-w-none text-foreground">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>

                    {msg.citations && msg.citations.length > 0 && (
                      <div className="flex flex-wrap gap-2 mt-2">
                        {msg.citations.map((c, j) => (
                          // readable: true/undefined = link; readable: false = plain tag
                          (c.readable !== false) ? (
                            <a
                              key={j}
                              href={`/read/${scriptureToSlug(c.scripture)}/${c.chapter}/${c.verse}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs text-muted hover:bg-surface hover:text-foreground transition-colors"
                            >
                              <ExternalLink className="h-3 w-3" />
                              {c.scripture} {c.chapter}.{c.verse}
                            </a>
                          ) : (
                            // OCR source — still clickable (user can read the text),
                            // but marked with ⓘ and tooltip to set expectations
                            <a
                              key={j}
                              href={`/read/${scriptureToSlug(c.scripture)}/${c.chapter}/${c.verse}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="group relative inline-flex items-center gap-1 rounded-md border border-border/50 px-2 py-1 text-xs text-muted/60 hover:text-foreground hover:border-border transition-colors"
                            >
                              {c.scripture} {c.chapter}.{c.verse}
                              <span className="text-[10px] text-muted/40 group-hover:text-muted">ⓘ</span>
                              {/* Tooltip on hover */}
                              <span className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-56 rounded-lg bg-foreground px-3 py-2 text-[11px] text-background leading-snug opacity-0 group-hover:opacity-100 transition-opacity duration-150 z-50 shadow-lg">
                                Source text may have OCR quality issues — you can still read it but formatting may be imperfect.
                                <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-foreground" />
                              </span>
                            </a>
                          )
                        ))}
                      </div>
                    )}

                    <div className="relative flex items-center gap-2 mt-2">
                      <button
                        onClick={() => msg.feedback !== 1 && handleFeedbackClick(i, 1, msg.traceId, msg.messageId)}
                        className={`rounded p-1 transition-colors ${msg.feedback === 1 ? "text-success" : "text-muted hover:text-success"}`}
                        aria-label="Helpful"
                        title={msg.feedback === 1 ? "You rated this helpful" : "Mark helpful"}
                      >
                        <ThumbsUp className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={() => msg.feedback !== -1 && handleFeedbackClick(i, -1, msg.traceId, msg.messageId)}
                        className={`rounded p-1 transition-colors ${msg.feedback === -1 ? "text-error" : "text-muted hover:text-error"}`}
                        aria-label="Not helpful"
                        title={msg.feedback === -1 ? "You rated this unhelpful" : "Mark unhelpful"}
                      >
                        <ThumbsDown className="h-3.5 w-3.5" />
                      </button>

                      {/* Optional comment card — appears below the voted message */}
                      {feedbackPending?.msgIdx === i && (
                        <div className="absolute left-0 right-0 mt-1 top-full z-10 rounded-xl border border-border shadow-lg p-3"
                          style={{ background: "var(--color-surface)" }}>
                          <p className="text-xs text-muted mb-2">
                            {feedbackPending.rating === 1 ? "What was helpful? (optional)" : "What went wrong? (optional)"}
                          </p>
                          <textarea
                            className="w-full text-xs bg-transparent border border-border/60 rounded-lg p-2 resize-none focus:outline-none focus:ring-1 focus:ring-accent"
                            placeholder={feedbackPending.rating === 1 ? "Great citations, clear explanation..." : "Wrong scripture, missed the point..."}
                            rows={2}
                            value={feedbackComment}
                            onChange={(e) => setFeedbackComment(e.target.value)}
                            autoFocus
                          />
                          <div className="flex justify-end gap-2 mt-2">
                            <button onClick={() => submitFeedback("")} className="text-xs text-muted hover:text-foreground px-2 py-1">
                              Skip
                            </button>
                            <button onClick={() => submitFeedback(feedbackComment)} className="text-xs bg-accent text-white rounded px-3 py-1 hover:bg-accent-hover">
                              Submit
                            </button>
                          </div>
                        </div>
                      )}
                      <button
                        onClick={() => handleCopyResponse(msg.content, i)}
                        className="rounded p-1 text-muted hover:text-foreground transition-colors"
                        aria-label="Copy response"
                        title="Copy response"
                      >
                        {copiedMsgIdx === i
                          ? <Check className="h-3.5 w-3.5 text-success" />
                          : <Copy className="h-3.5 w-3.5" />}
                      </button>
                      {msg.mode && (
                        <span className="text-xs text-muted/60 ml-2">
                          {msg.mode}
                          {msg.model ? ` · ${msg.model.includes("8b") ? "Llama 8B" : "Llama 17B"}` : null}
                          {msg.tokensUsed ? ` · ~${msg.tokensUsed.toLocaleString()} tokens` : null}
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}

            {loading && (
              <div className="flex gap-1 py-4">
                {[0, 150, 300].map((d) => (
                  <span key={d} className="h-2 w-2 animate-bounce rounded-full bg-accent" style={{ animationDelay: `${d}ms` }} />
                ))}
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input */}
        {/* Floating scroll buttons — stay inside the chat, visible on long conversations */}
        <div className="fixed right-6 bottom-20 flex flex-col gap-2 z-20">
          {showScrollUp && (
            <button
              onClick={() => messagesContainerRef.current?.scrollTo({ top: 0, behavior: "smooth" })}
              className="flex h-9 w-9 items-center justify-center rounded-full bg-surface border border-border shadow text-muted hover:text-foreground hover:bg-accent hover:border-accent hover:text-white transition-all"
              aria-label="Scroll to top"
              title="Back to top"
            >
              <ArrowUp className="h-4 w-4" />
            </button>
          )}
          <button
            onClick={() => messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })}
            className="flex h-9 w-9 items-center justify-center rounded-full bg-surface border border-border shadow text-muted hover:text-foreground hover:bg-accent hover:border-accent hover:text-white transition-all"
            aria-label="Scroll to bottom"
            title="Jump to latest"
          >
            <ArrowDown className="h-4 w-4" />
          </button>
        </div>

        {/* Floating "Ask about this" button — appears near selected text in AI response,
            auto-dismisses when selection is cleared */}
        {selectedResponseText && !isReadOnly && (
          <div
            className="fixed z-50 flex items-center gap-1.5 rounded-lg border border-border shadow-xl px-2.5 py-1.5 text-xs"
            style={{
              left: selectedResponseText.x,
              top: selectedResponseText.y,
              transform: "translateX(-50%) translateY(-100%)",
              background: "var(--color-surface)",
            }}
            onMouseDown={(e) => e.preventDefault()} // preserve selection while clicking button
          >
            <MessageSquareQuote className="h-3 w-3 text-accent shrink-0" />
            <button
              onClick={handleQuoteAndAsk}
              className="font-medium text-accent hover:underline whitespace-nowrap"
            >
              Ask about this
            </button>
          </div>
        )}

        {!isReadOnly && (
          <div className="border-t border-border">
            <div className="px-4 py-3">
            <form id="ask-form" onSubmit={handleSubmit} className="mx-auto flex max-w-2xl gap-2">
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={isExhausted ? "Daily limit reached. Come back tomorrow." : "Ask a question..."}
                disabled={loading || isExhausted}
                className="flex-1 rounded-xl border border-border bg-surface px-4 py-3 text-sm placeholder:text-muted/60 focus:outline-none focus:ring-2 focus:ring-accent disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={loading || !input.trim() || isExhausted}
                className="rounded-xl bg-accent px-4 py-3 text-white hover:bg-accent-hover transition-colors disabled:opacity-50"
                aria-label="Send message"
              >
                <Send className="h-4 w-4" />
              </button>
            </form>
            </div>
          </div>
        )}

        {isReadOnly && (
          <div className="border-t border-border px-4 py-3 text-center text-sm text-muted">
            This is a shared read-only conversation.{" "}
            <Link href="/ask" className="text-accent hover:underline">Start your own →</Link>
          </div>
        )}
      </div>
    </div>
  );
}

export function AskPageCore(props: AskPageCoreProps) {
  return (
    <Suspense fallback={<div className="flex items-center justify-center h-[50vh] text-muted">Loading...</div>}>
      <AskPageCoreInner {...props} />
    </Suspense>
  );
}
