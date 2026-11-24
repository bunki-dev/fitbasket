import type { Basket } from "../types";
import { ProductArt } from "./ProductArt";
import { Scribble } from "./Doodles";

const money = (n: number) => `$${n.toFixed(2)}`;

export function Cart({ basket }: { basket: Basket | null }) {
  if (!basket) {
    return (
      <div className="panel-empty">
        <EmptyTrolley />
        <h2>Your trolley's empty</h2>
        <p>Ask for a meal plan and this week's shop. Everything you need lands here, specials first.</p>
      </div>
    );
  }
  const over = basket.within_budget === false;
  const items = basket.lines.reduce((n, l) => n + l.packs, 0);
  return (
    <div className="cart">
      <header className="cart-head">
        <h2>Your trolley</h2>
        {basket.total_saving > 0 && (
          <p className="margin-note">
            {money(basket.total_saving)} saved on specials
            <Scribble />
          </p>
        )}
      </header>

      <ul className="cart-lines">
        {basket.lines.map((l) => (
          <li key={l.product_id} className="cart-line">
            <div className="cart-art">
              <ProductArt ingredient={l.ingredient} brand={l.brand} name={l.name} />
              {l.on_special && <span className="burst">Save {money(l.saving)}</span>}
            </div>
            <div className="cart-info">
              <p className="cart-name">{l.name}</p>
              <p className="cart-pack">{l.pack_label}</p>
              {reason(l.reason, l.on_special) && <p className="cart-why">{reason(l.reason, l.on_special)}</p>}
            </div>
            <div className="cart-price">
              <span className="cart-total">{money(l.line_total)}</span>
              {l.was_price != null && <s className="cart-was">{money(l.was_price * l.packs)}</s>}
              <span className="cart-qty">
                {l.packs} × {money(l.unit_price)}
              </span>
            </div>
          </li>
        ))}
      </ul>

      <footer className="tally">
        <dl>
          <div>
            <dt>{items} items</dt>
            <dd>{money(basket.total + basket.total_saving)}</dd>
          </div>
          {basket.total_saving > 0 && (
            <div className="tally-save">
              <dt>Specials</dt>
              <dd>−{money(basket.total_saving)}</dd>
            </div>
          )}
          <div className="tally-total">
            <dt>Total</dt>
            <dd>{money(basket.total)}</dd>
          </div>
          {basket.budget != null && (
            <div className={over ? "tally-budget is-over" : "tally-budget"}>
              <dt>Your budget</dt>
              <dd>{money(basket.budget)}</dd>
            </div>
          )}
        </dl>
        {basket.covered_by_pantry.length > 0 && (
          <p className="tally-note">Skipped, you've got these: {basket.covered_by_pantry.join(", ").toLowerCase()}</p>
        )}
        {over && (
          <ul className="tally-tips" aria-label="Ways to get under budget">
            {basket.tips.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
        )}
      </footer>
    </div>
  );
}

function reason(text: string, special: boolean): string {
  // The sticker already shows the saving, so drop that part of the explanation.
  let cleaned = text;
  if (special) {
    cleaned = cleaned
      .replace(/^Weekly special, saves \$[\d.]+\s*/, "")
      .replace(/, on special this week$/, "")
      .replace(/^\((.*)\)$/, "$1");
  }
  return cleaned ? cleaned.charAt(0).toUpperCase() + cleaned.slice(1) : "";
}

function EmptyTrolley() {
  return (
    <svg viewBox="0 0 160 110" width="160" height="110" aria-hidden="true" className="empty-art">
      <path d="M22 30h104l-12 46H38z" fill="#ffe800" transform="translate(4 3)" />
      <path d="M8 18h14l16 58h76l12-46H26" fill="none" stroke="#1b2a4a" strokeWidth="3" strokeLinecap="round"
        strokeLinejoin="round" />
      <path d="M48 42v22M66 42v22M84 42v22M102 42v22" stroke="#1b2a4a" strokeWidth="2" strokeLinecap="round" />
      <circle cx="50" cy="92" r="7" fill="#ff48b0" transform="translate(2 1)" />
      <circle cx="50" cy="92" r="7" fill="none" stroke="#1b2a4a" strokeWidth="3" />
      <circle cx="104" cy="92" r="7" fill="#ff48b0" transform="translate(2 1)" />
      <circle cx="104" cy="92" r="7" fill="none" stroke="#1b2a4a" strokeWidth="3" />
    </svg>
  );
}
