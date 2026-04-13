import { useEffect, useState, useCallback, useRef } from "react";
import { api } from "@/lib/api";
import {
  MessageSquare,
  AlertTriangle,
  Activity,
  Users,
  Shield,
  Radio,
  Zap,
  Globe,
  Clock,
  TrendingUp,
  Maximize2,
  Minimize2,
} from "lucide-react";
import {
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface DashboardStats {
  total_accounts: number;
  active_accounts: number;
  total_conversations: number;
  active_conversations: number;
  total_messages: number;
  today_messages: number;
  messages_24h: Array<{ hour: string; count: number }>;
  total_alerts: number;
  pending_alerts: number;
  today_alerts: number;
  alerts_by_level: Record<string, number>;
  total_keywords: number;
  active_keywords: number;
  keyword_groups: number;
  total_senders: number;
  updated_at: string;
}

interface HealthStatus {
  status: string;
  resources: { memory_mb: number; cpu_percent: number; memory_percent: number; threads: number; memory_total_gb: number; memory_used_gb: number; memory_available_gb: number; disk_total_gb: number; disk_used_gb: number; disk_free_gb: number; disk_percent: number };
  telegram: { clients_count: number; active_monitors: number };
  websocket: { connections: number };
}

interface AlertItem {
  id: number;
  keyword_text: string;
  keyword_group_name: string;
  alert_level: string;
  message_preview: string;
  created_at: string;
  status: string;
  conversation_id: number;
  sender_username?: string;
  conversation_title?: string;
}

const COLORS = ["#00f0ff", "#ff006e", "#b026ff", "#0aff00", "#ffaa00"];
const LEVEL_COLORS: Record<string, string> = {
  low: "#0aff00",
  medium: "#ffaa00",
  high: "#ff6b00",
  critical: "#ff006e",
};
const LEVEL_MAP: Record<string, string> = {
  critical: "严重",
  high: "高危",
  medium: "中危",
  low: "低危",
};

function AnimatedNumber({ value }: { value: number }) {
  const [display, setDisplay] = useState(0);
  const prevRef = useRef(0);
  useEffect(() => {
    const from = prevRef.current;
    const to = value;
    prevRef.current = to;
    if (from === to) return;
    const duration = 800;
    const start = performance.now();
    function tick(now: number) {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(Math.round(from + (to - from) * eased));
      if (progress < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }, [value]);
  return <>{display.toLocaleString()}</>;
}

function BigStatCard({
  label,
  value,
  unit,
  icon: Icon,
  color,
  glow,
}: {
  label: string;
  value: number | string;
  unit?: string;
  icon: any;
  color: string;
  glow?: string;
}) {
  return (
    <div
      className="relative rounded-xl md:rounded-2xl border border-white/10 bg-gradient-to-br from-white/[0.07] to-transparent p-3 md:p-6 flex flex-col justify-between min-h-[100px] md:min-h-[160px] overflow-hidden"
      style={{ boxShadow: glow ? `inset 0 0 30px ${glow}` : undefined }}
    >
      {/* 顶部发光线 */}
      <div
        className="absolute top-0 left-0 right-0 h-[2px]"
        style={{
          background: `linear-gradient(90deg, transparent, ${color}, transparent)`,
        }}
      />
      <div className="flex items-center gap-1.5 md:gap-2 text-gray-400 text-xs md:text-sm mb-2 md:mb-3">
        <Icon size={14} className="md:w-4 md:h-4" style={{ color }} />
        <span>{label}</span>
      </div>
      <div className="flex items-baseline gap-1">
        <span className="text-2xl md:text-4xl font-bold text-white tracking-tight font-mono">
          {typeof value === "number" ? <AnimatedNumber value={value} /> : value}
        </span>
        {unit && (
          <span className="text-xs md:text-sm text-gray-500">{unit}</span>
        )}
      </div>
    </div>
  );
}

export function BigScreenPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [isFullscreen, setIsFullscreen] = useState(false);
  const alertTableRef = useRef<HTMLDivElement>(null);
  const scrollIntervalRef = useRef<number | null>(null);

  const toggleFullscreen = useCallback(() => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen();
    } else {
      document.exitFullscreen();
    }
  }, []);

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
      // 全屏时隐藏主布局的 header 和 sidebar
      document.documentElement.classList.toggle('bigscreen-active', !!document.fullscreenElement);
    };
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => {
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
      document.documentElement.classList.remove('bigscreen-active');
    };
  }, []);

  const fetchData = useCallback(async () => {
    try {
      const [statsData, healthData] = await Promise.all([
        api.dashboard.getStats(),
        fetch("/health").then((r) => r.json()).catch(() => null),
      ]);
      setStats(statsData);
      setHealth(healthData);
      // 获取最新告警
      try {
        const alertsRes = await api.alerts.list({ page: 1, page_size: 30 });
        setAlerts(alertsRes.items || alertsRes || []);
      } catch {
        // ignore
      }
    } catch (e) {
      console.error("BigScreen fetch error", e);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const dataTimer = setInterval(fetchData, 15000);
    const clockTimer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => {
      clearInterval(dataTimer);
      clearInterval(clockTimer);
    };
  }, [fetchData]);

  // 告警表格自动滚动
  useEffect(() => {
    const container = alertTableRef.current;
    if (!container || alerts.length === 0) return;

    const scrollStep = 40; // 每次滚动的像素(约一行高度)
    let scrollTop = 0;

    const startScrolling = () => {
      scrollIntervalRef.current = window.setInterval(() => {
        if (!container) return;
        scrollTop += scrollStep;
        
        // 滚动到底部后重置
        if (scrollTop >= container.scrollHeight - container.clientHeight) {
          scrollTop = 0;
          container.scrollTop = 0;
        } else {
          container.scrollTop = scrollTop;
        }
      }, 3000);
    };

    startScrolling();

    return () => {
      if (scrollIntervalRef.current) {
        clearInterval(scrollIntervalRef.current);
      }
    };
  }, [alerts]);

  const handleMouseEnter = () => {
    if (scrollIntervalRef.current) {
      clearInterval(scrollIntervalRef.current);
      scrollIntervalRef.current = null;
    }
  };

  const handleMouseLeave = () => {
    const container = alertTableRef.current;
    if (!container || alerts.length === 0) return;

    const scrollStep = 40;
    scrollIntervalRef.current = window.setInterval(() => {
      if (!container) return;
      const newScrollTop = container.scrollTop + scrollStep;
      
      if (newScrollTop >= container.scrollHeight - container.clientHeight) {
        container.scrollTop = 0;
      } else {
        container.scrollTop = newScrollTop;
      }
    }, 3000);
  };

  if (!stats) {
    return (
      <div className="min-h-screen bg-[#030712] flex items-center justify-center">
        <div className="flex items-center gap-3 text-cyber-blue text-xl">
          <Radio className="animate-pulse" size={28} />
          <span>正在加载监控大屏...</span>
        </div>
      </div>
    );
  }

  const alertsPieData = Object.entries(stats.alerts_by_level || {}).map(
    ([name, value]) => ({ name: LEVEL_MAP[name] || name, value })
  );
  const messagesTrend = stats.messages_24h || [];

  // 计算运行时间指标
  const msgRate =
    stats.today_messages > 0
      ? (stats.today_messages / (new Date().getHours() || 1)).toFixed(1)
      : "0";

  return (
    <div className={`bg-[#030712] text-white ${isFullscreen ? 'fixed inset-0 z-[9999] overflow-hidden' : 'min-h-screen overflow-auto'}`}>
      {/* 背景网格 */}
      <div
        className="fixed inset-0 opacity-30 pointer-events-none"
        style={{
          backgroundImage:
            "linear-gradient(rgba(0,240,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(0,240,255,0.03) 1px, transparent 1px)",
          backgroundSize: "60px 60px",
        }}
      />

      {/* 顶部标题栏 */}
      <div className="relative z-10 border-b border-white/10 bg-black/40 backdrop-blur-sm sticky top-0">
        <div className="flex flex-col md:flex-row items-center justify-between px-4 md:px-8 py-3 md:py-4 gap-2 md:gap-0">
          <div className="flex items-center gap-3 md:gap-4">
            <div className="w-8 h-8 md:w-10 md:h-10 rounded-lg md:rounded-xl bg-gradient-to-br from-cyber-blue to-cyber-purple flex items-center justify-center">
              <Shield size={18} className="md:w-[22px] md:h-[22px]" />
            </div>
            <div className="text-center md:text-left">
              <h1 className="text-lg md:text-2xl font-bold tracking-wide">
                听风追影–群组数据预警分析系统
              </h1>
              <p className="hidden md:block text-xs text-gray-500 mt-0.5">
                TELEGRAM MONITORING & ALERT SYSTEM
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4 md:gap-8 w-full md:w-auto justify-between md:justify-end">
            <div className="flex items-center gap-2">
              <div
                className={`w-2 h-2 md:w-2.5 md:h-2.5 rounded-full ${
                  health?.status === "healthy"
                    ? "bg-green-400 shadow-[0_0_10px_rgba(74,222,128,0.8)]"
                    : "bg-red-400 shadow-[0_0_10px_rgba(248,113,113,0.8)] animate-pulse"
                }`}
              />
              <span className="text-xs md:text-sm text-gray-300">
                {health?.status === "healthy" ? "系统正常运行" : "系统异常"}
              </span>
            </div>
            <button
              onClick={toggleFullscreen}
              className="p-1.5 md:p-2 rounded-lg bg-white/5 hover:bg-white/10 transition-colors"
              title={isFullscreen ? "退出全屏" : "全屏"}
            >
              {isFullscreen ? (
                <Minimize2 size={16} className="md:w-5 md:h-5 text-gray-300" />
              ) : (
                <Maximize2 size={16} className="md:w-5 md:h-5 text-gray-300" />
              )}
            </button>
            <div className="text-right">
              <p className="text-lg md:text-2xl font-mono text-cyber-blue tracking-wider">
                {currentTime.toLocaleTimeString("zh-CN", { hour12: false })}
              </p>
              <p className="hidden md:block text-xs text-gray-500 font-mono">
                {currentTime.toLocaleDateString("zh-CN", {
                  year: "numeric",
                  month: "2-digit",
                  day: "2-digit",
                  weekday: "long",
                })}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* 主内容区 */}
      <div className={`relative z-10 p-3 md:p-6 grid grid-cols-1 md:grid-cols-12 gap-3 md:gap-4 auto-rows-auto md:grid-rows-[auto_1fr_1fr] ${isFullscreen ? 'h-[calc(100vh-72px)]' : ''}`}>
        {/* 第一行：核心指标 */}
        <div className="col-span-12 grid grid-cols-2 md:grid-cols-6 gap-3 md:gap-4">
          <BigStatCard
            label="监控账号"
            value={stats.active_accounts}
            icon={Users}
            color="#00f0ff"
            glow="rgba(0,240,255,0.05)"
          />
          <BigStatCard
            label="监控频道"
            value={stats.active_conversations}
            icon={Globe}
            color="#b026ff"
            glow="rgba(176,38,255,0.05)"
          />
          <BigStatCard
            label="今日消息"
            value={stats.today_messages}
            icon={MessageSquare}
            color="#0aff00"
            glow="rgba(10,255,0,0.05)"
          />
          <BigStatCard
            label="待处理告警"
            value={stats.pending_alerts}
            icon={AlertTriangle}
            color="#ff006e"
            glow="rgba(255,0,110,0.05)"
          />
          <BigStatCard
            label="消息速率"
            value={msgRate}
            unit="条/时"
            icon={Zap}
            color="#ffaa00"
            glow="rgba(255,170,0,0.05)"
          />
          <BigStatCard
            label="活跃关键词"
            value={stats.active_keywords}
            icon={Activity}
            color="#00f0ff"
            glow="rgba(0,240,255,0.05)"
          />
        </div>

        {/* 第二行：趋势图 + 告警饼图 */}
        <div className="col-span-12 md:col-span-8 rounded-xl md:rounded-2xl border border-white/10 bg-white/[0.03] backdrop-blur-sm p-3 md:p-5 flex flex-col h-[200px] md:h-auto">
          <div className="flex items-center justify-between mb-2 md:mb-3">
            <h3 className="text-sm md:text-base font-semibold text-gray-200 flex items-center gap-2">
              <TrendingUp size={14} className="md:w-4 md:h-4 text-cyber-blue" />
              24小时消息趋势
            </h3>
            <span className="text-xs text-gray-500 font-mono">
              TOTAL: {stats.total_messages.toLocaleString()}
            </span>
          </div>
          <div className="flex-1">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={messagesTrend}>
                <defs>
                  <linearGradient id="bsGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#00f0ff" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="#00f0ff" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="rgba(255,255,255,0.04)"
                />
                <XAxis
                  dataKey="hour"
                  name="时间"
                  stroke="#555"
                  fontSize={10}
                  interval="preserveStartEnd"
                  tick={{ fontSize: 10 }}
                />
                <YAxis stroke="#555" fontSize={10} tick={{ fontSize: 10 }} />
                <Tooltip
                  contentStyle={{
                    background: "rgba(3,7,18,0.95)",
                    border: "1px solid rgba(0,240,255,0.3)",
                    borderRadius: "8px",
                    color: "#fff",
                    fontSize: 12,
                  }}
                  formatter={(value: number, name: string) => [value, name === "count" ? "消息数" : name === "hour" ? "时间" : name]}
                  labelFormatter={(label) => `时间: ${label}`}
                />
                <Area
                  type="monotone"
                  dataKey="count"
                  name="消息数"
                  stroke="#00f0ff"
                  strokeWidth={2}
                  fill="url(#bsGrad)"
                  dot={false}
                  activeDot={{ r: 4, fill: "#00f0ff", stroke: "#030712", strokeWidth: 2 }}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* 告警级别分布 */}
        <div className="col-span-12 md:col-span-4 rounded-xl md:rounded-2xl border border-white/10 bg-white/[0.03] backdrop-blur-sm p-3 md:p-5 flex flex-col h-[200px] md:h-auto">
          <h3 className="text-sm md:text-base font-semibold text-gray-200 mb-2 md:mb-3 flex items-center gap-2">
            <AlertTriangle size={14} className="md:w-4 md:h-4 text-cyber-pink" />
            告警级别分布
          </h3>
          <div className="flex-1">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={alertsPieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={30}
                  outerRadius={48}
                  paddingAngle={4}
                  dataKey="value"
                  stroke="none"
                >
                  {alertsPieData.map((_, i) => (
                    <Cell
                      key={i}
                      fill={COLORS[i % COLORS.length]}
                    />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    background: "rgba(3,7,18,0.95)",
                    border: "1px solid rgba(0,240,255,0.3)",
                    borderRadius: "8px",
                    color: "#ffffff",
                    fontSize: 13,
                    fontWeight: "bold",
                  }}
                  formatter={(value: number, name: string) => [<span style={{ color: "#fff" }}>{value}</span>, <span style={{ color: "#fff" }}>{name}</span>]}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="flex flex-wrap justify-center gap-x-3 md:gap-x-4 gap-y-1 mt-1">
            {alertsPieData.map((item, i) => (
              <div key={item.name} className="flex items-center gap-1 text-xs">
                <div
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: COLORS[i % COLORS.length] }}
                />
                <span className="text-gray-400">
                  {item.name} {item.value}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* 第三行：最新告警 + 系统状态 */}
        <div className="col-span-12 md:col-span-8 rounded-xl md:rounded-2xl border border-white/10 bg-white/[0.03] backdrop-blur-sm p-3 md:p-5 flex flex-col min-h-[280px] md:h-auto">
          <h3 className="text-sm md:text-base font-semibold text-gray-200 mb-2 md:mb-3 flex items-center gap-2">
            <AlertTriangle size={14} className="md:w-4 md:h-4 text-cyber-pink" />
            最新告警
            {alerts.length > 0 && (
              <span className="text-xs bg-cyber-pink/20 text-cyber-pink px-2 py-0.5 rounded-full">
                {alerts.length}
              </span>
            )}
          </h3>
          <div
            ref={alertTableRef}
            className="flex-1 overflow-auto tech-scrollbar"
            onMouseEnter={handleMouseEnter}
            onMouseLeave={handleMouseLeave}
          >
            {alerts.length === 0 ? (
              <div className="flex items-center justify-center h-full text-gray-500">
                <div className="text-center">
                  <Shield size={28} className="mx-auto mb-2 opacity-30 md:w-8 md:h-8" />
                  <p className="text-sm">暂无告警</p>
                </div>
              </div>
            ) : (
              <>
                {/* 手机端卡片式布局 */}
                <div className="md:hidden space-y-2">
                  {alerts.slice(0, 10).map((alert) => (
                    <div
                      key={alert.id}
                      className="border-b border-white/5 pb-2 last:border-0"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span
                          className="inline-block px-2 py-0.5 rounded text-xs font-medium"
                          style={{
                            backgroundColor: `${LEVEL_COLORS[alert.alert_level] || "#666"}20`,
                            color: LEVEL_COLORS[alert.alert_level] || "#666",
                          }}
                        >
                          {LEVEL_MAP[alert.alert_level] || alert.alert_level || "低危"}
                        </span>
                        <span className="text-xs text-gray-500">
                          {alert.created_at
                            ? new Date(alert.created_at).toLocaleTimeString("zh-CN", {
                                hour12: false,
                              })
                            : "--"}
                        </span>
                      </div>
                      <div className="text-sm text-cyber-blue mb-1">
                        {alert.keyword_text}
                      </div>
                      <div className="text-xs text-gray-400">
                        {alert.conversation_title || `#${alert.conversation_id}`}
                      </div>
                    </div>
                  ))}
                </div>

                {/* PC端表格布局 */}
                <table className="hidden md:table w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/10">
                      <th className="text-left py-2 px-3 text-gray-500 font-medium">
                        级别
                      </th>
                      <th className="text-left py-2 px-3 text-gray-500 font-medium">
                        关键词
                      </th>
                      <th className="text-left py-2 px-3 text-gray-500 font-medium">
                        来源
                      </th>
                      <th className="text-left py-2 px-3 text-gray-500 font-medium">
                        消息预览
                      </th>
                      <th className="text-left py-2 px-3 text-gray-500 font-medium">
                        时间
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {alerts.slice(0, 8).map((alert) => (
                      <tr
                        key={alert.id}
                        className="border-b border-white/5 hover:bg-white/[0.03] transition-colors"
                      >
                        <td className="py-2.5 px-3">
                          <span
                            className="inline-block px-2 py-0.5 rounded text-xs font-medium"
                            style={{
                              backgroundColor: `${LEVEL_COLORS[alert.alert_level] || "#666"}20`,
                              color: LEVEL_COLORS[alert.alert_level] || "#666",
                            }}
                          >
                            {LEVEL_MAP[alert.alert_level] || alert.alert_level || "低危"}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-cyber-blue">
                          {alert.keyword_text}
                        </td>
                        <td className="py-2.5 px-3 text-gray-400">
                          {alert.conversation_title || `#${alert.conversation_id}`}
                        </td>
                        <td className="py-2.5 px-3 text-gray-300 max-w-[300px] truncate">
                          {alert.message_preview || "--"}
                        </td>
                        <td className="py-2.5 px-3 text-gray-500 text-xs whitespace-nowrap">
                          <Clock size={11} className="inline mr-1" />
                          {alert.created_at
                            ? new Date(alert.created_at).toLocaleTimeString("zh-CN", {
                                hour12: false,
                              })
                            : "--"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </div>
        </div>

        {/* 系统状态面板 */}
        <div className="col-span-12 md:col-span-4 rounded-xl md:rounded-2xl border border-white/10 bg-white/[0.03] backdrop-blur-sm p-3 md:p-5 flex flex-col">
          <h3 className="text-sm md:text-base font-semibold text-gray-200 mb-3 md:mb-4 flex items-center gap-2">
            <Shield size={14} className="md:w-4 md:h-4 text-cyber-blue" />
            系统状态
          </h3>
          <div className="flex-1 space-y-3 md:space-y-5">
            {/* CPU */}
            <div>
              <div className="flex justify-between text-xs md:text-sm mb-1 md:mb-1.5">
                <span className="text-gray-400">CPU 使用率</span>
                <span className="text-gray-300 font-mono">
                  {health?.resources?.cpu_percent?.toFixed(1) || "0"}%
                </span>
              </div>
              <div className="h-1.5 md:h-2 rounded-full bg-white/10 overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-1000"
                  style={{
                    width: `${Math.min(health?.resources?.cpu_percent || 0, 100)}%`,
                    background:
                      (health?.resources?.cpu_percent || 0) > 80
                        ? "#ff006e"
                        : (health?.resources?.cpu_percent || 0) > 50
                        ? "#ffaa00"
                        : "#0aff00",
                  }}
                />
              </div>
            </div>

            {/* Memory */}
            <div>
              <div className="flex justify-between text-xs md:text-sm mb-1 md:mb-1.5">
                <span className="text-gray-400">内存使用</span>
                <span className="text-gray-300 font-mono">
                  {health?.resources?.memory_used_gb?.toFixed(1) || "0"} / {health?.resources?.memory_total_gb?.toFixed(1) || "0"} GB
                </span>
              </div>
              <div className="h-1.5 md:h-2 rounded-full bg-white/10 overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-1000"
                  style={{
                    width: `${Math.min(health?.resources?.memory_percent || 0, 100)}%`,
                    background:
                      (health?.resources?.memory_percent || 0) > 80
                        ? "#ff006e"
                        : (health?.resources?.memory_percent || 0) > 50
                        ? "#ffaa00"
                        : "#00f0ff",
                  }}
                />
              </div>
              <div className="text-xs text-gray-500 mt-0.5">
                可用 {health?.resources?.memory_available_gb?.toFixed(1) || "0"} GB ({health?.resources?.memory_percent?.toFixed(1) || "0"}%)
              </div>
            </div>

            {/* Disk */}
            <div>
              <div className="flex justify-between text-xs md:text-sm mb-1 md:mb-1.5">
                <span className="text-gray-400">硬盘使用</span>
                <span className="text-gray-300 font-mono">
                  {health?.resources?.disk_used_gb?.toFixed(1) || "0"} / {health?.resources?.disk_total_gb?.toFixed(1) || "0"} GB
                </span>
              </div>
              <div className="h-1.5 md:h-2 rounded-full bg-white/10 overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-1000"
                  style={{
                    width: `${Math.min(health?.resources?.disk_percent || 0, 100)}%`,
                    background:
                      (health?.resources?.disk_percent || 0) > 90
                        ? "#ff006e"
                        : (health?.resources?.disk_percent || 0) > 70
                        ? "#ffaa00"
                        : "#00f0ff",
                  }}
                />
              </div>
              <div className="text-xs text-gray-500 mt-0.5">
                剩余 {health?.resources?.disk_free_gb?.toFixed(1) || "0"} GB ({health?.resources?.disk_percent?.toFixed(1) || "0"}%)
              </div>
            </div>

            {/* 运行指标 */}
            <div className="grid grid-cols-2 gap-2 md:gap-3 pt-1 md:pt-2">
              <div className="rounded-lg bg-white/[0.04] p-2 md:p-3 text-center">
                <p className="text-xs text-gray-500 mb-0.5 md:mb-1">TG 客户端</p>
                <p className="text-lg md:text-xl font-bold text-cyber-blue font-mono">
                  {health?.telegram?.clients_count || 0}
                </p>
              </div>
              <div className="rounded-lg bg-white/[0.04] p-2 md:p-3 text-center">
                <p className="text-xs text-gray-500 mb-0.5 md:mb-1">活跃监控</p>
                <p className="text-lg md:text-xl font-bold text-cyber-purple font-mono">
                  {health?.telegram?.active_monitors || 0}
                </p>
              </div>
              <div className="rounded-lg bg-white/[0.04] p-2 md:p-3 text-center">
                <p className="text-xs text-gray-500 mb-0.5 md:mb-1">WebSocket</p>
                <p className="text-lg md:text-xl font-bold text-cyber-green font-mono">
                  {health?.websocket?.connections || 0}
                </p>
              </div>
              <div className="rounded-lg bg-white/[0.04] p-2 md:p-3 text-center">
                <p className="text-xs text-gray-500 mb-0.5 md:mb-1">线程数</p>
                <p className="text-lg md:text-xl font-bold text-gray-300 font-mono">
                  {health?.resources?.threads || 0}
                </p>
              </div>
            </div>

            {/* 累计统计 */}
            <div className="pt-1 md:pt-2 border-t border-white/5 space-y-1.5 md:space-y-2 text-xs md:text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500">累计消息</span>
                <span className="text-gray-300 font-mono">
                  {stats.total_messages.toLocaleString()}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">累计告警</span>
                <span className="text-gray-300 font-mono">
                  {stats.total_alerts.toLocaleString()}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">发送者总数</span>
                <span className="text-gray-300 font-mono">
                  {stats.total_senders.toLocaleString()}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
