import { useEffect, useState } from "react";
import type { WorkoutExercise, WorkoutPlan } from "../types";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const todayShort = () => DAYS[(new Date().getDay() + 6) % 7];

const youtubeSearch = (q: string) => `https://www.youtube.com/results?search_query=${encodeURIComponent(q)}`;
const watchUrl = (e: WorkoutExercise) =>
  e.video_id ? `https://www.youtube.com/watch?v=${e.video_id}` : youtubeSearch(e.video_query);

function Video({ e }: { e: WorkoutExercise }) {
  if (!e.video_id) {
    return (
      <a className="video-fallback" href={youtubeSearch(e.video_query)} target="_blank" rel="noreferrer">
        Search YouTube for “{e.video_query}”
      </a>
    );
  }
  return (
    <div className="video">
      <iframe
        src={`https://www.youtube-nocookie.com/embed/${e.video_id}?rel=0&modestbranding=1&playsinline=1`}
        title={e.video_title ?? `How to do ${e.name}`}
        allow="accelerometer; encrypted-media; gyroscope; picture-in-picture; fullscreen"
        allowFullScreen
        loading="lazy"
      />
      <a href={watchUrl(e)} target="_blank" rel="noreferrer">
        Open in YouTube
      </a>
    </div>
  );
}

function FollowAlong({
  day,
  focus,
  exercises,
  onClose,
}: {
  day: string;
  focus: string;
  exercises: WorkoutExercise[];
  onClose: () => void;
}) {
  const [i, setI] = useState(0);
  const e = exercises[i];
  const last = i === exercises.length - 1;
  useEffect(() => {
    const onKey = (ev: KeyboardEvent) => ev.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="follow" role="dialog" aria-modal="true" aria-label={`${day} session`}>
      <header>
        <span>
          {day} · {focus}
        </span>
        <button className="follow-close" onClick={onClose}>
          Done
        </button>
      </header>
      <div className="follow-progress" aria-hidden>
        {exercises.map((x, j) => (
          <span key={x.exercise_id + j} className={j < i ? "done" : j === i ? "now" : ""} />
        ))}
      </div>
      <h2>
        {i + 1}. {e.name}
      </h2>
      <p className="follow-rx">{e.prescription}</p>
      <Video key={e.exercise_id} e={e} />
      <nav className="follow-nav">
        <button onClick={() => setI(i - 1)} disabled={i === 0}>
          Back
        </button>
        {last ? (
          <button className="primary" onClick={onClose}>
            Finish session
          </button>
        ) : (
          <button className="primary" onClick={() => setI(i + 1)}>
            Next: {exercises[i + 1].name}
          </button>
        )}
      </nav>
    </div>
  );
}

export function Workouts({ plan }: { plan: WorkoutPlan | null }) {
  const [open, setOpen] = useState<string | null>(null);
  const [following, setFollowing] = useState<string | null>(null);
  if (!plan) {
    return (
      <div className="panel-empty">
        <p>No workout plan yet.</p>
        <p>Tell me which days you play sport, how many days you can train and what you'd like to focus on.</p>
      </div>
    );
  }
  const today = todayShort();
  const byDay = new Map(plan.sessions.map((s) => [s.day, s]));
  const sport = new Set(plan.sport_days ?? []);
  const active = following ? byDay.get(following) : undefined;

  return (
    <div className="workouts">
      <ol className="week-strip" aria-label="This week">
        {DAYS.map((d) => {
          const s = byDay.get(d);
          const kind = s ? "train" : sport.has(d) ? "sport" : "rest";
          return (
            <li key={d} className={`${kind}${d === today ? " today" : ""}`}>
              <b>{d}</b>
              <span>{s ? s.focus.split(" ")[0] : sport.has(d) ? "Sport" : "Rest"}</span>
            </li>
          );
        })}
      </ol>

      {plan.sessions.map((s) => (
        <section key={s.day} className={`session${s.day === today ? " is-today" : ""}`}>
          <h3>
            {s.day} <span>{s.focus}</span>
            {s.day === today && <em className="today-tag">today</em>}
          </h3>
          <button className="start" onClick={() => setFollowing(s.day)}>
            Start {s.day} session
          </button>
          <ol>
            {s.exercises.map((e, j) => {
              const key = `${s.day}-${e.exercise_id}-${j}`;
              const isOpen = open === key;
              return (
                <li key={key} className={isOpen ? "open" : ""}>
                  <span className="ex-name">{e.name}</span>
                  <span className="ex-rx">{e.prescription}</span>
                  <button className="watch" aria-expanded={isOpen} onClick={() => setOpen(isOpen ? null : key)}>
                    {isOpen ? "Hide" : "Watch"}
                  </button>
                  {isOpen && <Video e={e} />}
                </li>
              );
            })}
          </ol>
        </section>
      ))}
      {plan.rest_days.length > 0 && <p className="fine">Rest: {plan.rest_days.join(", ")}</p>}
      <ul className="notes">
        {plan.notes.map((n) => (
          <li key={n}>{n}</li>
        ))}
      </ul>
      <p className="fine">Videos are hand-picked tutorials from YouTube creators.</p>
      {active && (
        <FollowAlong
          day={active.day}
          focus={active.focus}
          exercises={active.exercises}
          onClose={() => setFollowing(null)}
        />
      )}
    </div>
  );
}
