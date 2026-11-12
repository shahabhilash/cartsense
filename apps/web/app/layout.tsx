import type { Metadata } from "next";
import "./globals.css";
import { Header } from "@/components/Header";

export const metadata: Metadata = {
  title: "CartSense",
  description: "A video game store with explainable recommendations",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Header />
        <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
        <footer className="mx-auto max-w-6xl px-4 py-8 text-xs text-gray-500">
          Product data from the Amazon Reviews 2023 dataset (McAuley Lab, UCSD), used for non-commercial demonstration.
          Product names and brands belong to their owners.
        </footer>
      </body>
    </html>
  );
}
