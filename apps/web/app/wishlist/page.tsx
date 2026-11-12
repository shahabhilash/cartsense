"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ProductCard } from "@/components/ProductCard";
import { api, getToken, type Product } from "@/lib/api";

export default function WishlistPage() {
  const [items, setItems] = useState<Product[] | null>(null);
  const [signedIn, setSignedIn] = useState(true);

  useEffect(() => {
    if (!getToken()) {
      setSignedIn(false);
      return;
    }
    api<Product[]>("/me/wishlist").then(setItems).catch(() => setSignedIn(false));
  }, []);

  if (!signedIn)
    return (
      <p>
        <Link href="/login" className="text-indigo-700 underline">
          Sign in
        </Link>{" "}
        to see your wishlist.
      </p>
    );
  if (!items) return <p>Loading…</p>;
  return (
    <div>
      <h1 className="text-xl font-semibold">Your wishlist</h1>
      {items.length === 0 && <p className="mt-3 text-gray-600">Nothing here yet.</p>}
      <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        {items.map((p) => (
          <ProductCard key={p.id} product={p} />
        ))}
      </div>
    </div>
  );
}
