import { config as loadEnv } from "dotenv";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// The repo keeps frontend env vars in the root `.env` with `VITE_` prefixes
// (the old Vite app read them from there). Reuse those same values here so no
// duplicate configuration is needed.
loadEnv({ path: path.resolve(__dirname, "..", ".env") });
loadEnv({ path: path.resolve(__dirname, ".env.local") });

const pick = (...keys) => {
  for (const k of keys) {
    if (process.env[k]) return process.env[k];
  }
  return undefined;
};

const rawEnv = {
  NEXT_PUBLIC_API_BASE_URL: pick("NEXT_PUBLIC_API_BASE_URL", "VITE_API_BASE_URL"),
  NEXT_PUBLIC_SUPABASE_URL: pick("NEXT_PUBLIC_SUPABASE_URL", "VITE_SUPABASE_URL"),
  NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: pick(
    "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY",
    "VITE_SUPABASE_PUBLISHABLE_KEY"
  ),
};
// Next.js `env` must contain string values only — drop anything undefined.
const env = Object.fromEntries(
  Object.entries(rawEnv).filter(([, v]) => typeof v === "string" && v.length > 0)
);

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  eslint: { ignoreDuringBuilds: true },
  env,
};

export default nextConfig;
