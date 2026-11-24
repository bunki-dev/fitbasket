/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_RUNTIME?: "server" | "browser";
  readonly VITE_PY_VERSION?: string;
}
