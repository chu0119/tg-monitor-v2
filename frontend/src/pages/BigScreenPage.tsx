import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { api } from "@/lib/api";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  BellRing,
  CircleDot,
  Cpu,
  Database,
  Gauge,
  Globe,
  HardDrive,
  Maximize2,
  MessageSquare,
  Minimize2,
  Radio,
  Shield,
  Sparkles,
  TrendingUp,
  Users,
  Wifi,
  Zap,
} from "lucide-react";
import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
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
  resources?: {
    cpu_percent?: number;
    memory_percent?: number;
    memory_total_gb?: number;
    memory_used_gb?: number;
    memory_available_gb?: number;
    disk_total_gb?: number;
    disk_used_gb?: number;
    disk_free_gb?: number;
    disk_percent?: number;
    threads?: number;
    process_memory_mb?: number;
  };
  telegram?: {
    clients_count?: number;
    active_monitors?: number;
    message_queue?: { queue_size?: number; dropped?: number; processed?: number };
  };
  websocket?: { connections?: number };
  alert_pipeline?: {
    status?: string;
    latest_message_at?: string;
    latest_alert_at?: string;
    recent_alerts_1h?: number;
    matched_without_alert_1h?: number;
    notification_failures_24h?: number;
    notification_queue?: {
      queue_size?: number;
      workers?: number;
      processed?: number;
      failed?: number;
      dropped?: number;
    };
    problems?: string[];
  };
}

interface AlertItem {
  id: number;
  keyword_text?: string;
  keyword_group_name?: string;
  alert_level?: string;
  message_preview?: string;
  created_at?: string;
  status?: string;
  conversation_id?: number;
  sender_username?: string;
  conversation_title?: string;
}

interface KeywordTrend {
  keyword_group: string;
  dates: string[];
  counts: number[];
  top_keywords?: Array<{ word: string; count: number }>;
}

interface SenderRanking {
  sender_id: number;
  username?: string;
  first_name?: string;
  message_count: number;
  alert_count: number;
  rank: number;
}

interface ConversationActivity {
  conversation_id: number;
  title: string;
  chat_type: string;
  message_count: number;
  sender_count: number;
  alert_count: number;
  last_message_at?: string;
}

const LEVEL_MAP: Record<string, string> = {
  critical: "严重",
  high: "高危",
  medium: "中危",
  low: "低危",
};

const LEVEL_COLORS: Record<string, string> = {
  critical: "#f43f5e",
  high: "#fb923c",
  medium: "#facc15",
  low: "#22c55e",
};

const CHART_COLORS = ["#38bdf8", "#f43f5e", "#a78bfa", "#22c55e", "#facc15", "#fb7185"];

function formatNumber(value?: number | string) {
  if (typeof value === "number") return value.toLocaleString();
  return value ?? "--";
}

function shortNumber(value?: number) {
  if (!value) return "0";
  if (value >= 100000000) return `${(value / 100000000).toFixed(1)}亿`;
  if (value >= 10000) return `${(value / 10000).toFixed(1)}万`;
  return value.toLocaleString();
}

function sanitizePreview(value?: string) {
  if (!value) return "无消息预览";
  return value
    .replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/gu, "")
    .replace(/\s+/g, " ")
    .trim();
}

function AnimatedNumber({ value }: { value: number }) {
  const [display, setDisplay] = useState(value);
  const [rollKey, setRollKey] = useState(0);
  const previous = useRef(value);

  useEffect(() => {
    if (value === previous.current) return;
    previous.current = value;
    setDisplay(value);
    setRollKey((current) => current + 1);
  }, [value]);

  const text = display.toLocaleString();
  return (
    <span className="inline-flex overflow-hidden tabular-nums" aria-label={text}>
      {text.split("").map((char, index) => (
        <span
          key={`${rollKey}-${index}-${char}`}
          className={/\d/.test(char) ? "metric-roll-char" : "inline-block"}
          style={{ animationDelay: `${Math.min(index * 22, 120)}ms` }}
        >
          {char}
        </span>
      ))}
    </span>
  );
}

