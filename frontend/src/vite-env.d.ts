/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Backend address, e.g. https://api.example.com (default http://localhost:8000) */
  readonly VITE_API_URL?: string;
  /** Shown on the privacy / data-deletion pages */
  readonly VITE_SUPPORT_EMAIL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
