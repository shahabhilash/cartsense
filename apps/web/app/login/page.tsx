"use client";

import { useEffect, useState } from "react";
import { api, setToken, type DemoUser, type User } from "@/lib/api";

type Token = { access_token: string; user: User };

export default function LoginPage() {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [demo, setDemo] = useState<DemoUser[]>([]);

  useEffect(() => {
    api<DemoUser[]>("/auth/demo-users?limit=12").then(setDemo).catch(() => {});
  }, []);

  function done(t: Token) {
    setToken(t.access_token);
    window.location.href = "/";
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const body = mode === "login" ? { email, password } : { email, password, display_name: name };
      done(await api<Token>(`/auth/${mode}`, { method: "POST", body: JSON.stringify(body) }));
    } catch (err) {
      setError((err as Error).message);
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
    <div className="grid gap-8 md:grid-cols-2">
      <form onSubmit={submit} className="space-y-3 rounded-lg border bg-white p-5">
        <h1 className="text-lg font-semibold">{mode === "login" ? "Sign in" : "Create an account"}</h1>
        {mode === "register" && (
          <input
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Display name"
            className="w-full rounded border px-3 py-2 text-sm"
          />
        )}
        <input
          required
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Email"
          className="w-full rounded border px-3 py-2 text-sm"
        />
        <input
          required
          type="password"
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password (8+ characters)"
          className="w-full rounded border px-3 py-2 text-sm"
        />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button className="w-full rounded bg-indigo-600 py-2 text-sm text-white">
          {mode === "login" ? "Sign in" : "Register"}
        </button>
        <button
          type="button"
          onClick={() => setMode(mode === "login" ? "register" : "login")}
          className="text-xs text-indigo-700"
        >
          {mode === "login" ? "New here? Create an account" : "Have an account? Sign in"}
        </button>
      </form>
      <div className="rounded-lg border bg-white p-5">
        <h2 className="text-lg font-semibold">Try a demo shopper</h2>
        <p className="mt-1 text-sm text-gray-600">
          Real (anonymised) shoppers from the dataset. Their recommendations come from the trained hybrid model.
        </p>
        <ul className="mt-3 space-y-2">
          {demo.map((d) => (
            <li key={d.dataset_user_id}>
              <button
                onClick={() => demoLogin(d.dataset_user_id)}
                className="w-full rounded border px-3 py-2 text-left text-sm hover:bg-gray-50"
              >
                {d.display_name} <span className="text-gray-500">· {d.reviews} reviews</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
