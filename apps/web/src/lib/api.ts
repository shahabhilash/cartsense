// Typed client for the CartSense REST API.

export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export type Product = {
  id: string;
  title: string;
  brand: string | null;
  platform: string | null;
  price: number | null;
  image_url: string | null;
  review_count: number;
  popularity_rank: number | null;
};

export type ProductDetail = Product & {
  categories: string[];
  features: string[];
  description: string | null;
  release_date: string | null;
};

export type Reason = { type: string; text: string; item_id?: string | null; source?: string | null };

export type RecItem = { product: Product; rank: number; score: number; reasons: Reason[]; impression_id: string };

export type RecList = {
  request_id: string;
  model_version: string;
  strategy: "precomputed" | "session_similarity" | "popular";
  variant: "control" | "treatment" | null;
  items: RecItem[];
};

export type VariantStats = {
  variant: "control" | "treatment";
  units: number;
  impressions: number;
  clicks: number;
  ctr: number;
  converted_units: number;
  conversion_rate: number;
};

export type ABTest = {
  experiment: string;
  enabled: boolean;
  control_share: number;
  variants: VariantStats[];
  ctr_lift: number | null;
  ctr_p_value: number | null;
  conversion_p_value: number | null;
};

export type User = { id: number; display_name: string; email: string | null; is_demo: boolean; demo_platform: string | null };

export type DemoUser = { dataset_user_id: string; display_name: string; platform: string | null; reviews: number };

export type Analytics = {
  events_by_type: Record<string, number>;
  events_by_day: { date: string; events: number }[];
  recommendation_stats: { model_version: string; impressions: number; clicks: number; ctr: number }[];
  active_model_version: string | null;
  offline_metrics: Record<string, string | number>[];
  ab_test: ABTest;
};

const TOKEN_KEY = "cartsense_token";
const SESSION_KEY = "cartsense_session";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null) {
  try {
    if (token) window.localStorage.setItem(TOKEN_KEY, token);
    else window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable: stay signed out */
  }
}

export function sessionId(): string {
  try {
    let id = window.localStorage.getItem(SESSION_KEY);
    if (!id) {
      id = crypto.randomUUID();
      window.localStorage.setItem(SESSION_KEY, id);
    }
    return id;
  } catch {
    return "anonymous";
  }
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_URL}/api/v1${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      // Lets the API personalise for guests from their browsing in this session
      "X-Session-Id": sessionId(),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });
  if (!res.ok) {
    let message = res.statusText;
    try {
      message = (await res.json()).error?.message ?? message;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, message);
  }
  return res.json() as Promise<T>;
}

export function logEvent(event: { event_type: string; product_id?: string; query?: string; impression_id?: string }) {
  // Fire and forget: analytics must never break the page
  api("/events", { method: "POST", body: JSON.stringify({ ...event, session_id: sessionId() }) }).catch(() => {});
}

export function formatPrice(price: number | null): string {
  return price == null ? "Price unavailable" : `$${price.toFixed(2)}`;
}
