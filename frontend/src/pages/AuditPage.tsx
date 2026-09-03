import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { formatDate } from "@/lib/utils";
import {
  Shield,
  Filter,
  Search,
  User,
  FileText,
  Download,
  Eye,
  X,
} from "lucide-react";

interface AuditLog {
  id: number;
  operator: string;
  action_type: string;
  target_type: string;
  target_id: string;
  details: any;
  ip_address: string;
  created_at: string;
}

interface AuditStats {
  total: number;
  by_action: { action: string; count: number }[];
  by_operator: { operator: string; count: number }[];
  by_date: { date: string; count: number }[];
}

const actionTypeLabels: Record<string, string> = {
  create: "创建",
  update: "更新",
  delete: "删除",
  login: "登录",
  logout: "登出",
  export: "导出",
  import: "导入",
  handle: "处理",
  start: "启动",
  stop: "停止",
  batch_update: "批量更新",
  batch_delete: "批量删除",
  merge: "合并",
  login_request: "登录请求",
  create_conversation: "创建会话",
  delete_conversation: "删除会话",
  toggle_monitoring: "切换监控",
  create_keyword: "创建关键词",
  delete_keyword: "删除关键词",
  import_keywords: "导入关键词",
  export_keywords: "导出关键词",
  create_case: "创建案件",
  update_case: "更新案件",
  delete_case: "删除案件",
  update_proxy: "更新代理",
  create_backup: "创建备份",
  restore_backup: "恢复备份",
  add_watchlist: "添加关注名单",
  delete_watchlist: "删除关注名单",
  create_account: "创建账号",
  delete_account: "删除账号",
};

const actionTypeColors: Record<string, string> = {
  create: "default",
  delete: "destructive",
  login: "default",
  logout: "outline",
  handle: "default",
  merge: "secondary",
};

const targetTypeLabels: Record<string, string> = {
  alert: "告警",
  account: "账号",
  conversation: "会话",
  keyword: "关键词",
  notification: "通知",
  setting: "设置",
  case: "案件",
  watchlist: "关注名单",
  monitoring: "监控",
  backup: "备份",
};