function Panel({
  title,
  icon: Icon,
  action,
  children,
  className = "",
}: {
  title: string;
  icon: any;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`relative overflow-hidden rounded-lg border border-cyan-300/10 bg-slate-950/70 shadow-[0_0_28px_rgba(14,165,233,0.08)] ${className}`}>
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-300/70 to-transparent" />
      <div className="flex items-center justify-between border-b border-white/5 px-4 py-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-100">
          <Icon size={16} className="text-cyan-300" />
          <span>{title}</span>
        </div>
        {action}
      </div>
      <div className="p-4">{children}</div>
    </section>
  );
}

function MetricTile({
  label,
  value,
  sub,
  icon: Icon,
  color,
}: {
  label: string;
  value: number | string;
  sub?: string;
  icon: any;
  color: string;
}) {
  return (
    <div className="relative min-h-[104px] overflow-hidden rounded-lg border border-white/10 bg-white/[0.045] p-3.5">
      <div className="absolute -right-5 -top-8 h-24 w-24 rounded-full opacity-10 blur-2xl" style={{ backgroundColor: color }} />
      <div className="flex items-center justify-between">
        <span className="text-xs text-slate-400">{label}</span>
        <Icon size={18} style={{ color }} />
      </div>
      <div className="mt-3 flex items-end gap-2">
        <span className="font-mono text-2xl font-bold tracking-normal text-white 2xl:text-3xl">
          {typeof value === "number" ? <AnimatedNumber value={value} /> : value}
        </span>
      </div>
      {sub && <p className="mt-1.5 truncate text-xs text-slate-500">{sub}</p>}
    </div>
  );
}

function ProgressRow({ label, value, color, detail }: { label: string; value: number; color: string; detail?: string }) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="text-slate-400">{label}</span>
        <span className="font-mono text-slate-200">{detail ?? `${value.toFixed(1)}%`}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-white/10">
        <div className="h-full rounded-full transition-all duration-700" style={{ width: `${Math.min(value, 100)}%`, backgroundColor: color }} />
      </div>
    </div>
  );
}

function MessageTrendChart({ data }: { data: Array<{ hour: string; count: number }> }) {
  const width = 760;
  const height = 230;
  const pad = { left: 50, right: 16, top: 16, bottom: 30 };
  const max = Math.max(...data.map((item) => item.count), 1);
  const points = data.map((item, index) => {
    const x = pad.left + (data.length <= 1 ? 0 : (index / (data.length - 1)) * (width - pad.left - pad.right));
    const y = pad.top + (1 - item.count / max) * (height - pad.top - pad.bottom);
    return { x, y, ...item };
  });
  const linePath = points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join(" ");
  const areaPath = points.length
    ? `M ${pad.left} ${height - pad.bottom} ${linePath.replace(/^M/, "L")} L ${points[points.length - 1].x.toFixed(1)} ${height - pad.bottom} Z`
    : "";
  const yTicks = [max, max * 0.66, max * 0.33, 0];
  const xStep = Math.max(1, Math.ceil(data.length / 7));

  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" height="100%" preserveAspectRatio="none" role="img">
      <defs>
        <linearGradient id="bigscreenTrendFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.36" />
          <stop offset="100%" stopColor="#38bdf8" stopOpacity="0.02" />
        </linearGradient>
      </defs>
      {yTicks.map((tick, index) => {
        const y = pad.top + index * ((height - pad.top - pad.bottom) / (yTicks.length - 1));
        return (
          <g key={index}>
            <line x1={pad.left} x2={width - pad.right} y1={y} y2={y} stroke="rgba(148,163,184,0.13)" strokeDasharray="4 5" />
            <text x={pad.left - 9} y={y + 4} textAnchor="end" fill="#64748b" fontSize="11">{shortNumber(Math.round(tick))}</text>
          </g>
        );
      })}
      {data.map((item, index) => {
        if (index % xStep !== 0 && index !== data.length - 1) return null;
        const point = points[index];
        return <text key={item.hour} x={point.x} y={height - 8} textAnchor="middle" fill="#64748b" fontSize="11">{item.hour}</text>;
      })}
      <line x1={pad.left} x2={pad.left} y1={pad.top} y2={height - pad.bottom} stroke="rgba(148,163,184,0.35)" />
      <line x1={pad.left} x2={width - pad.right} y1={height - pad.bottom} y2={height - pad.bottom} stroke="rgba(148,163,184,0.35)" />
      {areaPath && <path d={areaPath} fill="url(#bigscreenTrendFill)" />}
      {linePath && <path d={linePath} fill="none" stroke="#38bdf8" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />}
    </svg>
  );
}

