import { useMemo, useState } from "react";
import {
  dayKey,
  type Food,
  type LogEntry,
  lookup,
  type Per100,
  rememberFood,
  scale,
  shiftDay,
  totals,
} from "../runtime/foodlog";
import type { Targets } from "../types";
import { Scanner } from "./Scanner";

const KJ_PER_KCAL = 4.184;
const r0 = (n: number) => Math.round(n);
const MACROS: { key: keyof Per100; label: string; unit: string; tone: string }[] = [
  { key: "kcal", label: "Energy", unit: "kcal", tone: "pink" },
  { key: "protein_g", label: "Protein", unit: "g", tone: "blue" },
  { key: "carbs_g", label: "Carbs", unit: "g", tone: "yellow" },
  { key: "fat_g", label: "Fat", unit: "g", tone: "orange" },
];

function dayLabel(day: string) {
  const today = dayKey();
  if (day === today) return "Today";
  if (day === shiftDay(today, -1)) return "Yesterday";
  const [y, m, d] = day.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-AU", { weekday: "short", day: "numeric", month: "short" });
}

type Sheet =
  | { kind: "scan" }
  | { kind: "looking"; barcode: string }
  | { kind: "confirm"; food: Food; grams?: number; editing?: string }
  | { kind: "manual"; draft: Partial<Food>; reason?: string }
  | null;

