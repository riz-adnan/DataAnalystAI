"use client";

import type { FormEvent } from "react";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Bot,
  Database,
  Activity,
  FileText,
  KeyRound,
  LogOut,
  MessageSquare,
  Send,
  ShieldCheck,
  Table2,
  User,
} from "lucide-react";
import ApiKeyModal from "@/components/ApiKeyModal";
import FileUploadButton from "@/components/FileUploadButton";
import { ChartResponse, ChatQueryResponse, CsvFile, getFiles, getMe, Project, sendChatQuery } from "@/lib/api";
import { clearToken, getToken } from "@/lib/auth";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  chart?: ChartResponse | null;
  table?: Record<string, unknown>[] | null;
  followUps?: string[];
  traces?: Record<string, unknown>[];
};

function formatNumber(value: number) {
  return new Intl.NumberFormat("en").format(value);
}

function outlierCount(file: CsvFile) {
  return Object.values(file.preprocessing_report?.outliers?.columns ?? {}).reduce(
    (sum, item) => sum + item.outlier_count,
    0,
  );
}

function columnTypeCounts(file: CsvFile) {
  const inference = file.preprocessing_report?.type_inference;
  return {
    numeric: inference?.numeric_columns?.length ?? 0,
    date: inference?.date_columns?.length ?? 0,
    categorical: inference?.categorical_columns?.length ?? 0,
    text: inference?.text_columns?.length ?? 0,
  };
}

