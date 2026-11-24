import type { Basket } from "../types";

const money = (n: number) => `$${n.toFixed(2)}`;

export function Receipt({ basket }: { basket: Basket | null }) {
  if (!basket) {
    return (
      <div className="panel-empty">
        <p>No shop yet.</p>
        <p>Ask for a meal plan and a weekly shop, and your docket will print here.</p>
      </div>
    );
  }
  const over = basket.within_budget === false;
  return (
    <div className="docket" aria-label="Shopping basket">
      <header className="docket-head">
        <strong>FitBasket weekly shop</strong>
        <span>{basket.lines.length} items</span>
      </header>
      <ul className="docket-lines">
        {basket.lines.map((l) => (
          <li key={l.product_id} className={l.on_special ? "is-special" : undefined}>
            <div className="docket-row">
              <span className="docket-qty">{l.packs}×</span>
              <span className="docket-name">{l.name}</span>
              <span className="docket-amt">{money(l.line_total)}</span>
            </div>
            <div className="docket-why">
              {l.on_special && <span className="ticket">Special −{money(l.saving)}</span>}
              {l.on_special ? l.reason.replace(/^Weekly special, saves \$[\d.]+\s*/, "") : l.reason}
            </div>
          </li>
        ))}
      </ul>
      <dl className="docket-totals">
        <div>
          <dt>Specials saved</dt>
          <dd>{money(basket.total_saving)}</dd>
        </div>
        {basket.budget != null && (
          <div className={over ? "is-over" : undefined}>
            <dt>Budget</dt>
            <dd>{money(basket.budget)}</dd>
          </div>
        )}
        <div className="docket-total">
          <dt>Total</dt>
          <dd>{money(basket.total)}</dd>
        </div>
      </dl>
      {basket.covered_by_pantry.length > 0 && (
        <p className="docket-note">Already in your pantry: {basket.covered_by_pantry.join(", ")}</p>
      )}
      {over && (
        <ul className="docket-tips" aria-label="Ways to get under budget">
          {basket.tips.map((t) => (
            <li key={t}>{t}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
