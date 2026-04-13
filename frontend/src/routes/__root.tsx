import { createFileRoute, Outlet, redirect, useLocation } from "@tanstack/react-router";
import { MainLayout } from "@/components/layout/MainLayout";
import { api } from "@/lib/api";

// 检查系统是否已初始化
const checkInitialized = async ({ location }: { location: { pathname: string } }) => {
  // 如果当前已经是 setup 页面，不需要检查
  if (location.pathname === "/setup") {
    return;
  }

  try {
    const status = await api.system.getStatus();
    if (status.initialized === false) {
      // 未初始化，重定向到设置页面
      throw redirect({ to: "/setup" });
    }
  } catch (error) {
    // 如果是重定向，继续抛出
    if (error && typeof error === "object" && "to" in error) {
      throw error;
    }
    // 其他错误（如网络错误），忽略
    console.error("Failed to check initialization status:", error);
  }
};

// @ts-expect-error - TanStack Router file route has recursive type
export const Route = createFileRoute("/")({
  beforeLoad: checkInitialized,
  component: RootComponent,
});

function RootComponent() {
  const location = useLocation();

  // setup 页面不使用 MainLayout
  if (location.pathname === "/setup") {
    return <Outlet />;
  }

  return (
    <MainLayout>
      <Outlet />
    </MainLayout>
  );
}
