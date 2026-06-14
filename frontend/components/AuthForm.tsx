"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Database, ExternalLink, KeyRound, Loader2, Lock, ShieldCheck, Sparkles } from "lucide-react";
import { createProject, loginProject } from "@/lib/api";
import { setToken } from "@/lib/auth";

type Mode = "create" | "login";

export default function AuthForm() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("create");
  const [projectName, setProjectName] = useState("");
  const [password, setPassword] = useState("");
  const [geminiKey, setGeminiKey] = useState("");
  const [useDefaultKey, setUseDefaultKey] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);

    try {
      const response =
        mode === "create"
          ? await createProject({
              project_name: projectName,
              password,
              gemini_key: useDefaultKey ? null : geminiKey || null,
              use_default_gemini_key: useDefaultKey,
            })
          : await loginProject({ project_name: projectName, password });

      setToken(response.access_token);
      router.push("/chat");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#f3f5f8] px-6 py-8 text-slate-950">
      <section className="mx-auto grid min-h-[calc(100vh-64px)] max-w-7xl overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm lg:grid-cols-[1.08fr_0.92fr]">
        <div className="flex flex-col justify-between bg-[#101827] p-8 text-white lg:p-10">
          <div>
            <div className="flex items-center gap-3">
              <div className="grid size-10 place-items-center rounded-lg bg-blue-500">
                <Database className="size-5" />
              </div>
              <div>
                <p className="text-sm font-semibold text-blue-100">DataAnalyst AI</p>
                <p className="text-xs text-slate-400">Project-based CSV intelligence</p>
              </div>
            </div>

            <div className="mt-20 max-w-2xl">
              <p className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-sm text-blue-100">
                <Sparkles className="size-4" />
                Secure workspaces, no email accounts
              </p>
              <h1 className="mt-6 text-5xl font-semibold leading-tight lg:text-6xl">
                Start with a project. Upload CSVs. Analyze next.
              </h1>
              <p className="mt-5 max-w-xl text-lg leading-8 text-slate-300">
                Create a shared project login, choose a Gemini key strategy, and
                keep every dataset tied to that workspace.
              </p>
            </div>
          </div>

          <div className="mt-12 grid gap-3 sm:grid-cols-3">
            {[
              ["bcrypt", "Passwords are hashed"],
              ["JWT", "Project sessions"],
              ["CSV", "Schema previews"],
            ].map(([label, text]) => (
              <div className="rounded-lg border border-white/10 bg-white/5 p-4" key={label}>
                <p className="text-sm font-semibold text-white">{label}</p>
                <p className="mt-1 text-sm text-slate-400">{text}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="flex items-center p-6 lg:p-10">
          <div className="w-full">
            <div className="mb-6">
              <h2 className="text-3xl font-semibold">
                {mode === "create" ? "Create project" : "Login project"}
              </h2>
              <p className="mt-2 text-sm leading-6 text-slate-500">
                Use the project name and password. No user email auth.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-2 rounded-lg bg-slate-100 p-1">
              <button
                className={`rounded-md px-4 py-2.5 text-sm font-semibold transition ${
                  mode === "create" ? "bg-white text-slate-950 shadow-sm" : "text-slate-600 hover:text-slate-950"
                }`}
                type="button"
                onClick={() => setMode("create")}
              >
                Create Project
              </button>
              <button
                className={`rounded-md px-4 py-2.5 text-sm font-semibold transition ${
                  mode === "login" ? "bg-white text-slate-950 shadow-sm" : "text-slate-600 hover:text-slate-950"
                }`}
                type="button"
                onClick={() => setMode("login")}
              >
                Login Project
              </button>
            </div>

            <form className="mt-6 grid gap-4" onSubmit={handleSubmit}>
              <label className="grid gap-2 text-sm font-semibold text-slate-700">
                Project name
                <div className="flex items-center gap-3 rounded-lg border border-slate-300 px-3 transition focus-within:border-blue-600">
                  <Database className="size-4 text-slate-400" />
                  <input
                    className="h-12 min-w-0 flex-1 outline-none"
                    value={projectName}
                    onChange={(event) => setProjectName(event.target.value)}
                    required
                  />
                </div>
              </label>

              <label className="grid gap-2 text-sm font-semibold text-slate-700">
                Password
                <div className="flex items-center gap-3 rounded-lg border border-slate-300 px-3 transition focus-within:border-blue-600">
                  <Lock className="size-4 text-slate-400" />
                  <input
                    className="h-12 min-w-0 flex-1 outline-none"
                    type="password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    required
                  />
                </div>
              </label>

              {mode === "create" ? (
                <div className="grid gap-2">
                  <label className="text-sm font-semibold text-slate-700">
                    Gemini API key
                  </label>
                  <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
                    <div className="flex items-center gap-3 rounded-lg border border-slate-300 px-3 transition focus-within:border-blue-600">
                      <KeyRound className="size-4 text-slate-400" />
                      <input
                        className="h-12 min-w-0 flex-1 outline-none disabled:bg-white disabled:text-slate-400"
                        disabled={useDefaultKey}
                        value={geminiKey}
                        onChange={(event) => setGeminiKey(event.target.value)}
                        placeholder="Optional"
                      />
                    </div>
                    <button
                      className={`inline-flex h-12 items-center justify-center gap-2 rounded-lg border px-4 text-sm font-semibold transition ${
                        useDefaultKey
                          ? "border-blue-700 bg-blue-50 text-blue-700"
                          : "border-slate-300 text-slate-700 hover:bg-slate-50"
                      }`}
                      type="button"
                      onClick={() => setUseDefaultKey((current) => !current)}
                    >
                      <ShieldCheck className="size-4" />
                      Use our key
                    </button>
                  </div>
                  <a
                    className="inline-flex w-fit items-center gap-2 text-sm font-semibold text-blue-700 hover:text-blue-800"
                    href="https://aistudio.google.com/app/apikey"
                    rel="noreferrer"
                    target="_blank"
                  >
                    <ExternalLink className="size-4" />
                    How to get Gemini API keys
                  </a>
                  <p className="text-sm leading-6 text-slate-500">
                    If you are using this for testing, you can use our keys. If you
                    are using it in production, please use your own key.
                  </p>
                </div>
              ) : null}

              {error ? (
                <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                  {error}
                </p>
              ) : null}

              <button
                className="inline-flex h-12 items-center justify-center gap-2 rounded-lg bg-blue-700 font-semibold text-white transition hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={isSubmitting}
                type="submit"
              >
                {isSubmitting ? <Loader2 className="size-4 animate-spin" /> : null}
                {isSubmitting
                  ? "Please wait..."
                  : mode === "create"
                    ? "Create Project"
                    : "Login"}
                {!isSubmitting ? <ArrowRight className="size-4" /> : null}
              </button>
            </form>
          </div>
        </div>
      </section>
      <footer className="mx-auto mt-4 flex max-w-7xl flex-wrap items-center justify-center gap-2 text-xs text-slate-500">
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
      </footer>
    </main>
  );
}
