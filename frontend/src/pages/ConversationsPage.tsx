import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { Input } from "@/components/ui/Input";
import {
  MessageSquare,
  Users,
  RefreshCw,
  Play,
  Pause,
  Settings,
  TrendingUp,
  Plus,
  X,
  Check,
  Hash,
  User,
  Radio,
  Trash2,
  CheckSquare,
  Square,
} from "lucide-react";

interface Account {
  id: number;
  phone: string;
  username?: string;
  status: string;
}

interface TelegramDialog {
  chat_id: number;
  title: string;
  username?: string;
  type: string;
  is_verified: boolean;
  participants_count?: number;
}

type DialogCategory = "all" | "private" | "channel" | "group";

interface Conversation {
  id: number;
  chat_id: number;
  title: string;
  username?: string;
  chat_type: string;
  status: string;
  enable_realtime: boolean;
  total_messages: number;
  total_alerts: number;
  last_message_at?: string;
}

export function ConversationsPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [showAddModal, setShowAddModal] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [selectedConversation, setSelectedConversation] = useState<Conversation | null>(null);
  const [availableDialogs, setAvailableDialogs] = useState<TelegramDialog[]>([]);
  const [selectedDialogs, setSelectedDialogs] = useState<Set<number>>(new Set());
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null);
  const [loadingAccounts, setLoadingAccounts] = useState(true);
  // 添加会话弹窗中的分类状态
  const [dialogCategory, setDialogCategory] = useState<DialogCategory>("all");

  // 批量操作相关状态
  const [selectedConversationIds, setSelectedConversationIds] = useState<Set<number>>(new Set());
  const [isBatchMode, setIsBatchMode] = useState(false);
  const [batchActionLoading, setBatchActionLoading] = useState(false);

  const [conversationsPage, setConversationsPage] = useState(1);
  const [conversationsTotal, setConversationsTotal] = useState(0);
  const CONVERSATIONS_PAGE_SIZE = 50;

  // 根据搜索过滤会话（前端分页）
  const filteredConversations = conversations.filter(conv => {
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    const title = conv.title || "";
    const username = conv.username || "";
    const chatType = conv.chat_type || "";
    return (
      title.toLowerCase().includes(query) ||
      username.toLowerCase().includes(query) ||
      chatType.toLowerCase().includes(query) ||
      (conv.chat_id && conv.chat_id.toString().includes(query))
    );
  });

  useEffect(() => {
    fetchConversations();
    fetchAccounts();
  }, [filter]);

  const fetchAccounts = async () => {
    setLoadingAccounts(true);
    try {
      const data = await api.accounts.list();
      setAccounts(data);
      // 自动选择第一个激活的账户
      const activeAccount = data?.find((acc: Account) => acc.status === "active");
      if (activeAccount) {
        setSelectedAccountId(activeAccount.id);
      } else if (data && data.length > 0) {
        setSelectedAccountId(data[0].id);
      }
    } catch (error) {
      console.error("Failed to fetch accounts:", error);
    } finally {
      setLoadingAccounts(false);
    }
  };

  const fetchConversations = async () => {
    try {
      const params: any = { page_size: CONVERSATIONS_PAGE_SIZE, page: conversationsPage };
      if (filter !== "all") {
        params.status = filter;
      }
      const data = await api.conversations.list(params);
      // API 返回格式可能是 {items: [], total: ...} 或直接是数组
      const conversationList = Array.isArray(data) ? data : data.items || [];
      const total = (data && typeof data === 'object' && 'total' in data) ? data.total : conversationList.length;
      setConversationsTotal(total);
      setConversations(conversationList);
    } catch (error) {
      console.error("获取会话失败:", error);
      setConversations([]);
    } finally {
      setLoading(false);
    }
  };

  const openAddModal = async () => {
    if (!selectedAccountId) {
      alert("请先选择一个账户");
      return;
    }
    setShowAddModal(true);
    // 重置分类为全部
    setDialogCategory("all");
    try {
      const response = await api.accounts.getDialogs(selectedAccountId);
      setAvailableDialogs(response.dialogs || []);
    } catch (error) {
      console.error("Failed to fetch dialogs:", error);
      alert("获取对话列表失败");
    }
  };

  const toggleDialogSelection = (chatId: number) => {
    const newSelected = new Set(selectedDialogs);
    if (newSelected.has(chatId)) {
      newSelected.delete(chatId);
    } else {
      newSelected.add(chatId);
    }
    setSelectedDialogs(newSelected);
  };

  // 全选/取消全选当前分类的对话
  const toggleSelectAllInCategory = () => {
    const filteredDialogs = getFilteredDialogs();
    const newSelected = new Set(selectedDialogs);

    // 检查当前分类下的所有对话是否都已被选中
    const allSelected = filteredDialogs.every(d => newSelected.has(d.chat_id));

    if (allSelected) {
      // 如果都已选中，则取消选中当前分类下的所有对话
      filteredDialogs.forEach(d => newSelected.delete(d.chat_id));
    } else {
      // 否则，选中当前分类下的所有对话
      filteredDialogs.forEach(d => newSelected.add(d.chat_id));
    }

    setSelectedDialogs(newSelected);
  };

  // 获取当前分类下的对话列表
  const getFilteredDialogs = (): TelegramDialog[] => {
    if (dialogCategory === "all") {
      return availableDialogs;
    }
    if (dialogCategory === "group") {
      // group 包括 supergroup 和 group
      return availableDialogs.filter(d => d.type === "supergroup" || d.type === "group");
    }
    return availableDialogs.filter(d => d.type === dialogCategory);
  };

  // 检查当前分类是否全选
  const isAllSelectedInCategory = (): boolean => {
    const filteredDialogs = getFilteredDialogs();
    if (filteredDialogs.length === 0) return false;
    return filteredDialogs.every(d => selectedDialogs.has(d.chat_id));
  };

  const addSelectedConversations = async () => {
    if (selectedDialogs.size === 0) {
      alert("请至少选择一个对话");
      return;
    }

    try {
      if (!selectedAccountId) {
        alert("请先选择一个账户");
        return;
      }

      // 使用批量创建API（自动跳过已存在的会话）
      const conversationsToCreate = Array.from(selectedDialogs)
        .map(chatId => {
          const dialog = availableDialogs.find(d => d.chat_id === chatId);
          if (!dialog) return null;
          return {
            account_id: selectedAccountId,
            chat_id: dialog.chat_id,
            chat_type: dialog.type,
            title: dialog.title,
            username: dialog.username,
          };
        })
        .filter((item): item is NonNullable<typeof item> => item !== null);

      const result = await api.conversations.batchCreate(conversationsToCreate);

      // 显示结果
      let { created, skipped } = result;

      if (skipped > 0 && !window.confirm(`${skipped} 个会话已存在。是否强制重新添加？（会删除旧记录并重建）`)) {
        let message = `成功添加 ${created} 个会话`;
        if (skipped > 0) {
          message += `，跳过 ${skipped} 个已存在的会话`;
        }
        alert(message);
      } else if (skipped > 0) {
        const forceResult = await api.conversations.batchCreate(conversationsToCreate, true);
        created = forceResult.created;
        skipped = 0;
        alert(`强制重新添加完成，成功添加 ${created} 个会话`);
      } else {
        alert(`成功添加 ${created} 个会话`);
      }

      setShowAddModal(false);
      setSelectedDialogs(new Set());
      fetchConversations();
    } catch (error) {
      console.error("Failed to add conversations:", error);
      alert("添加对话失败");
    }
  };

  const toggleMonitor = async (id: number, currentStatus: string) => {
    try {
      const newStatus = currentStatus === "active" ? "paused" : "active";
      await api.conversations.update(id, { status: newStatus });
      fetchConversations();
    } catch (error) {
      console.error("Failed to toggle monitor:", error);
      alert("切换监控状态失败");
    }
  };

  const pullHistory = async (id: number) => {
    try {
      await api.conversations.pullHistory(id);
      alert("历史消息拉取任务已启动");
    } catch (error) {
      console.error("Failed to pull history:", error);
    }
  };

  // 批量操作相关函数
  const toggleBatchMode = () => {
    setIsBatchMode(!isBatchMode);
    setSelectedConversationIds(new Set());
  };

  const toggleConversationSelection = (id: number) => {
    const newSelected = new Set(selectedConversationIds);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedConversationIds(newSelected);
  };

  const toggleSelectAllConversations = () => {
    const filteredConversations = getFilteredConversationsByStatus();
    const allSelected = filteredConversations.every(c => selectedConversationIds.has(c.id));

    if (allSelected) {
      setSelectedConversationIds(new Set());
    } else {
      setSelectedConversationIds(new Set(filteredConversations.map(c => c.id)));
    }
  };

  const getFilteredConversationsByStatus = (): Conversation[] => {
    if (filter === "all") return conversations;
    return conversations.filter(c => c.status === filter);
  };

  const isAllConversationsSelected = (): boolean => {
    const filtered = getFilteredConversationsByStatus();
    return filtered.length > 0 && filtered.every(c => selectedConversationIds.has(c.id));
  };

  const batchDelete = async () => {
    if (selectedConversationIds.size === 0) {
      alert("请至少选择一个会话");
      return;
    }

    if (!confirm(`确定要删除选中的 ${selectedConversationIds.size} 个会话吗？`)) {
      return;
    }

    setBatchActionLoading(true);
    try {
      const result = await api.conversations.batchDelete(Array.from(selectedConversationIds));
      alert(`成功删除 ${result.deleted} 个会话`);
      setSelectedConversationIds(new Set());
      fetchConversations();
    } catch (error: any) {
      console.error("Failed to batch delete:", error);
      alert("批量删除失败: " + error.message);
    } finally {
      setBatchActionLoading(false);
    }
  };

  const batchUpdateStatus = async (newStatus: string) => {
    if (selectedConversationIds.size === 0) {
      alert("请至少选择一个会话");
      return;
    }

    setBatchActionLoading(true);
    try {
      const result = await api.conversations.batchUpdate(
        Array.from(selectedConversationIds),
        { status: newStatus }
      );
      alert(`成功更新 ${result.updated} 个会话`);
      fetchConversations();
    } catch (error: any) {
      console.error("Failed to batch update:", error);
      alert("批量更新失败: " + error.message);
    } finally {
      setBatchActionLoading(false);
    }
  };

  const typeLabels = {
    private: "私聊",
    group: "群组",
    channel: "频道",
    supergroup: "超级群组",
  };

  const statusBadges = {
    active: { label: "监控中", variant: "success" },
    paused: { label: "已暂停", variant: "warning" },
    archived: { label: "已归档", variant: "outline" },
  };

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* 标题 */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold neon-text">会话管理</h1>
          <p className="text-xs sm:text-sm text-muted-foreground mt-1">管理 Telegram 群组/频道/私聊监控</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          {/* 批量操作按钮 - 桌面端 */}
          <div className="hidden sm:flex gap-3">
            {isBatchMode && (
              <>
                <Button variant="outline" onClick={toggleSelectAllConversations} className="min-h-[44px]">
                  {isAllConversationsSelected() ? (
                    <>
                      <CheckSquare size={18} className="mr-2" />
                      取消全选
                    </>
                  ) : (
                    <>
                      <Square size={18} className="mr-2" />
                      全选当前
                    </>
                  )}
                </Button>
                <Button
                  variant="tech"
                  onClick={() => batchUpdateStatus("active")}
                  disabled={batchActionLoading || selectedConversationIds.size === 0}
                  className="min-h-[44px]"
                >
                  <Play size={18} className="mr-2" />
                  启动 ({selectedConversationIds.size})
                </Button>
                <Button
                  variant="outline"
                  onClick={() => batchUpdateStatus("paused")}
                  disabled={batchActionLoading || selectedConversationIds.size === 0}
                  className="min-h-[44px]"
                >
                  <Pause size={18} className="mr-2" />
                  暂停 ({selectedConversationIds.size})
                </Button>
                <Button
                  variant="destructive"
                  onClick={batchDelete}
                  disabled={batchActionLoading || selectedConversationIds.size === 0}
                  className="min-h-[44px]"
                >
                  <Trash2 size={18} className="mr-2" />
                  删除 ({selectedConversationIds.size})
                </Button>
              </>
            )}
            <Button variant={isBatchMode ? "outline" : "tech"} onClick={toggleBatchMode} className="min-h-[44px]">
              <CheckSquare size={18} className="mr-2" />
              {isBatchMode ? "退出批量" : "批量操作"}
            </Button>
            <Button variant="tech" onClick={openAddModal} className="min-h-[44px]">
              <Plus size={18} className="mr-2" />
              添加会话
            </Button>
            <Button variant="outline" onClick={fetchConversations} className="min-h-[44px]">
              <RefreshCw size={18} className="mr-2" />
              刷新
            </Button>
          </div>

          {/* 手机端简化按钮 */}
          <div className="flex sm:hidden gap-2 flex-1">
            <Button variant="tech" onClick={openAddModal} className="flex-1 min-h-[44px]">
              <Plus size={18} className="mr-2" />
              添加
            </Button>
            <Button variant="outline" onClick={fetchConversations} className="min-h-[44px] px-3">
              <RefreshCw size={18} />
            </Button>
            <Button variant={isBatchMode ? "outline" : "tech"} onClick={toggleBatchMode} className="min-h-[44px] px-3">
              <CheckSquare size={18} />
            </Button>
          </div>
        </div>
      </div>

      {/* 手机端批量操作栏 */}
      {isBatchMode && (
        <div className="sm:hidden flex flex-col gap-2 bg-cyber-blue/10 border border-cyber-blue/30 rounded-lg p-3">
          <span className="text-sm text-center">已选择 {selectedConversationIds.size} 个会话</span>
          <div className="grid grid-cols-2 gap-2">
            <Button variant="outline" onClick={toggleSelectAllConversations} className="min-h-[44px]">
              {isAllConversationsSelected() ? "取消全选" : "全选当前"}
            </Button>
            <Button
              variant="tech"
              onClick={() => batchUpdateStatus("active")}
              disabled={batchActionLoading || selectedConversationIds.size === 0}
              className="min-h-[44px]"
            >
              <Play size={16} className="mr-1" />
              启动
            </Button>
            <Button
              variant="outline"
              onClick={() => batchUpdateStatus("paused")}
              disabled={batchActionLoading || selectedConversationIds.size === 0}
              className="min-h-[44px]"
            >
              <Pause size={16} className="mr-1" />
              暂停
            </Button>
            <Button
              variant="destructive"
              onClick={batchDelete}
              disabled={batchActionLoading || selectedConversationIds.size === 0}
              className="min-h-[44px]"
            >
              <Trash2 size={16} className="mr-1" />
              删除
            </Button>
          </div>
        </div>
      )}

      {/* 筛选栏 */}
      <Card>
        <CardContent className="pt-4 sm:pt-6">
          <div className="flex flex-col gap-3">
            {/* 状态筛选行 */}
            <div className="flex items-center gap-2 sm:gap-4 flex-wrap">
              <span className="text-xs sm:text-sm text-muted-foreground shrink-0">状态:</span>
              {["all", "active", "paused"].map((status) => (
                <button
                  key={status}
                  onClick={() => {
                    setFilter(status);
                    setSelectedConversationIds(new Set());
                  }}
                  className={`px-3 sm:px-4 py-2 rounded-lg transition-colors text-xs sm:text-sm min-h-[44px] ${
                    filter === status
                      ? "bg-cyber-blue/20 text-cyber-blue border border-cyber-blue/50"
                      : "bg-secondary/50 text-muted-foreground hover:bg-secondary"
                  }`}
                >
                  {status === "all" ? "全部" : status === "active" ? "监控中" : "已暂停"}
                </button>
              ))}
            </div>

            {/* 搜索框和账户选择 */}
            <div className="flex flex-col sm:flex-row gap-2 sm:gap-4">
              {/* 搜索框 */}
              <div className="relative flex-1 min-w-0">
                <input
                  type="text"
                  placeholder="搜索会话（标题、用户名、类型、ID）..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-8 py-2 bg-secondary/50 border border-cyber-blue/30 rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-cyber-blue focus:shadow-[0_0_10px_rgba(0,240,255,0.2)] transition-all text-sm min-h-[44px]"
                />
                <Hash size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                {searchQuery && (
                  <button
                    onClick={() => setSearchQuery("")}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground min-h-[44px] min-w-[44px] flex items-center justify-center"
                  >
                    <X size={16} />
                  </button>
                )}
              </div>

              {searchQuery && (
                <span className="text-xs sm:text-sm text-muted-foreground shrink-0 self-center">
                  找到 {filteredConversations.length} 个结果
                </span>
              )}

              {/* 账户选择 - 桌面端 */}
              <div className="hidden sm:flex items-center gap-2">
                <span className="text-sm text-muted-foreground shrink-0">账户:</span>
                {loadingAccounts ? (
                  <span className="text-sm text-muted-foreground">加载中...</span>
                ) : accounts.length === 0 ? (
                  <span className="text-sm text-muted-foreground">暂无可用账户</span>
                ) : (
                  <div className="flex gap-2 flex-wrap">
                    {accounts.map((acc) => (
                      <button
                        key={acc.id}
                        onClick={() => setSelectedAccountId(acc.id)}
                        className={`px-4 py-2 rounded-lg transition-colors text-sm min-h-[44px] ${
                          selectedAccountId === acc.id
                            ? "bg-cyber-green/20 text-cyber-green border border-cyber-green/50"
                            : "bg-secondary/50 text-muted-foreground hover:bg-secondary"
                        }`}
                      >
                        {acc.username || acc.phone}
                        {acc.status === "active" && (
                          <span className="ml-2 text-xs">●</span>
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* 账户选择 - 手机端（折叠） */}
            <div className="sm:hidden">
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">账户:</span>
                <select
                  value={selectedAccountId || ""}
                  onChange={(e) => setSelectedAccountId(Number(e.target.value))}
                  className="flex-1 input-tech px-3 py-2 rounded-lg text-sm min-h-[44px]"
                >
                  {loadingAccounts ? (
                    <option value="">加载中...</option>
                  ) : (
                    accounts.map((acc) => (
                      <option key={acc.id} value={acc.id}>
                        {acc.username || acc.phone}
                        {acc.status === "active" ? " ●" : ""}
                      </option>
                    ))
                  )}
                </select>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 会话列表 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
        {loading ? (
          <div className="col-span-full flex justify-center py-12">
            <div className="animate-spin w-8 h-8 border-2 border-cyber-blue border-t-transparent rounded-full" />
            <p className="ml-4 text-muted-foreground">加载中...</p>
          </div>
        ) : filteredConversations.length === 0 ? (
          <Card className="col-span-full">
            <CardContent className="py-12 text-center text-muted-foreground">
              <p className="text-lg mb-2">{searchQuery ? "未找到匹配的会话" : "暂无会话"}</p>
              {conversations.length > 0 && searchQuery && (
                <p className="text-sm mt-2">
                  共 {conversations.length} 个会话，搜索过滤后显示 {filteredConversations.length} 个
                </p>
              )}
              {!searchQuery && conversations.length === 0 && (
                <p className="text-sm mt-2">
                  请点击上方"添加会话"按钮添加需要监控的会话
                </p>
              )}
            </CardContent>
          </Card>
        ) : (
          filteredConversations.map((conv) => (
            <ConversationCard
              key={conv.id}
              conversation={conv}
              typeLabel={typeLabels[conv.chat_type as keyof typeof typeLabels]}
              statusBadge={statusBadges[conv.status as keyof typeof statusBadges]}
              isBatchMode={isBatchMode}
              isSelected={selectedConversationIds.has(conv.id)}
              onSelect={() => toggleConversationSelection(conv.id)}
              onToggleMonitor={() => toggleMonitor(conv.id, conv.status)}
              onPullHistory={() => pullHistory(conv.id)}
              onSettings={() => {
                setSelectedConversation(conv);
                setShowSettingsModal(true);
              }}
            />
          ))
        )}
      </div>

      {/* 会话列表分页 */}
      {conversationsTotal > CONVERSATIONS_PAGE_SIZE && (
        <div className="flex items-center justify-center gap-2 pt-4">
          <Button
            variant="outline"
            size="sm"
            disabled={conversationsPage === 1}
            onClick={() => setConversationsPage(conversationsPage - 1)}
            className="min-h-[44px] px-3"
          >
            上一页
          </Button>
          <span className="text-sm text-muted-foreground px-2">
            第 {conversationsPage} / {Math.ceil(conversationsTotal / CONVERSATIONS_PAGE_SIZE)} 页
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={conversationsPage >= Math.ceil(conversationsTotal / CONVERSATIONS_PAGE_SIZE)}
            onClick={() => setConversationsPage(conversationsPage + 1)}
            className="min-h-[44px] px-3"
          >
            下一页
          </Button>
        </div>
      )}

      {/* 添加会话模态框 */}
      <Modal
        isOpen={showAddModal}
        onClose={() => setShowAddModal(false)}
        title="添加监控会话"
      >
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            选择要监控的 Telegram 群组/频道 ({selectedDialogs.size} 已选择)
          </p>

          {/* 分类按钮 */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm text-muted-foreground">分类:</span>
            <div className="flex gap-2">
              <button
                onClick={() => setDialogCategory("all")}
                className={`px-3 py-1.5 rounded-lg text-sm transition-colors flex items-center gap-1.5 ${
                  dialogCategory === "all"
                    ? "bg-cyber-blue/20 text-cyber-blue border border-cyber-blue/50"
                    : "bg-secondary/50 text-muted-foreground hover:bg-secondary"
                }`}
              >
                <Hash size={14} />
                全部
              </button>
              <button
                onClick={() => setDialogCategory("private")}
                className={`px-3 py-1.5 rounded-lg text-sm transition-colors flex items-center gap-1.5 ${
                  dialogCategory === "private"
                    ? "bg-cyber-blue/20 text-cyber-blue border border-cyber-blue/50"
                    : "bg-secondary/50 text-muted-foreground hover:bg-secondary"
                }`}
              >
                <User size={14} />
                私聊
              </button>
              <button
                onClick={() => setDialogCategory("channel")}
                className={`px-3 py-1.5 rounded-lg text-sm transition-colors flex items-center gap-1.5 ${
                  dialogCategory === "channel"
                    ? "bg-cyber-blue/20 text-cyber-blue border border-cyber-blue/50"
                    : "bg-secondary/50 text-muted-foreground hover:bg-secondary"
                }`}
              >
                <Radio size={14} />
                频道
              </button>
              <button
                onClick={() => setDialogCategory("group")}
                className={`px-3 py-1.5 rounded-lg text-sm transition-colors flex items-center gap-1.5 ${
                  dialogCategory === "group"
                    ? "bg-cyber-blue/20 text-cyber-blue border border-cyber-blue/50"
                    : "bg-secondary/50 text-muted-foreground hover:bg-secondary"
                }`}
              >
                <Users size={14} />
                群聊
              </button>
            </div>

            {/* 全选按钮 */}
            <button
              onClick={toggleSelectAllInCategory}
              className={`ml-auto px-3 py-1.5 rounded-lg text-sm transition-colors flex items-center gap-1.5 ${
                isAllSelectedInCategory()
                  ? "bg-cyber-green/20 text-cyber-green border border-cyber-green/50"
                  : "bg-secondary/50 text-muted-foreground hover:bg-secondary"
              }`}
              disabled={getFilteredDialogs().length === 0}
            >
              <Check size={14} />
              {isAllSelectedInCategory() ? "取消全选" : "全选"}
            </button>
          </div>

          {/* 显示当前分类名称和数量 */}
          <p className="text-xs text-muted-foreground">
            {dialogCategory === "all" && `共 ${availableDialogs.length} 个对话`}
            {dialogCategory === "private" && `私聊: ${getFilteredDialogs().length} 个`}
            {dialogCategory === "channel" && `频道: ${getFilteredDialogs().length} 个`}
            {dialogCategory === "group" && `群聊: ${getFilteredDialogs().length} 个`}
          </p>

          <div className="max-h-96 overflow-y-auto space-y-2">
            {getFilteredDialogs().length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                {availableDialogs.length === 0 ? "暂无可用的对话" : "该分类下暂无对话"}
              </div>
            ) : (
              getFilteredDialogs().map((dialog) => (
                <div
                  key={dialog.chat_id}
                  onClick={() => toggleDialogSelection(dialog.chat_id)}
                  className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                    selectedDialogs.has(dialog.chat_id)
                      ? "bg-cyber-blue/20 border-cyber-blue"
                      : "bg-secondary/50 border-border hover:border-cyber-blue/50"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <input
                      type="checkbox"
                      checked={selectedDialogs.has(dialog.chat_id)}
                      onChange={() => toggleDialogSelection(dialog.chat_id)}
                      className="w-4 h-4"
                    />
                    <div className="flex-1">
                      <p className="font-medium">{dialog.title}</p>
                      <p className="text-sm text-muted-foreground">
                        {dialog.type === 'channel' ? '频道' :
                         dialog.type === 'supergroup' ? '群组' :
                         dialog.type === 'group' ? '群组' : '私聊'}
                        {dialog.username && ` @${dialog.username}`}
                        {dialog.participants_count && ` · ${dialog.participants_count.toLocaleString()} 成员`}
                      </p>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="flex gap-3 justify-end">
            <Button variant="outline" onClick={() => setShowAddModal(false)}>
              取消
            </Button>
            <Button variant="tech" onClick={addSelectedConversations}>
              添加选中的会话 ({selectedDialogs.size})
            </Button>
          </div>
        </div>
      </Modal>

      {/* 会话设置模态框 */}
      {showSettingsModal && selectedConversation && (
        <ConversationSettingsModal
          conversation={selectedConversation}
          onClose={() => {
            setShowSettingsModal(false);
            setSelectedConversation(null);
          }}
          onSave={async (settings) => {
            try {
              await api.conversations.update(selectedConversation.id, {
                monitor_config: settings,
              });
              fetchConversations();
              setShowSettingsModal(false);
              setSelectedConversation(null);
            } catch (error) {
              console.error("Failed to update conversation settings:", error);
              alert("更新设置失败");
            }
          }}
        />
      )}
    </div>
  );
}

interface ConversationCardProps {
  conversation: Conversation;
  typeLabel: string;
  statusBadge: { label: string; variant: string };
  isBatchMode: boolean;
  isSelected: boolean;
  onSelect: () => void;
  onToggleMonitor: () => void;
  onPullHistory: () => void;
  onSettings: () => void;
}

function ConversationCard({
  conversation,
  typeLabel,
  statusBadge,
  isBatchMode,
  isSelected,
  onSelect,
  onToggleMonitor,
  onPullHistory,
  onSettings,
}: ConversationCardProps) {
  return (
    <Card className={`card-hover relative ${isBatchMode && isSelected ? "ring-2 ring-cyber-blue" : ""}`}>
      {isBatchMode && (
        <div
          className="absolute top-3 left-3 z-10 min-h-[44px] min-w-[44px] flex items-center justify-center"
          onClick={onSelect}
        >
          {isSelected ? (
            <CheckSquare size={24} className="text-cyber-blue" />
          ) : (
            <Square size={24} className="text-muted-foreground" />
          )}
        </div>
      )}
      <CardHeader className="pb-2 sm:pb-3">
        <div className="flex items-start justify-between">
          <div className={`flex-1 min-w-0 ${isBatchMode ? "ml-10 sm:ml-12" : ""}`}>
            <CardTitle className="text-base sm:text-lg truncate">{conversation.title || "未知会话"}</CardTitle>
            {conversation.username && (
              <p className="text-xs sm:text-sm text-muted-foreground truncate">@{conversation.username}</p>
            )}
          </div>
          <Badge variant={statusBadge.variant as any} className="text-[10px] sm:text-xs shrink-0 ml-2">{statusBadge.label}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 sm:space-y-4">
        <div className="flex items-center gap-2 sm:gap-4 text-xs sm:text-sm">
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <MessageSquare size={14} className="sm:w-4 sm:h-4 shrink-0" />
            <span>{typeLabel}</span>
          </div>
          {conversation.status === "active" && (
            <div className="flex items-center gap-1.5 text-cyber-green">
              <Play size={14} className="sm:w-4 sm:h-4 shrink-0" />
              <span>监控中</span>
            </div>
          )}
        </div>

        <div className="grid grid-cols-2 gap-2 sm:gap-4 py-2 sm:py-3 border-t border-b border-cyber-blue/10">
          <div>
            <p className="text-lg sm:text-2xl font-bold">{conversation.total_messages.toLocaleString()}</p>
            <p className="text-[10px] sm:text-xs text-muted-foreground">消息数</p>
          </div>
          <div>
            <p className="text-lg sm:text-2xl font-bold text-cyber-pink">{conversation.total_alerts}</p>
            <p className="text-[10px] sm:text-xs text-muted-foreground">告警数</p>
          </div>
        </div>

        <div className="flex gap-2">
          <Button variant="tech" size="sm" className="flex-1 min-h-[44px]" onClick={onToggleMonitor}>
            {conversation.status === "active" ? (
              <>
                <Pause size={14} className="mr-1 sm:w-4 sm:h-4" />
                <span className="text-xs sm:text-sm">暂停</span>
              </>
            ) : (
              <>
                <Play size={14} className="mr-1 sm:w-4 sm:h-4" />
                <span className="text-xs sm:text-sm">启动</span>
              </>
            )}
          </Button>
          <Button variant="outline" size="sm" onClick={onPullHistory} className="min-h-[44px] min-w-[44px] sm:min-w-0 px-2 sm:px-4">
            <TrendingUp size={14} className="sm:mr-1 sm:w-4 sm:h-4" />
            <span className="hidden sm:inline text-xs sm:text-sm">拉取历史</span>
          </Button>
          <Button variant="ghost" size="sm" onClick={onSettings} className="min-h-[44px] min-w-[44px]">
            <Settings size={14} className="sm:w-4 sm:h-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function ConversationSettingsModal({
  conversation,
  onClose,
  onSave,
}: {
  conversation: Conversation;
  onClose: () => void;
  onSave: (settings: any) => void;
}) {
  const [enableRealtime, setEnableRealtime] = useState(conversation.enable_realtime);
  const [historyDays, setHistoryDays] = useState(7);
  const [messageLimit, setMessageLimit] = useState(1000);

  const handleSave = () => {
    onSave({
      enable_realtime: enableRealtime,
      history_days: historyDays,
      message_limit: messageLimit,
    });
  };

  return (
    <Modal isOpen={true} onClose={onClose} title={`会话设置 - ${conversation.title}`}>
      <div className="space-y-4">
        <div>
          <p className="text-sm text-muted-foreground mb-2">会话信息</p>
          <div className="bg-secondary/50 p-3 rounded-lg space-y-1 text-sm">
            <p>类型: {conversation.chat_type}</p>
            <p>消息数: {conversation.total_messages.toLocaleString()}</p>
            <p>告警数: {conversation.total_alerts}</p>
          </div>
        </div>

        <div className="flex items-center justify-between py-2 border-t border-cyber-blue/10">
          <div>
            <p>启用实时监控</p>
            <p className="text-xs text-muted-foreground">自动监听新消息</p>
          </div>
          <button
            onClick={() => setEnableRealtime(!enableRealtime)}
            className={`w-12 h-6 rounded-full relative transition-colors ${
              enableRealtime ? "bg-cyber-blue/40" : "bg-gray-500/20"
            }`}
          >
            <div
              className={`absolute top-1 w-4 h-4 bg-cyber-blue rounded-full transition-all ${
                enableRealtime ? "right-1" : "left-1"
              }`}
            />
          </button>
        </div>

        <div>
          <label className="text-sm text-muted-foreground">历史回溯天数</label>
          <Input
            type="number"
            value={historyDays}
            onChange={(e) => setHistoryDays(parseInt(e.target.value) || 7)}
            min={1}
            max={365}
          />
          <p className="text-xs text-muted-foreground mt-1">
            批量同步时回溯的历史天数
          </p>
        </div>

        <div>
          <label className="text-sm text-muted-foreground">历史消息限制</label>
          <Input
            type="number"
            value={messageLimit}
            onChange={(e) => setMessageLimit(parseInt(e.target.value) || 1000)}
            min={1}
            max={100000}
          />
          <p className="text-xs text-muted-foreground mt-1">
            每次最多拉取的历史消息数
          </p>
        </div>

        <div className="flex gap-3 pt-4">
          <Button variant="tech" className="flex-1" onClick={handleSave}>
            保存设置
          </Button>
          <Button variant="ghost" className="flex-1" onClick={onClose}>
            取消
          </Button>
        </div>
      </div>
    </Modal>
  );
}
