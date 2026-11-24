import type { MealPlan } from "../types";

const ORDER = ["breakfast", "lunch", "dinner", "snack"] as const;

export function MealWeek({ plan }: { plan: MealPlan | null }) {
  if (!plan) {
    return (
      <div className="panel-empty">
        <p>No meal plan yet.</p>
        <p>Ask me to plan your week and it'll show up here, day by day.</p>
      </div>
    );
  }
  const { daily_avg: avg, targets } = plan;
  return (
    <div className="meals">
      <div className="macro-bar">
        <Gauge label="Calories" value={avg.kcal} target={targets.kcal} unit="kcal" />
        <Gauge label="Protein" value={avg.protein_g} target={targets.protein_g} unit="g" />
      </div>
      <p className="fine">{targets.note}</p>
      {plan.days.map((day) => (
        <section key={day} className="meal-day">
          <h3>{day}</h3>
          <ul>
            {plan.meals
              .filter((m) => m.day === day)
              .sort((a, b) => ORDER.indexOf(a.meal_type) - ORDER.indexOf(b.meal_type))
              .map((m) => (
                <li key={m.meal_type}>
                  <span className="meal-type">{m.meal_type}</span>
                  <span>{m.recipe_name}</span>
                  {m.servings !== 1 && <span className="meal-serves">×{m.servings}</span>}
                </li>
              ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

function Gauge({ label, value, target, unit }: { label: string; value: number; target: number; unit: string }) {
  const pct = Math.min(100, Math.round((value / target) * 100));
  return (
    <div className="gauge">
      <div className="gauge-text">
        <span>{label}</span>
        <span>
          {Math.round(value)} / {target} {unit} a day
        </span>
      </div>
      <div className="gauge-track" role="meter" aria-valuenow={value} aria-valuemin={0} aria-valuemax={target}>
        <div className="gauge-fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
