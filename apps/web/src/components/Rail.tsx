import { ChevronLeft, ChevronRight } from "lucide-react";
import { useRef, type ReactNode } from "react";
import { ProductCardSkeleton } from "./ProductCard";

export function Section({
  eyebrow,
  title,
  subtitle,
  action,
  children,
}: {
  eyebrow?: string;
  title: string;
  subtitle?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="animate-fade-up">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          {eyebrow && <p className="eyebrow">{eyebrow}</p>}
          <h2 className="mt-1 text-2xl sm:text-3xl">{title}</h2>
          {subtitle && <p className="mt-1 text-sm text-ink-muted">{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

/** Horizontally scrolling row of cards with arrow buttons on larger screens. */
export function Rail({ children, loading = false }: { children: ReactNode; loading?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const scroll = (dir: number) => ref.current?.scrollBy({ left: dir * ref.current.clientWidth * 0.8, behavior: "smooth" });

  return (
    <div className="relative">
      <div ref={ref} className="no-scrollbar -mx-4 flex snap-x gap-4 overflow-x-auto px-4 pb-4 sm:-mx-6 sm:px-6">
        {loading
          ? Array.from({ length: 6 }, (_, i) => (
              <div key={i} className="w-[46%] shrink-0 sm:w-[30%] lg:w-[18.5%]">
                <ProductCardSkeleton />
              </div>
            ))
          : children}
      </div>
      <button onClick={() => scroll(-1)} aria-label="Scroll left"
        className="absolute -left-3 top-[38%] hidden h-10 w-10 items-center justify-center rounded-full bg-white shadow-lift hover:bg-ivory lg:flex">
        <ChevronLeft size={18} />
      </button>
      <button onClick={() => scroll(1)} aria-label="Scroll right"
        className="absolute -right-3 top-[38%] hidden h-10 w-10 items-center justify-center rounded-full bg-white shadow-lift hover:bg-ivory lg:flex">
        <ChevronRight size={18} />
      </button>
    </div>
  );
}

export function RailItem({ children }: { children: ReactNode }) {
  return <div className="w-[46%] shrink-0 snap-start sm:w-[30%] lg:w-[18.5%]">{children}</div>;
}

export function EmptyState({ icon, title, children }: { icon: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center rounded-3xl border border-dashed border-sand-deep bg-white/60 px-6 py-14 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-sand text-camel-dark">{icon}</div>
      <h3 className="mt-4 text-xl">{title}</h3>
      {children && <div className="mt-2 max-w-md text-sm text-ink-muted">{children}</div>}
    </div>
  );
}
