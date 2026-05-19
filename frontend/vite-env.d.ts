/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the backend REST API. Defaults to localhost:8001 if unset. */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
