/** @type {import('next').NextConfig} */
const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

const nextConfig = {
  reactStrictMode: true,
  // Proxies every /api/* request from the browser straight to the FastAPI
  // backend (see backend/main.py). This is what lets the frontend call
  // fetch("/api/documents") with no CORS handling: from the browser's
  // point of view it's the same origin as the Next.js app, and Next.js
  // forwards the request server-side. Override the target with the
  // BACKEND_URL env var if the API isn't running on localhost:8000.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND_URL}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
