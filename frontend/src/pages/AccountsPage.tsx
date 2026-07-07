import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { Input } from "@/components/ui/Input";
import {
  Users,
  Plus,
  LogOut,
  RefreshCw,
  MessageSquare,
  CheckCircle,
  XCircle,
  Trash2,
  LogIn,
} from "lucide-react";

interface Account {
  id: number;
  phone: string;
  username?: string;
  first_name?: string;
  is_active: boolean;
  is_authorized: boolean;
  total_messages: number;
  total_conversations: number;
  last_used_at?: string;
  sync_status?: "idle" | "syncing" | "success" | "error";
}

export function AccountsPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [reloginAccount, setReloginAccount] = useState<Account | null>(null);

  useEffect(() => {
    fetchAccounts();
  }, []);

  const fetchAccounts = async () => {
    setLoading(true);
    try {
      const data = await api.accounts.list();
      setAccounts(data.map((acc: Account) => ({ ...acc, sync_status: "idle" as const })));
    } catch (error) {
      console.error("Failed to fetch accounts:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleDisconnect = async (id: number) => {
    if (!confirm("确定要断开此账号吗？")) return;
    try {
      await api.accounts.disconnect(id);
      fetchAccounts();
    } catch (error) {
      console.error("Failed to disconnect account:", error);
      alert("断开账号失败");
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("确定要删除此账号吗？这将删除账号及其所有相关数据（会话、消息等），此操作不可恢复！")) return;
    const confirmDelete = prompt("此操作危险！请输入 'DELETE' 确认删除：");
    if (confirmDelete !== "DELETE") {
      alert("已取消删除");
      return;
    }
    try {
      await api.accounts.delete(id);
      fetchAccounts();
    } catch (error: any) {
      console.error("Failed to delete account:", error);
      alert(error.message || "删除账号失败");
    }
  };

  const handleToggle = async (id: number) => {
    try {
      await api.accounts.toggle(id);
      fetchAccounts();
    } catch (error: any) {
      console.error("Failed to toggle account:", error);
      alert(error.message || "切换账号状态失败");
    }
  };

  const handleSyncDialogs = async (id: number) => {
    // Update sync status to syncing
    setAccounts((prev) =>
      prev.map((acc) => (acc.id === id ? { ...acc, sync_status: "syncing" as const } : acc))
    );

    try {
      const result = await api.accounts.getDialogs(id);

      // Update sync status to success
      setAccounts((prev) =>
        prev.map((acc) => (acc.id === id ? { ...acc, sync_status: "success" as const } : acc))
      );

      // Show success message with details
      const message = result.message || "同步成功";
      alert(`${message}\n\n已同步对话列表，请在"会话管理"页面查看。`);

      // Reset status after 3 seconds
      setTimeout(() => {
        setAccounts((prev) =>
          prev.map((acc) => (acc.id === id ? { ...acc, sync_status: "idle" as const } : acc))
        );
      }, 3000);

      // Refresh accounts to get updated counts
      fetchAccounts();
    } catch (error: any) {
      console.error("Failed to sync dialogs:", error);

      // Update sync status to error
      setAccounts((prev) =>
        prev.map((acc) => (acc.id === id ? { ...acc, sync_status: "error" as const } : acc))
      );

      const errorMessage = error.response?.data?.detail || error.message || "同步失败，请检查账号是否已登录";
      alert(errorMessage);

      // Reset status after 3 seconds
      setTimeout(() => {
        setAccounts((prev) =>
          prev.map((acc) => (acc.id === id ? { ...acc, sync_status: "idle" as const } : acc))
        );
      }, 3000);
    }
  };

  const handleBatchSync = async (id: number) => {
    if (!confirm("确定要批量同步此账号的所有对话吗？这可能需要较长时间。")) return;

    // Update sync status to syncing
    setAccounts((prev) =>
      prev.map((acc) => (acc.id === id ? { ...acc, sync_status: "syncing" as const } : acc))
    );

    try {
      const result = await api.conversations.batchSync(id);

      // Update sync status to success
      setAccounts((prev) =>
        prev.map((acc) => (acc.id === id ? { ...acc, sync_status: "success" as const } : acc))
      );

      const message = result.message || "批量同步成功";
      alert(`${message}\n\n已在后台开始同步历史消息，请稍后在"消息查询"页面查看。`);

      // Reset status after 3 seconds
      setTimeout(() => {
        setAccounts((prev) =>
          prev.map((acc) => (acc.id === id ? { ...acc, sync_status: "idle" as const } : acc))
        );
      }, 3000);

      // Refresh accounts to get updated counts
      fetchAccounts();
    } catch (error: any) {
      console.error("Failed to batch sync:", error);

      // Update sync status to error
      setAccounts((prev) =>
        prev.map((acc) => (acc.id === id ? { ...acc, sync_status: "error" as const } : acc))
      );

      const errorMessage = error.response?.data?.detail || error.message || "批量同步失败";
      alert(errorMessage);

      // Reset status after 3 seconds
      setTimeout(() => {
        setAccounts((prev) =>
          prev.map((acc) => (acc.id === id ? { ...acc, sync_status: "idle" as const } : acc))
        );
      }, 3000);
    }
  };

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* 标题 */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold neon-text">账号管理</h1>
          <p className="text-xs sm:text-sm text-muted-foreground mt-1">管理 Telegram 账号登录状态</p>
        </div>
        <Button variant="tech" onClick={() => setShowLoginModal(true)} className="w-full sm:w-auto min-h-[44px]">
          <Plus size={18} className="mr-2" />
          添加账号
        </Button>
      </div>

      {/* 账号列表 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
        {loading ? (
          <div className="col-span-full flex justify-center py-12">
            <div className="animate-spin w-8 h-8 border-2 border-cyber-blue border-t-transparent rounded-full" />
          </div>
        ) : accounts.length === 0 ? (
          <Card className="col-span-full">
            <CardContent className="py-12 text-center text-muted-foreground">
              <p className="mb-4">暂无账号</p>
              <Button variant="tech" onClick={() => setShowLoginModal(true)}>
                添加第一个账号
              </Button>
            </CardContent>
          </Card>
        ) : (
          accounts.map((account) => (
            <AccountCard
              key={account.id}
              account={account}
              onDisconnect={() => handleDisconnect(account.id)}
              onDelete={() => handleDelete(account.id)}
              onRelogin={() => setReloginAccount(account)}
              onSyncDialogs={() => handleSyncDialogs(account.id)}
              onBatchSync={() => handleBatchSync(account.id)}
              onToggle={() => handleToggle(account.id)}
            />
          ))
        )}
      </div>

      {/* 登录弹窗 */}
      {showLoginModal && (
        <LoginModal onClose={() => setShowLoginModal(false)} onSuccess={() => {
          fetchAccounts();
          setShowLoginModal(false);
        }} />
      )}

      {/* 重新登录弹窗 */}
      {reloginAccount && (
        <ReloginModal
          account={reloginAccount}
          onClose={() => setReloginAccount(null)}
          onSuccess={() => {
            fetchAccounts();
            setReloginAccount(null);
          }}
        />
      )}
    </div>
  );
}

