import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Download, FileText } from "lucide-react";

interface ReportData {
  report_date?: string;
  report_period?: string;
  generated_at: string;
  summary?: {
    total_messages: number;
    total_alerts: number;
    active_conversations: number;
    alert_by_level: Record<string, number>;
  };
  message_trend?: Array<{ date: string; count: number }>;
  alert_trend?: Array<{ date: string; count: number }>;
  top_keyword_groups?: Array<{ name: string; count: number }>;
  top_senders?: Array<{ username: string; message_count: number }>;
  top_alerts?: Array<{
    keyword_text: string;
    keyword_group_name: string;
    alert_level: string;
    message_preview: string;
    created_at: string;
  }>;
}

interface ReportViewerProps {
  reportType: "daily" | "weekly";
  date?: string;
}

export function ReportViewer({ reportType, date }: ReportViewerProps) {
  const [report, setReport] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(true);

  const alertLevelLabels = {
    low: "低",
    medium: "中",
    high: "高",
    critical: "严重",
  };

  const fetchReport = async () => {
    setLoading(true);
    try {
      const endpoint = reportType === "daily" ? "/api/v1/analysis/report/daily" : "/api/v1/analysis/report/weekly";
      const params = date ? `?date=${date}` : "";
      const response = await fetch(endpoint + params);
      const data = await response.json();
      setReport(data);
    } catch (err) {
      console.error("获取报告失败:", err);
    } finally {
      setLoading(false);
    }
  };

  const downloadPDF = async () => {
    try {
      const endpoint = reportType === "daily"
        ? "/api/v1/analysis/report/pdf/daily"
        : "/api/v1/analysis/report/pdf/weekly";
      const params = date ? `?date=${date}` : "";
      const response = await fetch(endpoint + params);

      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${reportType}_report_${date || new Date().toISOString().split("T")[0]}.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
      } else {
        const error = await response.json();
        alert(error.detail || "下载失败，请确保后端已安装 reportlab");
      }
    } catch (err) {
      console.error("下载 PDF 失败:", err);
    }
  };

  useEffect(() => {
    fetchReport();
  }, [reportType, date]);

  if (loading) {
    return (
      <Card>
        <CardContent className="py-12">
          <div className="flex justify-center">
            <div className="animate-spin w-8 h-8 border-2 border-cyber-blue border-t-transparent rounded-full" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!report) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-muted-foreground">
          暂无报告数据
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* 标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold neon-text">
            {reportType === "daily" ? "日报" : "周报"}
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            {report.report_date || report.report_period}
          </p>
        </div>
        <Button variant="tech" onClick={downloadPDF}>
          <Download size={18} className="mr-2" />
          导出 PDF
        </Button>
      </div>

      {/* 统计摘要 */}
      {report.summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard
            title="总消息数"
            value={report.summary.total_messages}
            color="cyber-blue"
          />
          <StatCard
            title="总告警数"
            value={report.summary.total_alerts}
            color="cyber-pink"
          />
          <StatCard
            title="活跃会话"
            value={report.summary.active_conversations}
            color="cyber-purple"
          />
          <StatCard
            title="告警分布"
            value={Object.values(report.summary.alert_by_level || {}).reduce((a, b) => a + b, 0)}
            color="cyber-green"
          />
        </div>
      )}

      {/* 趋势图表 */}
      {(report.message_trend || report.alert_trend) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {report.message_trend && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">消息趋势</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {report.message_trend.map((item) => (
                    <div key={item.date} className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">{item.date}</span>
                      <span className="font-mono">{item.count}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {report.alert_trend && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">告警趋势</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {report.alert_trend.map((item) => (
                    <div key={item.date} className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">{item.date}</span>
                      <span className="font-mono text-cyber-pink">{item.count}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* 热门关键词组 */}
      {report.top_keyword_groups && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">热门关键词组</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {report.top_keyword_groups.map((item, i) => (
                <div key={item.name} className="flex items-center justify-between p-2 rounded bg-secondary/30">
                  <div className="flex items-center gap-3">
                    <span className="w-6 h-6 rounded-full bg-cyber-blue/20 flex items-center justify-center text-sm">
                      {i + 1}
                    </span>
                    <span>{item.name}</span>
                  </div>
                  <span className="font-mono">{item.count}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* 热门发送者 */}
      {report.top_senders && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">活跃发送者</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              {report.top_senders.map((sender, i) => (
                <div key={sender.username} className="text-center p-3 rounded bg-secondary/30">
                  <div className="w-10 h-10 mx-auto rounded-full bg-gradient-to-br from-cyber-blue to-cyber-purple flex items-center justify-center text-white font-bold">
                    {i + 1}
                  </div>
                  <p className="text-sm font-medium mt-2 truncate">{sender.username}</p>
                  <p className="text-xs text-muted-foreground">{sender.message_count} 条消息</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* 告警列表 */}
      {report.top_alerts && report.top_alerts.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <FileText size={18} />
              主要告警
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {report.top_alerts.map((alert) => (
                <div key={alert.keyword_text} className="p-3 rounded border border-cyber-pink/30 bg-cyber-pink/5">
                  <div className="flex items-start justify-between mb-1">
                    <div>
                      <span className="font-medium">{alert.keyword_text}</span>
                      <span className="text-sm text-muted-foreground ml-2">
                        {alert.keyword_group_name}
                      </span>
                    </div>
                    <span className={`text-xs px-2 py-1 rounded ${
                      alert.alert_level === "critical" ? "bg-cyber-pink/20 text-cyber-pink" :
                      alert.alert_level === "high" ? "bg-yellow-500/20 text-yellow-500" :
                      "bg-cyber-blue/20 text-cyber-blue"
                    }`}>
                      {alertLevelLabels[alert.alert_level as keyof typeof alertLevelLabels] || alert.alert_level}
                    </span>
                  </div>
                  <p className="text-sm text-gray-400 line-clamp-2">{alert.message_preview}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

interface StatCardProps {
  title: string;
  value: number;
  color: string;
}

function StatCard({ title, value, color }: StatCardProps) {
  return (
    <Card>
      <CardContent className="pt-6">
        <p className="text-sm text-muted-foreground">{title}</p>
        <p className={`text-3xl font-bold text-${color} mt-1`}>{value}</p>
      </CardContent>
    </Card>
  );
}
