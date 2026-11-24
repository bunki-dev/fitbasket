import type { ChatResponse } from "../types";

const label = (name: string) => {
  const s = name.replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
};

type Last = Pick<ChatResponse, "trace" | "usage" | "latency_ms" | "flags" | "est_cost_usd">;

export function TraceView({ last }: { last: Last | null }) {
  if (!last) {
    return (
      <div className="panel-empty">
        <p>No agent run yet.</p>
        <p>Every message shows here as a timeline of model calls, tool calls and guardrail checks.</p>
      </div>
    );
  }
  const total = Math.max(last.latency_ms, 1);
  return (
    <div className="trace">
      <dl className="trace-stats">
        <div>
          <dt>Latency</dt>
          <dd>{(last.latency_ms / 1000).toFixed(2)} s</dd>
        </div>
        <div>
          <dt>Tokens in / out</dt>
          <dd>
            {last.usage.input_tokens.toLocaleString()} / {last.usage.output_tokens.toLocaleString()}
          </dd>
        </div>
        {last.est_cost_usd != null && (
          <div>
            <dt>Est. cost</dt>
            <dd>${last.est_cost_usd.toFixed(4)}</dd>
          </div>
        )}
      </dl>
      {last.flags.length > 0 && <p className="trace-flags">Guardrail flags: {last.flags.join(", ")}</p>}
      <ol className="spans">
        {last.trace.spans.map((s, i) => (
          <li key={i} className={`span span-${s.kind}${s.error ? " span-error" : ""}`}>
            <div className="span-label">
              <span>{s.kind === "llm" ? "Model call" : label(s.name)}</span>
              <span>{s.duration_ms.toFixed(0)} ms</span>
            </div>
            <div className="span-track">
              <div
                className="span-bar"
                style={{
                  marginLeft: `${(s.start_ms / total) * 100}%`,
                  width: `${Math.max((s.duration_ms / total) * 100, 1)}%`,
                }}
              />
            </div>
            {s.error && <p className="span-err">{s.error}</p>}
          </li>
        ))}
      </ol>
      <p className="fine">Trace {last.trace.trace_id}</p>
    </div>
  );
}
