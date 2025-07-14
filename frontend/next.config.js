/** @type {import('next').NextConfig} */
const nextConfig = {
  // Optimize CSS loading
  optimizeFonts: true,
  poweredByHeader: false,
  reactStrictMode: true,
  swcMinify: true,
  compiler: {
    removeConsole: process.env.NODE_ENV === "production",
  },
  experimental: {
    optimizeCss: true, // Enable CSS optimization
  },
  // Ignore favicon for now
  webpack: (config) => {
    config.ignoreWarnings = [
      { module: /public\/favicon.ico$/ }
    ];
    return config;
  }
};

module.exports = nextConfig; 