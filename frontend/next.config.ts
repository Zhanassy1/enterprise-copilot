import type { NextConfig } from "next";

const apiInternal = process.env.API_INTERNAL_URL?.trim() || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  /** Браузер бьёт в same-origin /api/v1/* → Next проксирует на FastAPI (важно при открытии UI по LAN IP). */
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${apiInternal.replace(/\/$/, "")}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
