import type { Metadata } from "next";
import { Playfair_Display, Inter, Noto_Serif_Devanagari } from "next/font/google";
import { ThemeProvider } from "@/lib/theme-provider";
import { Header } from "@/components/shared/Header";
import "./globals.css";

const playfair = Playfair_Display({
  subsets: ["latin"],
  variable: "--font-serif",
  display: "swap",
});

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

// Devanagari for product name (अन्तर्दर्शन) and Sanskrit verse numbers
const notoSerifDevanagari = Noto_Serif_Devanagari({
  subsets: ["devanagari"],
  variable: "--font-devanagari",
  display: "swap",
  weight: ["400", "700"],
});

export const metadata: Metadata = {
  title: "AntarDarshan — Inner Vision Through Ancient Wisdom",
  description:
    "AI-powered Indian philosophy assistant. Get citation-grounded answers from Bhagavad Gita, Upanishads, Dhammapada, Yoga Sutras, and more.",
  keywords: ["Indian philosophy", "Bhagavad Gita", "Upanishads", "Vedanta", "Buddhism", "Yoga", "AI assistant"],
  icons: {
    icon: [
      { url: "/favicon.svg", type: "image/svg+xml" },
    ],
    apple: "/favicon.svg",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body suppressHydrationWarning className={`${inter.variable} ${playfair.variable} ${notoSerifDevanagari.variable} font-sans antialiased bg-background text-foreground`}>
        <ThemeProvider>
          <Header />
          <main suppressHydrationWarning className="min-h-[calc(100vh-3.5rem)]">{children}</main>
        </ThemeProvider>
      </body>
    </html>
  );
}
