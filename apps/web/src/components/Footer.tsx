import { Link } from "react-router-dom";

export function Footer() {
  return (
    <footer className="mt-20 bg-ink text-ivory/80">
      <div className="container-page grid gap-8 py-12 sm:grid-cols-3">
        <div>
          <p className="font-serif text-2xl tracking-[0.12em] text-ivory">
            CART<span className="text-camel">SENSE</span>
          </p>
          <p className="mt-3 max-w-xs text-sm text-ivory/60">
            A video game store where every recommendation comes with a reason.
          </p>
        </div>
        <div className="text-sm">
          <p className="eyebrow text-camel-light">Explore</p>
          <ul className="mt-3 space-y-2">
            <li><Link to="/products" className="hover:text-ivory">Shop all</Link></li>
            <li><Link to="/products?sort=newest" className="hover:text-ivory">New in</Link></li>
            <li><Link to="/dashboard" className="hover:text-ivory">Recommendation insights</Link></li>
          </ul>
        </div>
        <div className="text-xs leading-relaxed text-ivory/50">
          <p className="eyebrow text-camel-light">About the data</p>
          <p className="mt-3">
            Product data from the Amazon Reviews 2023 dataset (McAuley Lab, UC San Diego), used for non-commercial
            demonstration. Product names and brands belong to their owners. No real orders or payments are processed.
          </p>
        </div>
      </div>
    </footer>
  );
}
