import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { Input } from "@/components/ui/Input";
import {
  Bell,
  Mail,
  Plus,
  Edit,
  Trash2,
  Send,
  TestTube,
  CheckCircle,
  XCircle,
} from "lucide-react";

interface NotificationConfig {
  id: number;
  name: string;
  notification_type: string;
  is_active: boolean;
  total_sent: number;
  total_failed: number;
  last_sent_at?: string;
  config?: any;
  min_alert_level?: number | null;
  keyword_groups?: number[];
}

const typeIcons = {
  email: Mail,
  dingtalk: Bell,
  wecom: Bell,
  serverchan: Send,
  webhook: Send,
  telegram: Send,
};

const typeLabels = {
  email: "邮件",
  dingtalk: "钉钉",
  wecom: "企业微信",
  serverchan: "Server酱",
  webhook: "Webhook",
  telegram: "Telegram",
};

export function NotificationsPage() {
  const [configs, setConfigs] = useState<NotificationConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingConfig, setEditingConfig] = useState<NotificationConfig | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    console.log("NotificationsPage mounted");
    fetchConfigs();
  }, []);

  const fetchConfigs = async () => {
    setLoading(true);
    setError(null);
    try {
      console.log("Fetching notifications...");
      const data = await api.notifications.list();
      console.log("Notifications data:", data);
      setConfigs(data);
    } catch (error) {
      console.error("Failed to fetch notification configs:", error);
      setError("获取通知配置失败");
    } finally {
      setLoading(false);
    }
  };

  const handleTest = async (id: number) => {
    try {
      await api.notifications.test({ config_id: id, test_message: "这是一条测试消息" });
      alert("测试通知已发送");
    } catch (error: any) {
      console.error("Failed to test notification:", error);
      alert(error.response?.data?.detail || "测试失败");
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("确定要删除此通知配置吗？")) return;
    try {
      await api.notifications.delete(id);
      fetchConfigs();
    } catch (error: any) {
      console.error("Failed to delete notification:", error);
      alert(error.response?.data?.detail || "删除失败");
    }
  };

  const handleToggleActive = async (config: NotificationConfig) => {
    try {
      await api.notifications.update(config.id, {
        ...config,
        is_active: !config.is_active,
      });
      fetchConfigs();
    } catch (error: any) {
      console.error("Failed to toggle notification:", error);
      alert(error.response?.data?.detail || "更新失败");
    }
  };

  const handleEdit = (config: NotificationConfig) => {
    setEditingConfig(config);
    setShowModal(true);
  };

  console.log("NotificationsPage rendering, loading:", loading, "configs:", configs, "error:", error);

  return (
    <div className="space-y-6">
      {/* 错误显示 */}
      {error && (
        <Card className="bg-red-500/20 border border-red-500/50">
          <CardContent className="py-4 text-center text-red-400">
            {error}
          </CardContent>
        </Card>
      )}

      {/* 标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold neon-text">通知配置</h1>
          <p className="text-muted-foreground mt-1">配置告警通知推送渠道</p>
        </div>
        <Button variant="tech" onClick={() => {
          setEditingConfig(null);
          setShowModal(true);
        }}>
          <Plus size={18} className="mr-2" />
          新建通知配置
        </Button>
      </div>

      {/* 通知配置列表 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {loading ? (
          <div className="col-span-full flex justify-center py-12">
            <div className="animate-spin w-8 h-8 border-2 border-cyber-blue border-t-transparent rounded-full" />
          </div>
        ) : configs.length === 0 ? (
          <Card className="col-span-full">
            <CardContent className="py-12 text-center text-muted-foreground">
              <p className="mb-4">暂无通知配置</p>
              <p className="text-sm">点击上方按钮创建您的第一个通知配置</p>
            </CardContent>
          </Card>
        ) : (
          configs.map((config) => (
            <NotificationConfigCard
              key={config.id}
              config={config}
              onTest={() => handleTest(config.id)}
              onEdit={() => handleEdit(config)}
              onDelete={() => handleDelete(config.id)}
              onToggle={() => handleToggleActive(config)}
            />
          ))
        )}
      </div>

      {/* 创建/编辑弹窗 */}
      {showModal && (
        <NotificationConfigModal
          config={editingConfig}
          onClose={() => {
            setShowModal(false);
            setEditingConfig(null);
          }}
          onSubmit={async (data) => {
            try {
              if (editingConfig) {
                await api.notifications.update(editingConfig.id, data);
              } else {
                await api.notifications.create(data);
              }
              fetchConfigs();
              setShowModal(false);
              setEditingConfig(null);
            } catch (error: any) {
              console.error("Failed to save notification:", error);
              alert(error.response?.data?.detail || "保存失败");
            }
          }}
        />
      )}
    </div>
  );
}

