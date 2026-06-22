import { redirect } from "next/navigation";
import type { Metadata } from "next";
import { getVerseDetail } from "@/lib/api";

interface Props {
  params: Promise<{ slug: string; chapter: string; verse: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug, chapter, verse } = await params;
  try {
    const data = await getVerseDetail(slug, parseInt(chapter), parseInt(verse));
    const v = data.verse;
    return {
      title: `${v.scripture} ${chapter}.${verse} — AntarDarshan`,
      description: v.text.slice(0, 160),
      alternates: {
        canonical: `/read/${slug}/${chapter}`,
      },
    };
  } catch {
    return { title: "Verse — AntarDarshan" };
  }
}

export default async function VerseDeepLinkPage({ params }: Props) {
  const { slug, chapter, verse } = await params;
  // Redirect to chapter page with hash anchor for scroll-to-verse
  redirect(`/read/${slug}/${chapter}#verse-${verse}`);
}
