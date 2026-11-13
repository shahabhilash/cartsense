import { lazy, Suspense } from "react";
import { Link, Route, Routes } from "react-router-dom";
import { CartDrawer } from "@/components/CartDrawer";
import { Footer } from "@/components/Footer";
import { Header } from "@/components/Header";
import Account from "@/pages/Account";
import Cart from "@/pages/Cart";
import Home from "@/pages/Home";
import Login from "@/pages/Login";
import ProductDetail from "@/pages/ProductDetail";
import Products from "@/pages/Products";
import Wishlist from "@/pages/Wishlist";

// The dashboard pulls in the charting library; load it only when visited
const Dashboard = lazy(() => import("@/pages/Dashboard"));

function NotFound() {
  return (
    <div className="py-20 text-center">
      <p className="eyebrow">Error 404</p>
      <h1 className="mt-2 text-4xl">Page not found</h1>
      <Link to="/" className="btn-primary mt-6">Back to the store</Link>
    </div>
  );
}

export default function App() {
  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="container-page flex-1 py-8">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/products" element={<Products />} />
          <Route path="/products/:id" element={<ProductDetail />} />
          <Route path="/wishlist" element={<Wishlist />} />
          <Route path="/cart" element={<Cart />} />
          <Route path="/account" element={<Account />} />
          <Route path="/login" element={<Login />} />
          <Route
            path="/dashboard"
            element={
              <Suspense fallback={<div className="h-32 animate-pulse rounded-3xl bg-sand" />}>
                <Dashboard />
              </Suspense>
            }
          />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
      <Footer />
      <CartDrawer />
    </div>
  );
}
