import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow dev HMR from local network IPs (when accessing from phone or another device)
  allowedDevOrigins: ["10.25.46.200", "192.168.*", "10.*"],
};

export default nextConfig;
