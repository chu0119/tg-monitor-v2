import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import {
  Database,
  Bell,
  Shield,
  Server,
  Save,
  CheckCircle,
  RotateCcw,
  HardDrive,
  TestTube,
  Info,
  Download,
  Upload,
  FileJson,
  Trash2,
  BarChart3,
} from "lucide-react";

interface DatabaseStatus {
  configured: boolean;
  connected: boolean;
  host?: string;
  port?: number;
  database?: string;
  error?: string;
  connection_info?: {
    connected: boolean;
    database?: string;
    version?: string;
    table_count?: number;
    url?: string;
  };
}

interface DatabaseStats {
  tables: Record<string, number>;
  total_messages: number;
  total_alerts: number;
  total_conversations: number;
  total_senders: number;
  total_keywords: number;
}

interface MySQLConfig {
  host: string;
  port: number;
  user: string;
  password: string;
  database: string;
}

interface BackupInfoItem {
  name: string;
  created_at?: string;
  size_mb: number;
  db_size: number;
  session_count: number;
}

interface SystemSettings {
  // 数据采集设置
  default_history_days: number;
  default_message_limit: number;
  batch_size: number;
  enable_realtime_monitoring: boolean;

  // 通知设置
  enable_browser_notifications: boolean;
  enable_sound_alerts: boolean;
  minimum_alert_level: string;

  // 代理设置
  http_proxy: string | null;
  socks5_proxy: string | null;

  // 安全设置
  data_retention_days: number;
  auto_cleanup_expired_data: boolean;
}

const DEFAULT_SETTINGS: SystemSettings = {
  default_history_days: 7,
  default_message_limit: 1000,
  batch_size: 100,
  enable_realtime_monitoring: true,
  enable_browser_notifications: true,
  enable_sound_alerts: true,
  minimum_alert_level: "low",
  http_proxy: null,
  socks5_proxy: null,
  data_retention_days: 90,
  auto_cleanup_expired_data: false,
};

