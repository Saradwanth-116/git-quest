import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useRef, useState, type FormEvent } from "react";
import ReactMarkdown from "react-markdown";

export const Route = createFileRoute("/")({
  component: App,
});

const API = "http://127.0.0.1:8000";

type Section = "ask" | "issues" | "roadmap" | "pr";

type IndexResp = { files_indexed: number; chunks_created: number };
type AskResp = { answer: string; sources: string[] };
type IssueResp = { number: number; title: string; explanation: string };
type RoadmapResp = { roadmap: string };
type PRResp = {
  checklist: {
    has_tests: boolean;
    touches_docs: boolean;
    diff_size_lines: number;
    is_large_diff: boolean;
  };
  report: string;
};

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    });
  } catch {
    throw new Error("Could not reach backend at http://127.0.0.1:8000");
  }
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      msg = body.detail || body.error || body.message || msg;
    } catch {
      // ignore
    }
    throw new Error(msg);
  }
  return (await res.json()) as T;
}

function App() {
  const [repoUrl, setRepoUrl] = useState("");
  const [indexed, setIndexed] = useState<{ url: string; stats: IndexResp } | null>(null);

  if (!indexed) {
    return <IndexScreen repoUrl={repoUrl} setRepoUrl={setRepoUrl} onIndexed={setIndexed} />;
  }

  return (
    <Workspace
      repoUrl={indexed.url}
      stats={indexed.stats}
      onChangeRepo={() => {
        setIndexed(null);
        setRepoUrl("");
      }}
    />
  );
}

/* ---------------- Landing / Index screen ---------------- */