function HorizontalBarChart({ data }: { data: Array<{ name: string; value: number }> }) {
  const max = Math.max(...data.map((item) => item.value), 1);
  return (
    <div className="flex h-full min-h-[190px] flex-col justify-center gap-3">
      {data.slice(0, 6).map((item, index) => (
        <div key={`${item.name}-${index}`} className="grid grid-cols-[72px_1fr_48px] items-center gap-2">
          <div className="truncate text-xs text-slate-400" title={item.name}>{item.name}</div>
          <div className="h-3 overflow-hidden rounded-full bg-white/10">
            <div
              className="h-full rounded-full"
              style={{
                width: `${Math.max(2, Math.min(100, (item.value / max) * 100))}%`,
                background: CHART_COLORS[index % CHART_COLORS.length],
              }}
            />
          </div>
          <div className="text-right font-mono text-xs text-slate-300">{shortNumber(item.value)}</div>
        </div>
      ))}
    </div>
  );
}

function StatusPill({ ok, text }: { ok: boolean; text: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs ${
      ok ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-200" : "border-amber-400/30 bg-amber-400/10 text-amber-100"
    }`}>
      <span className={`h-1.5 w-1.5 rounded-full ${ok ? "bg-emerald-300" : "bg-amber-300 animate-pulse"}`} />
      {text}
    </span>
  );
}

export function BigScreenPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [keywordTrend, setKeywordTrend] = useState<KeywordTrend[]>([]);
  const [senders, setSenders] = useState<SenderRanking[]>([]);
  const [conversations, setConversations] = useState<ConversationActivity[]>([]);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [viewport, setViewport] = useState({ width: 1920, height: 1080 });

  const fetchData = useCallback(async () => {
    const [statsRes, healthRes, alertsRes, keywordRes, senderRes, conversationRes] = await Promise.allSettled([
      api.dashboard.getStats(),
      fetch("/health").then((r) => (r.ok ? r.json() : null)),
      api.alerts.list({ page: 1, page_size: 18 }),
      api.dashboard.getKeywordTrend(7, 6),
      api.dashboard.getSenderRanking(8, "alerts"),
      api.dashboard.getConversationActivity(8),
    ]);

    if (statsRes.status === "fulfilled") setStats(statsRes.value);
    if (healthRes.status === "fulfilled") setHealth(healthRes.value);
    if (alertsRes.status === "fulfilled") setAlerts(alertsRes.value?.items || alertsRes.value || []);
    if (keywordRes.status === "fulfilled") setKeywordTrend(keywordRes.value || []);
    if (senderRes.status === "fulfilled") setSenders(senderRes.value || []);
    if (conversationRes.status === "fulfilled") setConversations(conversationRes.value || []);
  }, []);

  useEffect(() => {
    fetchData();
    const dataTimer = window.setInterval(fetchData, 5000);
    const clockTimer = window.setInterval(() => setCurrentTime(new Date()), 1000);
    return () => {
      window.clearInterval(dataTimer);
      window.clearInterval(clockTimer);
    };
  }, [fetchData]);

  useEffect(() => {
    const onFullscreenChange = () => {
      const active = !!document.fullscreenElement;
      setIsFullscreen(active);
      document.documentElement.classList.toggle("bigscreen-active", active);
    };
    const onResize = () => setViewport({ width: window.innerWidth, height: window.innerHeight });
    onResize();
    document.addEventListener("fullscreenchange", onFullscreenChange);
    window.addEventListener("resize", onResize);
    return () => {
      document.removeEventListener("fullscreenchange", onFullscreenChange);
      window.removeEventListener("resize", onResize);
      document.documentElement.classList.remove("bigscreen-active");
    };
  }, []);

  const toggleFullscreen = useCallback(() => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen();
    } else {
      document.exitFullscreen();
    }
  }, []);

  const alertPieData = useMemo(
    () =>
      Object.entries(stats?.alerts_by_level || {})
        .filter(([, value]) => value > 0)
        .map(([key, value]) => ({ key, name: LEVEL_MAP[key] || key, value })),
    [stats?.alerts_by_level]
  );

  const keywordBars = useMemo(
    () =>
      keywordTrend.map((item) => ({
        name: item.keyword_group?.length > 8 ? `${item.keyword_group.slice(0, 8)}...` : item.keyword_group,
        value: item.counts?.reduce((sum, value) => sum + value, 0) || 0,
      })),
    [keywordTrend]
  );

  const messagePeak = Math.max(...(stats?.messages_24h || []).map((item) => item.count), 1);
  const senderAlertPeak = Math.max(...senders.map((sender) => sender.alert_count || 0), 1);
  const pipelineHardIssues =
    (health?.alert_pipeline?.matched_without_alert_1h || 0) > 0 ||
    (health?.alert_pipeline?.notification_queue?.queue_size || 0) > 100 ||
    (health?.alert_pipeline?.notification_queue?.failed || 0) > 0;
  const pipelineOk = health?.alert_pipeline?.status === "healthy" || !pipelineHardIssues;
  const resourceOk =
    (health?.resources?.cpu_percent || 0) < 85 &&
    (health?.resources?.memory_percent || 0) < 85 &&
    (health?.resources?.disk_percent || 0) < 90;
  const systemOk = health?.status === "healthy" || resourceOk;
  const hourlyRate = stats ? Math.round(stats.today_messages / Math.max(currentTime.getHours(), 1)) : 0;

  const threatScore = useMemo(() => {
    if (!stats) return 0;
    const alertPressure = Math.min(stats.today_alerts / Math.max(stats.today_messages, 1), 0.35) * 150;
    const pendingPressure = Math.min(stats.pending_alerts / Math.max(stats.total_alerts, 1), 1) * 35;
    const pipelinePressure = pipelineOk ? 0 : 12;
    const score = Math.min(100, alertPressure + pendingPressure + pipelinePressure);
    return Math.round(score);
  }, [pipelineOk, stats]);

  const designWidth = 1920;
  const designHeight = 1080;
  const fullscreenScale = isFullscreen
    ? Math.min(viewport.width / designWidth, viewport.height / designHeight)
    : 1;
  const fullscreenOffsetX = isFullscreen ? Math.max(0, (viewport.width - designWidth * fullscreenScale) / 2) : 0;
  const fullscreenOffsetY = isFullscreen ? Math.max(0, (viewport.height - designHeight * fullscreenScale) / 2) : 0;

  if (!stats) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-cyan-200">
        <div className="flex items-center gap-3 text-lg">
          <Radio className="animate-pulse" size={24} />
          正在加载监控大屏...
        </div>
      </div>
    );
  }

  return (
    <div className={`bg-[#030712] text-white ${isFullscreen ? "fixed inset-0 z-[9999] overflow-hidden" : "min-h-[calc(100vh-64px)] overflow-auto xl:h-[calc(100vh-64px)] xl:overflow-hidden"}`}>
      <div
        className="pointer-events-none fixed inset-0 opacity-40"
        style={{
          backgroundImage:
            "linear-gradient(rgba(56,189,248,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(56,189,248,0.05) 1px, transparent 1px)",
          backgroundSize: "52px 52px",
        }}
      />
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_18%_10%,rgba(56,189,248,0.16),transparent_26%),radial-gradient(circle_at_82%_18%,rgba(244,63,94,0.12),transparent_24%),radial-gradient(circle_at_50%_100%,rgba(34,197,94,0.10),transparent_28%)]" />

      <div
        className={isFullscreen ? "absolute z-10" : "relative z-10"}
        style={isFullscreen ? {
          width: designWidth,
          height: designHeight,
          transform: `translate(${fullscreenOffsetX}px, ${fullscreenOffsetY}px) scale(${fullscreenScale})`,
          transformOrigin: "top left",
        } : undefined}
      >
      <header className="relative z-10 border-b border-cyan-300/10 bg-slate-950/85 px-4 py-2.5 backdrop-blur md:px-6">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex items-center gap-4">
            <div className="flex h-11 w-11 items-center justify-center rounded-lg border border-cyan-300/30 bg-cyan-300/10 shadow-[0_0_24px_rgba(56,189,248,0.25)]">
              <Shield size={25} className="text-cyan-200" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-wide text-white md:text-[26px]">听风追影 群组数据预警分析指挥中心</h1>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-400">
                <span>TELEGRAM MONITORING & EARLY WARNING CENTER</span>
                <span className="hidden h-1 w-1 rounded-full bg-slate-500 sm:inline-block" />
                <span>数据刷新: 3s</span>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <StatusPill ok={systemOk} text={systemOk ? "系统运行稳定" : "系统资源需关注"} />
            <StatusPill ok={pipelineOk} text={pipelineOk ? "告警链路稳定" : "告警链路需关注"} />
            <div className="rounded-lg border border-white/10 bg-white/[0.04] px-3 py-1.5 text-right">
              <div className="font-mono text-xl text-cyan-200">{currentTime.toLocaleTimeString("zh-CN", { hour12: false })}</div>
              <div className="text-xs text-slate-500">
                {currentTime.toLocaleDateString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", weekday: "short" })}
              </div>
            </div>
            <button
              onClick={toggleFullscreen}
              className="rounded-lg border border-white/10 bg-white/[0.04] p-2.5 text-slate-300 transition hover:border-cyan-300/40 hover:text-cyan-100"
              title={isFullscreen ? "退出全屏" : "全屏展示"}
            >
              {isFullscreen ? <Minimize2 size={18} /> : <Maximize2 size={18} />}
            </button>
          </div>
        </div>
      </header>

      <main className={`relative z-10 grid gap-3 p-3 md:gap-3 xl:grid-rows-[112px_minmax(0,1.15fr)_minmax(0,1fr)] xl:overflow-hidden ${isFullscreen ? "h-[1002px] grid-rows-[112px_minmax(0,1.15fr)_minmax(0,1fr)]" : "xl:h-[calc(100vh-142px)]"}`}>
        <section className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6 xl:min-h-0">
          <MetricTile label="今日消息" value={stats.today_messages} sub={`峰值 ${shortNumber(messagePeak)} / 小时`} icon={MessageSquare} color="#38bdf8" />
          <MetricTile label="今日告警" value={stats.today_alerts} sub={`待处理 ${shortNumber(stats.pending_alerts)}`} icon={BellRing} color="#f43f5e" />
          <MetricTile label="活跃会话" value={stats.active_conversations} sub={`总会话 ${stats.total_conversations}`} icon={Globe} color="#a78bfa" />
          <MetricTile label="监控账号" value={stats.active_accounts} sub={`TG 客户端 ${health?.telegram?.clients_count || 0}`} icon={Users} color="#22c55e" />
          <MetricTile label="消息速率" value={hourlyRate} sub="条 / 小时" icon={Zap} color="#facc15" />
          <MetricTile label="态势指数" value={threatScore} sub={threatScore >= 70 ? "高压态势" : threatScore >= 35 ? "中等态势" : "态势平稳"} icon={Gauge} color={threatScore >= 70 ? "#f43f5e" : threatScore >= 35 ? "#facc15" : "#22c55e"} />
        </section>

        <section className="grid min-h-0 gap-3 xl:grid-cols-[1.45fr_0.8fr_0.95fr]">
          <Panel title="24小时消息态势" icon={TrendingUp} className="min-h-[260px] xl:min-h-0">
            <div className="h-[210px] xl:h-full xl:min-h-[190px]">
              <MessageTrendChart data={stats.messages_24h || []} />
            </div>
          </Panel>

          <Panel title="告警等级结构" icon={AlertTriangle} className="min-h-[260px] xl:min-h-0">
            <div className="grid h-[210px] grid-cols-[1fr_0.85fr] items-center gap-2 xl:h-full xl:min-h-[190px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={alertPieData} dataKey="value" innerRadius="56%" outerRadius="82%" paddingAngle={4} stroke="none" isAnimationActive={false}>
                    {alertPieData.map((item, index) => (
                      <Cell key={item.key} fill={LEVEL_COLORS[item.key] || CHART_COLORS[index % CHART_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ background: "rgba(2,6,23,0.96)", border: "1px solid rgba(244,63,94,0.25)", borderRadius: 8, color: "#fff" }}
                    formatter={(value: any, name: any) => [formatNumber(Number(value)), name]}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-2">
                {alertPieData.length === 0 ? (
                  <div className="text-sm text-slate-500">暂无告警分布</div>
                ) : (
                  alertPieData.map((item) => (
                    <div key={item.key} className="flex items-center justify-between rounded-md bg-white/[0.04] px-2 py-2 text-xs">
                      <span className="flex items-center gap-2 text-slate-300">
                        <span className="h-2 w-2 rounded-full" style={{ backgroundColor: LEVEL_COLORS[item.key] }} />
                        {item.name}
                      </span>
                      <span className="font-mono text-white">{formatNumber(item.value)}</span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </Panel>

          <Panel title="系统运行态势" icon={Cpu} className="min-h-[260px] xl:min-h-0">
            <div className="space-y-3">
              <ProgressRow label="CPU" value={health?.resources?.cpu_percent || 0} color="#22c55e" />
              <ProgressRow
                label="内存"
                value={health?.resources?.memory_percent || 0}
                color="#38bdf8"
                detail={`${health?.resources?.memory_used_gb?.toFixed(1) || "0"} / ${health?.resources?.memory_total_gb?.toFixed(1) || "0"} GB`}
              />
              <ProgressRow
                label="磁盘"
                value={health?.resources?.disk_percent || 0}
                color="#a78bfa"
                detail={`剩余 ${health?.resources?.disk_free_gb?.toFixed(0) || "0"} GB`}
              />
              <div className="grid grid-cols-2 gap-2 pt-1">
                <div className="rounded-md bg-white/[0.04] p-2.5">
                  <div className="flex items-center gap-1.5 text-xs text-slate-500"><Wifi size={13} />监控会话</div>
                  <div className="mt-1 font-mono text-xl text-cyan-100">{health?.telegram?.active_monitors || 0}</div>
                </div>
                <div className="rounded-md bg-white/[0.04] p-2.5">
                  <div className="flex items-center gap-1.5 text-xs text-slate-500"><Database size={13} />通知队列</div>
                  <div className="mt-1 font-mono text-xl text-emerald-100">{health?.alert_pipeline?.notification_queue?.queue_size || 0}</div>
                </div>
                <div className="rounded-md bg-white/[0.04] p-2.5">
                  <div className="flex items-center gap-1.5 text-xs text-slate-500"><Activity size={13} />链路异常</div>
                  <div className="mt-1 font-mono text-xl text-amber-100">{health?.alert_pipeline?.matched_without_alert_1h || 0}</div>
                </div>
                <div className="rounded-md bg-white/[0.04] p-2.5">
                  <div className="flex items-center gap-1.5 text-xs text-slate-500"><HardDrive size={13} />进程内存</div>
                  <div className="mt-1 font-mono text-xl text-slate-100">{health?.resources?.process_memory_mb || 0}M</div>
                </div>
              </div>
            </div>
          </Panel>
        </section>

        <section className="grid min-h-0 gap-3 xl:grid-cols-[0.9fr_0.9fr_1.35fr]">
          <Panel title="关键词组热度" icon={BarChart3} className="min-h-[260px] xl:min-h-0">
            <div className="h-[208px] xl:h-full xl:min-h-[190px]">
              <HorizontalBarChart data={keywordBars} />
            </div>
          </Panel>

          <Panel title="重点对象排行" icon={Users} className="min-h-[260px] xl:min-h-0">
            <div className="space-y-2">
              {senders.slice(0, 5).map((sender, index) => {
                const name = sender.username || sender.first_name || `用户 ${sender.sender_id}`;
                return (
                  <div key={sender.sender_id} className="flex items-center gap-3">
                    <div className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-md font-mono text-xs ${
                      index < 3 ? "bg-cyan-300/15 text-cyan-100" : "bg-white/[0.05] text-slate-400"
                    }`}>
                      {index + 1}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm text-slate-200">{name}</div>
                      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white/10">
                        <div
                          className="h-full rounded-full bg-cyan-300"
                          style={{ width: `${Math.min(100, ((sender.alert_count || 0) / senderAlertPeak) * 100)}%` }}
                        />
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-mono text-sm text-white">{shortNumber(sender.message_count)}</div>
                      <div className="text-[11px] text-rose-300">{sender.alert_count} 告警</div>
                    </div>
                  </div>
                );
              })}
            </div>
          </Panel>

          <Panel
            title="实时告警流"
            icon={Sparkles}
            className="min-h-[260px] xl:min-h-0"
            action={<span className="font-mono text-xs text-slate-500">RECENT {alerts.length}</span>}
          >
            <div className="max-h-[212px] space-y-2 overflow-hidden xl:max-h-none">
              {alerts.length === 0 ? (
                <div className="flex h-[220px] items-center justify-center text-sm text-slate-500">暂无最新告警</div>
              ) : (
                alerts.slice(0, 8).map((alert) => {
                  const color = LEVEL_COLORS[alert.alert_level || "low"] || "#38bdf8";
                  return (
                    <div key={alert.id} className="grid grid-cols-[88px_1fr_auto] items-center gap-3 rounded-md border border-white/5 bg-white/[0.035] px-3 py-2">
                      <div className="flex items-center gap-2">
                        <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color, boxShadow: `0 0 12px ${color}` }} />
                        <span className="text-xs" style={{ color }}>{LEVEL_MAP[alert.alert_level || ""] || "告警"}</span>
                      </div>
                      <div className="min-w-0">
                        <div className="truncate text-sm text-slate-100">
                          {alert.keyword_text || "--"}
                          <span className="ml-2 text-xs text-slate-500">{alert.keyword_group_name || ""}</span>
                        </div>
                        <div className="mt-0.5 truncate text-xs text-slate-500">
                          {alert.conversation_title || `会话 ${alert.conversation_id || "--"}`} · {sanitizePreview(alert.message_preview)}
                        </div>
                      </div>
                      <div className="whitespace-nowrap text-right text-[11px] text-slate-500">
                        {alert.created_at ? new Date(alert.created_at).toLocaleTimeString("zh-CN", { hour12: false }) : "--"}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </Panel>
        </section>

        <section className="hidden gap-3">
          <Panel title="会话活跃度" icon={Radio} className="min-h-[260px]">
            <div className="space-y-2">
              {conversations.slice(0, 6).map((conversation) => (
                <div key={conversation.conversation_id} className="grid grid-cols-[1fr_auto] gap-3 rounded-md bg-white/[0.035] px-3 py-2">
                  <div className="min-w-0">
                    <div className="truncate text-sm text-slate-200">{conversation.title || `会话 ${conversation.conversation_id}`}</div>
                    <div className="mt-1 flex flex-wrap gap-3 text-[11px] text-slate-500">
                      <span>{conversation.chat_type}</span>
                      <span>{conversation.sender_count} 发送者</span>
                      <span>{conversation.alert_count} 告警</span>
                    </div>
                  </div>
                  <div className="text-right font-mono text-sm text-cyan-100">{shortNumber(conversation.message_count)}</div>
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="处置压力" icon={CircleDot} className="min-h-[260px]">
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-lg bg-rose-400/10 p-4 text-center">
                <div className="font-mono text-3xl font-bold text-rose-200">{shortNumber(stats.pending_alerts)}</div>
                <div className="mt-1 text-xs text-rose-100/70">待处理告警</div>
              </div>
              <div className="rounded-lg bg-cyan-400/10 p-4 text-center">
                <div className="font-mono text-3xl font-bold text-cyan-100">{shortNumber(health?.alert_pipeline?.recent_alerts_1h || 0)}</div>
                <div className="mt-1 text-xs text-cyan-100/70">1小时告警</div>
              </div>
              <div className="rounded-lg bg-emerald-400/10 p-4 text-center">
                <div className="font-mono text-3xl font-bold text-emerald-100">{health?.alert_pipeline?.notification_queue?.workers || 0}</div>
                <div className="mt-1 text-xs text-emerald-100/70">通知线程</div>
              </div>
              <div className="rounded-lg bg-amber-400/10 p-4 text-center">
                <div className="font-mono text-3xl font-bold text-amber-100">{health?.alert_pipeline?.notification_failures_24h || 0}</div>
                <div className="mt-1 text-xs text-amber-100/70">24h通知失败</div>
              </div>
            </div>
          </Panel>

          <Panel title="数据资产概览" icon={Database} className="min-h-[260px]">
            <div className="space-y-3 text-sm">
              {[
                ["累计消息", stats.total_messages, "#38bdf8"],
                ["累计告警", stats.total_alerts, "#f43f5e"],
                ["关键词库", stats.total_keywords, "#a78bfa"],
                ["发送者画像", stats.total_senders, "#22c55e"],
              ].map(([label, value, color]) => (
                <div key={String(label)} className="flex items-center justify-between rounded-md bg-white/[0.035] px-3 py-2">
                  <span className="text-slate-400">{label}</span>
                  <span className="font-mono text-base font-semibold" style={{ color: String(color) }}>{shortNumber(Number(value))}</span>
                </div>
              ))}
            </div>
          </Panel>
        </section>
      </main>
      </div>
    </div>
  );
}
