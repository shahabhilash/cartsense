import type { ReactNode } from "react";
import { AuthProvider } from "./auth";
import { CartProvider } from "./cart";
import { ToastProvider } from "./toast";
import { WishlistProvider } from "./wishlist";

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <ToastProvider>
      <AuthProvider>
        <WishlistProvider>
          <CartProvider>{children}</CartProvider>
        </WishlistProvider>
      </AuthProvider>
    </ToastProvider>
  );
}