function formatCell(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return "null";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function numericValue(value: unknown) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function ChartRenderer({ chart }: { chart: ChartResponse }) {
  const yKey = chart.y_keys[0];
  const data = chart.data.slice(0, 100);
  const colors = ["#2563eb", "#16a34a", "#dc2626", "#9333ea", "#ea580c", "#0891b2", "#4f46e5", "#be123c"];

  if (data.length === 0 || !yKey) {
    return null;
  }

  return (
    <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
      <p className="font-semibold text-slate-900">{chart.title || "Chart"}</p>
      {chart.description ? <p className="mt-1 text-sm text-slate-500">{chart.description}</p> : null}
      <div className="mt-4 h-80 min-w-0">
        <ResponsiveContainer height="100%" width="100%">
          {chart.chart_type === "line" ? (
            <LineChart data={data} margin={{ bottom: 20, left: 8, right: 16, top: 8 }}>
              <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
              <XAxis dataKey={chart.x_key} tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Legend />
              {chart.y_keys.map((key, index) => (
                <Line dataKey={key} key={key} stroke={colors[index % colors.length]} strokeWidth={2} type="monotone" />
              ))}
            </LineChart>
          ) : chart.chart_type === "pie" ? (
            <PieChart>
              <Tooltip />
              <Legend />
              <Pie
                data={data.map((row) => ({ ...row, [yKey]: Math.max(numericValue(row[yKey]), 0) }))}
                dataKey={yKey}
                nameKey={chart.x_key}
                outerRadius={110}
              >
                {data.map((_, index) => (
                  <Cell fill={colors[index % colors.length]} key={`slice-${index}`} />
                ))}
              </Pie>
            </PieChart>
          ) : chart.chart_type === "scatter" ? (
            <ScatterChart margin={{ bottom: 20, left: 8, right: 16, top: 8 }}>
              <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
              <XAxis dataKey={chart.x_key} name={chart.x_key} tick={{ fontSize: 12 }} type="category" />
              <YAxis dataKey={yKey} name={yKey} tick={{ fontSize: 12 }} />
              <Tooltip cursor={{ strokeDasharray: "3 3" }} />
              <Legend />
              <Scatter data={data} fill="#2563eb" name={yKey} />
            </ScatterChart>
          ) : (
            <BarChart data={data} margin={{ bottom: 20, left: 8, right: 16, top: 8 }}>
              <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
              <XAxis dataKey={chart.x_key} tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Legend />
              {chart.y_keys.map((key, index) => (
                <Bar dataKey={key} fill={colors[index % colors.length]} key={key} radius={[4, 4, 0, 0]} />
              ))}
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
      <div className="mt-3 grid gap-1 text-xs text-slate-500 sm:grid-cols-2">
        {data.slice(0, 6).map((row, index) => (
          <p className="truncate" key={`${chart.x_key}-legend-${index}`}>
            {formatCell(row[chart.x_key])}: {formatNumber(numericValue(row[yKey]))}
          </p>
        ))}
      </div>
    </div>
  );
}

function TablePreview({ rows }: { rows: Record<string, unknown>[] }) {
  if (rows.length === 0) {
    return null;
  }
  const columns = Object.keys(rows[0]).slice(0, 8);
  return (
    <div className="mt-4 overflow-x-auto rounded-lg border border-slate-200">
      <table className="w-full min-w-max border-collapse bg-white text-left text-xs">
        <thead className="bg-slate-100 text-slate-700">
          <tr>
            {columns.map((column) => (
              <th className="border-b border-slate-200 px-3 py-2 font-semibold" key={column}>
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 10).map((row, index) => (
            <tr key={`chat-table-${index}`}>
              {columns.map((column) => (
                <td className="border-b border-slate-100 px-3 py-2" key={column}>
                  {formatCell(row[column])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ChatLayout() {
  const router = useRouter();
  const [project, setProject] = useState<Project | null>(null);
  const [files, setFiles] = useState<CsvFile[]>([]);
  const [apiKeyOpen, setApiKeyOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [question, setQuestion] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [chatError, setChatError] = useState("");
  const [openTraceMessageId, setOpenTraceMessageId] = useState<string | null>(null);
  const [showPreprocessingDetails, setShowPreprocessingDetails] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Your CSV workspace is ready. Ask a question after uploading CSV files, and I will plan deterministic analysis steps against the cleaned data.",
    },
  ]);

  const totalRows = useMemo(
    () => files.reduce((sum, file) => sum + file.row_count_before, 0),
    [files],
  );

  useEffect(() => {
    async function loadProject() {
      if (!getToken()) {
        router.replace("/");
        return;
      }

      try {
        const currentProject = await getMe();
        setProject(currentProject);
        setFiles(currentProject.csv_files ?? []);
      } catch (err) {
        clearToken();
        setError(err instanceof Error ? err.message : "Session expired");
        router.replace("/");
      } finally {
        setIsLoading(false);
      }
    }

    loadProject();
  }, [router]);

  async function refreshFiles() {
    const response = await getFiles();
    setFiles(response.files);
  }

  function handleLogout() {
    clearToken();
    router.replace("/");
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || isSending) {
      return;
    }

    setQuestion("");
    setChatError("");
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: "user", content: trimmed },
    ]);
    setIsSending(true);

    try {
      const response: ChatQueryResponse = await sendChatQuery(trimmed);
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: response.answer,
          chart: response.chart,
          table: response.table,
          followUps: response.follow_up_suggestions,
          traces: response.traces,
        },
      ]);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Chat request failed";
      setChatError(message);
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: message,
        },
      ]);
    } finally {
      setIsSending(false);
    }
  }

  if (isLoading) {
    return (
      <main className="grid min-h-screen place-items-center bg-[#f3f5f8] text-slate-600">
        Loading workspace...
      </main>
    );
  }

  return (
    <main className="flex min-h-screen bg-[#f3f5f8] text-slate-950">
      <aside className="hidden w-80 border-r border-slate-200 bg-[#101827] p-5 text-white lg:flex lg:flex-col">
        <div className="flex items-center gap-3">
          <div className="grid size-10 place-items-center rounded-lg bg-blue-500">
            <Database className="size-5" />
          </div>
          <div className="min-w-0">
            <p className="text-xs uppercase tracking-wide text-slate-400">Project</p>
            <h1 className="truncate text-xl font-semibold">{project?.project_name}</h1>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-2 gap-3">
          <div className="rounded-lg border border-white/10 bg-white/5 p-4">
            <p className="text-2xl font-semibold">{files.length}</p>
            <p className="mt-1 text-xs text-slate-400">CSV files</p>
          </div>
          <div className="rounded-lg border border-white/10 bg-white/5 p-4">
            <p className="text-2xl font-semibold">{formatNumber(totalRows)}</p>
            <p className="mt-1 text-xs text-slate-400">Total rows</p>
          </div>
        </div>

        <div className="mt-6 rounded-lg border border-white/10 bg-white/5 p-4">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <ShieldCheck className="size-4 text-blue-300" />
            Gemini key
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-400">
            {project?.use_default_gemini_key
              ? "Using default backend API key"
              : project?.has_gemini_key
                ? "Using this project's API key"
                : "No key configured"}
          </p>
        </div>

        <div className="mt-6 min-h-0 flex-1 overflow-hidden">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
            Uploaded files
          </p>
          <div className="grid max-h-[42vh] gap-2 overflow-auto pr-1">
            {files.length === 0 ? (
              <p className="rounded-lg border border-dashed border-white/15 p-4 text-sm text-slate-400">
                Upload CSV files to see row counts, columns, and preprocessing reports.
              </p>
            ) : (
              files.map((file) => (
                <div className="rounded-lg border border-white/10 bg-white/5 p-3" key={file.file_id}>
                  <div className="flex items-center gap-2">
                    <FileText className="size-4 shrink-0 text-blue-300" />
                    <p className="truncate text-sm font-semibold" title={file.original_name}>
                      {file.original_name}
                    </p>
                  </div>
                  <p className="mt-2 text-xs text-slate-400">
                    {formatNumber(file.row_count_before)} to {formatNumber(file.row_count_after)} rows
                    {" | "}
                    {file.preprocessing_report?.columns_count ?? file.columns.length} columns
                  </p>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="sticky bottom-0 mt-5 bg-[#101827] pt-3">
          <button
            className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-lg border border-white/10 text-sm font-semibold text-slate-200 hover:bg-white/10"
            type="button"
            onClick={handleLogout}
          >
            <LogOut className="size-4" />
            Logout
          </button>
        </div>
      </aside>

      <section className="flex min-w-0 flex-1 flex-col">
        <header className="border-b border-slate-200 bg-white px-5 py-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-slate-500">Workspace</p>
              <h2 className="truncate text-2xl font-semibold">
                {project?.project_name}
              </h2>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <FileUploadButton
                onUploaded={async (uploadedFiles) => {
                  if (uploadedFiles.length > 0) {
                    await refreshFiles();
                  }
                }}
              />
              <button
                className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                type="button"
                onClick={() => setShowPreprocessingDetails((current) => !current)}
              >
                <FileText className="size-4" />
                {showPreprocessingDetails ? "Hide file pre-processing details" : "Show file pre-processing details"}
              </button>
              <button
                className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                type="button"
                onClick={() => setApiKeyOpen(true)}
              >
                <KeyRound className="size-4" />
                Change API key
              </button>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {files.length === 0 ? (
              <span className="rounded-full bg-slate-100 px-3 py-1 text-sm text-slate-500">
                No CSV files uploaded
              </span>
            ) : (
              files.map((file) => (
                <span
                  className="inline-flex max-w-64 items-center gap-2 truncate rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-sm text-slate-700"
                  key={file.file_id}
                  title={file.original_name}
                >
                  <Table2 className="size-3.5 shrink-0 text-blue-700" />
                  <span className="truncate">{file.original_name}</span>
                </span>
              ))
            )}
          </div>
        </header>

        {error ? (
          <div className="border-b border-red-200 bg-red-50 px-5 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        <div className="flex-1 overflow-auto px-5 pb-48 pt-8">
          <div className="mx-auto grid max-w-4xl gap-5">
            {messages.map((message) => (
              <div className="flex gap-3" key={message.id}>
                <div
                  className={`grid size-9 shrink-0 place-items-center rounded-lg text-white ${
                    message.role === "user" ? "bg-slate-800" : "bg-blue-700"
                  }`}
                >
                  {message.role === "user" ? <User className="size-4" /> : <Bot className="size-4" />}
                </div>
                <div
                  className={`min-w-0 flex-1 rounded-lg border p-5 shadow-sm ${
                    message.role === "user"
                      ? "border-slate-300 bg-slate-900 text-white"
                      : "border-slate-200 bg-white text-slate-900"
                  }`}
                >
                  <p className="whitespace-pre-wrap text-sm leading-6">{message.content}</p>
                  {message.chart ? <ChartRenderer chart={message.chart} /> : null}
                  {message.table ? <TablePreview rows={message.table} /> : null}
                  {message.followUps && message.followUps.length > 0 ? (
                    <div className="mt-4 flex flex-wrap gap-2">
                      {message.followUps.slice(0, 4).map((item) => (
                        <span
                          className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-600"
                          key={item}
                        >
                          {item}
                        </span>
                      ))}
                    </div>
                  ) : null}
                  {message.role === "assistant" && message.traces && message.traces.length > 0 ? (
                    <div className="mt-4">
                      <button
                        className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-3 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                        type="button"
                        onClick={() =>
                          setOpenTraceMessageId((current) => (current === message.id ? null : message.id))
                        }
                      >
                        <Activity className="size-3.5" />
                        {openTraceMessageId === message.id ? "Hide traces" : "View traces"}
                      </button>

                      {openTraceMessageId === message.id ? (
                        <div className="mt-3 max-h-96 overflow-auto rounded-lg border border-slate-200 bg-slate-950 p-4 text-xs text-slate-100">
                          <pre className="whitespace-pre-wrap break-words">
                            {JSON.stringify(message.traces, null, 2)}
                          </pre>
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              </div>
            ))}

            {isSending ? (
              <div className="flex gap-3">
                <div className="grid size-9 shrink-0 place-items-center rounded-lg bg-blue-700 text-white">
                  <MessageSquare className="size-4" />
                </div>
                <div className="rounded-lg border border-slate-200 bg-white p-5 text-sm text-slate-500 shadow-sm">
                  Planning analysis...
                </div>
              </div>
            ) : null}

            {chatError ? (
              <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                {chatError}
              </div>
            ) : null}

            {showPreprocessingDetails && files.length > 0 ? (
              <div className="grid gap-3 md:grid-cols-2">
                {files.map((file) => {
                  const report = file.preprocessing_report;
                  const typeCounts = columnTypeCounts(file);
                  const missingColumns = Object.entries(report?.missing_values?.columns ?? {});
                  const conversions = Object.entries(report?.type_conversions ?? {});
                  const outliers = Object.entries(report?.outliers?.columns ?? {});
                  const schemaPreview = file.schema_preview;

                  return (
                    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm" key={file.file_id}>
                      <div className="flex items-center gap-2">
                        <FileText className="size-4 shrink-0 text-blue-700" />
                        <p className="truncate font-semibold" title={file.original_name}>
                          {file.original_name}
                        </p>
                      </div>

                      <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
                        <div className="rounded-md bg-slate-50 p-3">
                          <p className="font-semibold">
                            {formatNumber(file.row_count_before)} to {formatNumber(file.row_count_after)}
                          </p>
                          <p className="text-slate-500">Rows before/after</p>
                        </div>
                        <div className="rounded-md bg-slate-50 p-3">
                          <p className="font-semibold">{report?.columns_count ?? file.columns.length}</p>
                          <p className="text-slate-500">Columns</p>
                        </div>
                        <div className="rounded-md bg-slate-50 p-3">
                          <p className="font-semibold">
                            {formatNumber(report?.missing_values?.total_missing ?? 0)}
                          </p>
                          <p className="text-slate-500">Missing handled</p>
                        </div>
                        <div className="rounded-md bg-slate-50 p-3">
                          <p className="font-semibold">
                            {formatNumber(report?.duplicates_removed ?? 0)}
                          </p>
                          <p className="text-slate-500">Duplicates removed</p>
                        </div>
                        <div className="rounded-md bg-slate-50 p-3">
                          <p className="font-semibold">{typeCounts.numeric}</p>
                          <p className="text-slate-500">Numeric columns</p>
                        </div>
                        <div className="rounded-md bg-slate-50 p-3">
                          <p className="font-semibold">{typeCounts.date}</p>
                          <p className="text-slate-500">Date columns</p>
                        </div>
                        <div className="rounded-md bg-slate-50 p-3">
                          <p className="font-semibold">{formatNumber(outlierCount(file))}</p>
                          <p className="text-slate-500">Outliers capped</p>
                        </div>
                        <div className="rounded-md bg-slate-50 p-3">
                          <p className="font-semibold">{typeCounts.categorical + typeCounts.text}</p>
                          <p className="text-slate-500">Category/text columns</p>
                        </div>
                      </div>

                      <details className="mt-4 rounded-lg border border-slate-200 bg-white p-3 text-sm">
                        <summary className="cursor-pointer font-semibold text-slate-700">
                          Schema Preview
                        </summary>

                        <div className="mt-4 grid gap-4 text-slate-600">
                          <section>
                            <p className="font-semibold text-slate-800">CSV name</p>
                            <p className="mt-1">{schemaPreview?.csv_name ?? file.original_name}</p>
                          </section>

                          <section>
                            <p className="font-semibold text-slate-800">Column names</p>
                            <div className="mt-2 flex flex-wrap gap-2">
                              {(schemaPreview?.columns ?? file.columns).map((column) => (
                                <span
                                  className="rounded-full border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-700"
                                  key={column}
                                >
                                  {column}
                                </span>
                              ))}
                            </div>
                          </section>

                          <section>
                            <p className="font-semibold text-slate-800">First 2 rows</p>
                            {(schemaPreview?.sample_rows ?? []).length === 0 ? (
                              <p className="mt-1">No rows available.</p>
                            ) : (
                              <div className="mt-2 overflow-x-auto rounded-lg border border-slate-200">
                                <table className="w-full min-w-max border-collapse text-left text-xs">
                                  <thead className="bg-slate-100 text-slate-700">
                                    <tr>
                                      {(schemaPreview?.columns ?? file.columns).map((column) => (
                                        <th className="border-b border-slate-200 px-3 py-2 font-semibold" key={column}>
                                          {column}
                                        </th>
                                      ))}
                                    </tr>
                                  </thead>
                                  <tbody className="bg-white">
                                    {(schemaPreview?.sample_rows ?? []).map((row, rowIndex) => (
                                      <tr key={`${file.file_id}-preview-${rowIndex}`}>
                                        {(schemaPreview?.columns ?? file.columns).map((column) => (
                                          <td className="border-b border-slate-100 px-3 py-2" key={column}>
                                            {formatCell(row[column])}
                                          </td>
                                        ))}
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            )}
                          </section>
                        </div>
                      </details>

                      <details className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
                        <summary className="cursor-pointer font-semibold text-slate-700">
                          View preprocessing details
                        </summary>

                        <div className="mt-4 grid gap-4 text-slate-600">
                          <section>
                            <p className="font-semibold text-slate-800">Missing values by column</p>
                            {missingColumns.length === 0 ? (
                              <p className="mt-1">No missing values detected.</p>
                            ) : (
                              <div className="mt-2 grid gap-1">
                                {missingColumns.map(([column, detail]) => (
                                  <p key={column}>
                                    {column}: {detail.missing_count} missing ({detail.missing_percentage}%), strategy {detail.strategy}
                                  </p>
                                ))}
                              </div>
                            )}
                          </section>

                          <section>
                            <p className="font-semibold text-slate-800">Detected column types</p>
                            <div className="mt-2 grid gap-1">
                              <p>Numeric: {report?.type_inference?.numeric_columns?.join(", ") || "None"}</p>
                              <p>Date: {report?.type_inference?.date_columns?.join(", ") || "None"}</p>
                              <p>Categorical: {report?.type_inference?.categorical_columns?.join(", ") || "None"}</p>
                              <p>Text: {report?.type_inference?.text_columns?.join(", ") || "None"}</p>
                            </div>
                          </section>

                          <section>
                            <p className="font-semibold text-slate-800">Type conversions</p>
                            {conversions.length === 0 ? (
                              <p className="mt-1">No type conversions were needed.</p>
                            ) : (
                              <div className="mt-2 grid gap-1">
                                {conversions.map(([column, detail]) => (
                                  <p key={column}>
                                    {column}: {detail.from} to {detail.to}, failed values {detail.failed_values}
                                  </p>
                                ))}
                              </div>
                            )}
                          </section>

                          <section>
                            <p className="font-semibold text-slate-800">Outlier details</p>
                            {outliers.length === 0 ? (
                              <p className="mt-1">No outliers were capped.</p>
                            ) : (
                              <div className="mt-2 grid gap-1">
                                {outliers.map(([column, detail]) => (
                                  <p key={column}>
                                    {column}: {detail.outlier_count} capped with {detail.method} ({detail.lower_bound} to {detail.upper_bound})
                                  </p>
                                ))}
                              </div>
                            )}
                          </section>

                          <section>
                            <p className="font-semibold text-slate-800">Cleaning summary</p>
                            <ul className="mt-2 grid gap-1">
                              {(report?.cleaning_summary ?? []).map((item) => (
                                <li key={item}>{item}</li>
                              ))}
                            </ul>
                          </section>
                        </div>
                      </details>
                    </div>
                  );
                })}
              </div>
            ) : null}
          </div>
        </div>

        <footer className="fixed bottom-0 left-0 right-0 border-t border-slate-200 bg-white/95 px-5 py-4 shadow-[0_-8px_30px_rgba(15,23,42,0.08)] backdrop-blur lg:left-80">
          <form className="mx-auto flex max-w-4xl items-end gap-3" onSubmit={handleSubmit}>
            <textarea
              className="h-24 min-w-0 flex-1 resize-none rounded-lg border border-slate-300 bg-slate-50 px-4 py-3 text-slate-900 outline-none focus:border-blue-500 focus:bg-white"
              disabled={isSending}
              placeholder={
                files.length === 0
                  ? "Upload CSV files before asking a question."
                  : "Ask a question like: Show revenue by category"
              }
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
            />
            <button
              className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-blue-700 px-4 text-sm font-semibold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:bg-slate-300"
              disabled={isSending || files.length === 0 || !question.trim()}
              type="submit"
            >
              <Send className="size-4" />
              Send
            </button>
          </form>
          <div className="mx-auto mt-3 flex max-w-4xl flex-wrap items-center justify-center gap-2 text-xs text-slate-500">
            <span>Built by Adnan Rizvi</span>
            <span aria-hidden="true">|</span>
            <a
              className="font-semibold text-blue-700 hover:text-blue-800"
              href="https://adnanrizvi.netlify.app/"
              rel="noreferrer"
              target="_blank"
            >
              Portfolio
            </a>
            <span aria-hidden="true">|</span>
            <a
              className="font-semibold text-blue-700 hover:text-blue-800"
              href="https://github.com/riz-adnan/DataAnalystAI"
              rel="noreferrer"
              target="_blank"
            >
              Documentation
            </a>
          </div>
        </footer>
      </section>

      <ApiKeyModal
        open={apiKeyOpen}
        onClose={() => setApiKeyOpen(false)}
        onSaved={(updatedProject) => {
          setProject(updatedProject);
          setFiles(updatedProject.csv_files ?? []);
        }}
      />
    </main>
  );
}