interface NotificationConfigCardProps {
  config: NotificationConfig;
  onTest: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onToggle: () => void;
}

function NotificationConfigCard({ config, onTest, onEdit, onDelete, onToggle }: NotificationConfigCardProps) {
  const Icon = typeIcons[config.notification_type as keyof typeof typeIcons] || Bell;

  return (
    <Card className="card-hover">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-cyber-blue/20 flex items-center justify-center">
              <Icon className="text-cyber-blue" size={22} />
            </div>
            <div>
              <CardTitle className="text-base">{config.name}</CardTitle>
              <p className="text-xs text-muted-foreground mt-0.5">
                {typeLabels[config.notification_type as keyof typeof typeLabels] || config.notification_type}
              </p>
            </div>
          </div>
          <button
            onClick={onToggle}
            className={`px-2 py-1 rounded text-xs transition-colors ${
              config.is_active
                ? "bg-green-500/20 text-green-400 hover:bg-green-500/30"
                : "bg-gray-500/20 text-gray-400 hover:bg-gray-500/30"
            }`}
          >
            {config.is_active ? "启用" : "禁用"}
          </button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-4 py-3 border-t border-b border-cyber-blue/10">
          <div>
            <p className="text-xl font-bold text-cyber-green">{config.total_sent}</p>
            <p className="text-xs text-muted-foreground">发送成功</p>
          </div>
          <div>
            <p className="text-xl font-bold text-cyber-pink">{config.total_failed}</p>
            <p className="text-xs text-muted-foreground">发送失败</p>
          </div>
        </div>

        <div className="flex gap-2">
          <Button variant="tech" size="sm" className="flex-1" onClick={onTest}>
            <TestTube size={16} className="mr-1" />
            测试
          </Button>
          <Button variant="outline" size="icon" onClick={onEdit}>
            <Edit size={16} />
          </Button>
          <Button variant="ghost" size="icon" onClick={onDelete}>
            <Trash2 size={16} className="text-cyber-pink" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

interface NotificationConfigModalProps {
  config: NotificationConfig | null;
  onClose: () => void;
  onSubmit: (data: any) => void;
}

function NotificationConfigModal({ config, onClose, onSubmit }: NotificationConfigModalProps) {
  const isEdit = config !== null;
  const [type, setType] = useState(config?.notification_type || "email");
  const [name, setName] = useState(config?.name || "");
  const [loading, setLoading] = useState(false);

  // 过滤配置
  const [minAlertLevel, setMinAlertLevel] = useState(config?.min_alert_level || null);
  const [selectedKeywordGroups, setSelectedKeywordGroups] = useState<number[]>([]);
  const [keywordGroups, setKeywordGroups] = useState<Array<{id: number, name: string}>>([]);

  // 获取关键词组列表
  useEffect(() => {
    api.keywords.listGroups().then(setKeywordGroups).catch(console.error);
  }, []);

  // 初始化选中的关键词组
  useEffect(() => {
    if (config?.keyword_groups) {
      setSelectedKeywordGroups(config.keyword_groups);
    }
  }, [config]);

  // 根据类型存储配置
  const [emailConfig, setEmailConfig] = useState({
    smtp_server: "",
    smtp_port: "587",
    email: "",
    password: "",
    from_email: "",
  });
  const [dingtalkConfig, setDingtalkConfig] = useState({
    webhook_url: "",
    secret: "",
  });
  const [wecomConfig, setWecomConfig] = useState({
    webhook_url: "",
  });
  const [serverchanConfig, setServerchanConfig] = useState({
    sendkey: "",
  });
  const [webhookConfig, setWebhookConfig] = useState({
    url: "",
    method: "POST",
  });
  const [telegramConfig, setTelegramConfig] = useState({
    bot_token: "",
    chat_id: "",
  });

  // 初始化配置
  useEffect(() => {
    if (config?.config) {
      const cfg = config.config;
      switch (config.notification_type) {
        case "email":
          setEmailConfig(cfg || emailConfig);
          break;
        case "dingtalk":
          setDingtalkConfig(cfg || dingtalkConfig);
          break;
        case "wecom":
          setWecomConfig(cfg || wecomConfig);
          break;
        case "serverchan":
          setServerchanConfig(cfg || serverchanConfig);
          break;
        case "webhook":
          setWebhookConfig(cfg || webhookConfig);
          break;
        case "telegram":
          setTelegramConfig(cfg || telegramConfig);
          break;
      }
    }
  }, [config]);

  const handleSubmit = async () => {
    if (!name.trim()) {
      alert("请输入配置名称");
      return;
    }

    let finalConfig = {};
    switch (type) {
      case "email":
        if (!emailConfig.smtp_server || !emailConfig.email || !emailConfig.password) {
          alert("请填写完整的邮件配置");
          return;
        }
        finalConfig = emailConfig;
        break;
      case "dingtalk":
        if (!dingtalkConfig.webhook_url) {
          alert("请输入 Webhook URL");
          return;
        }
        finalConfig = dingtalkConfig;
        break;
      case "wecom":
        if (!wecomConfig.webhook_url) {
          alert("请输入 Webhook URL");
          return;
        }
        finalConfig = wecomConfig;
        break;
      case "serverchan":
        if (!serverchanConfig.sendkey) {
          alert("请输入 SendKey");
          return;
        }
        finalConfig = serverchanConfig;
        break;
      case "webhook":
        if (!webhookConfig.url) {
          alert("请输入 Webhook URL");
          return;
        }
        finalConfig = webhookConfig;
        break;
      case "telegram":
        if (!telegramConfig.bot_token || !telegramConfig.chat_id) {
          alert("请输入 Bot Token 和 Chat ID");
          return;
        }
        finalConfig = telegramConfig;
        break;
    }

    setLoading(true);
    try {
      await onSubmit({
        name,
        notification_type: type,
        config: finalConfig,
        is_active: true,
        min_alert_level: minAlertLevel || null,
        keyword_groups: selectedKeywordGroups.length > 0 ? selectedKeywordGroups : null,
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal isOpen={true} onClose={onClose} title={isEdit ? "编辑通知配置" : "创建通知配置"}>
      <div className="space-y-4 max-h-[60vh] overflow-y-auto">
        <div>
          <label className="text-sm text-muted-foreground">配置名称 *</label>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="如: 主告警通知"
          />
        </div>
        <div>
          <label className="text-sm text-muted-foreground">通知类型</label>
          <select
            value={type}
            onChange={(e) => setType(e.target.value)}
            className="input-tech w-full px-4 py-2 rounded-lg"
            disabled={isEdit}
          >
            <option value="email">邮件</option>
            <option value="dingtalk">钉钉</option>
            <option value="wecom">企业微信</option>
            <option value="serverchan">Server酱</option>
            <option value="webhook">Webhook</option>
            <option value="telegram">Telegram</option>
          </select>
        </div>

        {/* 邮件配置 */}
        {type === "email" && (
          <div className="space-y-3 p-4 bg-secondary/30 rounded-lg">
            <p className="text-sm font-medium mb-2">邮件配置</p>
            <Input
              placeholder="SMTP 服务器 (如: smtp.gmail.com)"
              value={emailConfig.smtp_server}
              onChange={(e) => setEmailConfig({ ...emailConfig, smtp_server: e.target.value })}
            />
            <Input
              type="number"
              placeholder="端口 (默认: 587)"
              value={emailConfig.smtp_port}
              onChange={(e) => setEmailConfig({ ...emailConfig, smtp_port: e.target.value })}
            />
            <Input
              placeholder="发件人邮箱"
              value={emailConfig.email}
              onChange={(e) => setEmailConfig({ ...emailConfig, email: e.target.value })}
            />
            <Input
              type="password"
              placeholder="邮箱密码或应用专用密码"
              value={emailConfig.password}
              onChange={(e) => setEmailConfig({ ...emailConfig, password: e.target.value })}
            />
            <Input
              placeholder="发件人名称"
              value={emailConfig.from_email}
              onChange={(e) => setEmailConfig({ ...emailConfig, from_email: e.target.value })}
            />
          </div>
        )}

        {/* 钉钉配置 */}
        {type === "dingtalk" && (
          <div className="space-y-3 p-4 bg-secondary/30 rounded-lg">
            <p className="text-sm font-medium mb-2">钉钉配置</p>
            <Input
              placeholder="Webhook URL"
              value={dingtalkConfig.webhook_url}
              onChange={(e) => setDingtalkConfig({ ...dingtalkConfig, webhook_url: e.target.value })}
            />
            <Input
              placeholder="加签密钥 (可选)"
              value={dingtalkConfig.secret}
              onChange={(e) => setDingtalkConfig({ ...dingtalkConfig, secret: e.target.value })}
            />
          </div>
        )}

        {/* 企业微信配置 */}
        {type === "wecom" && (
          <div className="space-y-3 p-4 bg-secondary/30 rounded-lg">
            <p className="text-sm font-medium mb-2">企业微信配置</p>
            <Input
              placeholder="Webhook URL"
              value={wecomConfig.webhook_url}
              onChange={(e) => setWecomConfig({ ...wecomConfig, webhook_url: e.target.value })}
            />
          </div>
        )}

        {/* Server酱配置 */}
        {type === "serverchan" && (
          <div className="space-y-3 p-4 bg-secondary/30 rounded-lg">
            <p className="text-sm font-medium mb-2">Server酱配置</p>
            <Input
              placeholder="SendKey"
              value={serverchanConfig.sendkey}
              onChange={(e) => setServerchanConfig({ ...serverchanConfig, sendkey: e.target.value })}
            />
          </div>
        )}

        {/* Webhook配置 */}
        {type === "webhook" && (
          <div className="space-y-3 p-4 bg-secondary/30 rounded-lg">
            <p className="text-sm font-medium mb-2">Webhook配置</p>
            <Input
              placeholder="Webhook URL"
              value={webhookConfig.url}
              onChange={(e) => setWebhookConfig({ ...webhookConfig, url: e.target.value })}
            />
            <select
              value={webhookConfig.method}
              onChange={(e) => setWebhookConfig({ ...webhookConfig, method: e.target.value })}
              className="input-tech w-full px-4 py-2 rounded-lg"
            >
              <option value="POST">POST</option>
              <option value="GET">GET</option>
            </select>
          </div>
        )}

        {/* Telegram配置 */}
        {type === "telegram" && (
          <div className="space-y-3 p-4 bg-secondary/30 rounded-lg">
            <p className="text-sm font-medium mb-2">Telegram配置</p>
            <Input
              placeholder="Bot Token (如: 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11)"
              value={telegramConfig.bot_token}
              onChange={(e) => setTelegramConfig({ ...telegramConfig, bot_token: e.target.value })}
            />
            <Input
              placeholder="Chat ID (如: -1001234567890 或 @channelname)"
              value={telegramConfig.chat_id}
              onChange={(e) => setTelegramConfig({ ...telegramConfig, chat_id: e.target.value })}
            />
          </div>
        )}

        {/* 过滤配置 */}
        <div className="space-y-3 p-4 bg-secondary/30 rounded-lg">
          <p className="text-sm font-medium mb-2">过滤配置 (可选)</p>

          <div>
            <label className="text-xs text-muted-foreground mb-1 block">最低告警级别</label>
            <select
              value={minAlertLevel ?? ""}
              onChange={(e) => setMinAlertLevel(e.target.value ? parseInt(e.target.value, 10) : null)}
              className="input-tech w-full px-4 py-2 rounded-lg"
            >
              <option value="">全部级别</option>
              <option value="1">低</option>
              <option value="2">中</option>
              <option value="3">高</option>
              <option value="4">严重</option>
            </select>
          </div>

          <div>
            <label className="text-xs text-muted-foreground mb-1 block">关键词组 (留空表示全部)</label>
            <div className="grid grid-cols-2 gap-2 max-h-32 overflow-y-auto">
              {keywordGroups.map((kg) => (
                <label key={kg.id} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={selectedKeywordGroups.includes(kg.id)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedKeywordGroups([...selectedKeywordGroups, kg.id]);
                      } else {
                        setSelectedKeywordGroups(selectedKeywordGroups.filter(id => id !== kg.id));
                      }
                    }}
                    className="rounded"
                  />
                  {kg.name}
                </label>
              ))}
            </div>
          </div>
        </div>

        <div className="flex gap-3 pt-4">
          <Button variant="tech" className="flex-1" onClick={handleSubmit} disabled={loading}>
            {loading ? "保存中..." : isEdit ? "更新" : "创建"}
          </Button>
          <Button variant="ghost" className="flex-1" onClick={onClose} disabled={loading}>
            取消
          </Button>
        </div>
      </div>
    </Modal>
  );
}

export default NotificationsPage;
