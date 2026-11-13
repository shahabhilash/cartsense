import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { monogram } from "@/components/ProductArt";
import { ProductCard } from "@/components/ProductCard";
import { ReasonChip, ReasonList } from "@/components/Reasons";
import { formatPrice, type Product } from "@/lib/api";
import { renderApp } from "./utils";

beforeEach(() => window.localStorage.clear());
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const product: Product = {
  id: "P1",
  title: "The Legend of Zelda: Breath of the Wild",
  brand: "Nintendo",
  platform: "Nintendo Switch",
  price: 59.99,
  image_url: null,
  review_count: 10,
  popularity_rank: 1,
};

describe("helpers", () => {
  it("formats prices and handles missing ones", () => {
    expect(formatPrice(59.99)).toBe("$59.99");
    expect(formatPrice(null)).toBe("Price unavailable");
  });

  it("builds a monogram from meaningful title words", () => {
    expect(monogram("The Legend of Zelda")).toBe("LZ");
    expect(monogram("***")).toBe("CS");
  });
});

describe("reasons", () => {
  it("labels each reason by its source", () => {
    render(<ReasonChip reason={{ type: "similar_taste", text: "x" }} />);
    expect(screen.getByText("Similar taste")).toBeTruthy();
  });

  it("lists every reason with its text", () => {
    render(<ReasonList reasons={[{ type: "trending", text: "Trending: #1" }, { type: "unknown", text: "Because Y" }]} />);
    expect(screen.getByText("Trending: #1")).toBeTruthy();
    expect(screen.getByText("Picked for you")).toBeTruthy(); // fallback label
  });
});

describe("ProductCard", () => {
  it("reveals reasons on Why this? and links to the product with its impression", () => {
    renderApp(<ProductCard product={product} reasons={[{ type: "similar_content", text: "Similar to Mario" }]} impressionId="imp-1" />);
    expect(screen.queryByText("Similar to Mario")).toBeNull();
    fireEvent.click(screen.getByText("Why this?"));
    expect(screen.getByText("Similar to Mario")).toBeTruthy();
    expect(screen.getByLabelText(product.title).getAttribute("href")).toBe("/products/P1?imp=imp-1");
    expect(screen.queryByRole("img")).toBeNull(); // generated art, no Amazon image
  });

  it("adds to the bag and remembers it across reloads", () => {
    renderApp(<ProductCard product={product} />);
    fireEvent.click(screen.getByText("Add"));
    const stored = JSON.parse(window.localStorage.getItem("cartsense_cart") ?? "[]");
    expect(stored).toEqual([{ product, quantity: 1 }]);
    expect(screen.getByText(/Added to bag/)).toBeTruthy(); // toast
  });

  it("asks guests to sign in before saving to the wishlist", () => {
    renderApp(<ProductCard product={product} />);
    fireEvent.click(screen.getByLabelText("Save to wishlist"));
    expect(screen.getByText(/Sign in to save items/)).toBeTruthy();
  });
});
