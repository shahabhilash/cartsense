import { BarChart3, Heart, LogOut, Search, ShoppingBag, Sparkles, User as UserIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { api, formatPrice, logEvent, type Product } from "@/lib/api";
import { useAuth } from "@/state/auth";
import { useCart } from "@/state/cart";
import { useWishlist } from "@/state/wishlist";
import { ProductArt } from "./ProductArt";

function SearchBox() {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [suggestions, setSuggestions] = useState<Product[]>([]);
  const [open, setOpen] = useState(false);
  const boxRef = useRef<HTMLFormElement>(null);

  // Debounced suggestions while typing
  useEffect(() => {
    const term = q.trim();
    if (term.length < 2) {
      setSuggestions([]);
      return;
    }
    const timer = window.setTimeout(() => {
      api<{ items: Product[] }>(`/products?q=${encodeURIComponent(term)}&page_size=5`)
        .then((r) => setSuggestions(r.items))
        .catch(() => setSuggestions([]));
    }, 250);
    return () => window.clearTimeout(timer);
  }, [q]);

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (!boxRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const term = q.trim();
    if (!term) return;
    logEvent({ event_type: "search", query: term });
    setOpen(false);
    navigate(`/products?q=${encodeURIComponent(term)}`);
  }

  return (
    <form ref={boxRef} onSubmit={submit} className="relative w-full" role="search">
      <Search size={16} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-ink-muted" />
      <input
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        placeholder="Search games, consoles, accessories…"
        aria-label="Search"
        className="input pl-10"
      />
      {open && suggestions.length > 0 && (
        <div className="absolute left-0 right-0 top-full z-50 mt-2 animate-fade-up overflow-hidden rounded-2xl bg-white shadow-lift">
          {suggestions.map((p) => (
            <Link
              key={p.id}
              to={`/products/${p.id}`}
              onClick={() => {
                setOpen(false);
                setQ("");
              }}
              className="flex items-center gap-3 px-3 py-2 hover:bg-canvas"
            >
              <div className="w-10 shrink-0">
                <ProductArt product={p} size="sm" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm">{p.title}</p>
                <p className="text-xs text-ink-muted">{p.platform}</p>
              </div>
              <span className="text-xs font-semibold">{formatPrice(p.price)}</span>
            </Link>
          ))}
          <button type="submit" className="w-full border-t border-mist px-3 py-2 text-left text-xs font-medium text-brand-dark hover:bg-canvas">
            See all results for “{q.trim()}”
          </button>
        </div>
      )}
    </form>
  );
}

export function Header() {
  const { user, signOut } = useAuth();
  const cart = useCart();
  const wishlist = useWishlist();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);

  const navClass = ({ isActive }: { isActive: boolean }) =>
    `text-sm transition hover:text-brand-dark ${isActive ? "font-semibold text-ink" : "text-ink-soft"}`;

  return (
    <header className="sticky top-0 z-40">
      <div className="bg-ink py-2 text-center text-xs text-canvas/80">
        Every recommendation is explained. Tap <span className="font-semibold text-white">“Why this?”</span> on any pick.
      </div>
      <div className="border-b border-mist bg-white/85 backdrop-blur">
        <div className="container-page flex flex-wrap items-center gap-x-6 gap-y-3 py-3">
          <Link to="/" className="flex items-center gap-2" aria-label="CartSense home">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-brand to-accent text-white shadow-sm">
              <Sparkles size={16} />
            </span>
            <span className="font-display text-xl font-extrabold tracking-tight">
              Cart<span className="text-brand">Sense</span>
            </span>
          </Link>
          <nav className="hidden items-center gap-5 md:flex" aria-label="Main">
            <NavLink to="/products" className={navClass}>Shop</NavLink>
            <NavLink to="/products?sort=newest" className={navClass}>New in</NavLink>
            <NavLink to="/dashboard" className={navClass}>Insights</NavLink>
          </nav>
          <div className="order-last w-full md:order-none md:max-w-md md:flex-1">
            <SearchBox />
          </div>
          <div className="ml-auto flex items-center gap-1">
            <Link to="/dashboard" className="rounded-full p-2 hover:bg-mist md:hidden" aria-label="Insights">
              <BarChart3 size={20} />
            </Link>
            <Link to="/wishlist" className="relative rounded-full p-2 hover:bg-mist" aria-label="Wishlist">
              <Heart size={20} />
              {wishlist.items.length > 0 && (
                <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-brand px-1 text-[10px] font-semibold text-white">
                  {wishlist.items.length}
                </span>
              )}
            </Link>
            <button onClick={() => cart.setOpen(true)} className="relative rounded-full p-2 hover:bg-mist" aria-label="Open bag">
              <ShoppingBag size={20} />
              {cart.count > 0 && (
                <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-accent px-1 text-[10px] font-semibold text-white">
                  {cart.count}
                </span>
              )}
            </button>
            {user ? (
              <div className="relative">
                <button
                  onClick={() => setMenuOpen(!menuOpen)}
                  className="ml-1 flex items-center gap-2 rounded-full border border-mist-deep bg-white py-1 pl-1 pr-3 text-sm hover:border-brand"
                  aria-expanded={menuOpen}
                >
                  <span className="flex h-7 w-7 items-center justify-center rounded-full bg-brand font-display text-xs font-bold text-white">
                    {user.display_name.slice(0, 1).toUpperCase()}
                  </span>
                  <span className="hidden max-w-[140px] truncate sm:inline">{user.display_name}</span>
                </button>
                {menuOpen && (
                  <div className="absolute right-0 top-full mt-2 w-52 animate-fade-up overflow-hidden rounded-2xl bg-white py-1 shadow-lift"
                    onMouseLeave={() => setMenuOpen(false)}>
                    <Link to="/account" onClick={() => setMenuOpen(false)} className="flex items-center gap-2 px-4 py-2 text-sm hover:bg-canvas">
                      <UserIcon size={15} /> Your account
                    </Link>
                    <Link to="/wishlist" onClick={() => setMenuOpen(false)} className="flex items-center gap-2 px-4 py-2 text-sm hover:bg-canvas">
                      <Heart size={15} /> Wishlist
                    </Link>
                    <button
                      onClick={() => {
                        setMenuOpen(false);
                        signOut();
                        navigate("/");
                      }}
                      className="flex w-full items-center gap-2 px-4 py-2 text-left text-sm hover:bg-canvas"
                    >
                      <LogOut size={15} /> Sign out
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <Link to="/login" className="btn-primary ml-1 px-4 py-2">Sign in</Link>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
