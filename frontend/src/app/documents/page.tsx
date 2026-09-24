"use client";

import { useEffect, useRef, useState } from "react";

import * as api from "@/lib/api";
import { ApiError } from "@/lib/api";
import AuthGuard from "@/components/AuthGuard";
import StatusBadge from "@/components/StatusBadge";
import type { Document } from "@/lib/types";

const POLL_INTERVAL_MS = 3000;

function DocumentsPageContent() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let ignore = false;

    async function load() {
      try {
        const docs = await api.listDocuments();
        if (!ignore) setDocuments(docs);
      } catch (err) {
        if (!ignore) {
          setError(err instanceof ApiError ? err.message : "Could not load documents.");
        }
      } finally {
        if (!ignore) setLoading(false);
      }
    }

    load();
    return () => {
      ignore = true;
    };
  }, []);

  // Poll while any document is still uploaded/processing.
  useEffect(() => {
    const pending = documents.filter((d) => d.status === "uploaded" || d.status === "processing");
    if (pending.length === 0) return;

    const interval = setInterval(async () => {
      const updates = await Promise.all(
        pending.map((d) => api.getDocument(d.id).catch(() => null)),
      );
      setDocuments((prev) =>
        prev.map((doc) => updates.find((u) => u && u.id === doc.id) ?? doc),
      );
    }, POLL_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [documents]);

  async function handleUpload(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setError(null);
    setUploading(true);
    try {
      const created = await api.uploadDocument(file);
      setDocuments((prev) => [created, ...prev]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("Delete this document? This can't be undone.")) return;
    try {
      await api.deleteDocument(id);
      setDocuments((prev) => prev.filter((d) => d.id !== id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not delete document.");
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Documents</h1>
        <label className="cursor-pointer rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800">
          {uploading ? "Uploading…" : "Upload PDF"}
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf"
            onChange={handleUpload}
            disabled={uploading}
            className="hidden"
          />
        </label>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {loading ? (
        <p className="text-sm text-slate-500">Loading…</p>
      ) : documents.length === 0 ? (
        <p className="rounded-lg border border-dashed border-slate-300 py-12 text-center text-sm text-slate-500">
          No documents yet. Upload a PDF to get started.
        </p>
      ) : (
        <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
          {documents.map((doc) => (
            <li key={doc.id} className="flex items-center justify-between gap-4 px-4 py-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-slate-900">{doc.file_name}</p>
                <p className="text-xs text-slate-400">
                  {new Date(doc.created_at).toLocaleString()}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <StatusBadge status={doc.status} />
                <button
                  onClick={() => handleDelete(doc.id)}
                  className="text-sm text-slate-400 hover:text-red-600"
                  aria-label={`Delete ${doc.file_name}`}
                >
                  Delete
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function DocumentsPage() {
  return (
    <AuthGuard>
      <DocumentsPageContent />
    </AuthGuard>
  );
}