interface AccountCardProps {
  account: Account;
  onDisconnect: () => void;
  onDelete: () => void;
  onRelogin: () => void;
  onSyncDialogs: () => void;
  onBatchSync: () => void;
  onToggle: () => void;
}

function AccountCard({ account, onDisconnect, onDelete, onRelogin, onSyncDialogs, onBatchSync, onToggle }: AccountCardProps) {
  const isSyncing = account.sync_status === "syncing";
  const showSyncStatus = account.sync_status === "success" || account.sync_status === "error";

  return (
    <Card className="card-hover">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-full bg-gradient-to-br from-cyber-blue to-cyber-purple flex items-center justify-center text-white text-lg font-bold">
              {(account.first_name || account.username || account.phone)[0].toUpperCase()}
            </div>
            <div>
              <CardTitle className="text-base">
                {account.first_name || account.username || "Unknown"}
              </CardTitle>
              <p className="text-sm text-muted-foreground">@{account.username || account.phone}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* 启用/禁用开关 */}
            <label className="relative inline-flex items-center cursor-pointer" title={account.is_active ? "点击禁用" : "点击启用"}>
              <input
                type="checkbox"
                className="sr-only peer"
                checked={account.is_active}
                onChange={onToggle}
              />
              <div className="w-11 h-6 bg-gray-600 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-cyber-blue"></div>
            </label>
            <Badge variant={account.is_authorized ? "success" : "warning"}>
              {account.is_authorized ? "已登录" : "未授权"}
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-4 py-3 border-t border-b border-cyber-blue/10">
          <div>
            <p className="text-xl font-bold">{account.total_messages}</p>
            <p className="text-xs text-muted-foreground">消息数</p>
          </div>
          <div>
            <p className="text-xl font-bold">{account.total_conversations}</p>
            <p className="text-xs text-muted-foreground">会话数</p>
          </div>
        </div>

        {/* Sync Status Indicator */}
        {showSyncStatus && (
          <div className={`flex items-center gap-2 text-sm py-2 px-3 rounded-lg ${
            account.sync_status === "success"
              ? "bg-green-500/20 text-green-400"
              : "bg-red-500/20 text-red-400"
          }`}>
            {account.sync_status === "success" ? (
              <>
                <CheckCircle size={16} />
                <span>同步成功</span>
              </>
            ) : (
              <>
                <XCircle size={16} />
                <span>同步失败</span>
              </>
            )}
          </div>
        )}

        <div className="space-y-2">
          <Button
            variant="outline"
            size="sm"
            className="w-full"
            onClick={onSyncDialogs}
            disabled={!account.is_authorized || isSyncing}
          >
            {isSyncing ? (
              <>
                <RefreshCw size={16} className="mr-2 animate-spin" />
                同步对话列表中...
              </>
            ) : (
              <>
                <MessageSquare size={16} className="mr-2" />
                同步对话列表
              </>
            )}
          </Button>

          <div className="flex gap-2">
            <Button
              variant="tech"
              size="sm"
              className="flex-1"
              onClick={onBatchSync}
              disabled={!account.is_authorized || isSyncing}
            >
              {isSyncing ? (
                <>
                  <RefreshCw size={14} className="mr-1 animate-spin" />
                  批量同步中...
                </>
              ) : (
                <>
                  <RefreshCw size={14} className="mr-1" />
                  批量同步历史
                </>
              )}
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={onRelogin}
              disabled={isSyncing}
              title="重新授权"
            >
              <RefreshCw size={16} className="text-cyber-blue" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={onDisconnect}
              disabled={isSyncing}
              title="断开连接"
            >
              <LogOut size={16} className="text-cyber-pink" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={onDelete}
              disabled={isSyncing}
              title="删除账号"
              className="text-red-500 hover:text-red-600 hover:bg-red-500/10"
            >
              <Trash2 size={16} />
            </Button>
          </div>
        </div>

        {!account.is_authorized && (
          <Button
            variant="tech"
            size="sm"
            className="w-full"
            onClick={onRelogin}
          >
            <LogIn size={16} className="mr-2" />
            重新登录
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

function LoginModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [phone, setPhone] = useState("");
  const [apiId, setApiId] = useState("");
  const [apiHash, setApiHash] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [step, setStep] = useState<"phone" | "code">("phone");
  const [loading, setLoading] = useState(false);

  const requestCode = async () => {
    setLoading(true);
    try {
      await api.accounts.requestLogin({
        phone,
        api_id: apiId ? parseInt(apiId) : undefined,
        api_hash: apiHash || undefined,
      });
      setStep("code");
    } catch (error: any) {
      alert(error.message || "请求验证码失败");
    } finally {
      setLoading(false);
    }
  };

  const submitCode = async () => {
    setLoading(true);
    try {
      await api.accounts.submitLogin({
        phone,
        code,
        api_id: apiId ? parseInt(apiId) : undefined,
        api_hash: apiHash || undefined,
        password: password || undefined,
      });
      onSuccess();
    } catch (error: any) {
      alert(error.message || "登录失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal isOpen={true} onClose={onClose} title="添加 Telegram 账号">
      <div className="space-y-4">
        {step === "phone" ? (
          <>
            <div>
              <label className="text-sm text-muted-foreground">API ID</label>
              <Input
                type="number"
                value={apiId}
                onChange={(e) => setApiId(e.target.value)}
                placeholder="12345678"
              />
              <p className="text-xs text-muted-foreground mt-1">留空则使用全局配置</p>
            </div>
            <div>
              <label className="text-sm text-muted-foreground">API Hash</label>
              <Input
                type="password"
                value={apiHash}
                onChange={(e) => setApiHash(e.target.value)}
                placeholder="输入 API Hash"
              />
              <p className="text-xs text-muted-foreground mt-1">留空则使用全局配置</p>
            </div>
            <div>
              <label className="text-sm text-muted-foreground">手机号</label>
              <Input
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+8613800138000"
              />
              <p className="text-xs text-muted-foreground mt-1">请输入国际格式手机号</p>
            </div>
            <div className="flex gap-3 pt-4">
              <Button
                variant="tech"
                className="flex-1"
                onClick={requestCode}
                disabled={!phone || loading}
              >
                {loading ? "发送中..." : "获取验证码"}
              </Button>
              <Button variant="ghost" className="flex-1" onClick={onClose}>
                取消
              </Button>
            </div>
          </>
        ) : (
          <>
            <div>
              <label className="text-sm text-muted-foreground">验证码</label>
              <Input
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="输入验证码"
                autoFocus
              />
            </div>
            <div>
              <label className="text-sm text-muted-foreground">两步验证密码 (如已启用)</label>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="输入两步验证密码"
              />
            </div>
            <div className="flex gap-3 pt-4">
              <Button
                variant="tech"
                className="flex-1"
                onClick={submitCode}
                disabled={!code || loading}
              >
                {loading ? "登录中..." : "登录"}
              </Button>
              <Button variant="ghost" className="flex-1" onClick={() => setStep("phone")}>
                返回
              </Button>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}

function ReloginModal({ account, onClose, onSuccess }: { account: Account; onClose: () => void; onSuccess: () => void }) {
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const submitCode = async () => {
    setLoading(true);
    try {
      await api.accounts.submitLogin({
        phone: account.phone,
        code,
        api_id: undefined,
        api_hash: undefined,
        password: password || undefined,
      });
      onSuccess();
    } catch (error: any) {
      alert(error.message || "登录失败");
    } finally {
      setLoading(false);
    }
  };

  const requestCode = async () => {
    setLoading(true);
    try {
      await api.accounts.requestLogin({
        phone: account.phone,
        api_id: undefined,
        api_hash: undefined,
      });
      alert("验证码已发送，请查收 Telegram 消息");
    } catch (error: any) {
      alert(error.message || "请求验证码失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal isOpen={true} onClose={onClose} title={`重新登录 - ${account.phone}`}>
      <div className="space-y-4">
        <div className="bg-cyber-blue/10 border border-cyber-blue/20 rounded-lg p-3">
          <p className="text-sm text-cyber-blue">
            未收到验证码？
            <button
              onClick={requestCode}
              className="ml-2 underline hover:text-cyber-blue/80"
              disabled={loading}
            >
              {loading ? "发送中..." : "重新发送验证码"}
            </button>
          </p>
        </div>

        <div>
          <label className="text-sm text-muted-foreground">验证码</label>
          <Input
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="输入 Telegram 验证码"
            autoFocus
          />
        </div>
        <div>
          <label className="text-sm text-muted-foreground">两步验证密码 (如已启用)</label>
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="输入两步验证密码"
          />
        </div>
        <div className="flex gap-3 pt-4">
          <Button
            variant="tech"
            className="flex-1"
            onClick={submitCode}
            disabled={!code || loading}
          >
            {loading ? "登录中..." : "登录"}
          </Button>
          <Button variant="ghost" className="flex-1" onClick={onClose}>
            取消
          </Button>
        </div>
      </div>
    </Modal>
  );
}

export default AccountsPage;
