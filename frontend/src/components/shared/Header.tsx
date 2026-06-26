"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Moon, Sun, BookOpen, User, LogOut, LogIn } from "lucide-react";
import { useTheme } from "next-themes";
import { createClient } from "@/utils/supabase/client";
import { AuthModal } from "./AuthModal";
import type { User as SupabaseUser } from "@supabase/supabase-js";

export function Header() {
  const { setTheme, resolvedTheme } = useTheme();
  const [user, setUser] = useState<SupabaseUser | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [showAuth, setShowAuth] = useState(false);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data }) => setUser(data.user));

    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
    });
    return () => listener.subscription.unsubscribe();
  }, []);

  // Close account dropdown on outside click
  useEffect(() => {
    if (!menuOpen) return;
    const handler = (e: MouseEvent) => {
      if (!(e.target as Element).closest("[data-account-menu]")) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [menuOpen]);

  const handleSignIn = () => setShowAuth(true);

  const handleSignOut = async () => {
    const supabase = createClient();
    await supabase.auth.signOut();
    setMenuOpen(false);
    // Redirect to home — clears all in-memory state (conversation, messages,
    // sidebar history) and lands the user somewhere clean.
    // This is the standard pattern: ChatGPT/Cursor both redirect on logout.
    window.location.href = "/";
  };

  return (
    <>
    <header className="sticky top-0 z-50 border-b border-border bg-background/95 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-4">
        <Link href="/" className="flex items-center gap-2.5">
          <BookOpen className="h-5 w-5 text-accent" />
          <span className="font-serif text-xl font-bold text-accent">AntarDarshan</span>
          <span className="font-devanagari text-base text-accent/70">अन्तर्दर्शन</span>
        </Link>

        <nav className="flex items-center gap-4">
          {[
            { href: "/ask",     label: "Ask" },
            { href: "/library", label: "Library" },
            { href: "/wisdom",  label: "Wisdom Wall" },
            { href: "/about",   label: "About" },
          ].map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className="text-sm text-foreground/60 hover:text-foreground transition-colors whitespace-nowrap relative group"
            >
              {label}
              <span className="absolute -bottom-0.5 left-0 right-0 h-px bg-accent scale-x-0 group-hover:scale-x-100 transition-transform origin-left" />
            </Link>
          ))}

          {/* Thin separator between nav and identity controls */}
          <div className="h-5 w-px bg-border/60 mx-0.5" />

          {/* Auth */}
          {user ? (
              <div className="relative" data-account-menu>
              {/* Avatar circle with initial — standard identity control pattern */}
              <button
                onClick={() => setMenuOpen((o) => !o)}
                className="h-8 w-8 rounded-full bg-accent text-white text-sm font-semibold flex items-center justify-center hover:bg-accent-hover transition-colors shrink-0"
                aria-label="Account menu"
                title={user.email ?? "Account"}
              >
                {(user.email?.[0] ?? "?").toUpperCase()}
              </button>

              {menuOpen && (
                <div className="absolute right-0 top-10 w-44 rounded-xl border border-border bg-background shadow-lg py-1 z-50">
                  <div className="px-3 py-2 text-xs text-muted truncate border-b border-border mb-1">
                    {user.email}
                  </div>
                  <Link
                    href="/profile"
                    onClick={() => setMenuOpen(false)}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-muted hover:text-foreground hover:bg-surface transition-colors"
                  >
                    <User className="h-3.5 w-3.5" />
                    My Journey
                  </Link>
                  <button
                    onClick={handleSignOut}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-muted hover:text-error hover:bg-surface transition-colors"
                  >
                    <LogOut className="h-3.5 w-3.5" />
                    Sign out
                  </button>
                </div>
              )}
            </div>
          ) : (
            <button
              onClick={handleSignIn}
              className="flex items-center gap-1.5 rounded-full border border-border px-2.5 py-1.5 text-xs text-muted hover:border-accent/40 hover:text-foreground transition-colors"
            >
              <LogIn className="h-3.5 w-3.5" />
              <span>Sign in</span>
            </button>
          )}

          {/* GitHub link — open source signal */}
          <a
            href="https://github.com/sharanharsoor/antardarshan"
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-md p-2 text-muted hover:text-foreground hover:bg-surface transition-colors"
            aria-label="View on GitHub"
            title="Open source on GitHub"
          >
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
            </svg>
          </a>

          <button
            onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
            className="rounded-md p-2 text-muted hover:text-foreground hover:bg-surface transition-colors"
            aria-label="Toggle dark mode"
          >
            {/* CSS-only icon swap — no JS state, no hydration mismatch.
                next-themes sets data-theme="dark" on <html>; we hide/show
                each icon purely via CSS so server and client render the same HTML. */}
            <Moon className="h-4 w-4 hidden [html[data-theme=dark]_&]:block" />
            <Sun  className="h-4 w-4 block  [html[data-theme=dark]_&]:hidden" />
          </button>
        </nav>
      </div>
    </header>

    {showAuth && <AuthModal onClose={() => setShowAuth(false)} />}
    </>
  );
}
