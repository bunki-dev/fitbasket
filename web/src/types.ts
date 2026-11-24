export interface Macros {
  kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
}

export interface PlannedMeal {
  day: string;
  meal_type: "breakfast" | "lunch" | "dinner" | "snack";
  recipe_id: string;
  recipe_name: string;
  servings: number;
}

export interface MealPlan {
  days: string[];
  meals: PlannedMeal[];
  daily_avg: Macros;
  targets: { kcal: number; protein_g: number; note: string };
}

export interface BasketLine {
  product_id: string;
  name: string;
  brand: string;
  ingredient: string;
  packs: number;
  unit_price: number;
  line_total: number;
  on_special: boolean;
  saving: number;
  needed_qty: number;
  unit: string;
  used_fraction: number;
  pack_label: string;
  was_price: number | null;
  reason: string;
}

export interface Basket {
  lines: BasketLine[];
  total: number;
  total_saving: number;
  specials_used: number;
  covered_by_pantry: string[];
  unavailable: string[];
  budget: number | null;
  within_budget: boolean | null;
  tips: string[];
}

export interface WorkoutPlan {
  sessions: {
    day: string;
    focus: string;
    exercises: { exercise_id: string; name: string; prescription: string; video_query: string }[];
  }[];
  rest_days: string[];
  notes: string[];
}

export interface Profile {
  name: string;
  goal: string;
  diet: string;
  allergies: string[];
  weekly_budget: number | null;
  [key: string]: unknown;
}

export interface AppState {
  profile: Profile;
  pantry: Record<string, number>;
  meal_plan: MealPlan | null;
  basket: Basket | null;
  workout_plan: WorkoutPlan | null;
}

export interface ToolEvent {
  name: string;
  arguments: Record<string, unknown>;
  ok: boolean;
  duration_ms: number;
  error: string | null;
}

export interface Span {
  name: string;
  kind: "llm" | "tool" | "guardrail";
  start_ms: number;
  duration_ms: number;
  attributes: Record<string, unknown>;
  error: string | null;
}

export interface ChatResponse {
  reply: string;
  tool_events: ToolEvent[];
  usage: { input_tokens: number; output_tokens: number };
  est_cost_usd: number | null;
  latency_ms: number;
  flags: string[];
  trace: { trace_id: string; spans: Span[] };
  state: AppState;
}

export interface Turn {
  role: "user" | "assistant";
  text: string;
  meta?: Pick<ChatResponse, "tool_events" | "latency_ms" | "usage" | "flags">;
}
