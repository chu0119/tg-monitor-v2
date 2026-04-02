import { useEffect, useState, useCallback, useRef, memo } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import {
  MessageSquare,
  AlertTriangle,
  Activity,
  Users,
  Eye,
  TrendingUp,
  Zap,
  Radio,
  Shield,
} from "lucide-react";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
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
  resources: { memory_mb: number; cpu_percent: number; memory_percent: number; memory_total_gb: number; memory_used_gb: number; disk_total_gb: number; disk_used_gb: number; disk_free_gb: number; disk_percent: number };
  telegram: { clients_count: number; active_monitors: number };
  websocket: { connections: number };
}

const COLORS = ["#00f0ff", "#ff006e", "#b026ff", "#0aff00", "#ffaa00"];

const LEVEL_MAP: Record<string, string> = {
  critical: "严重",
  high: "高危",
  medium: "中危",
  low: "低危",
};

const LiveClock = memo(function LiveClock() {
  const [currentTime, setCurrentTime] = useState(new Date());
  useEffect(() => {
    const timer = window.setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);
  return (
    <div className="text-left sm:text-right">
      <p className="text-xl sm:text-2xl font-mono text-cyber-blue">
        {currentTime.toLocaleTimeString("zh-CN", { hour12: false })}
      </p>
      <p className="text-xs text-muted-foreground">
        {currentTime.toLocaleDateString("zh-CN", {
          year: "numeric",
          month: "2-digit",
          day: "2-digit",
          weekday: "short",
        })}
      </p>
    </div>
  );
});

function StatCard({
  title,
  value,
  icon: Icon,
  color,
  sub,
}: {
  title: string;
  value: number | string;
  icon: any;
  color: string;
  sub?: string;
}) {
  return (
    <div className="relative overflow-hidden rounded-xl border border-white/10 bg-white/5 backdrop-blur-sm p-4 sm:p-5 group hover:border-opacity-30 transition-all duration-300">
      <div className="absolute top-0 left-0 w-full h-0.5 bg-gradient-to-r from-transparent via-cyber-blue to-transparent opacity-60" />
      <div className="flex items-start justify-between">
        <div className="min-w-0 flex-1">
          <p className="text-xs sm:text-sm text-gray-400 mb-1">{title}</p>
          <p className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
            {typeof value === "number" ? value.toLocaleString() : value}
          </p>
          {sub && <p className="text-[10px] sm:text-xs text-gray-500 mt-1 truncate">{sub}</p>}
        </div>
        <div
          className="p-2 sm:p-3 rounded-lg shrink-0"
          style={{ backgroundColor: `${color}15`, color }}
        >
          <Icon size={20} className="sm:w-6 sm:h-6" />
        </div>
      </div>
    </div>
  );
}

export function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const intervalRef = useRef<number | null>(null);

  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [statsData, healthData] = await Promise.all([
        api.dashboard.getStats(),
        fetch("/health").then((r) => r.ok ? r.json() : null),
      ]);
      setStats(statsData);
      setHealth(healthData);
      setError(null);
    } catch (e) {
      console.error("Dashboard fetch error", e);
      setError("数据加载失败");
    }
  }, []);

  useEffect(() => {
    fetchData().then(() => setLoading(false));
    intervalRef.current = window.setInterval(fetchData, 30000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchData]);

  if (loading && !stats) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex items-center gap-3 text-cyber-blue">
          <Radio className="animate-pulse" size={20} />
          <span className="text-lg">加载系统数据...</span>
        </div>
      </div>
    );
  }

  if (error && !stats) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <p className="text-red-400 text-lg">数据加载失败</p>
        <Button variant="tech" onClick={() => { setLoading(true); fetchData().then(() => setLoading(false)); }}>重试</Button>
      </div>
    );
  }

  if (!stats) return null;

  const alertsPieData = Object.entries(stats.alerts_by_level || {}).map(
    ([name, value]) => ({ name: LEVEL_MAP[name] || name, value })
  );
  const messagesTrend = stats.messages_24h || [];

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* 顶部时间 */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-xl sm:text-2xl font-bold text-foreground">系统总览</h2>
          <p className="text-xs sm:text-sm text-muted-foreground mt-1">
            实时监控系统运行状态
          </p>
        </div>
        <LiveClock />
      </div>

      {/* 核心指标 */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3 sm:gap-4">
        <StatCard
          title="监控账号"
          value={stats.active_accounts}
          icon={Users}
          color="#00f0ff"
          sub={`共 ${stats.total_accounts} 个`}
        />
        <StatCard
          title="监控频道"
          value={stats.active_conversations}
          icon={MessageSquare}
          color="#b026ff"
          sub={`共 ${stats.total_conversations} 个`}
        />
        <StatCard
          title="今日消息"
          value={stats.today_messages}
          icon={Activity}
          color="#0aff00"
          sub={`累计 ${stats.total_messages.toLocaleString()}`}
        />
        <StatCard
          title="待处理告警"
          value={stats.pending_alerts}
          icon={AlertTriangle}
          color="#ff006e"
          sub={`今日 ${stats.today_alerts}`}
        />
        <StatCard
          title="活跃关键词"
          value={stats.active_keywords}
          icon={Zap}
          color="#ffaa00"
          sub={`${stats.keyword_groups} 个分组`}
        />
        <StatCard
          title="系统资源"
          value={
            health
              ? `CPU ${health.resources?.cpu_percent?.toFixed(1) || 0}%`
              : "--"
          }
          icon={Shield}
          color="#00f0ff"
          sub={
            health
              ? `内存 ${health.resources?.memory_used_gb?.toFixed(1)}/${health.resources?.memory_total_gb?.toFixed(1)}GB (${health.resources?.memory_percent?.toFixed(0)}%) · 硬盘 ${health.resources?.disk_free_gb?.toFixed(0)}GB 可用`
              : ""
          }
        />
      </div>

      {/* 图表区域 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6">
        {/* 24h 消息趋势 */}
        <div className="lg:col-span-2 rounded-xl border border-white/10 bg-white/5 backdrop-blur-sm p-4 sm:p-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-4 gap-2">
            <h3 className="text-base sm:text-lg font-semibold text-foreground flex items-center gap-2">
              <TrendingUp size={18} className="text-cyber-blue shrink-0" />
              24小时消息趋势
            </h3>
            <span className="text-xs text-muted-foreground">
              {stats.today_messages.toLocaleString()} 条今日消息
            </span>
          </div>
          <ResponsiveContainer width="100%" height={240} className="sm:h-[280px]">
            <AreaChart data={messagesTrend} animationDuration={300}>
              <defs>
                <linearGradient id="msgGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#00f0ff" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#00f0ff" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="hour" name="时间" stroke="#666" fontSize={10} tick={{ fontSize: 10 }} />
              <YAxis stroke="#666" fontSize={10} tick={{ fontSize: 10}} />
              <Tooltip
                contentStyle={{
                  background: "rgba(10,10,30,0.9)",
                  border: "1px solid rgba(0,240,255,0.3)",
                  borderRadius: "8px",
                  color: "#fff",
                  fontSize: "12px",
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
                fill="url(#msgGradient)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* 告警级别分布 */}
        <div className="rounded-xl border border-white/10 bg-white/5 backdrop-blur-sm p-4 sm:p-5">
          <h3 className="text-base sm:text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
            <AlertTriangle size={18} className="text-cyber-pink shrink-0" />
            告警级别分布
          </h3>
          <ResponsiveContainer width="100%" height={240} className="sm:h-[280px]">
            <PieChart animationDuration={300}>
              <Pie
                data={alertsPieData}
                cx="50%"
                cy="45%"
                innerRadius={45}
                outerRadius={70}
                paddingAngle={5}
                dataKey="value"
                stroke="none"
              >
                {alertsPieData.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  background: "rgba(10,10,30,0.95)",
                  border: "1px solid rgba(0,240,255,0.3)",
                  borderRadius: "8px",
                  color: "#ffffff",
                  fontSize: "13px",
                  fontWeight: "bold",
                }}
                formatter={(value: number, name: string) => [<span style={{ color: "#fff" }}>{value}</span>, <span style={{ color: "#fff" }}>{name}</span>]}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex flex-wrap justify-center gap-2 sm:gap-4 mt-2">
            {alertsPieData.map((item, i) => (
              <div key={item.name} className="flex items-center gap-1.5 text-xs">
                <div
                  className="w-2 h-2 sm:w-2.5 sm:h-2.5 rounded-full shrink-0"
                  style={{ backgroundColor: COLORS[i % COLORS.length] }}
                />
                <span className="text-gray-400 truncate">
                  {item.name}: {item.value}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 底部状态栏 */}
      {health && (
        <div className="rounded-xl border border-white/10 bg-white/5 backdrop-blur-sm p-3 sm:p-4">
          <div className="flex flex-wrap items-center gap-3 sm:gap-6 text-xs sm:text-sm">
            <div className="flex items-center gap-2">
              <div
                className={`w-2 sm:w-2.5 h-2 sm:h-2.5 rounded-full ${
                  health.status === "healthy"
                    ? "bg-green-400 shadow-[0_0_8px_rgba(74,222,128,0.6)]"
                    : "bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.6)]"
                }`}
              />
              <span className="text-gray-300">
                系统状态: {health.status === "healthy" ? "正常" : "异常"}
              </span>
            </div>
            <div className="flex items-center gap-2 text-gray-400">
              <Radio size={14} className="text-cyber-blue shrink-0" />
              TG 客户端: {health.telegram?.clients_count || 0}
            </div>
            <div className="flex items-center gap-2 text-gray-400">
              <Eye size={14} className="text-cyber-purple shrink-0" />
              活跃监控: {health.telegram?.active_monitors || 0}
            </div>
            <div className="flex items-center gap-2 text-gray-400">
              <Activity size={14} className="text-cyber-green shrink-0" />
              WebSocket: {health.websocket?.connections || 0} 连接
            </div>
            <div className="text-gray-500 text-[10px] sm:text-xs ml-auto w-full sm:w-auto text-center sm:text-right">
              数据更新: {stats.updated_at || "--"}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
