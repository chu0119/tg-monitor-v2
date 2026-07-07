import { createFileRoute } from "@tanstack/react-router";
import { BigScreenPage } from "@/pages/BigScreenPage";
import { Monitor, Smartphone } from "lucide-react";

export const Route = createFileRoute("/bigscreen")({
  component: BigScreenWrapper,
});

function BigScreenWrapper() {
  // 检测是否为移动设备
  const isMobile = typeof window !== "undefined" && window.innerWidth < 768;

  if (isMobile) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-6">
        <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-cyber-blue/20 to-cyber-purple/20 flex items-center justify-center mb-6">
          <Monitor size={40} className="text-cyber-blue" />
        </div>
        <h2 className="text-2xl font-bold text-foreground mb-3">监控大屏</h2>
        <p className="text-muted-foreground mb-2 max-w-sm">
          大屏模式专为桌面显示器设计，请使用电脑访问以获得最佳体验
        </p>
        <div className="flex items-center gap-2 text-sm text-cyber-blue mt-4">
          <Smartphone size={16} />
          <span>当前为移动端，建议屏幕宽度 ≥ 768px</span>
        </div>
        <p className="text-xs text-muted-foreground mt-6">
          您可以返回仪表盘查看移动端优化的监控界面
        </p>
      </div>
    );
  }

  return <BigScreenPage />;
}
