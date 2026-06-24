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
          <Link href="/ask" className="text-sm text-muted hover:text-foreground transition-colors">
            Ask
          </Link>
          <Link href="/library" className="text-sm text-muted hover:text-foreground transition-colors">
            Library
          </Link>
          <Link href="/about" className="text-sm text-muted hover:text-foreground transition-colors">
            About
          </Link>

          {/* Auth */}
          {user ? (
              <div className="relative" data-account-menu>
              <button
                onClick={() => setMenuOpen((o) => !o)}
                className="flex items-center gap-1.5 rounded-full border border-border px-2.5 py-1.5 text-xs text-muted hover:border-accent/40 hover:text-foreground transition-colors"
                aria-label="Account menu"
              >
                <User className="h-3.5 w-3.5" />
                <span className="hidden sm:inline max-w-[100px] truncate">
                  {user.email?.split("@")[0]}
                </span>
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
