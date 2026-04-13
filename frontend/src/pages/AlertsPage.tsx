import { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { Input } from "@/components/ui/Input";
import { formatDate, truncateText, formatPhone } from "@/lib/utils";

function sanitizeHtml(html: string): string {
  const div = document.createElement("div");
  div.textContent = html;
  return div.innerHTML;
}
import {
  AlertTriangle,
  CheckCircle,
  XCircle,
  Clock,
  Search,
  Filter,
  ExternalLink,
  CheckSquare,
  Square,
  Download,
  Tag,
  ChevronDown,
} from "lucide-react";

interface Alert {
  id: number;
  keyword_text: string;
  keyword_group_name: string;
  alert_level: string;
  status: string;
  matched_text: string;
  message_preview: string;
  highlighted_message?: string;  // 带关键词高亮的消息内容
  created_at: string;
  message_time?: string;  // 消息原始发送时间
  sender_username?: string;
  sender_tg_id?: number;
  sender_phone?: string;
  conversation_title?: string;
  handler?: string;
  handler_note?: string;
  keyword_group_id?: number;
}

interface KeywordGroup {
  id: number;
  name: string;
}

export function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);
  const [filter, setFilter] = useState({ status: "", level: "", keyword: "", has_phone: false });
  const [search, setSearch] = useState("");
  const [showKeywordGroupFilter, setShowKeywordGroupFilter] = useState(false);
  const [selectedKeywordGroups, setSelectedKeywordGroups] = useState<number[]>([]);
  const [keywordGroups, setKeywordGroups] = useState<KeywordGroup[]>([]);
  const [selectedAlerts, setSelectedAlerts] = useState<Set<number>>(new Set());
  const [showBatchHandleModal, setShowBatchHandleModal] = useState(false);
  const [showKeywordGroupDropdown, setShowKeywordGroupDropdown] = useState(false);
  const [dropdownPosition, setDropdownPosition] = useState({ top: 0, left: 0 });
  const keywordGroupDropdownRef = useRef<HTMLDivElement>(null);
  const [exporting, setExporting] = useState(false);

  // 分页状态
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [totalCount, setTotalCount] = useState(0);

  // 防抖相关
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isFirstMountRef = useRef(true);

  // 点击外部关闭下拉菜单
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (showKeywordGroupDropdown && keywordGroupDropdownRef.current) {
        const dropdown = document.querySelector('[data-dropdown="keyword-groups"]');
        const button = keywordGroupDropdownRef.current;
        if (button && !button.contains(event.target as Node) && dropdown && !dropdown.contains(event.target as Node)) {
          setShowKeywordGroupDropdown(false);
        }
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [showKeywordGroupDropdown]);

  useEffect(() => {
    fetchKeywordGroups();
    
    // 初始加载时不防抖，直接请求
    if (isFirstMountRef.current) {
      isFirstMountRef.current = false;
      fetchAlerts();
      return;
    }

    // 后续筛选变化时使用 300ms 防抖
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    debounceTimerRef.current = setTimeout(() => {
      fetchAlerts();
    }, 300);

    // 清理函数
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [filter, selectedKeywordGroups, currentPage, pageSize]);

  const fetchKeywordGroups = async () => {
    try {
      const data = await api.keywords.listGroups();
      setKeywordGroups(data);
    } catch (error) {
      console.error("Failed to fetch keyword groups:", error);
    }
  };

  const fetchAlerts = async () => {
    setLoading(true);
    try {
      const params: any = {
        page: currentPage,
        page_size: pageSize,
      };
      if (filter.status) params.status = filter.status;
      if (filter.level) params.alert_level = filter.level;
      if (filter.keyword) params.keyword = filter.keyword;
      if (filter.has_phone) params.has_phone = true;
      if (selectedKeywordGroups.length > 0) {
        // 多个关键词组使用 OR 查询
        params.keyword_group_id = selectedKeywordGroups[0]; // API只支持单个，后续可以扩展
      }

      const data = await api.alerts.list(params);
      // API 返回格式: { items: [], total: number, page: number, page_size: number, total_pages: number }
      if (data && typeof data === 'object' && 'items' in data) {
        setAlerts(data.items || []);
        setTotalCount(data.total || 0);
      } else if (Array.isArray(data)) {
        setAlerts(data);
        setTotalCount(data.length);
      } else {
        setAlerts([]);
        setTotalCount(0);
      }
      setSelectedAlerts(new Set());
    } catch (error) {
      console.error("Failed to fetch alerts:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = () => {
    setFilter({ ...filter, keyword: search });
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleSearch();
    }
  };

  const handleAlert = async (status: string, note?: string) => {
    if (!selectedAlert) return;
    try {
      await api.alerts.handle(selectedAlert.id, { status, handler_note: note }, "admin");
      fetchAlerts();
      setSelectedAlert(null);
    } catch (error) {
      console.error("Failed to handle alert:", error);
    }
  };

  const handleBatchHandle = async (status: string, note?: string) => {
    if (selectedAlerts.size === 0) return;
    try {
      await api.alerts.batchUpdateStatus(
        Array.from(selectedAlerts),
        { status, handler_note: note }
      );
      fetchAlerts();
      setShowBatchHandleModal(false);
      setSelectedAlerts(new Set());
    } catch (error) {
      console.error("Failed to batch handle alerts:", error);
      alert("批量处理失败");
    }
  };

  const toggleSelectAlert = (id: number) => {
    const newSelected = new Set(selectedAlerts);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedAlerts(newSelected);
  };

  const toggleSelectAll = () => {
    if (selectedAlerts.size === alerts.length) {
      setSelectedAlerts(new Set());
    } else {
      setSelectedAlerts(new Set(alerts.map((a) => a.id)));
    }
  };

  const toggleKeywordGroup = (groupId: number) => {
    setSelectedKeywordGroups((prev) => {
      if (prev.includes(groupId)) {
        return prev.filter((id) => id !== groupId);
      } else {
        return [...prev, groupId];
      }
    });
  };

  const handleExportCSV = async () => {
    setExporting(true);
    try {
      await api.alerts.exportCSV({
        status: filter.status || undefined,
        alert_level: filter.level || undefined,
        keyword: search || undefined,
        keyword_group_id: selectedKeywordGroups.length > 0 ? selectedKeywordGroups[0] : undefined,
      });
    } catch (error) {
      console.error("Export failed:", error);
      alert("导出失败");
    } finally {
      setExporting(false);
    }
  };

  const levelColors = {
    low: "border-l-cyber-blue",
    medium: "border-l-cyber-purple",
    high: "border-l-yellow-500",
    critical: "border-l-cyber-pink",
  };

  const levelLabels = {
    low: "低",
    medium: "中",
    high: "高",
    critical: "严重",
  };

  const statusIcons = {
    pending: <Clock size={16} className="text-yellow-500" />,
    processing: <Clock size={16} className="text-cyber-blue" />,
    resolved: <CheckCircle size={16} className="text-cyber-green" />,
    ignored: <XCircle size={16} className="text-gray-500" />,
    false_positive: <XCircle size={16} className="text-gray-400" />,
  };

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* 标题 */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold neon-text">告警中心</h1>
          <p className="text-xs sm:text-sm text-muted-foreground mt-1">管理与处理关键词告警</p>
        </div>
        <Button
          variant="outline"
          onClick={handleExportCSV}
          disabled={exporting || loading || alerts.length === 0}
          className="w-full sm:w-auto min-h-[44px]"
        >
          <Download size={18} className="mr-2" />
          {exporting ? "导出中..." : "导出 CSV"}
        </Button>
      </div>

      {/* 筛选栏 */}
      <Card>
        <CardContent className="pt-4 sm:pt-6">
          <div className="flex flex-col gap-3">
            {/* 搜索行 */}
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="搜索关键词、会话..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  onKeyDown={handleKeyPress}
                  className="pl-10 min-h-[44px]"
                />
              </div>
              <Button variant="outline" onClick={handleSearch} className="min-h-[44px] px-4">
                搜索
              </Button>
            </div>

            {/* 筛选器行 - 桌面端 */}
            <div className="hidden sm:flex flex-wrap items-center gap-3">
              <select
                value={filter.status}
                onChange={(e) => setFilter({ ...filter, status: e.target.value })}
                className="input-tech px-4 py-2 rounded-lg min-h-[44px]"
              >
                <option value="">全部状态</option>
                <option value="pending">待处理</option>
                <option value="processing">处理中</option>
                <option value="resolved">已解决</option>
                <option value="ignored">已忽略</option>
                <option value="false_positive">误报</option>
              </select>
              <select
                value={filter.level}
                onChange={(e) => setFilter({ ...filter, level: e.target.value })}
                className="input-tech px-4 py-2 rounded-lg min-h-[44px]"
              >
                <option value="">全部级别</option>
                <option value="low">低</option>
                <option value="medium">中</option>
                <option value="high">高</option>
                <option value="critical">严重</option>
              </select>
              <label className="flex items-center gap-2 px-4 py-2 rounded-lg bg-secondary/50 border border-border cursor-pointer min-h-[44px] whitespace-nowrap">
                <input
                  type="checkbox"
                  checked={filter.has_phone}
                  onChange={(e) => setFilter({ ...filter, has_phone: e.target.checked })}
                  className="rounded"
                />
                <span className="text-sm">仅显示有手机号</span>
              </label>
              <div className="relative" ref={keywordGroupDropdownRef}>
                <Button
                  variant="outline"
                  onClick={() => {
                    if (!showKeywordGroupDropdown && keywordGroupDropdownRef.current) {
                      const rect = keywordGroupDropdownRef.current.getBoundingClientRect();
                      setDropdownPosition({
                        top: rect.bottom + window.scrollY + 4,
                        left: rect.left + window.scrollX,
                      });
                    }
                    setShowKeywordGroupDropdown(!showKeywordGroupDropdown);
                  }}
                  className="min-h-[44px]"
                >
                  关键词组筛选 ({selectedKeywordGroups.length})
                </Button>
                {showKeywordGroupDropdown && createPortal(
                  <div
                    data-dropdown="keyword-groups"
                    className="fixed bg-[#0a0e1a] border border-cyber-blue/30 rounded-lg p-2 min-w-[200px] z-[10000] max-h-64 overflow-y-auto tech-scrollbar shadow-lg"
                    style={{
                      top: `${dropdownPosition.top}px`,
                      left: `${dropdownPosition.left}px`,
                    }}
                  >
                    {keywordGroups.length === 0 ? (
                      <p className="text-xs text-muted-foreground p-2">加载中...</p>
                    ) : (
                      keywordGroups.map((kg) => (
                        <label
                          key={kg.id}
                          className="flex items-center gap-2 px-2 py-2 hover:bg-cyber-blue/10 rounded cursor-pointer min-h-[44px]"
                        >
                          <input
                            type="checkbox"
                            checked={selectedKeywordGroups.includes(kg.id)}
                            onChange={() => {
                              toggleKeywordGroup(kg.id);
                            }}
                            className="rounded w-5 h-5"
                          />
                          <span className="text-sm">{kg.name}</span>
                        </label>
                      ))
                    )}
                    <div className="border-t border-cyber-blue/10 mt-2 pt-2 flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        className="flex-1 text-xs min-h-[44px]"
                        onClick={() => setSelectedKeywordGroups(keywordGroups.map(kg => kg.id))}
                      >
                        全选
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="flex-1 text-xs min-h-[44px]"
                        onClick={() => setSelectedKeywordGroups([])}
                      >
                        清空
                      </Button>
                    </div>
                  </div>,
                  document.body
                )}
              </div>
              <Button variant="tech" onClick={fetchAlerts} className="min-h-[44px]">
                <Filter size={18} className="mr-2" />
                刷新
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  setFilter({ status: "", level: "", keyword: "", has_phone: false });
                  setSearch("");
                  setSelectedKeywordGroups([]);
                }}
                className="min-h-[44px]"
              >
                重置
              </Button>
            </div>

            {/* 筛选器行 - 手机端 */}
            <div className="space-y-2 sm:hidden">
              <div className="relative">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="搜索关键词..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && fetchAlerts()}
                  className="input-tech w-full pl-9 pr-3 py-2 rounded-lg min-h-[44px] text-sm"
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <select
                  value={filter.status}
                  onChange={(e) => setFilter({ ...filter, status: e.target.value })}
                  className="input-tech px-3 py-2 rounded-lg min-h-[44px] text-sm"
                >
                  <option value="">全部状态</option>
                  <option value="pending">待处理</option>
                  <option value="processing">处理中</option>
                  <option value="resolved">已解决</option>
                  <option value="ignored">已忽略</option>
                  <option value="false_positive">误报</option>
                </select>
                <select
                  value={filter.level}
                  onChange={(e) => setFilter({ ...filter, level: e.target.value })}
                  className="input-tech px-3 py-2 rounded-lg min-h-[44px] text-sm"
                >
                  <option value="">全部级别</option>
                  <option value="low">低</option>
                  <option value="medium">中</option>
                  <option value="high">高</option>
                  <option value="critical">严重</option>
                </select>
              </div>
              <Button
                variant="outline"
                onClick={() => setShowKeywordGroupFilter(!showKeywordGroupFilter)}
                className="w-full min-h-[44px] justify-between"
              >
                <span className="flex items-center gap-1">
                  <Tag size={16} />
                  关键词组筛选 ({selectedKeywordGroups.length})
                </span>
                <ChevronDown size={16} className={`transition-transform ${showKeywordGroupFilter ? "rotate-180" : ""}`} />
              </Button>
              {showKeywordGroupFilter && (
                <div className="grid grid-cols-2 gap-2 max-h-40 overflow-y-auto">
                  {keywordGroups.map((kg) => (
                    <button
                      key={kg.id}
                      onClick={() => toggleKeywordGroup(kg.id)}
                      className={`text-left px-3 py-2 rounded-lg text-xs min-h-[44px] border transition-colors ${
                        selectedKeywordGroups.includes(kg.id)
                          ? "bg-cyber-blue/20 border-cyber-blue/50 text-cyber-blue"
                          : "border-white/10 text-muted-foreground"
                      }`}
                    >
                      {kg.name}
                    </button>
                  ))}
                  <button
                    onClick={() => setSelectedKeywordGroups(keywordGroups.map(kg => kg.id))}
                    className="text-left px-3 py-2 rounded-lg text-xs min-h-[44px] border border-white/10 text-cyber-blue"
                  >
                    全选
                  </button>
                  <button
                    onClick={() => setSelectedKeywordGroups([])}
                    className="text-left px-3 py-2 rounded-lg text-xs min-h-[44px] border border-white/10 text-muted-foreground"
                  >
                    清除
                  </button>
                </div>
              )}
              <div className="grid grid-cols-2 gap-2">
                <Button variant="tech" onClick={fetchAlerts} className="min-h-[44px]">
                  <Filter size={16} className="mr-1" />
                  筛选
                </Button>
                <Button
                  variant="outline"
                  onClick={() => {
                    setFilter({ status: "", level: "", keyword: "", has_phone: false });
                    setSearch("");
                    setSelectedKeywordGroups([]);
                  }}
                  className="min-h-[44px]"
                >
                  重置
                </Button>
              </div>
            </div>
          </div>
          {/* 批量操作栏 */}
          {selectedAlerts.size > 0 && (
            <div className="mt-3 sm:mt-4 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2 bg-cyber-blue/10 border border-cyber-blue/30 rounded-lg px-3 sm:px-4 py-2">
              <span className="text-sm text-center sm:text-left">已选择 {selectedAlerts.size} 条告警</span>
              <div className="flex gap-2">
                <Button
                  variant="tech"
                  size="sm"
                  onClick={() => setShowBatchHandleModal(true)}
                  className="flex-1 sm:flex-initial min-h-[44px]"
                >
                  批量处理
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setSelectedAlerts(new Set())}
                  className="flex-1 sm:flex-initial min-h-[44px]"
                >
                  取消选择
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 告警列表 */}
      <div className="space-y-3">
        {loading ? (
          <div className="flex justify-center py-12">
            <div className="animate-spin w-8 h-8 border-2 border-cyber-blue border-t-transparent rounded-full" />
          </div>
        ) : alerts.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center text-muted-foreground">
              暂无告警
            </CardContent>
          </Card>
        ) : (
          <>
            {alerts.length > 0 && (
              <div className="flex items-center gap-2 px-4 py-2 text-sm text-muted-foreground">
                <button
                  onClick={toggleSelectAll}
                  className="flex items-center gap-2 hover:text-cyber-blue transition-colors"
                >
                  {selectedAlerts.size === alerts.length ? (
                    <CheckSquare size={18} className="text-cyber-blue" />
                  ) : (
                    <Square size={18} />
                  )}
                  {selectedAlerts.size === alerts.length ? "取消全选" : "全选"}
                </button>
              </div>
            )}
            {(() => {
              return alerts.map((alert) => (
              <AlertRow
                key={alert.id}
                alert={alert}
                onClick={() => setSelectedAlert(alert)}
                levelColor={levelColors[alert.alert_level as keyof typeof levelColors]}
                levelLabel={levelLabels[alert.alert_level as keyof typeof levelLabels]}
                isSelected={selectedAlerts.has(alert.id)}
                onToggleSelect={() => toggleSelectAlert(alert.id)}
              />
            ));
            })()}
          </>
        )}
      </div>

      {/* 分页控件 */}
      {totalCount > 0 && (
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-4 border-t border-cyber-blue/10">
          <div className="text-xs sm:text-sm text-muted-foreground text-center sm:text-left">
            共 {totalCount} 条告警，第 {currentPage} 页
          </div>
          <div className="flex items-center justify-center gap-2 flex-wrap">
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(parseInt(e.target.value));
                setCurrentPage(1);
              }}
              className="input-tech px-3 py-1.5 rounded-lg text-xs sm:text-sm min-h-[44px]"
            >
              <option value="10">10条/页</option>
              <option value="20">20条/页</option>
              <option value="50">50条/页</option>
              <option value="100">100条/页</option>
            </select>
            <Button
              variant="outline"
              size="sm"
              disabled={currentPage === 1}
              onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
              className="min-h-[44px] px-3"
            >
              上一页
            </Button>
            <span className="text-xs sm:text-sm px-2">
              第 {currentPage} / {Math.ceil(totalCount / pageSize)} 页
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={currentPage >= Math.ceil(totalCount / pageSize)}
              onClick={() => setCurrentPage(currentPage + 1)}
              className="min-h-[44px] px-3"
            >
              下一页
            </Button>
          </div>
        </div>
      )}

      {/* 详情弹窗 */}
      {selectedAlert && (
        <AlertDetailModal
          alert={selectedAlert}
          onClose={() => setSelectedAlert(null)}
          onHandle={handleAlert}
        />
      )}

      {/* 批量处理弹窗 */}
      {showBatchHandleModal && (
        <BatchHandleModal
          selectedCount={selectedAlerts.size}
          onClose={() => setShowBatchHandleModal(false)}
          onHandle={handleBatchHandle}
        />
      )}
    </div>
  );
}

