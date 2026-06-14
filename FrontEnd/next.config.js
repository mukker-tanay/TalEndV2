const { withSentryConfig } = require("@sentry/nextjs");

/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://127.0.0.1:8080/:path*',
      },
      {
        source: '/docs',
        destination: 'http://127.0.0.1:8080/docs',
      },
      {
        source: '/openapi.json',
        destination: 'http://127.0.0.1:8080/openapi.json',
      },
    ];
  },
};

module.exports = withSentryConfig(nextConfig, {
  silent: true,
  hideSourceMaps: true,
});
