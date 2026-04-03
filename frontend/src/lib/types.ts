export interface IngestionTask {
  id: string;
  status: "pending" | "processing" | "completed" | "error" | "skipped";
  progress: number;
  message: string;
  created_at: string;
  document_id?: string;
  filename?: string;
  metadata?: any;
}
