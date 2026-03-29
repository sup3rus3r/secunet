import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source      : "/api/auth/:path*",
        destination : "/api/auth/:path*",
      },
      {
        source      : "/api/:path*",
        destination : `${process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000"}/:path*`,
      },
    ];
  },
};

export default nextConfig;
