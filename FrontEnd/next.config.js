/** @type {import('next').NextConfig} */
const nextConfig = {
  // Rewrites are no longer needed as Nginx handles the proxying
  /*
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://127.0.0.1:8000/:path*', // Proxy to Backend
      },
      {
        source: '/docs',
        destination: 'http://127.0.0.1:8000/docs', // Proxy Swagger UI
      },
      {
        source: '/openapi.json',
        destination: 'http://127.0.0.1:8000/openapi.json', // Proxy OpenAPI schema
      },
    ]
  },
  */
};

module.exports = nextConfig;
