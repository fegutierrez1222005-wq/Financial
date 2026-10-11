/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Emit a self-contained server bundle so the runtime image carries no build tooling.
  output: "standalone",
  outputFileTracingRoot: process.cwd(),
  // The browser never talks to the API directly and never holds a provider credential:
  // every request goes through a server component or server action that reads the
  // session cookie on the server side.
  env: {
    NEXT_PUBLIC_PRODUCT_NAME: "FINAGENT LAB",
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        ],
      },
    ];
  },
};

export default nextConfig;