interface AlertRowProps {
  alert: Alert;
  onClick: () => void;
  levelColor: string;
  levelLabel: string;
  isSelected: boolean;
  onToggleSelect: () => void;
}

function AlertRow({ alert, onClick, levelColor, levelLabel, isSelected, onToggleSelect }: AlertRowProps) {
  const statusLabels = {
    pending: "待处理",
    processing: "处理中",
    resolved: "已解决",
    ignored: "已忽略",
    false_positive: "误报",
  };

  return (
    <Card
      onClick={onClick}
      className={`cursor-pointer border-l-4 ${levelColor} hover:shadow-[0_0_20px_rgba(0,240,255,0.15)] transition-all active:scale-[0.98] ${isSelected ? "bg-cyber-blue/10" : ""}`}
    >
      <CardContent className="p-3 sm:pt-4 sm:px-6">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-start gap-2 sm:gap-3 flex-1 min-w-0">
            <button
              onClick={(e) => {
                e.stopPropagation();
                onToggleSelect();
              }}
              className="mt-1 shrink-0 min-h-[44px] min-w-[44px] flex items-center justify-center -ml-1"
            >
              {isSelected ? (
                <CheckSquare size={20} className="text-cyber-blue" />
              ) : (
                <Square size={20} className="text-muted-foreground" />
              )}
            </button>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                <AlertTriangle size={18} className="text-cyber-blue shrink-0" />
                <Badge variant={alert.alert_level === "critical" ? "destructive" : "default"} className="text-xs">
                  {levelLabel}
                </Badge>
                <span className="text-xs sm:text-sm text-muted-foreground truncate">
                  {alert.keyword_group_name} · {alert.keyword_text}
                </span>
              </div>
              <p
                className="text-xs sm:text-sm text-gray-300 line-clamp-2 sm:line-clamp-3"
                dangerouslySetInnerHTML={{
                  __html: alert.highlighted_message || sanitizeHtml(alert.message_preview)
                }}
              />
              {/* 手机端显示时间和状态 */}
              <div className="flex items-center gap-2 mt-2 sm:hidden">
                <Badge variant="outline" className="text-xs flex items-center gap-1">
                  {statusLabels[alert.status as keyof typeof statusLabels]}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  {alert.message_time ? `${formatDate(alert.message_time)} (消息时间)` : formatDate(alert.created_at)}
                </span>
              </div>
            </div>
          </div>
          {/* 桌面端显示状态和时间 */}
          <div className="hidden sm:flex flex-col items-end gap-2 ml-4 shrink-0">
            <Badge variant="outline" className="flex items-center gap-1">
              {statusLabels[alert.status as keyof typeof statusLabels]}
            </Badge>
            <span className="text-xs text-muted-foreground">
                {alert.message_time ? `${formatDate(alert.message_time)} (消息时间)` : formatDate(alert.created_at)}
              </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

interface AlertDetailModalProps {
  alert: Alert;
  onClose: () => void;
  onHandle: (status: string, note?: string) => void;
}

function AlertDetailModal({ alert, onClose, onHandle }: AlertDetailModalProps) {
  const [note, setNote] = useState("");

  return (
    <Modal isOpen={true} onClose={onClose} title="告警详情">
      <div className="space-y-4 max-h-[60vh] sm:max-h-none overflow-y-auto">
        <div>
          <label className="text-xs sm:text-sm text-muted-foreground">关键词</label>
          <p className="font-semibold text-sm sm:text-base">{alert.keyword_text}</p>
          <p className="text-xs sm:text-sm text-muted-foreground">分组: {alert.keyword_group_name}</p>
        </div>

        <div>
          <label className="text-xs sm:text-sm text-muted-foreground">消息内容</label>
          <div
            className="text-xs sm:text-sm bg-secondary/50 p-2 sm:p-3 rounded mt-1 whitespace-pre-wrap break-words max-h-48 sm:max-h-96 overflow-y-auto"
            dangerouslySetInnerHTML={{
              __html: alert.highlighted_message || sanitizeHtml(alert.message_preview)
            }}
          />
        </div>

        <div className="grid grid-cols-2 gap-3 sm:gap-4">
          <div>
            <label className="text-xs sm:text-sm text-muted-foreground">发送者</label>
            <p className="text-sm sm:text-base">{alert.sender_username || "未知会话"}</p>
            {alert.sender_tg_id && (
              <p className="text-xs text-muted-foreground mt-0.5">TG ID: {alert.sender_tg_id}</p>
            )}
            <p className="text-xs text-muted-foreground mt-0.5">📱 {formatPhone(alert.sender_phone) || "无"}</p>
          </div>
          <div>
            <label className="text-xs sm:text-sm text-muted-foreground">会话</label>
            <p className="text-sm sm:text-base">{alert.conversation_title || "未知会话"}</p>
          </div>
        </div>

        {alert.status === "pending" && (
          <div>
            <label className="text-xs sm:text-sm text-muted-foreground">处理备注</label>
            <Input
              placeholder="添加处理备注..."
              value={note}
              onChange={(e) => setNote(e.target.value)}
              className="mt-1 min-h-[44px]"
            />
          </div>
        )}

        <div className="flex flex-col sm:flex-row gap-2 sm:gap-3 pt-4">
          {alert.status === "pending" && (
            <>
              <Button
                variant="tech"
                className="flex-1 min-h-[44px]"
                onClick={() => onHandle("resolved", note)}
              >
                <CheckCircle size={18} className="mr-2" />
                标记已解决
              </Button>
              <Button
                variant="outline"
                className="flex-1 min-h-[44px]"
                onClick={() => onHandle("ignored", note)}
              >
                <XCircle size={18} className="mr-2" />
                标记误报
              </Button>
            </>
          )}
          <Button variant="ghost" className="flex-1 min-h-[44px]" onClick={onClose}>
            关闭
          </Button>
        </div>
      </div>
    </Modal>
  );
}

interface BatchHandleModalProps {
  selectedCount: number;
  onClose: () => void;
  onHandle: (status: string, note?: string) => void;
}

function BatchHandleModal({ selectedCount, onClose, onHandle }: BatchHandleModalProps) {
  const [note, setNote] = useState("");
  const [processing, setProcessing] = useState(false);

  const handleBatchAction = async (status: string) => {
    setProcessing(true);
    await onHandle(status, note);
    setProcessing(false);
  };

  return (
    <Modal isOpen={true} onClose={onClose} title={`批量处理告警 (${selectedCount}条)`}>
      <div className="space-y-4 max-h-[60vh] sm:max-h-none overflow-y-auto">
        <div>
          <label className="text-xs sm:text-sm text-muted-foreground">处理备注</label>
          <Input
            placeholder="添加处理备注（可选）..."
            value={note}
            onChange={(e) => setNote(e.target.value)}
            className="mt-1 min-h-[44px]"
          />
        </div>

        <div className="bg-secondary/50 p-2 sm:p-3 rounded-lg text-xs sm:text-sm text-muted-foreground">
          即将批量处理 {selectedCount} 条告警，此操作不可撤销。
        </div>

        <div className="flex flex-col gap-2 sm:gap-3 pt-4">
          <Button
            variant="tech"
            className="w-full min-h-[44px]"
            disabled={processing}
            onClick={() => handleBatchAction("resolved")}
          >
            <CheckCircle size={18} className="mr-2" />
            标记为已解决
          </Button>
          <Button
            variant="outline"
            className="w-full min-h-[44px]"
            disabled={processing}
            onClick={() => handleBatchAction("ignored")}
          >
            <XCircle size={18} className="mr-2" />
            标记为已忽略
          </Button>
          <Button
            variant="outline"
            className="w-full min-h-[44px]"
            disabled={processing}
            onClick={() => handleBatchAction("false_positive")}
          >
            <XCircle size={18} className="mr-2" />
            标记为误报
          </Button>
          <Button variant="ghost" className="w-full min-h-[44px]" onClick={onClose} disabled={processing}>
            取消
          </Button>
        </div>
      </div>
    </Modal>
  );
}
