import { Link, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { api, getToken, logEvent, setToken, type User } from "@/lib/api";

export function Header() {
  const navigate = useNavigate();
  const [user, setUser] = useState<User | null>(null);
  const [q, setQ] = useState("");

  useEffect(() => {
    if (!getToken()) return;
    api<User>("/me").then(setUser).catch(() => setToken(null));
  }, []);

  function search(e: React.FormEvent) {
    e.preventDefault();
    if (!q.trim()) return;
    logEvent({ event_type: "search", query: q.trim() });
    navigate(`/products?q=${encodeURIComponent(q.trim())}`);
  }

  function logout() {
    setToken(null);
    setUser(null);
    window.location.href = "/";
  }

  return (
    <header className="border-b bg-white">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-3 px-4 py-3">
        <Link to="/" className="text-lg font-bold text-indigo-700">
          CartSense
        </Link>
        <form onSubmit={search} className="order-last flex w-full sm:order-none sm:w-auto sm:flex-1">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search games and accessories"
            aria-label="Search"
            className="w-full rounded border px-3 py-1.5 text-sm"
          />
        </form>
        <nav className="flex items-center gap-4 text-sm">
          <Link to="/products">Browse</Link>
          <Link to="/wishlist">Wishlist</Link>
          <Link to="/dashboard">Dashboard</Link>
          {user ? (
            <button onClick={logout} className="text-gray-600" title="Sign out">
              {user.display_name} · Sign out
            </button>
          ) : (
            <Link to="/login" className="font-medium text-indigo-700">
              Sign in
            </Link>
          )}
        </nav>
      </div>
    </header>
  );
}
