import type { Citation } from "@/lib/types";

export default function CitationList({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null;

  return (
    <details className="mt-2 text-xs text-slate-500">
      <summary className="cursor-pointer select-none font-medium text-slate-600 hover:text-slate-900">
        {citations.length} source{citations.length === 1 ? "" : "s"}
      </summary>
      <ul className="mt-2 flex flex-col gap-2">
        {citations.map((c, i) => (
          <li key={`${c.document_id}-${c.chunk_index}-${i}`} className="rounded-md bg-slate-50 p-2">
            <div className="mb-1 flex items-center gap-2 font-medium text-slate-600">
              <span>Document #{c.document_id}</span>
              {c.page_number != null && <span>· page {c.page_number}</span>}
              <span className="text-slate-400">· score {c.score.toFixed(2)}</span>
            </div>
            <p className="line-clamp-3 text-slate-500">{c.excerpt}</p>
          </li>
        ))}
      </ul>
    </details>
  );
}
