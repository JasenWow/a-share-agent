import type { NextConfig } from "next"

const nextConfig: NextConfig = {
  // No standalone output — no Docker
  // Turbopack is enabled via CLI flags in dev script
}

export default nextConfig
