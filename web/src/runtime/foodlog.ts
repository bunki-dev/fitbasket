// Food log: lives on this device only. Products come from Open Food Facts (real, open data);
// anything it doesn't have can be added by hand and is remembered for the next scan.

export interface Per100 {
  kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
}

export interface Food {
  name: string;
  brand?: string;
  barcode?: string;
  per100: Per100;
  serving_g?: number; // grams in one serving, when known
  image?: string;
  source: "openfoodfacts" | "manual";
}

export interface LogEntry {
  id: string;
  date: string; // YYYY-MM-DD, local time
  time: string; // HH:MM
  grams: number;
  food: Food;
}

/** What the Python agent receives (matches fitbasket.models.FoodEntry). */
export interface FoodEntryOut {
  name: string;
  grams: number;
  kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  source: "openfoodfacts" | "manual";
}

const LOG_KEY = "fitbasket.foodlog";
const MY_FOODS_KEY = "fitbasket.myfoods";
const KEEP_DAYS = 90;

const pad = (n: number) => String(n).padStart(2, "0");
export const dayKey = (d = new Date()) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
export const shiftDay = (day: string, by: number) => {
  const [y, m, d] = day.split("-").map(Number);
  return dayKey(new Date(y, m - 1, d + by));
};

function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function write(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage full or blocked: the log lasts for this visit */
  }
}

export function loadLog(): LogEntry[] {
  return read<LogEntry[]>(LOG_KEY, []);
}

export function saveLog(entries: LogEntry[]) {
  const cutoff = shiftDay(dayKey(), -KEEP_DAYS);
  write(
    LOG_KEY,
    entries.filter((e) => e.date >= cutoff),
  );
}

export function loadMyFoods(): Food[] {
  return read<Food[]>(MY_FOODS_KEY, []);
}

export function rememberFood(food: Food) {
  const mine = loadMyFoods().filter((f) => !(food.barcode && f.barcode === food.barcode) && f.name !== food.name);
  write(MY_FOODS_KEY, [food, ...mine].slice(0, 200));
}

export const scale = (food: Food, grams: number): Per100 => {
  const k = grams / 100;
  return {
    kcal: food.per100.kcal * k,
    protein_g: food.per100.protein_g * k,
    carbs_g: food.per100.carbs_g * k,
    fat_g: food.per100.fat_g * k,
  };
};

export function totals(entries: LogEntry[]): Per100 {
  return entries.reduce(
    (t, e) => {
      const s = scale(e.food, e.grams);
      return {
        kcal: t.kcal + s.kcal,
        protein_g: t.protein_g + s.protein_g,
        carbs_g: t.carbs_g + s.carbs_g,
        fat_g: t.fat_g + s.fat_g,
      };
    },
    { kcal: 0, protein_g: 0, carbs_g: 0, fat_g: 0 },
  );
}

export function forAgent(entries: LogEntry[]): FoodEntryOut[] {
  return entries.map((e) => {
    const s = scale(e.food, e.grams);
    const r = (n: number) => Math.round(n * 10) / 10;
    return {
      name: [e.food.brand, e.food.name].filter(Boolean).join(" ").slice(0, 120),
      grams: e.grams,
      kcal: r(s.kcal),
      protein_g: r(s.protein_g),
      carbs_g: r(s.carbs_g),
      fat_g: r(s.fat_g),
      source: e.food.source,
    };
  });
}

export const todaysEntries = () => loadLog().filter((e) => e.date === dayKey());

// ---------- Open Food Facts ----------

export const validBarcode = (code: string) => /^\d{8}$|^\d{12,14}$/.test(code);

const OFF_FIELDS = "code,product_name,product_name_en,brands,nutriments,serving_quantity,image_front_small_url";

export type Lookup = { kind: "found"; food: Food } | { kind: "missing" } | { kind: "no_macros"; food: Food };

/** Finds a product by barcode: your own foods first, then Open Food Facts. */
export async function lookup(barcode: string): Promise<Lookup> {
  const mine = loadMyFoods().find((f) => f.barcode === barcode);
  if (mine) return { kind: "found", food: mine };

  const url = `https://world.openfoodfacts.org/api/v2/product/${barcode}.json?fields=${OFF_FIELDS}`;
  const res = await fetch(url);
  if (res.status === 404) return { kind: "missing" };
  if (!res.ok) throw new Error(`Open Food Facts didn't respond (${res.status}). Try again or add it by hand.`);
  const data = await res.json();
  if (data.status !== 1 || !data.product) return { kind: "missing" };
  const p = data.product;
  const n = p.nutriments ?? {};
  const num = (v: unknown) => (typeof v === "number" ? v : typeof v === "string" && v.trim() ? Number(v) : NaN);
  let kcal = num(n["energy-kcal_100g"]);
  if (!Number.isFinite(kcal) && Number.isFinite(num(n["energy_100g"]))) kcal = num(n["energy_100g"]) / 4.184; // kJ
  const food: Food = {
    name: (p.product_name_en || p.product_name || "Unnamed product").trim(),
    brand: (p.brands || "").split(",")[0].trim() || undefined,
    barcode,
    per100: {
      kcal: kcal,
      protein_g: num(n.proteins_100g),
      carbs_g: num(n.carbohydrates_100g),
      fat_g: num(n.fat_100g),
    },
    serving_g: num(p.serving_quantity) > 0 ? num(p.serving_quantity) : undefined,
    image: p.image_front_small_url || undefined,
    source: "openfoodfacts",
  };
  const complete = Object.values(food.per100).every((v) => Number.isFinite(v) && v >= 0);
  if (!complete) {
    // Keep what's known so the manual form starts pre-filled.
    for (const k of Object.keys(food.per100) as (keyof Per100)[]) {
      if (!Number.isFinite(food.per100[k])) food.per100[k] = NaN;
    }
    return { kind: "no_macros", food };
  }
  return { kind: "found", food };
}
