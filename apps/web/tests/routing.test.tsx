import { cleanup, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "@/App";
import { renderApp } from "./utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("App routing", () => {
  it("renders the not-found page for unknown paths", () => {
    renderApp(<App />, "/does-not-exist");
    expect(screen.getByText("Page not found")).toBeTruthy();
    expect(screen.getAllByText("Sense").length).toBeGreaterThan(0); // logo in header and footer
  });

  it("shows an empty bag page", () => {
    renderApp(<App />, "/cart");
    expect(screen.getByText("Your bag is empty")).toBeTruthy();
  });
});
