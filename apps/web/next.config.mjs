/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    remotePatterns: [
      { hostname: "maps.googleapis.com" },
      { hostname: "streetviewpixels-pa.googleapis.com" },
      { hostname: "graph.mapillary.com" },
      { hostname: "scontent.mapillary.com" },
    ]
  }
};

export default nextConfig;

