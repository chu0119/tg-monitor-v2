import { Link, Outlet } from "@tanstack/react-router";
import { useState } from "react";
import {
  LayoutDashboard,
  Activity,
  AlertTriangle,
  Key,
  MessageSquare,
  Bell,
  Users,
  Settings,
  Monitor,
  Menu,
  X,
  MoreHorizontal,
  ChevronUp,
  Globe,
} from "lucide-react";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import InternetStatus from "@/components/InternetStatus";

const navItems = [
  { path: "/", label: "仪表盘", icon: LayoutDashboard, mobilePriority: 0 },
  { path: "/monitoring", label: "实时监控", icon: Activity, mobilePriority: 1 },
  { path: "/alerts", label: "告警中心", icon: AlertTriangle, mobilePriority: 2 },
  { path: "/proxy", label: "代理管理", icon: Globe, mobilePriority: 3 },
  { path: "/keywords", label: "关键词管理", icon: Key, mobilePriority: 4 },
  { path: "/conversations", label: "会话管理", icon: MessageSquare, mobilePriority: 5 },
  { path: "/notifications", label: "通知配置", icon: Bell, mobilePriority: 6 },
  { path: "/accounts", label: "账号管理", icon: Users, mobilePriority: 7 },
  { path: "/settings", label: "系统设置", icon: Settings, mobilePriority: 8 },
  { path: "/bigscreen", label: "监控大屏", icon: Monitor, mobilePriority: 9 },
];

// 手机端底部导航的前3个 + 更多
const mobileNavItems = navItems.filter((item) => item.mobilePriority < 3);
const moreNavItems = navItems.filter((item) => item.mobilePriority >= 3);

export function MainLayout({ children }: { children?: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [moreMenuOpen, setMoreMenuOpen] = useState(false);

  return (
    <div className="min-h-screen bg-background grid-bg">
      {/* 背景扫描线效果 */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden opacity-20 dark:opacity-20 light:opacity-10">
        <div className="w-full h-full bg-gradient-to-b from-transparent via-cyber-blue/5 to-transparent animate-scan-line" />
      </div>

      {/* 顶部导航栏 */}
      <header data-layout-header className="fixed top-0 left-0 right-0 z-50 glass border-b border-cyber-blue/20">
        <div className="flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="lg:hidden p-2 hover:bg-cyber-blue/10 rounded-lg transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center"
            >
              {sidebarOpen ? <X size={24} /> : <Menu size={24} />}
            </button>
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded bg-gradient-to-br from-cyber-blue to-cyber-purple flex items-center justify-center">
                <MessageSquare size={20} className="text-white" />
              </div>
              <h1 className="text-xl font-bold neon-text hidden sm:block">
                听风追影
              </h1>
              {/* 手机端显示简短标题 */}
              <h1 className="text-base font-bold neon-text sm:hidden">
                追影预警
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-2 sm:gap-4">
            <ThemeToggle />
            <InternetStatus />
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-secondary/50 border border-cyber-blue/30">
              <div id="internet-dot" className="w-2 h-2 rounded-full bg-yellow-500 animate-pulse" />
              <span id="internet-text" className="text-sm text-muted-foreground">检测中...</span>
            </div>
            {/* 手机端只显示状态点 */}
            <div className="sm:hidden flex items-center px-2 py-1.5 rounded-full bg-secondary/50 border border-cyber-blue/30">
              <div id="internet-dot-mobile" className="w-2 h-2 rounded-full bg-yellow-500 animate-pulse" />
            </div>
          </div>
        </div>
      </header>

      {/* PC端侧边栏 */}
      <aside data-layout-sidebar
        className={`fixed left-0 top-16 bottom-0 z-40 w-64 glass border-r border-cyber-blue/20 transform transition-transform duration-300 lg:translate-x-0 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        } hidden md:block`}
      >
        <nav className="p-4 space-y-1 overflow-y-auto h-full tech-scrollbar">
          {navItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className="flex items-center gap-3 px-4 py-3 rounded-lg text-muted-foreground hover:text-cyber-blue hover:bg-cyber-blue/10 transition-all group [&.active]:bg-cyber-blue/20 [&.active]:text-cyber-blue"
              activeProps={{ className: "bg-cyber-blue/20 text-cyber-blue" }}
              onClick={() => setSidebarOpen(false)}
            >
              <item.icon size={20} className="group-hover:scale-110 transition-transform" />
              <span className="font-medium">{item.label}</span>
            </Link>
          ))}
        </nav>
      </aside>

      {/* 主内容区 - 手机端底部留出导航栏空间 */}
      <main className="pt-16 lg:pl-64 min-h-screen pb-20 md:pb-0">
        <div className="p-4 md:p-6">{children || <Outlet />}</div>
      </main>

      {/* 遮罩层 (移动端侧边栏) */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-30 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* 手机端底部导航栏 */}
      <nav data-layout-mobile-nav className="fixed bottom-0 left-0 right-0 z-50 bg-gray-950/95 backdrop-blur-lg border-t border-cyber-blue/20 md:hidden">
        <div className="flex items-center justify-around h-14 px-2">
          {mobileNavItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className="flex flex-col items-center justify-center min-w-[60px] min-h-[44px] text-muted-foreground hover:text-cyber-blue transition-colors [&.active]:text-cyber-blue"
              activeProps={{ className: "text-cyber-blue" }}
            >
              <item.icon size={22} />
              <span className="text-[10px] mt-0.5">{item.label}</span>
            </Link>
          ))}
          {/* 更多按钮 */}
          <button
            onClick={() => setMoreMenuOpen(!moreMenuOpen)}
            className={`flex flex-col items-center justify-center min-w-[60px] min-h-[44px] transition-colors ${
              moreMenuOpen ? "text-cyber-blue" : "text-muted-foreground hover:text-cyber-blue"
            }`}
          >
            {moreMenuOpen ? <ChevronUp size={22} /> : <MoreHorizontal size={22} />}
            <span className="text-[10px] mt-0.5">更多</span>
          </button>
        </div>

        {/* 更多菜单抽屉 */}
        {moreMenuOpen && (
          <>
            <div
              className="fixed inset-0 bg-black/70 z-40"
              onClick={() => setMoreMenuOpen(false)}
            />
            <div className="absolute bottom-14 left-0 right-0 bg-gray-950 border-t border-cyber-blue/30 z-50 p-4 animate-in slide-in-from-bottom duration-200">
              <div className="grid grid-cols-3 gap-3">
                {moreNavItems.map((item) => (
                  <Link
                    key={item.path}
                    to={item.path}
                    className="flex flex-col items-center justify-center p-3 rounded-lg bg-secondary/30 hover:bg-cyber-blue/10 text-muted-foreground hover:text-cyber-blue transition-colors [&.active]:text-cyber-blue [&.active]:bg-cyber-blue/20 min-h-[44px]"
                    activeProps={{ className: "text-cyber-blue bg-cyber-blue/20" }}
                    onClick={() => setMoreMenuOpen(false)}
                  >
                    <item.icon size={22} />
                    <span className="text-xs mt-1 text-center">{item.label}</span>
                  </Link>
                ))}
              </div>
            </div>
          </>
        )}
      </nav>
    </div>
  );
}
