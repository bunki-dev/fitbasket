import type { WorkoutPlan } from "../types";

const youtubeSearch = (q: string) => `https://www.youtube.com/results?search_query=${encodeURIComponent(q)}`;

export function Workouts({ plan }: { plan: WorkoutPlan | null }) {
  if (!plan) {
    return (
      <div className="panel-empty">
        <p>No workout plan yet.</p>
        <p>Tell me how many days you can train and what you'd like to focus on.</p>
      </div>
    );
  }
  return (
    <div className="workouts">
      {plan.sessions.map((s) => (
        <section key={s.day} className="session">
          <h3>
            {s.day} <span>{s.focus}</span>
          </h3>
          <ol>
            {s.exercises.map((e) => (
              <li key={e.exercise_id}>
                <span className="ex-name">{e.name}</span>
                <span className="ex-rx">{e.prescription}</span>
                <a href={youtubeSearch(e.video_query)} target="_blank" rel="noreferrer">
                  How to
                </a>
              </li>
            ))}
          </ol>
        </section>
      ))}
      <p className="fine">Rest: {plan.rest_days.join(", ")}</p>
      <ul className="notes">
        {plan.notes.map((n) => (
          <li key={n}>{n}</li>
        ))}
      </ul>
    </div>
  );
}
