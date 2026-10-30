/** @type {import('next').NextConfig} */
const isDev = process.env.NODE_ENV === "development";

const nextConfig = {
  // In development the FastAPI server runs separately on port 8000 (npm run dev starts both).
  // On Vercel, /api/py/* is handled by the Python function in api/index.py.
  rewrites: async () => [
    {
      source: "/api/py/:path*",
      destination: isDev ? "http://127.0.0.1:8000/api/py/:path*" : "/api/",
    },
  ],
};

export default nextConfig;
