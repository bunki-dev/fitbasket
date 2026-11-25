// Runs FitBasket's Python agent inside the browser with Pyodide, off the main thread.

const PYODIDE_URL = "https://cdn.jsdelivr.net/pyodide/v314.0.8/full/";
// The version query changes on every deploy, so phones never run a stale cached bundle.
const BUNDLE_URL = `${import.meta.env.BASE_URL}py/fitbasket.zip?v=${import.meta.env.VITE_PY_VERSION ?? "dev"}`;

type Request = { id: number; method: "init" | "chat" | "reset" | "describe"; args: unknown[] };

// Minimal surface of the Pyodide API that we use.
interface Pyodide {
  loadPackage(names: string[]): Promise<void>;
  unpackArchive(buffer: ArrayBuffer, format: string, options: { extractDir: string }): void;
  runPython(code: string): unknown;
  runPythonAsync(code: string): Promise<unknown>;
  globals: { set(name: string, value: unknown): void };
}

// Typed view of the worker global (the project's TS lib is DOM, not WebWorker).
const ctx = self as unknown as {
  postMessage(message: unknown): void;
  onmessage: ((event: MessageEvent<Request>) => void) | null;
};

const progress = (text: string) => ctx.postMessage({ type: "progress", text });

async function boot(): Promise<Pyodide> {
  progress("Downloading the Python runtime (first time only)…");
  const { loadPyodide } = await import(/* @vite-ignore */ `${PYODIDE_URL}pyodide.mjs`);
  const py: Pyodide = await loadPyodide({ indexURL: PYODIDE_URL });
  progress("Loading libraries…");
  await py.loadPackage(["pydantic"]);
  progress("Loading FitBasket…");
  const res = await fetch(BUNDLE_URL);
  if (!res.ok) throw new Error(`Couldn't download the app bundle (${res.status}).`);
  py.unpackArchive(await res.arrayBuffer(), "zip", { extractDir: "/home/pyodide/app" });
  py.runPython("import sys; sys.path.insert(0, '/home/pyodide/app'); import fitbasket.browser as fb");
  return py;
}

const ready = boot();

ctx.onmessage = async (event: MessageEvent<Request>) => {
  const { id, method, args } = event.data;
  try {
    const py = await ready;
    let out: unknown;
    if (method === "init") {
      py.globals.set("_saved", args[0] ?? null);
      out = py.runPython("fb.init(_saved)");
    } else if (method === "reset") {
      out = py.runPython("fb.reset(False)");
    } else if (method === "describe") {
      py.globals.set("_settings", JSON.stringify(args[0] ?? {}));
      out = py.runPython("fb.describe(_settings)");
    } else {
      py.globals.set("_msg", args[0]);
      py.globals.set("_settings", JSON.stringify(args[1] ?? {}));
      py.globals.set("_intake", JSON.stringify(args[2] ?? []));
      out = await py.runPythonAsync("await fb.chat(_msg, _settings, _intake)");
    }
    ctx.postMessage({ type: "result", id, result: JSON.parse(String(out)) });
  } catch (e) {
    ctx.postMessage({ type: "result", id, error: (e as Error).message ?? String(e) });
  }
};
