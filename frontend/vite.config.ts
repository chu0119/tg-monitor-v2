import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    // 监听所有网络接口，支持任何方式访问
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,

    // 允许通过任何域名/IP访问（包括公网域名）
    allowedHosts: ["nas.xiaomuxi.cn", ".xiaomuxi.cn", "localhost", "127.0.0.1"],

    // HMR 热更新配置 - 适配各种访问方式
    hmr: {
      clientPort: 5173,
      host: undefined, // 自动使用请求的主机名
    },

    // API 和 WebSocket 代理配置
    // 无论用什么地址访问前端，API 请求都会被代理到后端
    proxy: {
      "/health": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/api/v1": {
        target: "http://localhost:8000",
        changeOrigin: true, // 保持原始 Host 头，避免后端 CORS 问题
        rewrite: (path) => path, // 保持路径不变
      },
      "/ws": {
        target: "ws://localhost:8000",
        ws: true, // 启用 WebSocket 代理
      },
    },
  },
  // 构建优化
  build: {
    // 代码分割优化
    rollupOptions: {
      output: {
        manualChunks: {
          // 将 React 相关库打包在一起
          'react-vendor': ['react', 'react-dom', 'react-is'],
          // 将路由相关库打包在一起
          'router-vendor': ['@tanstack/react-router'],
          // 将图表库单独打包（较大）
          'charts': ['recharts'],
          // 将 UI 组件库打包
          'ui': ['lucide-react', 'class-variance-authority', 'clsx'],
        },
      },
    },
    // 设置 chunk 大小警告的阈值
    chunkSizeWarningLimit: 1000,
  },
  // 优化依赖预构建
  optimizeDeps: {
    include: ['react', 'react-dom', 'react-is'],
  },
});
