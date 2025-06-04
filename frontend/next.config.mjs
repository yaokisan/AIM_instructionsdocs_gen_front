/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*', // フロントエンドが /api/ で始まるパスにアクセスしたら
        destination: 'http://localhost:8000/api/:path*', // ローカルのFastAPIサーバーの同じパスに転送
      },
    ];
  },
};

export default nextConfig;
