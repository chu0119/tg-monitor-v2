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
} from "lucide-react";

interface AuditLog {
  id: number;
  operator: string;
  action_type: string;
  target_type: string;
  target_id: string;
  details: string;
  ip_address: string;
  created_at: string;
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
};

const actionTypeColors: Record<string, string> = {
  create: "default",
  delete: "destructive",
  login: "default",
  logout: "outline",
  handle: "default",
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
};

export function AuditPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
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

  useEffect(() => {
    fetchLogs();
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

  const handleReset = () => {
    setFilter({ operator: "", action_type: "", target_type: "", start_date: "", end_date: "" });
    setCurrentPage(1);
  };

  return (
    <div className="space-y-4 sm:space-y-6">
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold neon-text">审计日志</h1>
        <p className="text-xs sm:text-sm text-muted-foreground mt-1">查看系统操作记录与审计追踪</p>
      </div>

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
              <option value="create">创建</option>
              <option value="update">更新</option>
              <option value="delete">删除</option>
              <option value="login">登录</option>
              <option value="logout">登出</option>
              <option value="export">导出</option>
              <option value="handle">处理</option>
              <option value="batch_update">批量更新</option>
              <option value="batch_delete">批量删除</option>
            </select>
            <select
              value={filter.target_type}
              onChange={(e) => { setFilter({ ...filter, target_type: e.target.value }); setCurrentPage(1); }}
              className="input-tech px-4 py-2 rounded-lg min-h-[44px]"
            >
              <option value="">全部目标类型</option>
              <option value="alert">告警</option>
              <option value="account">账号</option>
              <option value="conversation">会话</option>
              <option value="keyword">关键词</option>
              <option value="notification">通知</option>
              <option value="setting">设置</option>
              <option value="case">案件</option>
              <option value="watchlist">关注名单</option>
            </select>
            <input
              type="date"
              value={filter.start_date}
              onChange={(e) => { setFilter({ ...filter, start_date: e.target.value }); setCurrentPage(1); }}
              className="input-tech px-4 py-2 rounded-lg min-h-[44px]"
              placeholder="开始日期"
            />
            <input
              type="date"
              value={filter.end_date}
              onChange={(e) => { setFilter({ ...filter, end_date: e.target.value }); setCurrentPage(1); }}
              className="input-tech px-4 py-2 rounded-lg min-h-[44px]"
              placeholder="结束日期"
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
                <th className="text-left py-3 px-4 text-muted-foreground font-medium">IP</th>
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
                  <td className="py-3 px-4 max-w-[300px]">
                    <p className="text-xs text-muted-foreground truncate" title={log.details}>
                      {log.details || "-"}
                    </p>
                  </td>
                  <td className="py-3 px-4 text-xs text-muted-foreground font-mono">{log.ip_address || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

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
    </div>
  );
}