export function Macros({
  log,
  setLog,
  targets,
}: {
  log: LogEntry[];
  setLog: (next: LogEntry[]) => void;
  targets: Targets | null;
}) {
  const [day, setDay] = useState(dayKey());
  const [sheet, setSheet] = useState<Sheet>(null);
  const [error, setError] = useState("");
  const entries = useMemo(
    () => log.filter((e) => e.date === day).sort((a, b) => a.time.localeCompare(b.time)),
    [log, day],
  );
  const eaten = totals(entries);
  const recent = useMemo(() => {
    const seen = new Set<string>();
    const out: Food[] = [];
    for (const e of [...log].reverse()) {
      const k = e.food.barcode || e.food.name;
      if (!seen.has(k)) {
        seen.add(k);
        out.push(e.food);
      }
      if (out.length === 6) break;
    }
    return out;
  }, [log]);

  async function scanned(barcode: string) {
    setSheet({ kind: "looking", barcode });
    setError("");
    try {
      const res = await lookup(barcode);
      if (res.kind === "found") setSheet({ kind: "confirm", food: res.food });
      else
        setSheet({
          kind: "manual",
          draft: res.kind === "no_macros" ? res.food : { barcode },
          reason:
            res.kind === "missing"
              ? "Open Food Facts doesn't have this barcode yet. Add it from the label and FitBasket will remember it."
              : "Open Food Facts has this product but not all of its nutrition. Fill in the gaps from the label.",
        });
    } catch (e) {
      setSheet({ kind: "manual", draft: { barcode }, reason: (e as Error).message });
    }
  }

  function add(food: Food, grams: number, editing?: string) {
    const now = new Date();
    const time = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
    if (editing) {
      setLog(log.map((e) => (e.id === editing ? { ...e, grams } : e)));
    } else {
      const id = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
      setLog([...log, { id, date: day, time, grams, food }]);
    }
    if (food.source === "manual") rememberFood(food);
    setSheet(null);
  }

  return (
    <div className="macros">
      <div className="day-nav">
        <button type="button" aria-label="Previous day" onClick={() => setDay(shiftDay(day, -1))}>
          ‹
        </button>
        <h3>{dayLabel(day)}</h3>
        <button
          type="button"
          aria-label="Next day"
          disabled={day >= dayKey()}
          onClick={() => setDay(shiftDay(day, 1))}
        >
          ›
        </button>
      </div>

      <div className="macro-bars">
        {MACROS.map((m) => {
          const target = targets ? targets[m.key] : 0;
          const have = eaten[m.key];
          const pct = target ? Math.min(have / target, 1.25) : 0;
          const left = target - have;
          return (
            <div key={m.key} className={`macro macro-${m.tone}`}>
              <div className="macro-head">
                <span>{m.label}</span>
                <b>
                  {r0(have)}
                  {target ? <small> / {r0(target)} {m.unit}</small> : <small> {m.unit}</small>}
                </b>
              </div>
              <div className="macro-track" aria-hidden>
                <div className="macro-fill" style={{ width: `${(pct / 1.25) * 100}%` }} />
                <div className="macro-goal" />
              </div>
              {target > 0 && (
                <p className="macro-left">{left >= 0 ? `${r0(left)} ${m.unit} to go` : `${r0(-left)} ${m.unit} over`}</p>
              )}
            </div>
          );
        })}
      </div>

      <div className="log-actions">
        <button type="button" className="scan-btn" onClick={() => setSheet({ kind: "scan" })}>
          Scan a barcode
        </button>
        <button type="button" className="ghost" onClick={() => setSheet({ kind: "manual", draft: {} })}>
          Add by hand
        </button>
      </div>
      {error && <p className="error">{error}</p>}

      {recent.length > 0 && (
        <div className="recent">
          <p className="fine">Add again</p>
          <ul>
            {recent.map((f) => (
              <li key={f.barcode || f.name}>
                <button type="button" onClick={() => setSheet({ kind: "confirm", food: f })}>
                  {f.name}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {entries.length === 0 ? (
        <div className="panel-empty">
          <p>Nothing logged {day === dayKey() ? "yet today" : "this day"}.</p>
          <p>Scan the barcode on anything you eat, or add home-cooked food by hand.</p>
        </div>
      ) : (
        <ul className="food-log">
          {entries.map((e) => {
            const s = scale(e.food, e.grams);
            return (
              <li key={e.id}>
                {e.food.image ? <img src={e.food.image} alt="" loading="lazy" /> : <span className="food-dot" />}
                <button
                  type="button"
                  className="food-main"
                  onClick={() => setSheet({ kind: "confirm", food: e.food, grams: e.grams, editing: e.id })}
                >
                  <span className="food-name">{e.food.name}</span>
                  <span className="food-meta">
                    {e.time} · {e.grams} g · {r0(s.kcal)} kcal · P {r0(s.protein_g)} C {r0(s.carbs_g)} F{" "}
                    {r0(s.fat_g)}
                  </span>
                </button>
                <button
                  type="button"
                  className="food-del"
                  aria-label={`Remove ${e.food.name}`}
                  onClick={() => setLog(log.filter((x) => x.id !== e.id))}
                >
                  ×
                </button>
              </li>
            );
          })}
        </ul>
      )}

      <p className="fine">
        Product data from <a href="https://world.openfoodfacts.org" target="_blank" rel="noreferrer">Open Food Facts</a>
        , an open database anyone can improve. Your log stays on this phone. Ask the chat “how much protein have I got
        left?” any time.
      </p>
      {targets && <p className="fine">{targets.note}</p>}

      {sheet?.kind === "scan" && <Scanner onCode={scanned} onClose={() => setSheet(null)} />}
      {sheet?.kind === "looking" && (
        <div className="sheet-backdrop">
          <div className="sheet" role="status">
            <p>Looking up {sheet.barcode}…</p>
          </div>
        </div>
      )}
      {sheet?.kind === "confirm" && (
        <ConfirmFood
          food={sheet.food}
          initialGrams={sheet.grams}
          editing={!!sheet.editing}
          onAdd={(g) => add(sheet.food, g, sheet.editing)}
          onClose={() => setSheet(null)}
        />
      )}
      {sheet?.kind === "manual" && (
        <ManualFood
          draft={sheet.draft}
          reason={sheet.reason}
          onSave={(food, grams) => add(food, grams)}
          onClose={() => setSheet(null)}
        />
      )}
    </div>
  );
}

function ConfirmFood({
  food,
  initialGrams,
  editing,
  onAdd,
  onClose,
}: {
  food: Food;
  initialGrams?: number;
  editing: boolean;
  onAdd: (grams: number) => void;
  onClose: () => void;
}) {
  const [grams, setGrams] = useState(String(initialGrams ?? food.serving_g ?? 100));
  const g = Number(grams);
  const ok = Number.isFinite(g) && g > 0 && g <= 5000;
  const s = scale(food, ok ? g : 0);
  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <form
        className="sheet food-sheet"
        role="dialog"
        aria-modal="true"
        aria-label={food.name}
        onClick={(e) => e.stopPropagation()}
        onSubmit={(e) => {
          e.preventDefault();
          if (ok) onAdd(g);
        }}
      >
        <div className="food-hero">
          {food.image && <img src={food.image} alt="" />}
          <div>
            <h2>{food.name}</h2>
            {food.brand && <p className="fine">{food.brand}</p>}
            <p className="fine">
              Per 100 g: {r0(food.per100.kcal)} kcal · P {food.per100.protein_g} · C {food.per100.carbs_g} · F{" "}
              {food.per100.fat_g}
            </p>
          </div>
        </div>
        <label>
          How much did you have?
          <div className="grams-row">
            <input
              inputMode="decimal"
              value={grams}
              onChange={(e) => setGrams(e.target.value.replace(/[^\d.]/g, ""))}
              aria-label="Grams"
            />
            <span>g</span>
          </div>
        </label>
        <div className="quick">
          {food.serving_g && (
            <button type="button" onClick={() => setGrams(String(food.serving_g))}>
              1 serve ({food.serving_g} g)
            </button>
          )}
          {food.serving_g && (
            <button type="button" onClick={() => setGrams(String(food.serving_g! * 2))}>
              2 serves
            </button>
          )}
          <button type="button" onClick={() => setGrams("100")}>
            100 g
          </button>
        </div>
        <p className="food-total">
          <b>{r0(s.kcal)} kcal</b> · {r0(s.protein_g)} g protein · {r0(s.carbs_g)} g carbs · {r0(s.fat_g)} g fat
        </p>
        <div className="sheet-actions">
          <button type="button" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="primary" disabled={!ok}>
            {editing ? "Save" : "Add to log"}
          </button>
        </div>
      </form>
    </div>
  );
}

function ManualFood({
  draft,
  reason,
  onSave,
  onClose,
}: {
  draft: Partial<Food>;
  reason?: string;
  onSave: (food: Food, grams: number) => void;
  onClose: () => void;
}) {
  const known = (v: number | undefined) => (v !== undefined && Number.isFinite(v) ? String(Math.round(v * 10) / 10) : "");
  const [name, setName] = useState(draft.name ?? "");
  // Values from Open Food Facts are per 100 g; a label you're reading usually leads with per serve.
  const [basis, setBasisRaw] = useState<"100g" | "serve">(draft.per100 ? "100g" : "serve");
  const [serve, setServe] = useState(known(draft.serving_g));
  const [energyUnit, setEnergyUnit] = useState<"kJ" | "kcal">("kJ"); // Australian labels lead with kJ
  const [v, setV] = useState({
    energy: draft.per100 ? known(draft.per100.kcal * KJ_PER_KCAL) : "",
    protein: known(draft.per100?.protein_g),
    carbs: known(draft.per100?.carbs_g),
    fat: known(draft.per100?.fat_g),
  });
  const [eaten, setEaten] = useState(draft.per100 ? known(draft.serving_g) || "100" : "1");
  const setBasis = (b: "100g" | "serve") => {
    setBasisRaw(b);
    setEaten(b === "serve" ? "1" : serve || "100");
  };
  const n = (s: string) => (s.trim() === "" ? NaN : Number(s));
  const serveG = n(serve);
  const base = basis === "100g" ? 100 : serveG;
  const kcal = energyUnit === "kJ" ? n(v.energy) / KJ_PER_KCAL : n(v.energy);
  const per = (x: number) => (x / base) * 100;
  const valid =
    name.trim() &&
    base > 0 &&
    [kcal, n(v.protein), n(v.carbs), n(v.fat)].every((x) => Number.isFinite(x) && x >= 0) &&
    n(eaten) > 0;
  const gramsEaten = basis === "serve" ? n(eaten) * serveG : n(eaten);

  const field = (key: keyof typeof v, label: string) => (
    <label>
      {label}
      <input inputMode="decimal" value={v[key]} onChange={(e) => setV({ ...v, [key]: e.target.value.replace(/[^\d.]/g, "") })} />
    </label>
  );

  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <form
        className="sheet food-sheet"
        role="dialog"
        aria-modal="true"
        aria-label="Add food by hand"
        onClick={(e) => e.stopPropagation()}
        onSubmit={(e) => {
          e.preventDefault();
          if (!valid) return;
          onSave(
            {
              name: name.trim(),
              brand: draft.brand,
              barcode: draft.barcode,
              image: draft.image,
              serving_g: basis === "serve" ? serveG : draft.serving_g,
              per100: { kcal: per(kcal), protein_g: per(n(v.protein)), carbs_g: per(n(v.carbs)), fat_g: per(n(v.fat)) },
              source: "manual",
            },
            Math.round(gramsEaten),
          );
        }}
      >
        <h2>Add by hand</h2>
        {reason && <p className="fine">{reason}</p>}
        {draft.barcode && <p className="fine">Barcode {draft.barcode}</p>}
        <label>
          Food
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Chicken fried rice" />
        </label>
        <div className="seg" role="radiogroup" aria-label="Values are per">
          <button type="button" aria-pressed={basis === "serve"} onClick={() => setBasis("serve")}>
            Per serve
          </button>
          <button type="button" aria-pressed={basis === "100g"} onClick={() => setBasis("100g")}>
            Per 100 g
          </button>
        </div>
        {basis === "serve" && (
          <label>
            Serving size (g)
            <input inputMode="decimal" value={serve} onChange={(e) => setServe(e.target.value.replace(/[^\d.]/g, ""))} />
          </label>
        )}
        <div className="nip">
          <label>
            Energy
            <div className="grams-row">
              <input
                inputMode="decimal"
                value={v.energy}
                onChange={(e) => setV({ ...v, energy: e.target.value.replace(/[^\d.]/g, "") })}
              />
              <button
                type="button"
                className="unit"
                onClick={() => {
                  const x = n(v.energy);
                  const next = energyUnit === "kJ" ? "kcal" : "kJ";
                  if (Number.isFinite(x))
                    setV({ ...v, energy: String(Math.round(next === "kcal" ? x / KJ_PER_KCAL : x * KJ_PER_KCAL)) });
                  setEnergyUnit(next);
                }}
              >
                {energyUnit}
              </button>
            </div>
          </label>
          {field("protein", "Protein (g)")}
          {field("carbs", "Carbs (g)")}
          {field("fat", "Fat (g)")}
        </div>
        <label>
          {basis === "serve" ? "Serves you had" : "Grams you had"}
          <input inputMode="decimal" value={eaten} onChange={(e) => setEaten(e.target.value.replace(/[^\d.]/g, ""))} />
        </label>
        <div className="sheet-actions">
          <button type="button" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="primary" disabled={!valid}>
            Add to log
          </button>
        </div>
        <p className="fine">Saved foods appear under “Add again” and are found next time you scan the same barcode.</p>
      </form>
    </div>
  );
}
