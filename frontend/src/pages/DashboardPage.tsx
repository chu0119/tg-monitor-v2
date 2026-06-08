import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  BellRing,
  Database,
  Eye,
  FileText,
  Gauge,
  Hash,
  MessageSquare,
  Radio,
  RefreshCcw,
  Shield,
  TrendingUp,
  Users,
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
    disk_free_gb?: number;
    disk_percent?: number;
    process_memory_mb?: number;
  };
  telegram?: { clients_count?: number; active_monitors?: number; message_queue?: { queue_size?: number; dropped?: number } };
  websocket?: { connections?: number };
  alert_pipeline?: {
    status?: string;
    recent_alerts_1h?: number;
    matched_without_alert_1h?: number;
    notification_failures_24h?: number;
    notification_queue?: { queue_size?: number; failed?: number; retried?: number; workers?: number };
  };
}

interface KeywordTrend {
  keyword_group: string;
  dates: string[];
  counts: number[];
  top_keywords: Array<{ word: string; count: number }>;
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

interface RecentAlert {
  id: number;
  keyword_text?: string;
  keyword_group_name?: string;
  alert_level?: string;
  status?: string;
  matched_text?: string;
  created_at?: string;
  conversation_title?: string;
  sender_username?: string;
}

interface TopWord {
  word: string;
  count: number;
}

const COLORS = ["#38bdf8", "#f43f5e", "#a78bfa", "#22c55e", "#facc15", "#fb923c"];
const LEVEL_MAP: Record<string, string> = { critical: "严重", high: "高危", medium: "中危", low: "低危" };
const LEVEL_COLORS: Record<string, string> = { critical: "#f43f5e", high: "#fb923c", medium: "#facc15", low: "#22c55e" };

function shortNumber(value?: number) {
  if (!value) return "0";
  if (value >= 100000000) return `${(value / 100000000).toFixed(1)}亿`;
  if (value >= 10000) return `${(value / 10000).toFixed(1)}万`;
  return value.toLocaleString();
}

function DashboardPanel({
  title,
  icon: Icon,
  action,
  children,
  className = "",
  contentClassName = "",
}: {
  title: string;
  icon: any;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  contentClassName?: string;
}) {
  return (
    <section className={`flex h-full flex-col rounded-xl border border-white/10 bg-white/[0.045] backdrop-blur-sm ${className}`}>
      <div className="flex shrink-0 items-center justify-between border-b border-white/5 px-4 py-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <Icon size={17} className="text-cyber-blue" />
          {title}
        </div>
        {action}
      </div>
      <div className={`min-h-0 flex-1 p-4 ${contentClassName}`}>{children}</div>
    </section>
  );
}

function StatCard({ title, value, icon: Icon, color, sub }: { title: string; value: number | string; icon: any; color: string; sub?: string }) {
  return (
    <div className="relative overflow-hidden rounded-xl border border-white/10 bg-white/5 p-4 transition hover:border-white/20">
      <div className="absolute -right-5 -top-8 h-24 w-24 rounded-full opacity-10 blur-2xl" style={{ backgroundColor: color }} />
      <div className="flex items-start justify-between">
        <div className="min-w-0">
          <p className="text-xs text-gray-400">{title}</p>
          <p className="mt-2 truncate text-2xl font-bold text-white">{typeof value === "number" ? value.toLocaleString() : value}</p>
          {sub && <p className="mt-1 truncate text-xs text-gray-500">{sub}</p>}
        </div>
        <div className="rounded-lg p-2" style={{ backgroundColor: `${color}18`, color }}>
          <Icon size={20} />
        </div>
      </div>
    </div>
  );
}

function MiniProgress({ label, value, max, color, right }: { label: string; value: number; max: number; color: string; right?: string }) {
  const width = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="truncate text-gray-400">{label}</span>
        <span className="ml-2 shrink-0 font-mono text-gray-300">{right ?? shortNumber(value)}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
        <div className="h-full rounded-full" style={{ width: `${width}%`, backgroundColor: color }} />
      </div>
    </div>
  );
}

