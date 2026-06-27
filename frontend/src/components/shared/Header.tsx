"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Moon, Sun, BookOpen, User, LogOut, LogIn, Menu, X } from "lucide-react";
import { useTheme } from "next-themes";
import { createClient } from "@/utils/supabase/client";
import { AuthModal } from "./AuthModal";
import type { User as SupabaseUser } from "@supabase/supabase-js";

const NAV_ITEMS = [
  { href: "/ask", label: "Ask" },
  { href: "/library", label: "Library" },
  { href: "/wisdom", label: "Wisdom Wall" },
  { href: "/about", label: "About" },
] as const;

export function Header() {
  const pathname = usePathname();
  const { setTheme, resolvedTheme } = useTheme();
  const [user, setUser] = useState<SupabaseUser | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
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

  const isActive = (href: string) => (
    pathname === href || (pathname?.startsWith(`${href}/`) ?? false)
  );

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
    <header className="sticky top-0 z-50 border-b border-border/65 bg-background/86 backdrop-blur-xl supports-[backdrop-filter]:bg-background/76">
      <div className="mx-auto flex h-[4.25rem] max-w-6xl items-center gap-4 px-4 sm:px-5">
        <Link href="/" className="group flex items-center gap-3 shrink-0">
          <div className="rounded-xl bg-accent/12 p-2 text-accent transition-colors group-hover:bg-accent/18">
            <BookOpen className="h-4 w-4 sm:h-[18px] sm:w-[18px]" />
          </div>
          <div className="leading-tight">
            <div className="font-serif text-lg font-semibold tracking-tight text-accent sm:text-[1.18rem]">
              AntarDarshan
            </div>
            <div className="hidden font-devanagari text-[11px] text-accent/75 sm:block">
              अन्तर्दर्शन
            </div>
          </div>
        </Link>

        {/* Nav + account — flex-1 so meta controls stay at extreme right */}
        <div className="flex flex-1 items-center justify-end gap-1 sm:gap-2">
          {/* Desktop nav — pills always visible so users know what's clickable */}
          <nav className="hidden items-center gap-1 md:flex">
            {NAV_ITEMS.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-all ${
                  isActive(href)
                    ? "bg-accent/15 text-accent ring-1 ring-accent/25"
                    : "bg-surface/60 text-foreground hover:bg-surface hover:shadow-sm"
                }`}
                aria-current={isActive(href) ? "page" : undefined}
              >
                {label}
              </Link>
            ))}
          </nav>

          {/* Divider — separates nav from account */}
          <div className="mx-1 hidden h-5 w-px bg-border md:block" />

          {user ? (
            <div className="relative hidden md:block" data-account-menu>
              <button
                onClick={() => setMenuOpen((o) => !o)}
                className="h-9 w-9 rounded-full border border-accent/35 bg-accent text-sm font-semibold text-white shadow-sm transition-colors hover:bg-accent-hover"
                aria-label="Account menu"
                title={user.email ?? "Account"}
              >
                {(user.email?.[0] ?? "?").toUpperCase()}
              </button>

              {menuOpen && (
                <div className="absolute right-0 top-11 z-50 w-56 rounded-lg border border-border bg-background py-1 shadow-lg">
                  <div className="mb-1 border-b border-border px-3 py-2 text-xs text-muted truncate">
                    {user.email}
                  </div>
                  <Link
                    href="/profile"
                    onClick={() => setMenuOpen(false)}
                    className="flex w-full items-center gap-2 px-3 py-2 text-sm text-muted transition-colors hover:bg-surface hover:text-foreground"
                  >
                    <User className="h-3.5 w-3.5" />
                    My Journey
                  </Link>
                  <button
                    onClick={handleSignOut}
                    className="flex w-full items-center gap-2 px-3 py-2 text-sm text-muted transition-colors hover:bg-surface hover:text-error"
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
              className="hidden items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm text-white transition-colors hover:bg-accent-hover md:flex"
            >
              <LogIn className="h-4 w-4" />
              <span>Sign in</span>
            </button>
          )}

          <button
            onClick={() => setMobileOpen((o) => !o)}
            className="rounded-md p-2 text-muted transition-colors hover:bg-surface hover:text-foreground md:hidden"
            aria-label={mobileOpen ? "Close menu" : "Open menu"}
          >
            {mobileOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </button>
        </div>

      </div>

      {/* Meta controls — pinned to true viewport right edge, outside the max-w container */}
      <div className="absolute right-3 top-1/2 -translate-y-1/2 hidden md:flex items-center gap-0.5">
        <button
          onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
          className="rounded-lg p-2 text-muted/50 hover:text-muted hover:bg-surface/60 transition-colors"
          aria-label="Toggle dark mode"
        >
          <Moon className="h-5 w-5 hidden [html[data-theme=dark]_&]:block" />
          <Sun className="h-5 w-5 block [html[data-theme=dark]_&]:hidden" />
        </button>
        <a
          href="https://github.com/sharanharsoor/antardarshan"
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-lg p-2 text-muted/50 hover:text-muted hover:bg-surface/60 transition-colors"
          aria-label="View on GitHub"
        >
          <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
          </svg>
        </a>
      </div>

      {mobileOpen && (
        <div className="border-t border-border/70 bg-background/95 px-4 py-3 md:hidden">
          <nav className="flex flex-col gap-1">
            {NAV_ITEMS.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                onClick={() => setMobileOpen(false)}
                className={`rounded-lg px-3 py-2 text-sm transition-colors ${
                  isActive(href)
                    ? "border-l-2 border-accent bg-surface text-foreground"
                    : "text-foreground/80 hover:bg-surface hover:text-foreground"
                }`}
              >
                {label}
              </Link>
            ))}
          </nav>

          <div className="mt-3 border-t border-border/70 pt-3">
            {user ? (
              <div className="space-y-1">
                <Link
                  href="/profile"
                  onClick={() => setMobileOpen(false)}
                  className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-foreground/80 transition-colors hover:bg-surface hover:text-foreground"
                >
                  <User className="h-4 w-4" />
                  My Journey
                </Link>
                <button
                  onClick={handleSignOut}
                  className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-foreground/80 transition-colors hover:bg-surface hover:text-error"
                >
                  <LogOut className="h-4 w-4" />
                  Sign out
                </button>
              </div>
            ) : (
              <button
                onClick={() => {
                  setMobileOpen(false);
                  handleSignIn();
                }}
                className="flex w-full items-center justify-center gap-2 rounded-lg border border-border px-3 py-2 text-sm text-muted transition-colors hover:border-accent/40 hover:text-foreground"
              >
                <LogIn className="h-4 w-4" />
                Sign in
              </button>
            )}
          </div>
        </div>
      )}
    </header>

    {showAuth && <AuthModal onClose={() => setShowAuth(false)} />}
    </>
  );
}
