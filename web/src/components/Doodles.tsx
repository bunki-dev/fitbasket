// Small hand-drawn marks used around the interface.

export function Scribble() {
  return (
    <svg className="scribble" viewBox="0 0 120 14" preserveAspectRatio="none" aria-hidden="true">
      <path d="M2 9c14-6 24 4 38-1s22-5 36 0 26 3 42-3" fill="none" stroke="currentColor" strokeWidth="2.4"
        strokeLinecap="round" />
    </svg>
  );
}

export function Arrow() {
  return (
    <svg className="doodle-arrow" viewBox="0 0 60 40" aria-hidden="true">
      <path d="M4 6c10 20 26 28 46 26M42 24l9 8-11 4" fill="none" stroke="currentColor" strokeWidth="2.4"
        strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Wordmark() {
  return (
    <span className="wordmark" aria-label="FitBasket">
      <span aria-hidden="true" className="wordmark-print" data-text="FitBasket">
        FitBasket
      </span>
    </span>
  );
}

// Bottom-nav icons, drawn with a slightly wobbly hand.
const NAV_PATHS: Record<string, { ink: string; tint: string }> = {
  chat: { ink: "M5 6c5-2 10-2 14 0 1 3 1 7 0 9-3 1-7 1-10 0l-4 4 1-5c-2-3-2-6-1-8z", tint: "M6 7h12v7H6z" },
  basket: { ink: "M3 10c6-1 12-1 18 0l-2 10c-4 1-10 1-14 0zM8 10l4-6 4 6", tint: "M5 11h14l-2 8H7z" },
  meals: { ink: "M7 3v7c0 2-1 3-2 3M9 3v7c0 2 1 3 2 3M7 13v8M17 3c-3 3-3 8 0 10v8", tint: "M15 4c-2 3-2 7 0 9z" },
  workouts: { ink: "M3 10v4M6 7v10M18 7v10M21 10v4M6 12c4-1 8 1 12 0", tint: "M5 8h2v8H5zM17 8h2v8h-2z" },
};

export function NavIcon({ id }: { id: string }) {
  const p = NAV_PATHS[id];
  if (!p) return null;
  return (
    <svg viewBox="0 0 24 24" width="26" height="26" aria-hidden="true" className="nav-icon">
      <path d={p.tint} className="nav-icon-tint" transform="translate(1 0.8)" />
      <path d={p.ink} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"
        strokeLinejoin="round" />
    </svg>
  );
}