export function AuditPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [stats, setStats] = useState<AuditStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState({
    operator: "",
    action_type: "",
    target_type: "",
    start_date: "",
    end_date: "",
  });
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [totalCount, setTotalCount] = useState(0);
  const [selectedLog, setSelectedLog] = useState<AuditLog | null>(null);

  useEffect(() => {
    fetchLogs();
    fetchStats();
  }, [filter, currentPage, pageSize]);

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const params: any = { page: currentPage, page_size: pageSize };
      if (filter.operator) params.operator = filter.operator;
      if (filter.action_type) params.action_type = filter.action_type;
      if (filter.target_type) params.target_type = filter.target_type;
      if (filter.start_date) params.start_date = filter.start_date;
      if (filter.end_date) params.end_date = filter.end_date;
      const data = await api.audit.list(params);
      if (data && typeof data === "object" && "items" in data) {
        setLogs(data.items || []);
        setTotalCount(data.total || 0);
      } else if (Array.isArray(data)) {
        setLogs(data);
        setTotalCount(data.length);
      }
    } catch (error) {
      console.error("Failed to fetch audit logs:", error);
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const data = await api.audit.getStats();
      setStats(data);
    } catch (error) {
      console.error("Failed to fetch audit stats:", error);
    }
  };

  const handleReset = () => {
    setFilter({ operator: "", action_type: "", target_type: "", start_date: "", end_date: "" });
    setCurrentPage(1);
  };

  const handleExport = () => {
    const headers = ["时间", "操作人", "操作类型", "目标类型", "目标ID", "详情", "IP"];
    const rows = logs.map((log) => [
      formatDate(log.created_at),
      log.operator,
      actionTypeLabels[log.action_type] || log.action_type,
      targetTypeLabels[log.target_type] || log.target_type,
      log.target_id || "-",
      typeof log.details === "object" ? JSON.stringify(log.details) : log.details || "-",
      log.ip_address || "-",
    ]);
    const csv = [headers, ...rows].map((row) => row.map((c) => `"${c}"`).join(",")).join("\n");
    const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `audit_logs_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4 sm:space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold neon-text">审计日志</h1>
          <p className="text-xs sm:text-sm text-muted-foreground mt-1">查看系统操作记录与审计追踪</p>
        </div>
        <Button variant="outline" size="sm" onClick={handleExport}>
          <Download size={16} className="mr-2" />
          导出 CSV
        </Button>
      </div>

      {/* 统计卡片 */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <Card>
            <CardContent className="pt-4">
              <div className="text-xs text-muted-foreground">总记录数</div>
              <div className="text-2xl font-bold text-cyan-400">{stats.total}</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <div className="text-xs text-muted-foreground">操作类型</div>
              <div className="text-2xl font-bold text-cyan-400">{stats.by_action?.length || 0}</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <div className="text-xs text-muted-foreground">操作人数</div>
              <div className="text-2xl font-bold text-cyan-400">{stats.by_operator?.length || 0}</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <div className="text-xs text-muted-foreground">近30天</div>
              <div className="text-2xl font-bold text-cyan-400">
                {stats.by_date?.reduce((sum, d) => sum + d.count, 0) || 0}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* 筛选 */}
      <Card>
        <CardContent className="pt-4 sm:pt-6">
          <div className="flex flex-col sm:flex-row flex-wrap items-stretch sm:items-center gap-3">
            <div className="relative flex-1 min-w-[200px]">
              <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="搜索操作人..."
                value={filter.operator}
                onChange={(e) => { setFilter({ ...filter, operator: e.target.value }); setCurrentPage(1); }}
                className="pl-10 min-h-[44px]"
              />
            </div>
            <select
              value={filter.action_type}
              onChange={(e) => { setFilter({ ...filter, action_type: e.target.value }); setCurrentPage(1); }}
              className="input-tech px-4 py-2 rounded-lg min-h-[44px]"
            >
              <option value="">全部操作类型</option>
              {Object.entries(actionTypeLabels).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
            <select
              value={filter.target_type}
              onChange={(e) => { setFilter({ ...filter, target_type: e.target.value }); setCurrentPage(1); }}
              className="input-tech px-4 py-2 rounded-lg min-h-[44px]"
            >
              <option value="">全部目标类型</option>
              {Object.entries(targetTypeLabels).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
            <input
              type="date"
              value={filter.start_date}
              onChange={(e) => { setFilter({ ...filter, start_date: e.target.value }); setCurrentPage(1); }}
              className="input-tech px-4 py-2 rounded-lg min-h-[44px]"
            />
            <input
              type="date"
              value={filter.end_date}
              onChange={(e) => { setFilter({ ...filter, end_date: e.target.value }); setCurrentPage(1); }}
              className="input-tech px-4 py-2 rounded-lg min-h-[44px]"
            />
            <Button variant="tech" onClick={fetchLogs} className="min-h-[44px]">
              <Filter size={18} className="mr-2" />
              刷新
            </Button>
            <Button variant="outline" onClick={handleReset} className="min-h-[44px]">
              重置
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 日志列表 */}
      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin w-8 h-8 border-2 border-cyber-blue border-t-transparent rounded-full" />
        </div>
      ) : logs.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">暂无审计日志</CardContent>
        </Card>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-cyber-blue/20">
                <th className="text-left py-3 px-4 text-muted-foreground font-medium">时间</th>
                <th className="text-left py-3 px-4 text-muted-foreground font-medium">操作人</th>
                <th className="text-left py-3 px-4 text-muted-foreground font-medium">操作类型</th>
                <th className="text-left py-3 px-4 text-muted-foreground font-medium">目标类型</th>
                <th className="text-left py-3 px-4 text-muted-foreground font-medium">目标ID</th>
                <th className="text-left py-3 px-4 text-muted-foreground font-medium">详情</th>
                <th className="text-left py-3 px-4 text-muted-foreground font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id} className="border-b border-white/5 hover:bg-cyber-blue/5 transition-colors">
                  <td className="py-3 px-4 text-xs text-muted-foreground whitespace-nowrap">
                    {formatDate(log.created_at)}
                  </td>
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-2">
                      <User size={14} className="text-cyber-blue shrink-0" />
                      <span className="truncate max-w-[120px]">{log.operator || "系统"}</span>
                    </div>
                  </td>
                  <td className="py-3 px-4">
                    <Badge variant={actionTypeColors[log.action_type] as any || "outline"} className="text-xs">
                      {actionTypeLabels[log.action_type] || log.action_type}
                    </Badge>
                  </td>
                  <td className="py-3 px-4">
                    <span className="text-xs">{targetTypeLabels[log.target_type] || log.target_type}</span>
                  </td>
                  <td className="py-3 px-4 font-mono text-xs text-cyber-blue">{log.target_id || "-"}</td>
                  <td className="py-3 px-4 max-w-[200px]">
                    <p className="text-xs text-muted-foreground truncate" title={JSON.stringify(log.details)}>
                      {typeof log.details === "object" ? JSON.stringify(log.details) : log.details || "-"}
                    </p>
                  </td>
                  <td className="py-3 px-4">
                    <Button variant="ghost" size="sm" onClick={() => setSelectedLog(log)}>
                      <Eye size={14} />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 分页 */}
      {totalCount > 0 && (
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-4 border-t border-cyber-blue/10">
          <div className="text-xs sm:text-sm text-muted-foreground text-center sm:text-left">
            共 {totalCount} 条，第 {currentPage} 页
          </div>
          <div className="flex items-center justify-center gap-2">
            <select
              value={pageSize}
              onChange={(e) => { setPageSize(parseInt(e.target.value)); setCurrentPage(1); }}
              className="input-tech px-3 py-1.5 rounded-lg text-sm min-h-[44px]"
            >
              <option value="10">10条/页</option>
              <option value="20">20条/页</option>
              <option value="50">50条/页</option>
              <option value="100">100条/页</option>
            </select>
            <Button variant="outline" size="sm" disabled={currentPage === 1} onClick={() => setCurrentPage(currentPage - 1)} className="min-h-[44px] px-3">上一页</Button>
            <span className="text-sm px-2">第 {currentPage} / {Math.ceil(totalCount / pageSize)} 页</span>
            <Button variant="outline" size="sm" disabled={currentPage >= Math.ceil(totalCount / pageSize)} onClick={() => setCurrentPage(currentPage + 1)} className="min-h-[44px] px-3">下一页</Button>
          </div>
        </div>
      )}

      {/* 详情弹窗 */}
      {selectedLog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={() => setSelectedLog(null)}>
          <div className="bg-secondary rounded-lg border border-border/50 max-w-2xl w-full max-h-[80vh] overflow-auto p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">审计日志详情</h3>
              <Button variant="ghost" size="sm" onClick={() => setSelectedLog(null)}>
                <X size={18} />
              </Button>
            </div>
            <div className="space-y-3 text-sm">
              <div className="grid grid-cols-2 gap-3">
                <div><span className="text-muted-foreground">ID:</span> {selectedLog.id}</div>
                <div><span className="text-muted-foreground">时间:</span> {formatDate(selectedLog.created_at)}</div>
                <div><span className="text-muted-foreground">操作人:</span> {selectedLog.operator}</div>
                <div><span className="text-muted-foreground">操作类型:</span> {actionTypeLabels[selectedLog.action_type] || selectedLog.action_type}</div>
                <div><span className="text-muted-foreground">目标类型:</span> {targetTypeLabels[selectedLog.target_type] || selectedLog.target_type}</div>
                <div><span className="text-muted-foreground">目标ID:</span> {selectedLog.target_id || "-"}</div>
                <div><span className="text-muted-foreground">IP:</span> {selectedLog.ip_address || "-"}</div>
              </div>
              <div>
                <div className="text-muted-foreground mb-1">详情:</div>
                <pre className="bg-black/30 rounded p-3 text-xs overflow-auto max-h-60">
                  {JSON.stringify(selectedLog.details, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