export function SettingsPage() {
  const [settings, setSettings] = useState<SystemSettings>(DEFAULT_SETTINGS);
  const [cleanupDays, setCleanupDays] = useState(30);
  const [cleanupStats, setCleanupStats] = useState<any>(null);
  const [cleanupMessage, setCleanupMessage] = useState("");
  const [cleanupLoading, setCleanupLoading] = useState(false);

  const handleCleanupStats = async () => {
    setCleanupLoading(true);
    try {
      const res = await fetch("/api/v1/settings/cleanup/stats");
      const data = await res.json();
      setCleanupStats(data);
      setCleanupMessage("");
    } catch {
      setCleanupMessage("获取统计失败");
    } finally {
      setCleanupLoading(false);
    }
  };

  const handleCleanup = async (dryRun: boolean) => {
    if (!dryRun && !confirm(`确定要清理 ${cleanupDays} 天之前的数据吗？此操作不可撤销！`)) return;
    setCleanupLoading(true);
    try {
      const res = await fetch("/api/v1/settings/cleanup/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ retention_days: cleanupDays, dry_run: false }),
      });
      const data = await res.json();
      setCleanupMessage(data.message || "清理完成");
      // 刷新统计
      handleCleanupStats();
    } catch {
      setCleanupMessage("清理失败");
    } finally {
      setCleanupLoading(false);
    }
  };
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // 数据库相关状态
  const [dbStatus, setDbStatus] = useState<DatabaseStatus | null>(null);
  const [dbStats, setDbStats] = useState<DatabaseStats | null>(null);
  const [mysqlConfig, setMysqlConfig] = useState<MySQLConfig>({
    host: "localhost",
    port: 3306,
    user: "",
    password: "",
    database: "tg_monitor",
  });
  const [testingConnection, setTestingConnection] = useState(false);
  const [configuring, setConfiguring] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);

  // 导入导出相关状态
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [backups, setBackups] = useState<BackupInfoItem[]>([]);
  const [backupLoading, setBackupLoading] = useState(false);
  const [backupName, setBackupName] = useState("");

  useEffect(() => {
    fetchSettings();
    fetchDatabaseInfo();
    fetchBackups();
  }, []);

  const fetchSettings = async () => {
    setLoading(true);
    try {
      const data = await api.settings.get();
      setSettings(data);
    } catch (error) {
      console.error("Failed to fetch settings:", error);
    } finally {
      setLoading(false);
    }
  };

  const fetchDatabaseInfo = async () => {
    try {
      const [status, stats] = await Promise.all([
        api.database.getStatus(),
        api.database.getStats(),
      ]);
      setDbStatus(status);
      setDbStats(stats);
      // 更新配置表单为当前配置
      if (status.host) {
        setMysqlConfig({
          host: status.host,
          port: status.port || 3306,
          user: "",
          password: "",
          database: status.database || "tg_monitor",
        });
      }
    } catch (error) {
      console.error("Failed to fetch database info:", error);
    }
  };

  const fetchBackups = async () => {
    setBackupLoading(true);
    try {
      const list = await api.backups.list();
      setBackups(Array.isArray(list) ? list : []);
    } catch (error) {
      console.error("Failed to fetch backups:", error);
    } finally {
      setBackupLoading(false);
    }
  };

  const handleCreateBackup = async () => {
    setBackupLoading(true);
    try {
      await api.backups.create(backupName.trim() || undefined);
      setBackupName("");
      await fetchBackups();
      alert("备份创建成功");
    } catch (error: any) {
      alert(error.message || "创建备份失败");
    } finally {
      setBackupLoading(false);
    }
  };

  const handleRestoreBackup = async (name: string) => {
    if (!confirm(`恢复备份 ${name} 将覆盖当前数据库，确定继续吗？`)) return;
    setBackupLoading(true);
    try {
      const result = await api.backups.restore(name);
      alert(`恢复任务已提交：${result.status || "pending"}。建议稍后刷新并重启服务。`);
    } catch (error: any) {
      alert(error.message || "恢复备份失败");
    } finally {
      setBackupLoading(false);
    }
  };

  const handleDeleteBackup = async (name: string) => {
    if (!confirm(`确定删除备份 ${name}？`)) return;
    setBackupLoading(true);
    try {
      await api.backups.delete(name);
      await fetchBackups();
    } catch (error: any) {
      alert(error.message || "删除备份失败");
    } finally {
      setBackupLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setSaveSuccess(false);
    try {
      await api.settings.update(settings);
      setHasChanges(false);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (error) {
      console.error("Failed to save settings:", error);
      alert("保存设置失败，请重试");
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    if (!confirm("确定要重置所有设置为默认值吗？")) return;
    try {
      const data = await api.settings.reset();
      setSettings(data);
      setHasChanges(true);
    } catch (error) {
      console.error("Failed to reset settings:", error);
      alert("重置设置失败");
    }
  };

  // 导出所有配置
  const handleExportAll = async () => {
    setExporting(true);
    try {
      const data = await api.settings.exportAll();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `tg-monitor-backup-${new Date().toISOString().split("T")[0]}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      alert("导出成功！");
    } catch (error) {
      console.error("Export failed:", error);
      alert("导出失败");
    } finally {
      setExporting(false);
    }
  };

  // 导出关键词
  const handleExportKeywords = async () => {
    setExporting(true);
    try {
      const data = await api.settings.exportKeywords();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `keywords-backup-${new Date().toISOString().split("T")[0]}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      alert("关键词导出成功！");
    } catch (error) {
      console.error("Export keywords failed:", error);
      alert("导出失败");
    } finally {
      setExporting(false);
    }
  };

  // 导入配置
  const handleImport = async (file: File) => {
    if (!confirm("导入配置将覆盖现有设置，确定要继续吗？")) return;

    setImporting(true);
    try {
      const text = await file.text();
      const data = JSON.parse(text);

      if (data.keyword_groups && !data.data) {
        // 是完整备份格式
        const result = await api.settings.importAll(data);
        let message = "导入完成！\n\n";
        message += `系统设置: ${result.details.system_settings.success ? "✓" : "✗"}\n`;
        message += `关键词组: 导入 ${result.details.keyword_groups.imported} 个，跳过 ${result.details.keyword_groups.skipped} 个\n`;
        if (result.details.keyword_groups.errors.length > 0) {
          message += `错误: ${result.details.keyword_groups.errors.join(", ")}\n`;
        }
        message += `通知配置: 导入 ${result.details.notification_configs.imported} 个，跳过 ${result.details.notification_configs.skipped} 个`;
        alert(message);
      } else if (data.data) {
        // 是关键词格式
        const result = await api.settings.importKeywords(data);
        let message = `导入完成！\n\n`;
        message += `导入: ${result.imported} 个\n`;
        message += `跳过: ${result.skipped} 个`;
        if (result.errors.length > 0) {
          message += `\n错误: ${result.errors.join(", ")}`;
        }
        alert(message);
      } else {
        alert("无效的导入文件格式");
      }

      fetchSettings();
      fetchDatabaseInfo();
    } catch (error) {
      console.error("Import failed:", error);
      alert("导入失败：" + (error instanceof Error ? error.message : "未知错误"));
    } finally {
      setImporting(false);
    }
  };

  const updateSetting = <K extends keyof SystemSettings>(key: K, value: SystemSettings[K]) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
    setHasChanges(true);
  };

  // Toggle switch component
  const ToggleSwitch = ({
    enabled,
    onChange,
  }: {
    enabled: boolean;
    onChange: (value: boolean) => void;
  }) => (
    <button
      onClick={() => onChange(!enabled)}
      className={`w-12 h-6 rounded-full relative transition-colors ${
        enabled ? "bg-cyber-blue/40" : "bg-gray-500/20"
      }`}
    >
      <div
        className={`absolute top-1 w-4 h-4 bg-cyber-blue rounded-full transition-all ${
          enabled ? "right-1" : "left-1"
        }`}
      />
    </button>
  );

  return (
    <div className="space-y-6">
      {/* 标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold neon-text">系统设置</h1>
          <p className="text-muted-foreground mt-1">配置系统参数与偏好</p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" onClick={handleReset} disabled={loading || saving}>
            <RotateCcw size={18} className="mr-2" />
            重置默认
          </Button>
          <Button
            variant="tech"
            onClick={handleSave}
            disabled={loading || saving || !hasChanges}
            className="min-w-[120px]"
          >
            {saveSuccess ? (
              <>
                <CheckCircle size={18} className="mr-2" />
                已保存
              </>
            ) : saving ? (
              <>
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin mr-2" />
                保存中...
              </>
            ) : (
              <>
                <Save size={18} className="mr-2" />
                保存设置
              </>
            )}
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin w-8 h-8 border-2 border-cyber-blue border-t-transparent rounded-full" />
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* 数据采集设置 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Database size={20} />
                数据采集
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-sm text-muted-foreground">默认历史回溯天数</label>
                <Input
                  type="number"
                  value={settings.default_history_days}
                  onChange={(e) => {
                    const val = parseInt(e.target.value);
                    if (!isNaN(val) && val >= 1 && val <= 365) {
                      updateSetting("default_history_days", val);
                    }
                  }}
                  min={1}
                  max={365}
                />
                <p className="text-xs text-muted-foreground mt-1">
                  批量同步时默认回溯的天数
                </p>
              </div>
              <div>
                <label className="text-sm text-muted-foreground">默认历史消息限制</label>
                <Input
                  type="number"
                  value={settings.default_message_limit}
                  onChange={(e) => {
                    const val = parseInt(e.target.value);
                    if (!isNaN(val) && val >= 1 && val <= 100000) {
                      updateSetting("default_message_limit", val);
                    }
                  }}
                  min={1}
                  max={100000}
                />
                <p className="text-xs text-muted-foreground mt-1">
                  每个对话最多拉取的历史消息数
                </p>
              </div>
              <div>
                <label className="text-sm text-muted-foreground">批量处理大小</label>
                <Input
                  type="number"
                  value={settings.batch_size}
                  onChange={(e) => {
                    const val = parseInt(e.target.value);
                    if (!isNaN(val) && val >= 1 && val <= 1000) {
                      updateSetting("batch_size", val);
                    }
                  }}
                  min={1}
                  max={1000}
                />
                <p className="text-xs text-muted-foreground mt-1">
                  批量操作时每批处理的数量
                </p>
              </div>
              <div className="flex items-center justify-between py-2">
                <div>
                  <p>启用实时监控</p>
                  <p className="text-xs text-muted-foreground">自动监听新消息</p>
                </div>
                <ToggleSwitch
                  enabled={settings.enable_realtime_monitoring}
                  onChange={(value) => updateSetting("enable_realtime_monitoring", value)}
                />
              </div>
            </CardContent>
          </Card>

          {/* 通知设置 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Bell size={20} />
                通知设置
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between py-2">
                <div>
                  <p>浏览器通知</p>
                  <p className="text-xs text-muted-foreground">在浏览器中接收告警通知</p>
                </div>
                <ToggleSwitch
                  enabled={settings.enable_browser_notifications}
                  onChange={(value) => updateSetting("enable_browser_notifications", value)}
                />
              </div>
              <div className="flex items-center justify-between py-2">
                <div>
                  <p>声音提示</p>
                  <p className="text-xs text-muted-foreground">新告警时播放提示音</p>
                </div>
                <ToggleSwitch
                  enabled={settings.enable_sound_alerts}
                  onChange={(value) => updateSetting("enable_sound_alerts", value)}
                />
              </div>
              <div>
                <label className="text-sm text-muted-foreground">最低告警级别</label>
                <select
                  value={settings.minimum_alert_level}
                  onChange={(e) => updateSetting("minimum_alert_level", e.target.value)}
                  className="input-tech w-full px-4 py-2 rounded-lg"
                >
                  <option value="low">低</option>
                  <option value="medium">中</option>
                  <option value="high">高</option>
                  <option value="critical">严重</option>
                </select>
                <p className="text-xs text-muted-foreground mt-1">
                  只显示此级别及以上的告警
                </p>
              </div>
            </CardContent>
          </Card>

          {/* 代理设置 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Server size={20} />
                代理配置
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-sm text-muted-foreground">HTTP 代理</label>
                <Input
                  placeholder="http://127.0.0.1:7890"
                  value={settings.http_proxy || ""}
                  onChange={(e) => updateSetting("http_proxy", e.target.value || null)}
                />
              </div>
              <div>
                <label className="text-sm text-muted-foreground">SOCKS5 代理</label>
                <Input
                  placeholder="socks5://127.0.0.1:7891"
                  value={settings.socks5_proxy || ""}
                  onChange={(e) => updateSetting("socks5_proxy", e.target.value || null)}
                />
              </div>
              <p className="text-xs text-muted-foreground">
                代理设置将用于所有 Telegram 账号连接。修改后需要重新连接账号才能生效。
              </p>
            </CardContent>
          </Card>

          {/* 安全设置 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Shield size={20} />
                安全设置
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-sm text-muted-foreground">数据保留天数</label>
                <Input
                  type="number"
                  value={settings.data_retention_days}
                  onChange={(e) => {
                    const val = parseInt(e.target.value);
                    if (!isNaN(val) && val >= 1 && val <= 365) {
                      updateSetting("data_retention_days", val);
                    }
                  }}
                  min={1}
                  max={365}
                />
                <p className="text-xs text-muted-foreground mt-1">
                  超过此天数的数据将被自动清理
                </p>
              </div>
              <div className="flex items-center justify-between py-2">
                <div>
                  <p>自动清理过期数据</p>
                  <p className="text-xs text-muted-foreground">定期清理历史数据</p>
                </div>
                <ToggleSwitch
                  enabled={settings.auto_cleanup_expired_data}
                  onChange={(value) => updateSetting("auto_cleanup_expired_data", value)}
                />
              </div>
            </CardContent>
          </Card>

          {/* 数据清理 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Trash2 size={20} />
                数据清理
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">清理多少天之前的数据</label>
                <div className="flex items-center gap-3">
                  <input
                    type="number"
                    value={cleanupDays}
                    onChange={(e) => setCleanupDays(Math.max(1, parseInt(e.target.value) || 30))}
                    min={1}
                    max={365}
                    className="input-tech w-24 px-3 py-2 rounded-lg text-sm"
                  />
                  <span className="text-sm text-muted-foreground">天</span>
                </div>
              </div>
              {cleanupStats && (
                <div className="bg-cyber-blue/5 border border-cyber-blue/20 rounded-lg p-3 space-y-1 text-sm">
                  <p>📊 数据库大小: <strong>{cleanupStats.database_size_mb.toFixed(1)} MB</strong></p>
                  <p>🗑️ 将清理告警: <strong>{(cleanupStats.expired?.alerts || 0).toLocaleString()}</strong> 条</p>
                  <p>🗑️ 将清理消息: <strong>{(cleanupStats.expired?.messages || 0).toLocaleString()}</strong> 条</p>
                  <p className="text-xs text-muted-foreground mt-1">仅清理已处理/已忽略的告警，待处理告警保留 90 天</p>
                </div>
              )}
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={handleCleanupStats}
                  disabled={cleanupLoading}
                  className="flex-1 min-h-[44px]"
                >
                  <BarChart3 size={16} className="mr-1" />
                  统计预览
                </Button>
                <Button
                  variant="tech"
                  onClick={() => handleCleanup(false)}
                  disabled={cleanupLoading}
                  className="flex-1 min-h-[44px]"
                >
                  <Trash2 size={16} className="mr-1" />
                  立即清理
                </Button>
              </div>
              {cleanupMessage && (
                <p className={`text-sm ${cleanupMessage.includes('演练') || cleanupMessage.includes('完成') ? 'text-green-400' : 'text-red-400'}`}>
                  {cleanupMessage}
                </p>
              )}
            </CardContent>
          </Card>

          {/* 导入导出设置 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <FileJson size={20} />
                数据导入导出
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <p className="text-sm font-semibold mb-3">导出配置</p>
                <div className="space-y-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full justify-start"
                    onClick={handleExportAll}
                    disabled={exporting || importing}
                  >
                    <Download size={16} className="mr-2" />
                    {exporting ? "导出中..." : "导出全部配置"}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full justify-start"
                    onClick={handleExportKeywords}
                    disabled={exporting || importing}
                  >
                    <Download size={16} className="mr-2" />
                    {exporting ? "导出中..." : "仅导出关键词"}
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground mt-2">
                  导出配置可备份系统设置、关键词组和通知配置
                </p>
              </div>

              <div className="border-t border-cyber-blue/10 pt-4">
                <p className="text-sm font-semibold mb-3">导入配置</p>
                <label className="block">
                  <input
                    type="file"
                    accept=".json"
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) {
                        handleImport(file);
                        e.target.value = "";
                      }
                    }}
                    disabled={importing || exporting}
                  />
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full justify-start"
                    onClick={() => (document.querySelector('input[type="file"]') as HTMLInputElement)?.click()}
                    disabled={importing || exporting}
                  >
                    <Upload size={16} className="mr-2" />
                    {importing ? "导入中..." : "导入配置文件"}
                  </Button>
                </label>
                <p className="text-xs text-muted-foreground mt-2">
                  支持导入之前导出的配置文件（JSON 格式）
                </p>
              </div>

              <div className="p-3 rounded bg-cyber-blue/10 border border-cyber-blue/20 text-xs">
                <p className="text-cyber-blue font-semibold mb-1">说明：</p>
                <ul className="list-disc list-inside space-y-1 text-muted-foreground">
                  <li>导出全部配置包含：系统设置、关键词组、通知配置结构</li>
                  <li>导出关键词仅包含关键词组和关键词数据</li>
                  <li>导入时会跳过已存在的同名配置</li>
                  <li>通知配置不包含敏感信息，需重新配置</li>
                </ul>
              </div>
            </CardContent>
          </Card>

          {/* 数据库备份与恢复 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <HardDrive size={20} />
                数据库备份与恢复
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <Input
                  placeholder="备份名称（可选）"
                  value={backupName}
                  onChange={(e) => setBackupName(e.target.value)}
                />
                <Button variant="tech" onClick={handleCreateBackup} disabled={backupLoading}>
                  创建备份
                </Button>
                <Button variant="outline" onClick={fetchBackups} disabled={backupLoading}>
                  刷新
                </Button>
              </div>

              <div className="space-y-2 max-h-64 overflow-auto">
                {backupLoading ? (
                  <p className="text-sm text-muted-foreground">备份列表加载中...</p>
                ) : backups.length === 0 ? (
                  <p className="text-sm text-muted-foreground">暂无备份</p>
                ) : (
                  backups.map((b) => (
                    <div key={b.name} className="p-3 rounded-lg border border-cyber-blue/10 bg-secondary/20">
                      <div className="flex items-center justify-between gap-2">
                        <div>
                          <p className="font-semibold">{b.name}</p>
                          <p className="text-xs text-muted-foreground">
                            时间: {b.created_at || "未知"} · 大小: {b.size_mb} MB · 会话文件: {b.session_count}
                          </p>
                        </div>
                        <div className="flex gap-2">
                          <Button size="sm" variant="outline" onClick={() => handleRestoreBackup(b.name)}>
                            恢复
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => handleDeleteBackup(b.name)}>
                            删除
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>

          {/* 数据库配置 */}
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <HardDrive size={20} />
                数据库配置 (MySQL)
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* 当前数据库状态 */}
              <div className="p-4 rounded-lg bg-secondary/30">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <p className="text-sm text-muted-foreground">连接状态</p>
                    <div className="flex items-center gap-2">
                      <p className={`text-2xl font-bold ${dbStatus?.connected ? "text-cyber-green" : "text-cyber-pink"}`}>
                        {dbStatus?.connected ? "已连接" : "未连接"}
                      </p>
                      {dbStatus?.connection_info?.version && (
                        <span className="text-xs text-muted-foreground">MySQL {dbStatus.connection_info.version}</span>
                      )}
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={fetchDatabaseInfo}
                  >
                    <RotateCcw size={14} className="mr-1" />
                    刷新
                  </Button>
                </div>

                {dbStatus?.configured && (
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm mb-4">
                    <div>
                      <p className="text-muted-foreground">主机</p>
                      <p className="font-semibold">{dbStatus.host}:{dbStatus.port}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">数据库</p>
                      <p className="font-semibold">{dbStatus.database}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">表数量</p>
                      <p className="font-semibold">{dbStatus.connection_info?.table_count || 0}</p>
                    </div>
                  </div>
                )}

                {dbStats && (
                  <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm pt-4 border-t border-border">
                    <div>
                      <p className="text-muted-foreground">账号数</p>
                      <p className="font-semibold">{dbStats.tables?.telegram_accounts || 0}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">会话数</p>
                      <p className="font-semibold">{dbStats.total_conversations || 0}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">消息数</p>
                      <p className="font-semibold">{dbStats.total_messages || 0}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">发送者</p>
                      <p className="font-semibold">{dbStats.total_senders || 0}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">告警数</p>
                      <p className="font-semibold">{dbStats.total_alerts || 0}</p>
                    </div>
                  </div>
                )}

                {!dbStatus?.configured && (
                  <div className="text-center py-4">
                    <p className="text-cyber-pink">数据库未配置</p>
                    <p className="text-sm text-muted-foreground mt-1">请在下方配置 MySQL 连接信息</p>
                  </div>
                )}
              </div>

              {/* MySQL 配置表单 */}
              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  <Server size={18} />
                  <h3 className="font-semibold">MySQL 连接配置</h3>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm text-muted-foreground">主机地址</label>
                    <Input
                      placeholder="localhost"
                      value={mysqlConfig.host}
                      onChange={(e) => setMysqlConfig({ ...mysqlConfig, host: e.target.value })}
                    />
                  </div>
                  <div>
                    <label className="text-sm text-muted-foreground">端口</label>
                    <Input
                      type="number"
                      value={mysqlConfig.port}
                      onChange={(e) => setMysqlConfig({ ...mysqlConfig, port: parseInt(e.target.value) || 3306 })}
                    />
                  </div>
                  <div>
                    <label className="text-sm text-muted-foreground">用户名</label>
                    <Input
                      placeholder="tgmonitor"
                      value={mysqlConfig.user}
                      onChange={(e) => setMysqlConfig({ ...mysqlConfig, user: e.target.value })}
                    />
                  </div>
                  <div>
                    <label className="text-sm text-muted-foreground">数据库名</label>
                    <Input
                      placeholder="tg_monitor"
                      value={mysqlConfig.database}
                      onChange={(e) => setMysqlConfig({ ...mysqlConfig, database: e.target.value })}
                    />
                  </div>
                  <div className="col-span-2">
                    <label className="text-sm text-muted-foreground">密码</label>
                    <Input
                      type="password"
                      placeholder="MySQL 密码"
                      value={mysqlConfig.password}
                      onChange={(e) => setMysqlConfig({ ...mysqlConfig, password: e.target.value })}
                    />
                  </div>
                </div>

                {/* 操作按钮 */}
                <div className="flex items-center gap-3 pt-2 flex-wrap">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={testingConnection || !mysqlConfig.host || !mysqlConfig.user}
                    onClick={async () => {
                      setTestingConnection(true);
                      setTestResult(null);
                      try {
                        const result = await api.database.testConnection(mysqlConfig);
                        setTestResult(result.success ? "连接测试成功！" : result.message);
                      } catch (error: any) {
                        setTestResult("连接测试失败: " + error.message);
                      } finally {
                        setTestingConnection(false);
                      }
                    }}
                  >
                    <TestTube size={14} className="mr-1" />
                    {testingConnection ? "测试中..." : "测试连接"}
                  </Button>

                  <Button
                    variant="tech"
                    size="sm"
                    disabled={configuring || !mysqlConfig.host || !mysqlConfig.user || !mysqlConfig.password}
                    onClick={async () => {
                      setConfiguring(true);
                      setTestResult(null);
                      try {
                        const result = await api.database.configure({
                          ...mysqlConfig,
                          save_config: true,
                        });
                        if (result.success) {
                          setTestResult("配置已保存，请重启服务以应用新配置。");
                          await fetchDatabaseInfo();
                        } else {
                          setTestResult("配置失败: " + result.message);
                        }
                      } catch (error: any) {
                        setTestResult("配置失败: " + error.message);
                      } finally {
                        setConfiguring(false);
                      }
                    }}
                  >
                    <Save size={14} className="mr-1" />
                    {configuring ? "保存中..." : "保存配置"}
                  </Button>

                  <Button
                    variant="outline"
                    size="sm"
                    onClick={async () => {
                      if (!confirm("确定要初始化数据库吗？这将创建所有必要的表结构。")) return;
                      try {
                        const result = await api.database.init();
                        if (result.success) {
                          setTestResult("数据库初始化成功！");
                          await fetchDatabaseInfo();
                        } else {
                          setTestResult("初始化失败: " + result.message);
                        }
                      } catch (error: any) {
                        setTestResult("初始化失败: " + error.message);
                      }
                    }}
                  >
                    <Database size={14} className="mr-1" />
                    初始化数据库
                  </Button>

                  {testResult && (
                    <div className={`text-sm ${testResult.includes("成功") ? "text-cyber-green" : "text-cyber-pink"}`}>
                      <Info size={14} className="inline mr-1" />
                      {testResult}
                    </div>
                  )}
                </div>

                <div className="p-3 rounded bg-cyber-blue/10 border border-cyber-blue/20 text-sm">
                  <p className="text-cyber-blue font-semibold mb-1">使用说明：</p>
                  <ol className="list-decimal list-inside space-y-1 text-muted-foreground">
                    <li>填写 MySQL 连接信息（需要已创建数据库用户）</li>
                    <li>点击"测试连接"验证配置是否正确</li>
                    <li>点击"保存配置"将配置写入 .env 文件</li>
                    <li>点击"初始化数据库"创建表结构（首次使用）</li>
                    <li>保存配置后需重启服务才能生效</li>
                  </ol>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

export default SettingsPage;
