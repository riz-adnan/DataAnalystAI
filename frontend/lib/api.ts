import { getToken } from "@/lib/auth";

export type CsvFile = {
  file_id: string;
  original_name: string;
  original_supabase_path?: string | null;
  cleaned_supabase_path?: string | null;
  uploaded_at: string;
  row_count?: number | null;
  row_count_before: number;
  row_count_after: number;
  columns: string[];
  schema: Record<string, string>;
  schema_preview: SchemaPreview;
  sample_rows: Record<string, unknown>[];
  preprocessing_report: PreprocessingReport;
};

export type SchemaPreview = {
  csv_name: string;
  columns: string[];
  sample_rows: Record<string, unknown>[];
};

export type PreprocessingReport = {
  rows_before: number;
  rows_after: number;
  columns_count: number;
  duplicates_removed: number;
  missing_values: {
    total_missing: number;
    columns: Record<
      string,
      {
        missing_count: number;
        missing_percentage: number;
        strategy: string;
      }
    >;
  };
  type_inference: {
    date_columns: string[];
    numeric_columns: string[];
    categorical_columns: string[];
    text_columns: string[];
  };
  type_conversions: Record<
    string,
    {
      from: string;
      to: string;
      failed_values: number;
    }
  >;
  outliers: {
    columns: Record<
      string,
      {
        method: string;
        outlier_count: number;
        lower_bound: number;
        upper_bound: number;
        strategy: string;
      }
    >;
  };
  cleaning_summary: string[];
};

export type UploadCsvError = {
  original_name: string;
  error: string;
};

export type UploadCsvMetrics = {
  requested_count: number;
  uploaded_count: number;
  failed_count: number;
  total_rows_before: number;
  total_rows_after: number;
  total_rows: number;
  total_cleaned_rows: number;
  duplicates_removed: number;
};

export type Project = {
  id: string;
  project_name: string;
  has_gemini_key: boolean;
  use_default_gemini_key: boolean;
  csv_files: CsvFile[];
  created_at: string;
  updated_at: string;
};

export type ChartResponse = {
  chart_type: "bar" | "line" | "pie" | "scatter";
  title: string;
  description?: string;
  x_key: string;
  y_keys: string[];
  data: Record<string, unknown>[];
};

export type ChatQueryResponse = {
  success: boolean;
  answer: string;
  response_type: "text" | "chart" | "chart_and_text" | "table";
  chart?: ChartResponse | null;
  table?: Record<string, unknown>[] | null;
  follow_up_suggestions?: string[];
  traces: Record<string, unknown>[];
};

export type LoginResponse = {
  access_token: string;
  token_type: "bearer";
  project: Project;
};

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

async function parseResponse<T>(response: Response): Promise<T> {
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const detail = typeof data.detail === "string" ? data.detail : "Request failed";
    throw new Error(detail);
  }

  return data as T;
}

function authHeaders(): HeadersInit {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function createProject(payload: {
  project_name: string;
  password: string;
  gemini_key: string | null;
  use_default_gemini_key: boolean;
}): Promise<LoginResponse> {
  const response = await fetch(`${API_URL}/projects/create`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseResponse<LoginResponse>(response);
}

export async function loginProject(payload: {
  project_name: string;
  password: string;
}): Promise<LoginResponse> {
  const response = await fetch(`${API_URL}/projects/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseResponse<LoginResponse>(response);
}

export async function getMe(): Promise<Project> {
  const response = await fetch(`${API_URL}/projects/me`, {
    headers: authHeaders(),
  });
  return parseResponse<Project>(response);
}

export async function updateApiKey(payload: {
  gemini_key: string | null;
  use_default_gemini_key: boolean;
}): Promise<Project> {
  const response = await fetch(`${API_URL}/projects/api-key`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(payload),
  });
  return parseResponse<Project>(response);
}

export async function uploadCsv(files: FileList): Promise<{
  files: CsvFile[];
  uploaded_count: number;
  metrics: UploadCsvMetrics;
  errors: UploadCsvError[];
}> {
  const formData = new FormData();
  Array.from(files).forEach((file) => formData.append("files", file));

  const response = await fetch(`${API_URL}/projects/upload-csv`, {
    method: "POST",
    headers: authHeaders(),
    body: formData,
  });

  return parseResponse<{
    files: CsvFile[];
    uploaded_count: number;
    metrics: UploadCsvMetrics;
    errors: UploadCsvError[];
  }>(response);
}

export async function getFiles(): Promise<{ files: CsvFile[] }> {
  const response = await fetch(`${API_URL}/projects/files`, {
    headers: authHeaders(),
  });
  return parseResponse<{ files: CsvFile[] }>(response);
}

export async function sendChatQuery(question: string): Promise<ChatQueryResponse> {
  const response = await fetch(`${API_URL}/chat/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ question }),
  });
  return parseResponse<ChatQueryResponse>(response);
}
