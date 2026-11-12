import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { ProductCard, ReasonList } from "@/components/ProductCard";
import { formatPrice, type Product } from "@/lib/api";

afterEach(cleanup);

const product: Product = {
  id: "P1",
  title: "Zelda",
  brand: "Nintendo",
  platform: "Nintendo Switch",
  price: 59.99,
  image_url: null,
  review_count: 10,
  popularity_rank: 1,
};

describe("formatPrice", () => {
  it("formats prices and handles missing ones", () => {
    expect(formatPrice(59.99)).toBe("$59.99");
    expect(formatPrice(null)).toBe("Price unavailable");
  });
});

describe("ReasonList", () => {
  it("renders every reason", () => {
    render(<ReasonList reasons={[{ type: "trending", text: "Trending: #1" }, { type: "x", text: "Because Y" }]} />);
    expect(screen.getByText("Trending: #1")).toBeTruthy();
    expect(screen.getByText("Because Y")).toBeTruthy();
  });
});

describe("ProductCard", () => {
  it("hides reasons until Why this? is clicked, and links to the product page", () => {
    render(
      <MemoryRouter>
        <ProductCard product={product} reasons={[{ type: "similar", text: "Similar to Mario" }]} impressionId="imp-1" />
      </MemoryRouter>,
    );
    expect(screen.queryByText("Similar to Mario")).toBeNull();
    fireEvent.click(screen.getByText("Why this?"));
    expect(screen.getByText("Similar to Mario")).toBeTruthy();
    expect(screen.getByText("Nintendo Switch")).toBeTruthy(); // placeholder tile, no image
    expect(screen.queryByRole("img")).toBeNull();
    expect(screen.getByRole("link").getAttribute("href")).toBe("/products/P1?imp=imp-1");
  });
});
