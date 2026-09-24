"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

import * as api from "@/lib/api";
import { ApiError } from "@/lib/api";
import AuthGuard from "@/components/AuthGuard";
import CitationList from "@/components/CitationList";
import type { ChatTurn } from "@/lib/types";

function ChatPageContent() {
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || sending) return;

    setSending(true);
    setError(null);
    try {
      const response = await api.askQuestion(trimmed);
      setTurns((prev) => [...prev, { question: trimmed, response }]);
      setQuestion("");
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        setError("You've reached today's question limit. Try again tomorrow.");
      } else if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Something went wrong. Try again.");
      }
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold">Chat</h1>
      <p className="text-sm text-slate-500">
        Ask a question about any of your uploaded documents.
      </p>

      <div className="flex min-h-[24rem] flex-col gap-4 rounded-lg border border-slate-200 bg-white p-4">
        {turns.length === 0 ? (
          <p className="m-auto text-sm text-slate-400">No questions yet — ask one below.</p>
        ) : (
          turns.map((turn, i) => (
            <div key={i} className="flex flex-col gap-2">
              <div className="self-end rounded-lg bg-slate-900 px-3 py-2 text-sm text-white">
                {turn.question}
              </div>
              <div className="self-start rounded-lg bg-slate-100 px-3 py-2 text-sm text-slate-900">
                <p className="whitespace-pre-wrap">{turn.response.answer}</p>
                <CitationList citations={turn.response.citations} />
              </div>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question about your documents…"
          disabled={sending}
          className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
        />
        <button
          type="submit"
          disabled={sending || !question.trim()}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          {sending ? "Asking…" : "Ask"}
        </button>
      </form>
    </div>
  );
}

export default function ChatPage() {
  return (
    <AuthGuard>
      <ChatPageContent />
    </AuthGuard>
  );
}
