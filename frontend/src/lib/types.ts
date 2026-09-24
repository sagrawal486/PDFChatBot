export interface User {
  id: number;
  name: string;
  email: string;
}

export type DocumentStatus = "uploaded" | "processing" | "ready" | "failed";

export interface Document {
  id: number;
  file_name: string;
  status: DocumentStatus;
  created_at: string;
}

export interface Citation {
  document_id: number;
  chunk_index: number;
  page_number: number | null;
  score: number;
  excerpt: string;
}

export interface QuestionResponse {
  answer: string;
  citations: Citation[];
}

export interface ChatTurn {
  question: string;
  response: QuestionResponse;
}
