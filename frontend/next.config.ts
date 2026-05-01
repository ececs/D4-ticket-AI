import type { NextConfig } from "next";

/**
 * Next.js 15 configuration.
 *
 * Key settings:
 *  - output: "standalone" for Docker deployment (copies only required files)
 *  - images.domains: allow Google profile pictures to be displayed via next/image
 */
const nextConfig: NextConfig = {
  output: "standalone",
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "lh3.googleusercontent.com", // Google profile avatars
        pathname: "/**",
      },
    ],
  },
  // The backend API URL is available server-side via process.env
  // Client-side code uses NEXT_PUBLIC_API_URL (prefixed for browser access)
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
  },
};

export default nextConfig;
