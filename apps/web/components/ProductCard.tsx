"use client";

import Link from "next/link";
import { useState } from "react";
import { formatPrice, logEvent, type Product, type Reason } from "@/lib/api";

const PLATFORM_COLOURS: Record<string, string> = {
  PC: "bg-slate-700",
  "Nintendo Switch": "bg-red-600",
  "PlayStation 4": "bg-blue-700",
  "PlayStation 5": "bg-blue-500",
  "Xbox One": "bg-green-700",
  "Xbox Series X & S": "bg-green-600",
  "Legacy Systems": "bg-amber-700",
};

export function ProductThumb({ product }: { product: Product }) {
  if (product.image_url) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={product.image_url} alt="" className="h-32 w-full rounded object-contain bg-white" />;
  }
  const colour = PLATFORM_COLOURS[product.platform ?? ""] ?? "bg-gray-500";
  return (
    <div className={`flex h-32 w-full items-center justify-center rounded ${colour} px-2 text-center text-xs font-semibold text-white`}>
      {product.platform ?? "Video Games"}
    </div>
  );
}

export function ReasonList({ reasons }: { reasons: Reason[] }) {
  if (!reasons.length) return null;
  return (
    <ul className="mt-2 space-y-1 text-xs text-gray-600" aria-label="Why this was recommended">
      {reasons.map((r, i) => (
        <li key={i} className="rounded bg-gray-100 px-2 py-1">
          {r.text}
        </li>
      ))}
    </ul>
  );
}

export function ProductCard({
  product,
  reasons,
  impressionId,
}: {
  product: Product;
  reasons?: Reason[];
  impressionId?: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="flex flex-col rounded-lg border bg-white p-3 shadow-sm">
      <Link
        href={`/products/${product.id}${impressionId ? `?imp=${impressionId}` : ""}`}
        onClick={() => logEvent({ event_type: "click", product_id: product.id, impression_id: impressionId })}
        className="flex-1"
      >
        <ProductThumb product={product} />
        <h3 className="mt-2 line-clamp-2 text-sm font-medium">{product.title}</h3>
        <p className="text-xs text-gray-500">{product.brand ?? "Unknown brand"}</p>
        <p className="mt-1 text-sm font-semibold">{formatPrice(product.price)}</p>
      </Link>
      {reasons && reasons.length > 0 && (
        <>
          <button onClick={() => setOpen(!open)} className="mt-2 self-start text-xs text-indigo-600 hover:underline">
            {open ? "Hide" : "Why this?"}
          </button>
          {open && <ReasonList reasons={reasons} />}
        </>
      )}
    </div>
  );
}
