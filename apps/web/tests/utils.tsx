import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import { AppProviders } from "@/state/AppProviders";

/** Render inside the router and app providers, with the network stubbed out. */
export function renderApp(ui: ReactElement, path = "/") {
  vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppProviders>{ui}</AppProviders>
    </MemoryRouter>,
  );
}
