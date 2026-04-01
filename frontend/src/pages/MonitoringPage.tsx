import { useState, useEffect, useRef, useCallback } from "react";
import { useWebSocket } from "@/hooks/useWebSocket";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { formatRelativeTime } from "@/lib/utils";
import {
  Activity,
  Pause,
  Play,
  Filter,
  Search,
  User,
  MessageSquare,
  Clock,
  Video,
  Image,
  File,
  Bell,
  CheckCircle,
  XCircle,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  GripVertical,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  X,
} from "lucide-react";

interface Message {
  id: number;
  conversation_id: number;
  sender_id: number;
  message_type: string;
  text: string;
  date: string;
  sender_username?: string;
  conversation_title?: string;
  alert_id?: number | null;
}

interface Conversation {
  id: number;
  title: string;
  chat_type: string;
  status: string;
  account_phone?: string;
  total_messages?: number;
  last_message_at?: string;
}

interface MonitoringStatus {
  account_id: number;
  account_phone: string;
  conversation_id: number;
  conversation_title: string;
  is_monitoring: boolean;
  messages_last_hour: number;
  alerts_last_hour: number;
  last_activity: string;
}

export function MonitoringPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [monitoringStatus, setMonitoringStatus] = useState<MonitoringStatus[]>([]);
  const [selectedConversation, setSelectedConversation] = useState<number | null>(null);
  const [filter, setFilter] = useState("");
  const [messageTypeFilter, setMessageTypeFilter] = useState<string>("all");
  const [alertFilter, setAlertFilter] = useState<string>("all");
  const [autoScroll, setAutoScroll] = useState(true);
  const [globalStats, setGlobalStats] = useState<any>(null);
  const { isConnected, messages: wsMessages, clearMessages } = useWebSocket();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 分页状态
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [totalCount, setTotalCount] = useState(0);

  // 排序状态
  const [sortField, setSortField] = useState<"title" | "total_messages" | "status" | "last_message_at" | "custom">("custom");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("asc");
  const [draggedItem, setDraggedItem] = useState<number | null>(null);
  const [customOrder, setCustomOrder] = useState<number[]>([]);

  // 新消息提示状态
  const [conversationsWithNewMessages, setConversationsWithNewMessages] = useState<Set<number>>(new Set());
  const [showNewMessageBadge, setShowNewMessageBadge] = useState<Record<number, number>>({});

  // 自动轮询状态（当WebSocket断开时启用）
  const [pollingInterval, setPollingInterval] = useState<ReturnType<typeof setInterval> | null>(null);
  const [isPolling, setIsPolling] = useState(false);

  // 声音通知状态
  const [soundEnabled, setSoundEnabled] = useState(true);
  const audioContextRef = useRef<AudioContext | null>(null);

  // 会话搜索状态
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearchFocused, setIsSearchFocused] = useState(false);

  // 播放通知声音
  const playNotificationSound = useCallback(() => {
    if (!soundEnabled) return;

    try {
      // 使用Web Audio API生成简单的提示音
      if (!audioContextRef.current) {
        audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
      }

      const audioContext = audioContextRef.current;
      const oscillator = audioContext.createOscillator();
      const gainNode = audioContext.createGain();

      oscillator.connect(gainNode);
      gainNode.connect(audioContext.destination);

      oscillator.frequency.value = 800; // 频率
      oscillator.type = "sine"; // 波形

      gainNode.gain.setValueAtTime(0.1, audioContext.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.1);

      oscillator.start(audioContext.currentTime);
      oscillator.stop(audioContext.currentTime + 0.1);
    } catch (error) {
      console.error("播放通知声音失败:", error);
    }
  }, [soundEnabled]);

  // localStorage 键名
  const SORT_PREFERENCES_KEY = "tg-monitoring-conversation-sort";

  // 从 localStorage 加载排序偏好
  const loadSortPreferences = useCallback(() => {
    try {
      const saved = localStorage.getItem(SORT_PREFERENCES_KEY);
      if (saved) {
        const prefs = JSON.parse(saved);
        setSortField(prefs.sortField || "custom");
        setSortOrder(prefs.sortOrder || "asc");
        setCustomOrder(prefs.customOrder || []);
      }
    } catch (error) {
      console.error("Failed to load sort preferences:", error);
    }
  }, []);

  // 保存排序偏好到 localStorage
  const saveSortPreferences = useCallback((field: typeof sortField, order: typeof sortOrder, orderList: number[]) => {
    try {
      const prefs = {
        sortField: field,
        sortOrder: order,
        customOrder: orderList,
      };
      localStorage.setItem(SORT_PREFERENCES_KEY, JSON.stringify(prefs));
    } catch (error) {
      console.error("Failed to save sort preferences:", error);
    }
  }, []);

  useEffect(() => {
    // 先加载排序偏好
    loadSortPreferences();
    // 然后获取数据
    fetchConversations();
    fetchGlobalStats();
    const interval = setInterval(() => {
      fetchGlobalStats();
    }, 5000); // 每5秒刷新全局统计
    return () => clearInterval(interval);
  }, [loadSortPreferences]);

  // 当会话或分页参数变化时重新获取消息
  useEffect(() => {
    if (selectedConversation) {
      fetchMessages();
    }
  }, [selectedConversation, currentPage, pageSize, filter, messageTypeFilter, alertFilter]);

  // 监听 WebSocket 消息，实时更新消息列表
  useEffect(() => {
    if (wsMessages.length > 0) {
      // 处理所有未处理的 WebSocket 消息
      wsMessages.forEach((wsMessage) => {
        if (wsMessage.type === "new_message" && wsMessage.data) {
          const newMessage = wsMessage.data as Message;

          // 只有当新消息属于当前选中的会话时才添加到列表
          if (selectedConversation && newMessage.conversation_id === selectedConversation) {
            setMessages((prev) => {
              // 检查消息是否已存在（防止重复）
              if (prev.some((m) => m.id === newMessage.id)) {
                return prev;
              }
              // 播放通知声音
              playNotificationSound();
              // 将新消息添加到列表开头
              return [newMessage, ...prev];
            });

            // 更新全局统计（今日消息数 +1）
            setGlobalStats((prev: any) => ({
              ...prev,
              today_messages: (prev?.today_messages || 0) + 1,
            }));

            // 清除该会话的新消息标记
            setConversationsWithNewMessages((prev) => {
              const newSet = new Set(prev);
              newSet.delete(newMessage.conversation_id);
              return newSet;
            });
            setShowNewMessageBadge((prev) => {
              const newBadge = { ...prev };
              delete newBadge[newMessage.conversation_id];
              return newBadge;
            });
          } else {
            // 如果新消息不属于当前选中的会话，添加新消息提示
            playNotificationSound();
            setConversationsWithNewMessages((prev) => new Set([...prev, newMessage.conversation_id]));
            setShowNewMessageBadge((prev) => ({
              ...prev,
              [newMessage.conversation_id]: (prev[newMessage.conversation_id] || 0) + 1,
            }));
          }

          // 更新会话的消息数量和最后消息时间
          setConversations((prev) =>
            prev.map((conv) =>
              conv.id === newMessage.conversation_id
                ? {
                    ...conv,
                    total_messages: (conv.total_messages || 0) + 1,
                    last_message_at: newMessage.date,
                  }
                : conv
            )
          );
        } else if (wsMessage.type === "new_alert" && wsMessage.data) {
          // 更新今日告警数
          setGlobalStats((prev: any) => ({
            ...prev,
            today_alerts: (prev?.today_alerts || 0) + 1,
          }));
        }
      });

      // 清除已处理的 WebSocket 消息
      clearMessages();
    }
  }, [wsMessages, selectedConversation, clearMessages]);

  // 监控WebSocket连接状态，断开时启用自动轮询
  useEffect(() => {
    if (!isConnected && !pollingInterval) {
      // WebSocket断开，启动自动轮询
      console.log("WebSocket断开，启用自动轮询");
      setIsPolling(true);

      const interval = setInterval(async () => {
        // 轮询当前选中的会话消息
        if (selectedConversation) {
          try {
            const params: any = {
              conversation_id: selectedConversation,
              page: 1,
              page_size: 10, // 只获取最新的10条消息
            };
            const response = await api.messages.list(params);
            const newMessages = Array.isArray(response) ? response : response.items || [];

            if (newMessages.length > 0) {
              // 检查是否有新消息
              setMessages((prev) => {
                const existingIds = new Set(prev.map((m) => m.id));
                const trulyNew = newMessages.filter((m: Message) => !existingIds.has(m.id));
                if (trulyNew.length > 0) {
                  return [...trulyNew, ...prev];
                }
                return prev;
              });
            }

            // 同时更新会话列表
            fetchConversations();
          } catch (error) {
            console.error("轮询失败:", error);
          }
        }
      }, 5000); // 每5秒轮询一次

      setPollingInterval(interval);
    } else if (isConnected && pollingInterval) {
      // WebSocket恢复，停止自动轮询
      console.log("WebSocket恢复，停止自动轮询");
      clearInterval(pollingInterval);
      setPollingInterval(null);
      setIsPolling(false);
    }

    // 清理函数
    return () => {
      if (pollingInterval) {
        clearInterval(pollingInterval);
        setPollingInterval(null);
        setIsPolling(false);
      }
    };
  }, [isConnected, selectedConversation, pollingInterval]);

  const fetchGlobalStats = async () => {
    try {
      const stats = await api.dashboard.getStats();
      setGlobalStats(stats);
    } catch (error) {
      console.error("Failed to fetch global stats:", error);
    }
  };

  // 移除自动刷新，避免干扰筛选
  // useEffect(() => {
  //   const interval = setInterval(fetchMessages, 3000); // 每3秒刷新消息
  //   return () => clearInterval(interval);
  // }, [selectedConversation]);

  useEffect(() => {
    if (autoScroll && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, autoScroll]);

  const fetchConversations = async () => {
    try {
      const data = await api.conversations.list({ status: "active", page_size: 500 });
      // API 返回格式可能是 {items: [], total: ...} 或直接是数组
      const conversationList = Array.isArray(data) ? data : data.items || [];
      setConversations(conversationList);
      if (conversationList.length > 0 && !selectedConversation) {
        setSelectedConversation(conversationList[0].id);
      }
    } catch (error) {
      console.error("Failed to fetch conversations:", error);
    }
  };

  // 排序会话列表
  const getSortedConversations = () => {
    let result = [...conversations];

    // 应用搜索过滤
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase().trim();
      result = result.filter((conv) => {
        // 搜索标题
        if (conv.title && conv.title.toLowerCase().includes(query)) {
          return true;
        }
        // 搜索类型
        if (conv.chat_type && conv.chat_type.toLowerCase().includes(query)) {
          return true;
        }
        // 搜索状态
        if (conv.status && conv.status.toLowerCase().includes(query)) {
          return true;
        }
        // 搜索账号手机号
        if (conv.account_phone && conv.account_phone.toLowerCase().includes(query)) {
          return true;
        }
        // 搜索ID
        if (conv.id && conv.id.toString().includes(query)) {
          return true;
        }
        return false;
      });
    }

    // 应用排序
    if (sortField === "custom") {
      // 自定义拖动排序模式
      const orderMap = new Map(customOrder.map((id, index) => [id, index]));
      result = result.sort((a, b) => {
        const aIndex = orderMap.get(a.id) ?? 999;
        const bIndex = orderMap.get(b.id) ?? 999;
        return aIndex - bIndex;
      });
    } else {
      // 字段排序模式
      result = result.sort((a, b) => {
        let comparison = 0;

        switch (sortField) {
          case "title":
            comparison = (a.title || "").localeCompare(b.title || "");
            break;
          case "total_messages":
            comparison = (a.total_messages || 0) - (b.total_messages || 0);
            break;
          case "status":
            comparison = a.status.localeCompare(b.status);
            break;
          case "last_message_at":
            comparison = new Date(a.last_message_at || 0).getTime() - new Date(b.last_message_at || 0).getTime();
            break;
          default:
            comparison = 0;
        }

        return sortOrder === "asc" ? comparison : -comparison;
      });
    }

    return result;
  };

  // 切换排序字段
  const handleSort = (field: "title" | "total_messages" | "status") => {
    let newField: typeof sortField = field;
    let newOrder: typeof sortOrder = "asc";

    if (sortField === field) {
      // 点击同一字段，切换方向
      newOrder = sortOrder === "asc" ? "desc" : "asc";
    } else {
      // 切换到新字段，默认升序，清空自定义顺序
      newOrder = "asc";
    }

    setSortField(newField);
    setSortOrder(newOrder);
    setCustomOrder([]);
    saveSortPreferences(newField, newOrder, []);
  };

  // 拖放开始
  const handleDragStart = (e: React.DragEvent, conversationId: number) => {
    setDraggedItem(conversationId);
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", conversationId.toString());
  };

  // 拖放结束
  const handleDragEnd = () => {
    setDraggedItem(null);
  };

  // 拖放悬停
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  };

  // 拖放放置
  const handleDrop = (e: React.DragEvent, targetConversationId: number) => {
    e.preventDefault();
    const draggedId = parseInt(e.dataTransfer.getData("text/plain"));

    if (draggedId === targetConversationId || draggedItem === null) return;

    // 获取当前显示的会话列表
    const currentList = getSortedConversations();
    const draggedIndex = currentList.findIndex(c => c.id === draggedId);
    const targetIndex = currentList.findIndex(c => c.id === targetConversationId);

    if (draggedIndex === -1 || targetIndex === -1) return;

    // 创建新顺序
    const newOrder = currentList.map(c => c.id);
    newOrder.splice(draggedIndex, 1);
    newOrder.splice(targetIndex, 0, draggedId);

    // 更新为自定义模式并保存新顺序
    setSortField("custom");
    setSortOrder("asc");
    setCustomOrder(newOrder);
    saveSortPreferences("custom", "asc", newOrder);
  };

  // 获取排序图标
  const getSortIcon = (field: "title" | "total_messages" | "status") => {
    if (sortField === "custom") return <ArrowUpDown size={14} />;
    if (sortField !== field) return <ArrowUpDown size={14} />;
    return sortOrder === "asc" ? <ArrowUp size={14} /> : <ArrowDown size={14} />;
  };

  const fetchMonitoringStatus = async () => {
    try {
      // 使用 dashboard API 获取监控状态
      const stats = await api.dashboard.getStats();
      // 将 dashboard stats 转换为 MonitoringStatus 格式
      setMonitoringStatus(stats.monitoring_status || []);
    } catch (error) {
      console.error("Failed to fetch monitoring status:", error);
    }
  };

  const fetchMessages = async () => {
    if (!selectedConversation) return;
    try {
      const params: any = {
        conversation_id: selectedConversation,
        page: currentPage,
        page_size: pageSize,
      };

      // 添加搜索参数
      if (filter) params.keyword = filter;
      if (messageTypeFilter !== "all") params.message_type = messageTypeFilter;
      if (alertFilter === "alerted") params.has_alert = true;
      if (alertFilter === "normal") params.has_alert = false;

      const response = await api.messages.list(params);

      // API 返回的数据结构可能是 { items: [], total: } 或直接是数组
      const newMessages = Array.isArray(response) ? response : response.items || [];
      const total = Array.isArray(response) ? newMessages.length : (response.total || newMessages.length);

      setMessages(newMessages);
      setTotalCount(total);
    } catch (error) {
      console.error("Failed to fetch messages:", error);
    }
  };

  const filteredMessages = messages; // 搜索现在在服务器端进行

  const handlePauseMonitoring = async (conversationId: number) => {
    try {
      await api.conversations.update(conversationId, { status: "paused" });
      fetchConversations();
    } catch (error) {
      console.error("Failed to pause monitoring:", error);
      alert("暂停监控失败");
    }
  };

  const handleResumeMonitoring = async (conversationId: number) => {
    try {
      await api.conversations.update(conversationId, { status: "active" });
      fetchConversations();
    } catch (error) {
      console.error("Failed to resume monitoring:", error);
      alert("恢复监控失败");
    }
  };

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* 标题 */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold neon-text">实时监控</h1>
          <p className="text-xs sm:text-sm text-muted-foreground mt-1">
            {isConnected ? "实时查看 Telegram 消息流" : "WebSocket 已断开，使用自动轮询"}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-secondary/50 border border-cyber-blue/30">
            <div className={`w-2 h-2 rounded-full ${
              isConnected ? "status-dot.online" : isPolling ? "status-dot.warning" : "status-dot.offline"
            }`} />
            <span className="text-xs sm:text-sm text-muted-foreground">
              {isConnected ? "WebSocket 已连接" : isPolling ? "自动轮询中" : "连接已断开"}
            </span>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setSoundEnabled(!soundEnabled)}
            className={`min-h-[44px] ${soundEnabled ? "border-cyber-blue text-cyber-blue" : ""}`}
          >
            <Bell size={16} className={soundEnabled ? "animate-pulse" : ""} />
            <span className="ml-1 hidden sm:inline">{soundEnabled ? " 声音: 开" : " 声音: 关"}</span>
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setAutoScroll(!autoScroll)}
            className="min-h-[44px] hidden sm:flex"
          >
            {autoScroll ? "自动滚动: 开" : "自动滚动: 关"}
          </Button>
        </div>
      </div>

      {/* 监控状态概览 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 sm:gap-4">
        <Card>
          <CardContent className="p-3 sm:pt-6">
            <div className="flex items-center gap-2 sm:gap-4">
              <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-lg bg-cyber-blue/20 flex items-center justify-center shrink-0">
                <Activity size={20} className="text-cyber-blue sm:w-6 sm:h-6" />
              </div>
              <div className="min-w-0">
                <p className="text-xl sm:text-2xl font-bold">{globalStats?.active_conversations ?? conversations.length}</p>
                <p className="text-[10px] sm:text-sm text-muted-foreground">监控会话</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-3 sm:pt-6">
            <div className="flex items-center gap-2 sm:gap-4">
              <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-lg bg-cyber-green/20 flex items-center justify-center shrink-0">
                <MessageSquare size={20} className="text-cyber-green sm:w-6 sm:h-6" />
              </div>
              <div className="min-w-0">
                <p className="text-xl sm:text-2xl font-bold">{globalStats?.today_messages ?? 0}</p>
                <p className="text-[10px] sm:text-sm text-muted-foreground">今日消息</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-3 sm:pt-6">
            <div className="flex items-center gap-2 sm:gap-4">
              <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-lg bg-cyber-purple/20 flex items-center justify-center shrink-0">
                <Bell size={20} className="text-cyber-purple sm:w-6 sm:h-6" />
              </div>
              <div className="min-w-0">
                <p className="text-xl sm:text-2xl font-bold">{globalStats?.today_alerts ?? 0}</p>
                <p className="text-[10px] sm:text-sm text-muted-foreground">今日告警</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-3 sm:pt-6">
            <div className="flex items-center gap-2 sm:gap-4">
              <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-lg bg-cyber-pink/20 flex items-center justify-center shrink-0">
                <CheckCircle size={20} className="text-cyber-pink sm:w-6 sm:h-6" />
              </div>
              <div className="min-w-0">
                <p className="text-xl sm:text-2xl font-bold">{globalStats?.active_accounts ?? 0}</p>
                <p className="text-[10px] sm:text-sm text-muted-foreground">运行账号</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 sm:gap-6">
        {/* 会话列表 */}
        <Card className="lg:col-span-1">
          <CardHeader className="p-3 sm:p-6">
            <div className="space-y-2 sm:space-y-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base sm:text-lg">监控会话</CardTitle>
                <div className="text-[10px] sm:text-xs text-muted-foreground">
                  {getSortedConversations().length} 个会话
                  {searchQuery && ` · ${getSortedConversations().length} 个结果`}
                </div>
              </div>

              {/* 搜索框 */}
              <div className="relative">
                <Search
                  size={16}
                  className={`absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground ${
                    isSearchFocused ? "text-cyber-blue" : ""
                  }`}
                />
                <Input
                  type="text"
                  placeholder="搜索会话..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onFocus={() => setIsSearchFocused(true)}
                  onBlur={() => setIsSearchFocused(false)}
                  className="pl-9 h-9 sm:h-10 text-xs sm:text-sm"
                />
                {searchQuery && (
                  <button
                    onClick={() => setSearchQuery("")}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground min-h-[44px] min-w-[44px] flex items-center justify-center"
                  >
                    <X size={14} />
                  </button>
                )}
              </div>

              {/* 排序按钮 - 桌面端 */}
              <div className="hidden sm:flex items-center justify-between">
                <div className="text-xs text-muted-foreground">
                  排序方式
                </div>
                <div className="flex items-center gap-1">
                  <Button variant="ghost" size="icon" onClick={() => handleSort("title")} title="按名称排序">
                    {getSortIcon("title")}
                  </Button>
                  <Button variant="ghost" size="icon" onClick={() => handleSort("total_messages")} title="按消息数排序">
                    {getSortIcon("total_messages")}
                  </Button>
                  <Button variant="ghost" size="icon" onClick={fetchConversations}>
                    <RefreshCw size={16} />
                  </Button>
                </div>
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <div className="space-y-1 max-h-[300px] sm:max-h-[600px] overflow-y-auto tech-scrollbar">
              {conversations.length === 0 ? (
                <div className="p-4 text-center text-muted-foreground text-sm">
                  暂无监控会话
                </div>
              ) : (
                getSortedConversations().map((conv) => (
                  <div
                    key={conv.id}
                    draggable
                    onDragStart={(e) => handleDragStart(e, conv.id)}
                    onDragEnd={handleDragEnd}
                    onDragOver={handleDragOver}
                    onDrop={(e) => handleDrop(e, conv.id)}
                    className={`group px-3 sm:px-4 py-2 sm:py-3 hover:bg-cyber-blue/10 transition-colors cursor-move relative active:bg-cyber-blue/20 ${
                      selectedConversation === conv.id ? "bg-cyber-blue/20 border-l-2 border-cyber-blue" : ""
                    } ${draggedItem === conv.id ? "opacity-50" : ""} ${
                      conversationsWithNewMessages.has(conv.id) ? "bg-cyber-blue/5" : ""
                    }`}
                  >
                    {/* 新消息徽章 */}
                    {showNewMessageBadge[conv.id] > 0 && (
                      <div className="absolute top-1 right-2 z-10">
                        <Badge variant="destructive" className="animate-pulse text-[10px] px-1.5 py-0.5">
                          新消息 +{showNewMessageBadge[conv.id]}
                        </Badge>
                      </div>
                    )}

                    <div className="flex items-center gap-2">
                      <GripVertical size={14} className="text-muted-foreground shrink-0 cursor-grab hidden sm:block" />
                      {/* 左侧：会话名称 + 副标题 */}
                      <button
                        onClick={() => setSelectedConversation(conv.id)}
                        className="flex-1 text-left min-w-0 min-h-[44px] py-1"
                      >
                        <div className="flex items-center gap-2">
                          <p className="font-medium truncate text-sm sm:text-base flex-1 min-w-0">{conv.title || "未知会话"}</p>
                          {conversationsWithNewMessages.has(conv.id) && (
                            <span className="relative flex h-2 w-2 shrink-0">
                              <span className="animate-ping absolute inline-flex h-2 w-2 rounded-full bg-cyber-blue opacity-75"></span>
                              <span className="relative inline-flex rounded-full h-2 w-2 bg-cyber-blue"></span>
                            </span>
                          )}
                        </div>
                        <p className="text-[10px] sm:text-xs text-muted-foreground mt-0.5 truncate">
                          {conv.chat_type} · {conv.total_messages || 0} 条消息
                        </p>
                      </button>
                      {/* 右侧：状态 + 暂停按钮 */}
                      <div className="flex items-center gap-1.5 shrink-0">
                        <Badge variant={conv.status === "active" ? "success" : "warning"} className="text-[10px] sm:text-xs">
                          {conv.status === "active" ? "监控中" : "已暂停"}
                        </Badge>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            if (conv.status === "active") {
                              handlePauseMonitoring(conv.id);
                            } else {
                              handleResumeMonitoring(conv.id);
                            }
                          }}
                          className={`p-1.5 rounded-md transition-all min-h-[32px] min-w-[32px] flex items-center justify-center ${
                            conv.status === "active" 
                              ? "text-muted-foreground hover:text-amber-500 hover:bg-amber-50/10" 
                              : "text-muted-foreground hover:text-green-500 hover:bg-green-50/10"
                          }`}
                          title={conv.status === "active" ? "暂停监控" : "恢复监控"}
                        >
                          {conv.status === "active" ? (
                            <Pause size={14} />
                          ) : (
                            <Play size={14} />
                          )}
                        </button>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>

        {/* 消息列表 */}
        <Card className="lg:col-span-3">
          <CardHeader className="p-3 sm:p-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <CardTitle className="text-base sm:text-lg">
                消息流
                {selectedConversation && (
                  <span className="text-xs sm:text-sm text-muted-foreground ml-2">
                    - {conversations.find((c) => c.id === selectedConversation)?.title}
                  </span>
                )}
              </CardTitle>
              <div className="flex items-center gap-2 flex-wrap">
                <div className="relative flex-1 sm:flex-initial">
                  <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    placeholder="搜索消息..."
                    value={filter}
                    onChange={(e) => setFilter(e.target.value)}
                    onKeyPress={(e) => {
                      if (e.key === "Enter") {
                        setCurrentPage(1);
                        fetchMessages();
                      }
                    }}
                    className="pl-10 w-full sm:w-48 min-h-[44px] text-sm"
                  />
                </div>
                <select
                  value={messageTypeFilter}
                  onChange={(e) => {
                    setMessageTypeFilter(e.target.value);
                    setCurrentPage(1);
                  }}
                  className="input-tech px-3 py-1.5 rounded-lg text-xs sm:text-sm min-h-[44px]"
                >
                  <option value="all">全部类型</option>
                  <option value="text">文本</option>
                  <option value="photo">图片</option>
                  <option value="video">视频</option>
                  <option value="document">文档</option>
                  <option value="sticker">贴纸</option>
                </select>
                <select
                  value={alertFilter}
                  onChange={(e) => {
                    setAlertFilter(e.target.value);
                    setCurrentPage(1);
                  }}
                  className="input-tech px-3 py-1.5 rounded-lg text-xs sm:text-sm min-h-[44px]"
                >
                  <option value="all">全部消息</option>
                  <option value="alerted">有告警</option>
                  <option value="normal">无告警</option>
                </select>
                <select
                  value={pageSize}
                  onChange={(e) => {
                    setPageSize(parseInt(e.target.value));
                    setCurrentPage(1);
                  }}
                  className="input-tech px-3 py-1.5 rounded-lg text-xs sm:text-sm min-h-[44px] hidden sm:block"
                >
                  <option value="10">10条/页</option>
                  <option value="20">20条/页</option>
                  <option value="50">50条/页</option>
                  <option value="100">100条/页</option>
                </select>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setFilter("");
                    setMessageTypeFilter("all");
                    setAlertFilter("all");
                    setCurrentPage(1);
                  }}
                  className="min-h-[44px]"
                >
                  <Filter size={18} className="mr-2 sm:mr-0" />
                  <span className="sm:hidden">重置</span>
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-3 sm:p-6 pt-0 sm:pt-0">
            <div className="space-y-4">
              {/* 消息列表 */}
              <div className="max-h-[400px] sm:max-h-[600px] overflow-y-auto tech-scrollbar pr-0 sm:pr-2">
                {!selectedConversation ? (
                  <div className="flex items-center justify-center h-64 text-muted-foreground">
                    请选择一个会话开始监控
                  </div>
                ) : filteredMessages.length === 0 ? (
                  <div className="flex items-center justify-center h-64 text-muted-foreground">
                    暂无消息
                  </div>
                ) : (
                  <>
                    {filteredMessages.map((msg) => (
                      <MessageCard key={msg.id} message={msg} />
                    ))}
                  </>
                )}
              </div>

              {/* 分页控件 */}
              {selectedConversation && totalCount > 0 && (
                <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-4 border-t border-cyber-blue/10">
                  <div className="text-xs sm:text-sm text-muted-foreground text-center sm:text-left">
                    共 {totalCount} 条消息，第 {currentPage} 页
                  </div>
                  <div className="flex items-center justify-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={currentPage === 1}
                      onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                      className="min-h-[44px] px-3"
                    >
                      <ChevronLeft size={16} className="sm:mr-1" />
                      <span className="hidden sm:inline">上一页</span>
                    </Button>
                    <span className="text-xs sm:text-sm px-2">
                      第 <input
                        type="number"
                        value={currentPage}
                        onChange={(e) => {
                          const page = parseInt(e.target.value);
                          if (page > 0 && page <= Math.ceil(totalCount / pageSize)) {
                            setCurrentPage(page);
                          }
                        }}
                        className="w-10 sm:w-12 px-1 sm:px-2 py-1 rounded bg-secondary/50 border border-cyber-blue/20 text-center text-xs sm:text-sm"
                        min={1}
                        max={Math.ceil(totalCount / pageSize)}
                      /> / {Math.ceil(totalCount / pageSize)}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={currentPage >= Math.ceil(totalCount / pageSize)}
                      onClick={() => setCurrentPage(currentPage + 1)}
                      className="min-h-[44px] px-3"
                    >
                      <span className="hidden sm:inline">下一页</span>
                      <ChevronRight size={16} className="sm:ml-1" />
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

interface MessageCardProps {
  message: Message;
}

function MessageCard({ message }: MessageCardProps) {
  const [expanded, setExpanded] = useState(false);
  const messageTypeIcons = {
    text: MessageSquare,
    photo: Image,
    video: Video,
    document: File,
    audio: File,
    sticker: Image,
  };

  const Icon = messageTypeIcons[message.message_type as keyof typeof messageTypeIcons] || MessageSquare;

  return (
    <>
      <div
        className="glass rounded-lg p-4 border border-cyber-blue/10 hover:border-cyber-blue/30 transition-colors cursor-pointer"
        onClick={() => setExpanded(true)}
      >
        <div className="flex items-start justify-between mb-2">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-cyber-blue/20 flex items-center justify-center">
              <User size={20} className="text-cyber-blue" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <p className="font-semibold">{message.sender_username || "未知会话"}</p>
                {message.alert_id !== null && message.alert_id !== undefined && (
                  <Badge variant="destructive" className="text-xs">
                    <Bell size={10} className="mr-1" />
                    告警
                  </Badge>
                )}
              </div>
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Clock size={14} />
                {formatRelativeTime(message.date)}
              </div>
            </div>
          </div>
          <Badge variant="outline" className="text-xs shrink-0">
            <Icon size={12} className="mr-1" />
            {message.message_type}
          </Badge>
        </div>
        {message.text && (
          <p className="text-sm mt-2 text-gray-300 whitespace-pre-wrap break-words line-clamp-3">
            {message.text}
          </p>
        )}
        <p className="text-xs text-muted-foreground mt-2 text-right">点击查看详情 →</p>
      </div>

      <Modal
        isOpen={expanded}
        onClose={() => setExpanded(false)}
        title="消息详情"
      >
        <div className="space-y-4 max-h-[60vh] sm:max-h-none overflow-y-auto">
          <div className="grid grid-cols-2 gap-3 sm:gap-4">
            <div>
              <label className="text-xs sm:text-sm text-muted-foreground">发送者</label>
              <p className="text-sm sm:text-base font-medium">{message.sender_username || "未知会话"}</p>
              {message.sender_id && (
                <p className="text-xs text-muted-foreground mt-0.5">ID: {message.sender_id}</p>
              )}
            </div>
            <div>
              <label className="text-xs sm:text-sm text-muted-foreground">会话</label>
              <p className="text-sm sm:text-base font-medium">{message.conversation_title || "未知会话"}</p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:gap-4">
            <div>
              <label className="text-xs sm:text-sm text-muted-foreground">消息类型</label>
              <p className="text-sm sm:text-base">{message.message_type}</p>
            </div>
            <div>
              <label className="text-xs sm:text-sm text-muted-foreground">时间</label>
              <p className="text-sm sm:text-base">{message.date ? new Date(message.date).toLocaleString("zh-CN") : "Unknown"}</p>
            </div>
          </div>

          {message.alert_id !== null && message.alert_id !== undefined && (
            <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30">
              <p className="text-sm text-red-400">
                <Bell size={14} className="inline mr-1" />
                该消息已触发告警（告警 ID: {message.alert_id}）
              </p>
            </div>
          )}

          {message.text && (
            <div>
              <label className="text-xs sm:text-sm text-muted-foreground">消息内容</label>
              <div className="text-sm bg-secondary/50 p-3 rounded mt-1 whitespace-pre-wrap break-words max-h-96 overflow-y-auto">
                {message.text}
              </div>
            </div>
          )}

          <div className="flex gap-2 pt-4">
            <Button variant="ghost" className="flex-1 min-h-[44px]" onClick={() => setExpanded(false)}>
              关闭
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
}
