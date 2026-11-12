import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "@/App";

afterEach(cleanup);

describe("App routing", () => {
  it("renders the not-found page for unknown paths", () => {
    // Pages fetch from the API on mount; keep the network out of unit tests
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    render(
      <MemoryRouter initialEntries={["/does-not-exist"]}>
        <App />
      </MemoryRouter>,
    );
    expect(screen.getByText(/Page not found/)).toBeTruthy();
    expect(screen.getByText("CartSense")).toBeTruthy(); // header is always present
    vi.unstubAllGlobals();
  });
});