function MessageTrendChart({ data, height = 300 }: { data: Array<{ hour: string; count: number }>; height?: number }) {
  const width = 760;
  const chartHeight = 280;
  const pad = { left: 54, right: 18, top: 18, bottom: 34 };
  const max = Math.max(...data.map((item) => item.count), 1);
  const points = data.map((item, index) => {
    const x = pad.left + (data.length <= 1 ? 0 : (index / (data.length - 1)) * (width - pad.left - pad.right));
    const y = pad.top + (1 - item.count / max) * (chartHeight - pad.top - pad.bottom);
    return { x, y, ...item };
  });
  const linePath = points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join(" ");
  const areaPath = points.length
    ? `M ${pad.left} ${chartHeight - pad.bottom} ${linePath.replace(/^M/, "L")} L ${points[points.length - 1].x.toFixed(1)} ${chartHeight - pad.bottom} Z`
    : "";
  const yTicks = [max, max * 0.75, max * 0.5, max * 0.25, 0];
  const xStep = Math.max(1, Math.ceil(data.length / 8));

  return (
    <svg viewBox={`0 0 ${width} ${chartHeight}`} width="100%" height={height} preserveAspectRatio="none" role="img">
      <defs>
        <linearGradient id="dashboardTrendFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.34" />
          <stop offset="100%" stopColor="#38bdf8" stopOpacity="0.02" />
        </linearGradient>
      </defs>
      {yTicks.map((tick, index) => {
        const y = pad.top + index * ((chartHeight - pad.top - pad.bottom) / (yTicks.length - 1));
        return (
          <g key={index}>
            <line x1={pad.left} x2={width - pad.right} y1={y} y2={y} stroke="rgba(148,163,184,0.14)" strokeDasharray="4 5" />
            <text x={pad.left - 10} y={y + 4} textAnchor="end" fill="#64748b" fontSize="11">{shortNumber(Math.round(tick))}</text>
          </g>
        );
      })}
      {data.map((item, index) => {
        if (index % xStep !== 0 && index !== data.length - 1) return null;
        const point = points[index];
        return <text key={item.hour} x={point.x} y={chartHeight - 10} textAnchor="middle" fill="#64748b" fontSize="11">{item.hour}</text>;
      })}
      <line x1={pad.left} x2={pad.left} y1={pad.top} y2={chartHeight - pad.bottom} stroke="rgba(148,163,184,0.35)" />
      <line x1={pad.left} x2={width - pad.right} y1={chartHeight - pad.bottom} y2={chartHeight - pad.bottom} stroke="rgba(148,163,184,0.35)" />
      {areaPath && <path d={areaPath} fill="url(#dashboardTrendFill)" />}
      {linePath && <path d={linePath} fill="none" stroke="#38bdf8" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />}
    </svg>
  );
}

function HorizontalBarChart({ data, height = 290 }: { data: Array<{ name: string; value: number }>; height?: number }) {
  const max = Math.max(...data.map((item) => item.value), 1);
  return (
    <div className="flex flex-col justify-center gap-3" style={{ minHeight: height }}>
      {data.map((item, index) => (
        <div key={`${item.name}-${index}`} className="grid grid-cols-[86px_1fr_54px] items-center gap-3">
          <div className="truncate text-xs text-slate-400" title={item.name}>{item.name}</div>
          <div className="h-3 overflow-hidden rounded-full bg-white/10">
            <div
              className="h-full rounded-full"
              style={{
                width: `${Math.max(2, Math.min(100, (item.value / max) * 100))}%`,
                background: COLORS[index % COLORS.length],
              }}
            />
          </div>
          <div className="text-right font-mono text-xs text-slate-300">{shortNumber(item.value)}</div>
        </div>
      ))}
    </div>
  );
}

