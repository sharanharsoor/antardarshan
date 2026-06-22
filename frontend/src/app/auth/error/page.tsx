import Link from "next/link";

export default function AuthError() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[50vh] text-center px-4">
      <h1 className="font-serif text-2xl font-bold mb-3">Sign in failed</h1>
      <p className="text-muted mb-6">Something went wrong during sign in. Please try again.</p>
      <Link href="/" className="rounded-lg bg-accent px-6 py-2 text-sm text-white hover:bg-accent-hover">
        Back to home
      </Link>
    </div>
  );
}