function IndexScreen({
  repoUrl,
  setRepoUrl,
  onIndexed,
}: {
  repoUrl: string;
  setRepoUrl: (v: string) => void;
  onIndexed: (v: { url: string; stats: IndexResp }) => void;
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!repoUrl.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const stats = await apiFetch<IndexResp>("/index", {
        method: "POST",
        body: JSON.stringify({ repo_url: repoUrl.trim() }),
      });
      onIndexed({ url: repoUrl.trim(), stats });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      <TopBar />
      <main className="flex-1 flex items-center justify-center px-6 py-16">
        <div className="w-full max-w-2xl">
          <div className="mb-10">
            <div className="mono text-xs text-muted-foreground mb-3 tracking-widest uppercase">
              Open Source Mentor++
            </div>
            <h1 className="text-4xl md:text-5xl font-semibold tracking-tight leading-tight">
              Onboard to any repository,
              <br />
              <span className="text-muted-foreground">in minutes.</span>
            </h1>
            <p className="mt-4 text-muted-foreground max-w-lg">
              Index a GitHub repo, then ask questions, get issue recommendations,
              generate a learning roadmap, and check PR readiness.
            </p>
          </div>

          <form onSubmit={submit} className="space-y-3">
            <label className="mono text-xs text-muted-foreground block">
              GITHUB REPOSITORY URL
            </label>
            <div className="flex flex-col sm:flex-row gap-2">
              <input
                type="url"
                required
                placeholder="https://github.com/owner/repo"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                className="mono flex-1 px-4 py-3 rounded-md bg-input border border-border text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition"
                disabled={loading}
              />
              <button
                type="submit"
                disabled={loading}
                className="px-5 py-3 rounded-md bg-accent text-accent-foreground text-sm font-medium hover:opacity-90 disabled:opacity-50 transition inline-flex items-center justify-center gap-2 min-w-[160px]"
              >
                {loading ? (
                  <>
                    <Spinner /> Indexing…
                  </>
                ) : (
                  "Index repository"
                )}
              </button>
            </div>
            {error && <ErrorBox message={error} />}
          </form>

          <div className="mt-10 grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { k: "Ask", d: "RAG Q&A over the codebase" },
              { k: "Issues", d: "Good-first-issue picks" },
              { k: "Roadmap", d: "Personalized learning path" },
              { k: "PR Check", d: "Diff readiness report" },
            ].map((x) => (
              <div
                key={x.k}
                className="p-4 rounded-md border border-border bg-card"
              >
                <div className="mono text-xs text-accent">{x.k}</div>
                <div className="text-xs text-muted-foreground mt-1">{x.d}</div>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}

/* ---------------- Workspace ---------------- */

function Workspace({
  repoUrl,
  stats,
  onChangeRepo,
}: {
  repoUrl: string;
  stats: IndexResp;
  onChangeRepo: () => void;
}) {
  const [section, setSection] = useState<Section>("ask");
  const repoName = repoUrl.replace(/^https?:\/\/(www\.)?github\.com\//, "").replace(/\/$/, "");

  const tabs: { key: Section; label: string }[] = [
    { key: "ask", label: "Ask" },
    { key: "issues", label: "Issues" },
    { key: "roadmap", label: "Roadmap" },
    { key: "pr", label: "PR Check" },
  ];

  return (
    <div className="min-h-screen flex flex-col">
      <TopBar />
      <div className="border-b border-border">
        <div className="max-w-6xl mx-auto px-6 py-4 flex flex-wrap items-center gap-4 justify-between">
          <div className="min-w-0">
            <div className="mono text-xs text-muted-foreground">INDEXED REPOSITORY</div>
            <div className="mono text-sm text-foreground truncate mt-0.5">{repoName}</div>
            <div className="mono text-xs text-muted-foreground mt-1">
              {stats.files_indexed} files · {stats.chunks_created} chunks
            </div>
          </div>
          <button
            onClick={onChangeRepo}
            className="px-3 py-1.5 rounded-md border border-border bg-card text-xs hover:bg-muted transition mono"
          >
            ← Change repo
          </button>
        </div>
        <div className="max-w-6xl mx-auto px-6 flex gap-1">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setSection(t.key)}
              className={`px-4 py-2.5 text-sm border-b-2 -mb-px transition ${
                section === t.key
                  ? "border-accent text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <main className="flex-1">
        <div className="max-w-6xl mx-auto px-6 py-8">
          {section === "ask" && <AskPanel repoUrl={repoUrl} />}
          {section === "issues" && <IssuesPanel repoUrl={repoUrl} />}
          {section === "roadmap" && <RoadmapPanel repoUrl={repoUrl} />}
          {section === "pr" && <PRPanel />}
        </div>
      </main>
    </div>
  );
}

/* ---------------- Ask ---------------- */

type ChatMessage =
  | { role: "user"; content: string }
  | { role: "assistant"; content: string; sources: string[] }
  | { role: "error"; content: string };

function AskPanel({ repoUrl }: { repoUrl: string }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  const send = async (e: FormEvent) => {
    e.preventDefault();
    const q = input.trim();
    if (!q || loading) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: q }]);
    setLoading(true);
    try {
      const r = await apiFetch<AskResp>("/ask", {
        method: "POST",
        body: JSON.stringify({ repo_url: repoUrl, question: q }),
      });
      setMessages((m) => [...m, { role: "assistant", content: r.answer, sources: r.sources || [] }]);
    } catch (err) {
      setMessages((m) => [...m, { role: "error", content: (err as Error).message }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-260px)] min-h-[500px]">
      <div ref={scrollRef} className="flex-1 overflow-y-auto pr-2 space-y-6">
        {messages.length === 0 && (
          <div className="text-center py-16 text-muted-foreground text-sm">
            Ask anything about this repository — architecture, files, how to run it, where a
            feature lives…
          </div>
        )}
        {messages.map((m, i) => (
          <MessageBubble key={i} message={m} />
        ))}
        {loading && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Spinner /> <span className="mono text-xs">thinking…</span>
          </div>
        )}
      </div>

      <form onSubmit={send} className="mt-4 flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about this repository…"
          disabled={loading}
          className="flex-1 px-4 py-3 rounded-md bg-input border border-border text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring transition"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="px-5 py-3 rounded-md bg-accent text-accent-foreground text-sm font-medium hover:opacity-90 disabled:opacity-50 transition"
        >
          Send
        </button>
      </form>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] px-4 py-2.5 rounded-md bg-secondary text-secondary-foreground text-sm">
          {message.content}
        </div>
      </div>
    );
  }
  if (message.role === "error") {
    return <ErrorBox message={message.content} />;
  }
  return (
    <div>
      <div className="mono text-xs text-muted-foreground mb-2">ASSISTANT</div>
      <div className="prose-md text-sm">
        <ReactMarkdown>{message.content}</ReactMarkdown>
      </div>
      {message.sources.length > 0 && (
        <div className="mt-3">
          <div className="mono text-[10px] text-muted-foreground mb-1.5 tracking-widest">
            SOURCES
          </div>
          <div className="flex flex-wrap gap-1.5">
            {message.sources.map((s, i) => (
              <span
                key={i}
                className="mono text-xs px-2 py-1 rounded border border-border bg-card text-muted-foreground"
              >
                {s}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ---------------- Issues ---------------- */

function IssuesPanel({ repoUrl }: { repoUrl: string }) {
  const [issue, setIssue] = useState<IssueResp | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await apiFetch<IssueResp>(
        `/recommend-issue?repo_url=${encodeURIComponent(repoUrl)}`,
      );
      setIssue(r);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl">
      <SectionHeader
        title="Recommend an issue"
        description="Get a suggested good-first-issue based on the indexed codebase."
      />

      {!issue && !loading && (
        <button
          onClick={run}
          className="px-5 py-3 rounded-md bg-accent text-accent-foreground text-sm font-medium hover:opacity-90 transition"
        >
          Recommend an issue
        </button>
      )}

      {loading && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner /> <span className="mono text-xs">finding a good match…</span>
        </div>
      )}

      {error && !loading && <ErrorBox message={error} />}

      {issue && !loading && (
        <div className="space-y-4">
          <div className="p-6 rounded-md border border-border bg-card">
            <div className="flex items-baseline gap-3 mb-3">
              <span className="mono text-sm text-accent">#{issue.number}</span>
              <h3 className="text-lg font-semibold leading-tight">{issue.title}</h3>
            </div>
            <div className="mono text-[10px] text-muted-foreground mb-2 tracking-widest">
              WHY IT'S A GOOD START
            </div>
            <div className="prose-md text-sm">
              <ReactMarkdown>{issue.explanation}</ReactMarkdown>
            </div>
          </div>
          <button
            onClick={run}
            className="px-4 py-2 rounded-md border border-border bg-card text-sm hover:bg-muted transition"
          >
            Get another recommendation
          </button>
        </div>
      )}
    </div>
  );
}

/* ---------------- Roadmap ---------------- */

function RoadmapPanel({ repoUrl }: { repoUrl: string }) {
  const [roadmap, setRoadmap] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await apiFetch<RoadmapResp>("/roadmap", {
        method: "POST",
        body: JSON.stringify({ repo_url: repoUrl }),
      });
      setRoadmap(r.roadmap);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl">
      <SectionHeader
        title="Learning roadmap"
        description="Generate a personalized path for exploring this codebase."
      />

      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={run}
          disabled={loading}
          className="px-5 py-3 rounded-md bg-accent text-accent-foreground text-sm font-medium hover:opacity-90 disabled:opacity-50 transition inline-flex items-center gap-2"
        >
          {loading ? (
            <>
              <Spinner /> Generating…
            </>
          ) : roadmap ? (
            "Regenerate roadmap"
          ) : (
            "Generate roadmap"
          )}
        </button>
      </div>

      {error && <ErrorBox message={error} />}

      {roadmap && !loading && (
        <div className="p-6 rounded-md border border-border bg-card prose-md text-sm">
          <ReactMarkdown>{roadmap}</ReactMarkdown>
        </div>
      )}

      {loading && !roadmap && (
        <div className="space-y-2">
          <Skeleton className="h-5 w-1/3" />
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-11/12" />
          <Skeleton className="h-3 w-10/12" />
          <Skeleton className="h-5 w-1/4 mt-4" />
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-9/12" />
        </div>
      )}
    </div>
  );
}

/* ---------------- PR Check ---------------- */

function PRPanel() {
  const [diff, setDiff] = useState("");
  const [result, setResult] = useState<PRResp | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async (e: FormEvent) => {
    e.preventDefault();
    if (!diff.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const r = await apiFetch<PRResp>("/pr-check", {
        method: "POST",
        body: JSON.stringify({ diff_text: diff }),
      });
      setResult(r);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl">
      <SectionHeader
        title="PR readiness check"
        description="Paste a git diff to get a readiness report and rule checklist."
      />

      <form onSubmit={run} className="space-y-3">
        <label className="mono text-xs text-muted-foreground block">GIT DIFF</label>
        <textarea
          value={diff}
          onChange={(e) => setDiff(e.target.value)}
          placeholder="diff --git a/src/index.ts b/src/index.ts&#10;@@ -1,5 +1,7 @@..."
          rows={12}
          className="mono w-full px-4 py-3 rounded-md bg-input border border-border text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring transition resize-y"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !diff.trim()}
          className="px-5 py-3 rounded-md bg-accent text-accent-foreground text-sm font-medium hover:opacity-90 disabled:opacity-50 transition inline-flex items-center gap-2"
        >
          {loading ? (
            <>
              <Spinner /> Checking…
            </>
          ) : (
            "Check readiness"
          )}
        </button>
      </form>

      {error && <div className="mt-4"><ErrorBox message={error} /></div>}

      {result && !loading && (
        <div className="mt-8 space-y-6">
          <div>
            <div className="mono text-xs text-muted-foreground mb-3 tracking-widest">
              CHECKLIST
            </div>
            <div className="grid sm:grid-cols-2 gap-2">
              <CheckRow label="Has tests" pass={result.checklist.has_tests} />
              <CheckRow label="Touches docs" pass={result.checklist.touches_docs} />
              <CheckRow
                label="Diff size"
                neutral
                value={`${result.checklist.diff_size_lines} lines`}
              />
              <CheckRow
                label="Diff size acceptable"
                pass={!result.checklist.is_large_diff}
              />
            </div>
          </div>

          <div>
            <div className="mono text-xs text-muted-foreground mb-3 tracking-widest">
              READINESS REPORT
            </div>
            <div className="p-6 rounded-md border border-border bg-card prose-md text-sm">
              <ReactMarkdown>{result.report}</ReactMarkdown>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function CheckRow({
  label,
  pass,
  neutral,
  value,
}: {
  label: string;
  pass?: boolean;
  neutral?: boolean;
  value?: string;
}) {
  return (
    <div className="flex items-center justify-between px-4 py-3 rounded-md border border-border bg-card">
      <div className="text-sm">{label}</div>
      {neutral ? (
        <span className="mono text-xs text-muted-foreground">{value}</span>
      ) : (
        <span
          className={`mono text-xs px-2 py-1 rounded inline-flex items-center gap-1.5 ${
            pass
              ? "bg-success/15 text-success"
              : "bg-destructive/15 text-destructive"
          }`}
          style={{
            color: pass ? "var(--color-success)" : "var(--color-destructive)",
            backgroundColor: pass
              ? "color-mix(in oklab, var(--color-success) 15%, transparent)"
              : "color-mix(in oklab, var(--color-destructive) 15%, transparent)",
          }}
        >
          <span
            className="w-1.5 h-1.5 rounded-full"
            style={{
              backgroundColor: pass ? "var(--color-success)" : "var(--color-destructive)",
            }}
          />
          {pass ? "PASS" : "FAIL"}
        </span>
      )}
    </div>
  );
}

/* ---------------- Shared UI ---------------- */

function TopBar() {
  const [rateLimit, setRateLimit] = useState<{ limit: number; remaining: number; reset: string } | null>(null);
  const [loading, setLoading] = useState(false);

  const checkRateLimit = async () => {
    setLoading(true);
    try {
      const data = await apiFetch<{ limit: number; remaining: number; reset: string }>("/rate-limit");
      setRateLimit(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <header className="border-b border-border bg-card/50">
      <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex items-center justify-center w-6 h-6 rounded bg-primary/10">
            <div className="w-2 h-2 rounded-sm bg-accent" />
          </div>
          <span className="mono text-sm font-medium">mentor++</span>
        </div>
        
        <div className="flex items-center gap-4">
          {rateLimit && (
            <div className={`mono text-xs px-2 py-1 rounded border ${rateLimit.remaining > 0 ? "bg-green-500/10 text-green-500 border-green-500/20" : "bg-red-500/10 text-red-500 border-red-500/20"}`}>
              {rateLimit.remaining > 0 ? (
                `API Usable: ${rateLimit.remaining}/${rateLimit.limit}`
              ) : (
                `Exhausted (Resets at ${new Date(rateLimit.reset).toLocaleTimeString()})`
              )}
            </div>
          )}
          <button 
            onClick={checkRateLimit}
            disabled={loading}
            className="mono text-xs text-muted-foreground hover:text-foreground transition flex items-center gap-1"
          >
            {loading ? "Checking..." : "Check Rate Limit"}
          </button>
          <span className="mono text-xs text-muted-foreground ml-2 border-l border-border pl-4">v0.1 · local</span>
        </div>
      </div>
    </header>
  );
}

function SectionHeader({ title, description }: { title: string; description: string }) {
  return (
    <div className="mb-6">
      <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
      <p className="text-sm text-muted-foreground mt-1">{description}</p>
    </div>
  );
}

function Spinner() {
  return (
    <span
      className="inline-block w-3.5 h-3.5 rounded-full border-2 border-current border-t-transparent animate-spin"
      aria-label="loading"
    />
  );
}

function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      className={`rounded bg-muted animate-pulse ${className}`}
    />
  );
}

function ErrorBox({ message }: { message: string }) {
  return (
    <div
      className="p-3 rounded-md text-sm border"
      style={{
        borderColor: "color-mix(in oklab, var(--color-destructive) 40%, transparent)",
        backgroundColor: "color-mix(in oklab, var(--color-destructive) 12%, transparent)",
        color: "var(--color-destructive)",
      }}
    >
      <span className="mono text-[10px] tracking-widest mr-2">ERROR</span>
      {message}
    </div>
  );
}
