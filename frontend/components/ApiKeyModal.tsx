"use client";

import { FormEvent, useState } from "react";
import { KeyRound, Loader2, ShieldCheck, X } from "lucide-react";
import { Project, updateApiKey } from "@/lib/api";

type Props = {
  open: boolean;
  onClose: () => void;
  onSaved: (project: Project) => void;
};

export default function ApiKeyModal({ open, onClose, onSaved }: Props) {
  const [apiKey, setApiKey] = useState("");
  const [useDefault, setUseDefault] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");

  if (!open) {
    return null;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSaving(true);
    setError("");

    try {
      const project = await updateApiKey({
        gemini_key: useDefault ? null : apiKey || null,
        use_default_gemini_key: useDefault,
      });
      onSaved(project);
      setApiKey("");
      setUseDefault(false);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update API key");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/40 px-4 backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wide text-blue-700">
              Gemini settings
            </p>
            <h2 className="mt-1 text-2xl font-semibold">Change API key</h2>
            <p className="mt-2 text-sm leading-6 text-slate-500">
              Save a project Gemini key or switch this workspace to the default
              backend key.
            </p>
          </div>
          <button
            className="grid size-9 place-items-center rounded-lg text-slate-500 hover:bg-slate-100"
            type="button"
            onClick={onClose}
            aria-label="Close"
          >
            <X className="size-4" />
          </button>
        </div>

        <form className="mt-6 grid gap-4" onSubmit={handleSubmit}>
          <div className="grid gap-2">
            <label className="text-sm font-semibold text-slate-700">
              New Gemini API key
            </label>
            <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
              <div className="flex items-center gap-3 rounded-lg border border-slate-300 px-3 transition focus-within:border-blue-600">
                <KeyRound className="size-4 text-slate-400" />
                <input
                  className="h-12 min-w-0 flex-1 outline-none disabled:bg-white disabled:text-slate-400"
                  disabled={useDefault}
                  value={apiKey}
                  onChange={(event) => setApiKey(event.target.value)}
                  placeholder="Paste key"
                />
              </div>
              <button
                className={`inline-flex h-12 items-center justify-center gap-2 rounded-lg border px-4 text-sm font-semibold transition ${
                  useDefault
                    ? "border-blue-700 bg-blue-50 text-blue-700"
                    : "border-slate-300 text-slate-700 hover:bg-slate-50"
                }`}
                type="button"
                onClick={() => setUseDefault((current) => !current)}
              >
                <ShieldCheck className="size-4" />
                Use our API
              </button>
            </div>
          </div>

          {error ? (
            <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </p>
          ) : null}

          <div className="flex justify-end gap-3 pt-2">
            <button
              className="rounded-lg border border-slate-300 px-4 py-2 font-semibold text-slate-700 hover:bg-slate-50"
              type="button"
              onClick={onClose}
            >
              Cancel
            </button>
            <button
              className="inline-flex items-center gap-2 rounded-lg bg-blue-700 px-4 py-2 font-semibold text-white hover:bg-blue-800 disabled:opacity-60"
              disabled={isSaving}
              type="submit"
            >
              {isSaving ? <Loader2 className="size-4 animate-spin" /> : null}
              {isSaving ? "Saving..." : "Save"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

