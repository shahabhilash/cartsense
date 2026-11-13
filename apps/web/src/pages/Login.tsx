import { ArrowRight, Gamepad2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type DemoUser, type User } from "@/lib/api";
import { useAuth } from "@/state/auth";
import { useToast } from "@/state/toast";

type Token = { access_token: string; user: User };

export default function Login() {
  const { signIn } = useAuth();
  const { notify } = useToast();
  const navigate = useNavigate();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [demo, setDemo] = useState<DemoUser[] | null>(null);

  useEffect(() => {
    api<DemoUser[]>("/auth/demo-users?limit=12").then(setDemo).catch(() => setDemo([]));
  }, []);

  function done(t: Token) {
    signIn(t.access_token, t.user);
    notify(`Welcome, ${t.user.display_name}`);
    navigate("/");
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const body = mode === "login" ? { email, password } : { email, password, display_name: name };
      done(await api<Token>(`/auth/${mode}`, { method: "POST", body: JSON.stringify(body) }));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function demoLogin(id: string) {
    try {
      done(await api<Token>("/auth/demo", { method: "POST", body: JSON.stringify({ dataset_user_id: id }) }));
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_1.2fr]">
      <form onSubmit={submit} className="rounded-3xl bg-surface p-8 shadow-card">
        <p className="eyebrow">{mode === "login" ? "Welcome back" : "Join CartSense"}</p>
        <h1 className="mt-1 text-3xl">{mode === "login" ? "Sign in" : "Create an account"}</h1>
        <div className="mt-6 space-y-3">
          {mode === "register" && (
            <input required value={name} onChange={(e) => setName(e.target.value)} placeholder="Display name" className="input" />
          )}
          <input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" className="input" autoComplete="email" />
          <input required type="password" minLength={8} value={password} onChange={(e) => setPassword(e.target.value)}
            placeholder="Password (8+ characters)" className="input" autoComplete={mode === "login" ? "current-password" : "new-password"} />
        </div>
        {error && <p className="mt-3 text-sm text-brand" role="alert">{error}</p>}
        <button disabled={busy} className="btn-primary mt-6 w-full py-3">
          {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"} <ArrowRight size={16} />
        </button>
        <button type="button" onClick={() => setMode(mode === "login" ? "register" : "login")}
          className="mt-4 w-full text-center text-sm text-ink-muted hover:text-ink">
          {mode === "login" ? "New here? Create an account" : "Already a member? Sign in"}
        </button>
        <p className="mt-6 rounded-2xl bg-canvas-deep p-3 text-xs leading-relaxed text-ink-muted">
          New accounts start with trending picks. Browse a few products and your recommendations adapt straight away.
        </p>
      </form>

      <div className="rounded-3xl bg-brand p-8 text-canvas">
        <p className="eyebrow text-brand-light">No account needed</p>
        <h2 className="mt-1 text-3xl">Shop as a real customer</h2>
        <p className="mt-2 text-sm text-canvas/60">
          These are anonymised shoppers from the dataset. Pick one to see the recommendations our hybrid model built
          from their review history.
        </p>
        <ul className="mt-6 grid gap-3 sm:grid-cols-2">
          {demo === null &&
            Array.from({ length: 6 }, (_, i) => <li key={i} className="h-16 animate-pulse rounded-2xl bg-canvas/10" />)}
          {demo?.map((d) => (
            <li key={d.dataset_user_id}>
              <button onClick={() => demoLogin(d.dataset_user_id)}
                className="group flex w-full items-center gap-3 rounded-2xl border border-canvas/10 bg-canvas/5 p-3 text-left transition hover:border-accent-light hover:bg-canvas/10">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-accent text-white">
                  <Gamepad2 size={18} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">{d.display_name.replace(/\s*\(.*\)$/, "")}</span>
                  <span className="block truncate text-xs text-canvas/50">{d.platform ?? "Mixed"} · {d.reviews} reviews</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