function LiveClock() {
  const [currentTime, setCurrentTime] = useState(new Date());
  useEffect(() => {
    const timer = window.setInterval(() => setCurrentTime(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  return (
    <div className="text-left sm:text-right">
      <p className="font-mono text-xl text-cyber-blue sm:text-2xl">{currentTime.toLocaleTimeString("zh-CN", { hour12: false })}</p>
      <p className="text-xs text-muted-foreground">
        {currentTime.toLocaleDateString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", weekday: "short" })}
      </p>
    </div>
  );
}

export function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [keywordTrend, setKeywordTrend] = useState<KeywordTrend[]>([]);
  const [senders, setSenders] = useState<SenderRanking[]>([]);
  const [conversations, setConversations] = useState<ConversationActivity[]>([]);
  const [recentAlerts, setRecentAlerts] = useState<RecentAlert[]>([]);
  const [topWords, setTopWords] = useState<TopWord[]>([]);
  const [dailyReport, setDailyReport] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<number | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [statsData, healthData, keywordData, senderData, conversationData, alertData, wordsData, reportData] = await Promise.all([
        api.dashboard.getStats(),
        fetch("/health").then((r) => (r.ok ? r.json() : null)).catch(() => null),
        api.dashboard.getKeywordTrend(7, 8).catch(() => []),
        api.dashboard.getSenderRanking(12, "alerts").catch(() => []),
        api.dashboard.getConversationActivity(12).catch(() => []),
        api.dashboard.getRecentAlerts(12).catch(() => ({ items: [] })),
        api.analysis.getTopWords(undefined, undefined, 1, 40).catch(() => ({ words: [] })),
        api.analysis.getDailyReport().catch(() => null),
      ]);

      setStats(statsData);
      setHealth(healthData);
      setKeywordTrend(keywordData || []);
      setSenders(senderData || []);
      setConversations(conversationData || []);
      setRecentAlerts(alertData?.items || []);
      setTopWords(wordsData?.words || []);
      setDailyReport(reportData);
      setError(null);
    } catch (e) {
      console.error("Dashboard fetch error", e);
      setError("数据加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    intervalRef.current = window.setInterval(fetchData, 30000);
    return () => {
      if (intervalRef.current) window.clearInterval(intervalRef.current);
    };
  }, [fetchData]);

  const alertsPieData = useMemo(
    () => Object.entries(stats?.alerts_by_level || {}).map(([name, value]) => ({ key: name, name: LEVEL_MAP[name] || name, value })),
    [stats?.alerts_by_level]
  );

  const keywordBars = useMemo(
    () =>
      keywordTrend.map((item) => ({
        name: item.keyword_group?.length > 10 ? `${item.keyword_group.slice(0, 10)}...` : item.keyword_group,
        value: item.counts?.reduce((sum, count) => sum + count, 0) || 0,
      })),
    [keywordTrend]
  );

  const wordMax = Math.max(...topWords.map((w) => w.count), 1);
  const senderAlertMax = Math.max(...senders.map((s) => s.alert_count), 1);
  const conversationMax = Math.max(...conversations.map((c) => c.message_count), 1);
  const hourlyRate = stats ? Math.round(stats.today_messages / Math.max(new Date().getHours(), 1)) : 0;
  const alertRate = stats ? ((stats.today_alerts / Math.max(stats.today_messages, 1)) * 100).toFixed(1) : "0.0";

  if (loading && !stats) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="flex items-center gap-3 text-cyber-blue">
          <Radio className="animate-pulse" size={20} />
          <span className="text-lg">加载系统数据...</span>
        </div>
      </div>
    );
  }

  if (error && !stats) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4">
        <p className="text-lg text-red-400">数据加载失败</p>
        <Button variant="tech" onClick={fetchData}>重试</Button>
      </div>
    );
  }

  if (!stats) return null;

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold text-foreground">系统仪表盘</h2>
          <p className="mt-1 text-sm text-muted-foreground">监控态势、告警分析、关键词热度、对象排行与系统健康</p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline" onClick={fetchData} className="min-h-[40px]">
            <RefreshCcw size={16} className="mr-2" />
            刷新
          </Button>
          <LiveClock />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <StatCard title="今日消息" value={stats.today_messages} icon={MessageSquare} color="#38bdf8" sub={`累计 ${shortNumber(stats.total_messages)}`} />
        <StatCard title="今日告警" value={stats.today_alerts} icon={BellRing} color="#f43f5e" sub={`命中率 ${alertRate}%`} />
        <StatCard title="待处理告警" value={stats.pending_alerts} icon={AlertTriangle} color="#fb923c" sub={`总告警 ${shortNumber(stats.total_alerts)}`} />
        <StatCard title="活跃会话" value={stats.active_conversations} icon={Radio} color="#a78bfa" sub={`总会话 ${stats.total_conversations}`} />
        <StatCard title="消息速率" value={hourlyRate} icon={Zap} color="#facc15" sub="条 / 小时" />
        <StatCard title="发送者画像" value={stats.total_senders} icon={Users} color="#22c55e" sub={`${stats.active_keywords} 个活跃关键词`} />
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
        <DashboardPanel title="24小时消息趋势" icon={TrendingUp} className="xl:col-span-2">
          <MessageTrendChart data={stats.messages_24h || []} height={300} />
        </DashboardPanel>

        <DashboardPanel title="告警级别分布" icon={AlertTriangle}>
          <ResponsiveContainer width="100%" height={230}>
            <PieChart>
              <Pie data={alertsPieData} cx="50%" cy="48%" innerRadius={55} outerRadius={82} paddingAngle={4} dataKey="value" stroke="none" isAnimationActive={false}>
                {alertsPieData.map((item, i) => (
                  <Cell key={item.key} fill={LEVEL_COLORS[item.key] || COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ background: "rgba(10,10,30,0.95)", border: "1px solid rgba(244,63,94,0.28)", borderRadius: 8, color: "#fff" }} />
            </PieChart>
          </ResponsiveContainer>
          <div className="grid grid-cols-2 gap-2">
            {alertsPieData.map((item, i) => (
              <div key={item.key} className="flex items-center justify-between rounded-lg bg-white/[0.04] px-3 py-2 text-xs">
                <span className="flex items-center gap-2 text-gray-300">
                  <span className="h-2 w-2 rounded-full" style={{ backgroundColor: LEVEL_COLORS[item.key] || COLORS[i % COLORS.length] }} />
                  {item.name}
                </span>
                <span className="font-mono text-white">{shortNumber(item.value)}</span>
              </div>
            ))}
          </div>
        </DashboardPanel>
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
        <DashboardPanel title="关键词组 7 日热度" icon={BarChart3}>
          <HorizontalBarChart data={keywordBars} height={290} />
        </DashboardPanel>

        <DashboardPanel title="高频词云数据" icon={Hash}>
          <div className="flex min-h-[290px] flex-wrap content-start gap-2">
            {topWords.slice(0, 36).map((word, i) => {
              const scale = 0.78 + Math.min(1.3, word.count / wordMax) * 1.25;
              return (
                <span
                  key={`${word.word}-${i}`}
                  className="rounded-full border border-cyan-300/10 bg-cyan-300/10 px-3 py-1 text-cyan-100"
                  style={{ fontSize: `${scale}rem`, opacity: 0.62 + Math.min(0.35, word.count / wordMax) }}
                  title={`${word.word}: ${word.count}`}
                >
                  {word.word}
                </span>
              );
            })}
          </div>
        </DashboardPanel>

        <DashboardPanel title="系统健康与链路状态" icon={Shield}>
          <div className="space-y-4">
            <MiniProgress label="CPU 使用率" value={health?.resources?.cpu_percent || 0} max={100} color="#22c55e" right={`${health?.resources?.cpu_percent?.toFixed(1) || 0}%`} />
            <MiniProgress label="内存使用率" value={health?.resources?.memory_percent || 0} max={100} color="#38bdf8" right={`${health?.resources?.memory_used_gb?.toFixed(1) || 0}/${health?.resources?.memory_total_gb?.toFixed(1) || 0}GB`} />
            <MiniProgress label="硬盘使用率" value={health?.resources?.disk_percent || 0} max={100} color="#a78bfa" right={`剩余 ${health?.resources?.disk_free_gb?.toFixed(0) || 0}GB`} />
            <div className="grid grid-cols-2 gap-3 pt-2">
              <div className="rounded-lg bg-white/[0.04] p-3">
                <p className="text-xs text-gray-500">告警链路</p>
                <p className={`mt-1 text-lg font-semibold ${health?.alert_pipeline?.status === "healthy" ? "text-emerald-300" : "text-amber-300"}`}>
                  {health?.alert_pipeline?.status === "healthy" ? "正常" : "需关注"}
                </p>
              </div>
              <div className="rounded-lg bg-white/[0.04] p-3">
                <p className="text-xs text-gray-500">通知队列</p>
                <p className="mt-1 font-mono text-lg text-cyan-100">{health?.alert_pipeline?.notification_queue?.queue_size || 0}</p>
              </div>
              <div className="rounded-lg bg-white/[0.04] p-3">
                <p className="text-xs text-gray-500">1小时告警</p>
                <p className="mt-1 font-mono text-lg text-rose-200">{health?.alert_pipeline?.recent_alerts_1h || 0}</p>
              </div>
              <div className="rounded-lg bg-white/[0.04] p-3">
                <p className="text-xs text-gray-500">链路异常</p>
                <p className="mt-1 font-mono text-lg text-amber-200">{health?.alert_pipeline?.matched_without_alert_1h || 0}</p>
              </div>
            </div>
          </div>
        </DashboardPanel>
      </div>

      <div className="grid grid-cols-1 items-stretch gap-5 xl:grid-cols-3">
        <DashboardPanel title="高风险对象排行" icon={Users} className="self-stretch" contentClassName="flex flex-col">
          <div className="flex h-full flex-col justify-between gap-3">
            {senders.slice(0, 8).map((sender) => {
              const name = sender.username || sender.first_name || `用户 ${sender.sender_id}`;
              return (
                <div key={sender.sender_id} className="grid min-h-[58px] grid-cols-[32px_1fr_auto] items-center gap-3 rounded-lg bg-white/[0.025] px-2">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyber-blue/15 font-mono text-xs text-cyber-blue">{sender.rank}</div>
                  <div className="min-w-0">
                    <div className="truncate text-sm text-gray-200">{name}</div>
                    <MiniProgress label="" value={sender.alert_count} max={senderAlertMax} color="#f43f5e" />
                  </div>
                  <div className="text-right">
                    <div className="font-mono text-sm text-white">{shortNumber(sender.message_count)}</div>
                    <div className="text-xs text-rose-300">{sender.alert_count} 告警</div>
                  </div>
                </div>
              );
            })}
          </div>
        </DashboardPanel>

        <DashboardPanel title="会话活跃度" icon={Radio} className="self-stretch" contentClassName="flex flex-col">
          <div className="flex h-full flex-col justify-between gap-3">
            {conversations.slice(0, 8).map((conversation) => (
              <div key={conversation.conversation_id} className="min-h-[58px] rounded-lg bg-white/[0.035] px-3 py-2">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate text-sm text-gray-200">{conversation.title || `会话 ${conversation.conversation_id}`}</div>
                    <div className="mt-1 text-xs text-gray-500">{conversation.chat_type} · {conversation.sender_count} 发送者 · {conversation.alert_count} 告警</div>
                  </div>
                  <div className="font-mono text-sm text-cyber-blue">{shortNumber(conversation.message_count)}</div>
                </div>
                <div className="mt-2">
                  <MiniProgress label="" value={conversation.message_count} max={conversationMax} color="#a78bfa" />
                </div>
              </div>
            ))}
          </div>
        </DashboardPanel>

        <DashboardPanel title="最新告警流" icon={AlertTriangle} className="self-stretch" contentClassName="flex flex-col">
          <div className="flex h-full flex-col gap-3">
            {recentAlerts.slice(0, 8).map((alert) => {
              const color = LEVEL_COLORS[alert.alert_level || "low"] || "#38bdf8";
              return (
                <div key={alert.id} className="min-h-[72px] rounded-lg border border-white/5 bg-white/[0.035] px-3 py-2">
                  <div className="flex items-center justify-between gap-3">
                    <span className="flex items-center gap-2 text-sm" style={{ color }}>
                      <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
                      {LEVEL_MAP[alert.alert_level || ""] || "告警"}
                    </span>
                    <span className="text-xs text-gray-500">{alert.created_at ? new Date(alert.created_at).toLocaleTimeString("zh-CN", { hour12: false }) : "--"}</span>
                  </div>
                  <div className="mt-1 truncate text-sm text-gray-200">{alert.keyword_text || "--"} <span className="text-xs text-gray-500">{alert.keyword_group_name || ""}</span></div>
                  <div className="truncate text-xs text-gray-500">{alert.conversation_title || "未知会话"} · {alert.sender_username || "未知发送者"}</div>
                </div>
              );
            })}
          </div>
        </DashboardPanel>
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <DashboardPanel title="日报摘要" icon={FileText}>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard title="日报消息" value={dailyReport?.summary?.total_messages ?? stats.today_messages} icon={MessageSquare} color="#38bdf8" />
            <StatCard title="日报告警" value={dailyReport?.summary?.total_alerts ?? stats.today_alerts} icon={AlertTriangle} color="#f43f5e" />
            <StatCard title="活跃会话" value={dailyReport?.summary?.active_conversations ?? stats.active_conversations} icon={Radio} color="#a78bfa" />
            <StatCard title="浏览器连接" value={health?.websocket?.connections || 0} icon={Eye} color="#22c55e" />
          </div>
        </DashboardPanel>

        <DashboardPanel title="运行指标" icon={Gauge}>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard title="TG 客户端" value={health?.telegram?.clients_count || 0} icon={Radio} color="#38bdf8" />
            <StatCard title="监控会话" value={health?.telegram?.active_monitors || 0} icon={Activity} color="#a78bfa" />
            <StatCard title="消息队列" value={health?.telegram?.message_queue?.queue_size || 0} icon={Database} color="#facc15" />
            <StatCard title="进程内存" value={`${health?.resources?.process_memory_mb || 0}M`} icon={Shield} color="#22c55e" />
          </div>
        </DashboardPanel>
      </div>
    </div>
  );
}
