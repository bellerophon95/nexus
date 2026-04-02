import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/knowledge-base",
        destination: "/",
      },
      {
        source: "/settings",
        destination: "/",
      },
    ];
  },
};

export default nextConfig;
