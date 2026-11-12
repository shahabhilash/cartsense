import { lazy, Suspense } from "react";
import { Link, Route, Routes } from "react-router-dom";
import { Header } from "@/components/Header";
import Home from "@/pages/Home";
import Login from "@/pages/Login";
import ProductDetail from "@/pages/ProductDetail";
import Products from "@/pages/Products";
import Wishlist from "@/pages/Wishlist";

// The dashboard pulls in the charting library; load it only when visited
const Dashboard = lazy(() => import("@/pages/Dashboard"));

function NotFound() {
  return (
    <p>
      Page not found. <Link to="/" className="text-indigo-700 underline">Back to the store</Link>
    </p>
  );
}

export default function App() {
  return (
    <>
      <Header />
      <main className="mx-auto max-w-6xl px-4 py-6">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/products" element={<Products />} />
          <Route path="/products/:id" element={<ProductDetail />} />
          <Route path="/wishlist" element={<Wishlist />} />
          <Route path="/login" element={<Login />} />
          <Route path="/dashboard" element={<Suspense fallback={<p>Loading…</p>}><Dashboard /></Suspense>} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
      <footer className="mx-auto max-w-6xl px-4 py-8 text-xs text-gray-500">
        Product data from the Amazon Reviews 2023 dataset (McAuley Lab, UCSD), used for non-commercial demonstration.
        Product names and brands belong to their owners.
      </footer>
    </>
  );
}
