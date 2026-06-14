"use client";

import { ChangeEvent, useRef, useState } from "react";
import { Loader2, Upload } from "lucide-react";
import { CsvFile, UploadCsvError, UploadCsvMetrics, uploadCsv } from "@/lib/api";

type Props = {
  onUploaded: (
    files: CsvFile[],
    errors: UploadCsvError[],
    metrics: UploadCsvMetrics,
  ) => void | Promise<void>;
};

function formatNumber(value: number) {
  return new Intl.NumberFormat("en").format(value);
}

export default function FileUploadButton({ onUploaded }: Props) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState("");
  const [fileErrors, setFileErrors] = useState<UploadCsvError[]>([]);
  const [metrics, setMetrics] = useState<UploadCsvMetrics | null>(null);

  async function handleFiles(event: ChangeEvent<HTMLInputElement>) {
    const files = event.target.files;
    if (!files || files.length === 0) {
      return;
    }

    setIsUploading(true);
    setError("");
    setFileErrors([]);
    setMetrics(null);

    try {
      const response = await uploadCsv(files);
      await onUploaded(response.files, response.errors ?? [], response.metrics);
      setFileErrors(response.errors ?? []);
      setMetrics(response.metrics);
      event.target.value = "";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <div className="grid gap-2">
      <input
        ref={inputRef}
        className="hidden"
        type="file"
        accept=".csv,text/csv"
        multiple
        onChange={handleFiles}
      />
      <button
        className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-blue-700 px-4 text-sm font-semibold text-white transition hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-60"
        disabled={isUploading}
        type="button"
        onClick={() => inputRef.current?.click()}
      >
        {isUploading ? <Loader2 className="size-4 animate-spin" /> : <Upload className="size-4" />}
        {isUploading ? "Uploading..." : "Upload file"}
      </button>
      {error ? <span className="text-sm text-red-600">{error}</span> : null}
      {metrics ? (
        <div className="rounded-lg border border-blue-100 bg-blue-50 px-3 py-2 text-sm text-blue-800">
          Uploaded {metrics.uploaded_count} of {metrics.requested_count} files. Rows:{" "}
          {formatNumber(metrics.total_rows_before)} to {formatNumber(metrics.total_rows_after)}.
        </div>
      ) : null}
      {fileErrors.length > 0 ? (
        <div className="grid gap-1 text-sm text-red-600">
          {fileErrors.map((fileError) => (
            <span key={`${fileError.original_name}-${fileError.error}`}>
              {fileError.original_name}: {fileError.error}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}
