"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/lib/auth-context";

export default function Home() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && user) router.replace("/documents");
  }, [loading, user, router]);

  if (loading || user) return null;

  return (
    <div className="flex flex-col items-center gap-6 py-16 text-center">
      <h1 className="text-3xl font-bold tracking-tight">AI PDF Chatbot</h1>
      <p className="max-w-md text-slate-600">
        Upload a PDF, then ask questions about it. Answers are grounded in your
        document and cite the exact page they came from.
      </p>
      <div className="flex gap-3">
        <Link
          href="/login"
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
        >
          Log in
        </Link>
        <Link
          href="/register"
          className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-900 hover:bg-slate-100"
        >
          Create an account
        </Link>
      </div>
    </div>
  );
}
