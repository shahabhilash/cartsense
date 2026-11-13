import { ArrowRight, Gamepad2, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ProductCard } from "@/components/ProductCard";
import { Rail, RailItem, Section } from "@/components/Rail";
import { api, type Product, type RecList } from "@/lib/api";
import { useAuth } from "@/state/auth";
import { recentlyViewed } from "@/state/recent";

const STRATEGY: Record<RecList["strategy"], { eyebrow: string; title: string; subtitle: string }> = {
  precomputed: {
    eyebrow: "Curated for you",
    title: "Recommended for you",
    subtitle: "Ranked by our hybrid model from your review history. Tap “Why this?” on any pick.",
  },
  session_similarity: {
    eyebrow: "Based on your browsing",
    title: "Picked from what you viewed",
    subtitle: "Products similar to the ones you looked at in this store.",
  },
  popular: {
    eyebrow: "Right now",
    title: "Trending in the store",
    subtitle: "What shoppers are reviewing most at the moment.",
  },
};

function Hero({ signedIn }: { signedIn: boolean }) {
  return (
    <section className="relative overflow-hidden rounded-[2rem] bg-ink text-canvas">
      <div className="absolute -right-24 -top-24 h-96 w-96 rounded-full bg-brand/60 blur-3xl" />
      <div className="absolute -bottom-32 left-1/4 h-80 w-80 rounded-full bg-accent/30 blur-3xl" />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_1px_1px,rgba(255,255,255,0.06)_1px,transparent_0)] [background-size:22px_22px]" />
      <div className="relative grid gap-8 px-6 py-12 sm:px-12 sm:py-16 lg:grid-cols-[1.3fr_1fr] lg:items-center">
        <div>
          <p className="eyebrow text-brand-light">The explainable game store</p>
          <h1 className="mt-3 text-4xl leading-tight sm:text-5xl lg:text-6xl">
            Games chosen for you,<br />
            <span className="bg-gradient-to-r from-brand-light via-accent-light to-accent-light bg-clip-text text-transparent">and the reason why.</span>
          </h1>
          <p className="mt-5 max-w-lg text-canvas/70">
            25,000+ titles and accessories. Recommendations come from a model trained on 814,000 real reviews, and
            every one tells you what it was based on.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/products" className="btn bg-canvas text-ink hover:bg-mist">
              Shop the collection <ArrowRight size={16} />
            </Link>
            {!signedIn && (
              <Link to="/login" className="btn border border-canvas/30 text-canvas hover:border-canvas">
                <Sparkles size={16} /> Try a demo shopper
              </Link>
            )}
          </div>
        </div>
        <dl className="grid grid-cols-3 gap-3 text-center lg:grid-cols-1 lg:text-left">
          {[
            ["+39%", "ranking quality vs. the best single model"],
            ["4", "models combined by a learned ranker"],
            ["100%", "of recommendations explained"],
          ].map(([value, label]) => (
            <div key={label} className="rounded-2xl border border-canvas/10 bg-canvas/5 p-4">
              <dt className="font-display text-3xl font-extrabold text-white">{value}</dt>
              <dd className="mt-1 text-xs text-canvas/60">{label}</dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}

export default function Home() {
  const { user } = useAuth();
  const [recs, setRecs] = useState<RecList | null>(null);
  const [trending, setTrending] = useState<Product[] | null>(null);
  const [platforms, setPlatforms] = useState<{ platform: string; products: number }[]>([]);
  const [error, setError] = useState<string | null>(null);
  const recent = recentlyViewed();

  useEffect(() => {
    setRecs(null);
    api<RecList>("/recommendations?k=12&surface=home").then(setRecs).catch((e) => setError(e.message));
  }, [user]);

  useEffect(() => {
    api<{ items: Product[] }>("/products?sort=popular&page_size=12").then((r) => setTrending(r.items)).catch(() => {});
    api<{ platform: string; products: number }[]>("/platforms").then(setPlatforms).catch(() => {});
  }, []);

  const meta = STRATEGY[recs?.strategy ?? "popular"];

  return (
    <div className="space-y-16">
      <Hero signedIn={!!user} />

      <Section
        eyebrow={meta.eyebrow}
        title={meta.title}
        subtitle={meta.subtitle}
        action={recs && <span className="rounded-full bg-mist px-3 py-1 text-[11px] text-ink-soft">model · {recs.model_version}</span>}
      >
        {error ? (
          <p className="text-sm text-brand">Could not load recommendations: {error}</p>
        ) : (
          <Rail loading={!recs}>
            {recs?.items.map((r) => (
              <RailItem key={r.product.id}>
                <ProductCard product={r.product} reasons={r.reasons} impressionId={r.impression_id} />
              </RailItem>
            ))}
          </Rail>
        )}
      </Section>

      {recent.length > 0 && (
        <Section eyebrow="Pick up where you left off" title="Recently viewed">
          <Rail>
            {recent.map((p) => (
              <RailItem key={p.id}>
                <ProductCard product={p} />
              </RailItem>
            ))}
          </Rail>
        </Section>
      )}

      <Section eyebrow="Browse by system" title="Shop by platform">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {platforms.slice(0, 10).map((p, i) => (
            <Link
              key={p.platform}
              to={`/products?platform=${encodeURIComponent(p.platform)}`}
              className={`group flex flex-col justify-between rounded-2xl border p-4 shadow-card transition hover:-translate-y-0.5 hover:border-brand hover:shadow-lift ${
                i === 0 ? "border-transparent bg-gradient-to-br from-brand to-accent-dark text-white" : "border-mist bg-white"
              }`}
            >
              <Gamepad2 size={20} className={i === 0 ? "opacity-80" : "text-brand"} />
              <div className="mt-6">
                <p className="font-display text-lg leading-tight">{p.platform}</p>
                <p className="mt-1 text-xs opacity-70">{p.products.toLocaleString()} products</p>
              </div>
            </Link>
          ))}
        </div>
      </Section>

      {user && (
        <Section eyebrow="Everyone is playing" title="Bestsellers" action={<Link to="/products" className="text-sm font-medium text-brand-dark hover:underline">View all</Link>}>
          <Rail loading={!trending}>
            {trending?.map((p) => (
              <RailItem key={p.id}>
                <ProductCard product={p} />
              </RailItem>
            ))}
          </Rail>
        </Section>
      )}
    </div>
  );
}
