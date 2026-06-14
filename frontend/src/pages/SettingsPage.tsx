import { useState, useEffect, useRef } from "react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import {
  Database,
  Bell,
  Save,
  CheckCircle,
  RotateCcw,
  Download,
  Upload,
  FileJson,
  Trash2,
  BarChart3,
  Loader2,
  Eye,
  EyeOff,
  Info,
  HardDrive,
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

interface SystemSettings {
  enable_realtime_monitoring: boolean;
  enable_browser_notifications: boolean;
  enable_sound_alerts: boolean;
  minimum_alert_level: string;
  enable_alert_notification_dedup?: boolean;
  alert_dedup_window_minutes?: number;
  notification_queue_workers?: number;
  notification_max_retries?: number;
  max_message_records?: number;
  max_alert_records?: number;
  max_database_size_gb?: number;
}

const DEFAULT_SETTINGS: SystemSettings = {
  enable_realtime_monitoring: true,
  enable_browser_notifications: true,
  enable_sound_alerts: true,
  minimum_alert_level: "low",
  enable_alert_notification_dedup: true,
  alert_dedup_window_minutes: 10,
  notification_queue_workers: 2,
  notification_max_retries: 3,
  max_message_records: 200_000_000,
  max_alert_records: 100_000_000,
  max_database_size_gb: 900,
};

interface DbConfigInfo {
  host: string;
  port: number;
  user: string;
  database: string;
  password: string;
}

export function SettingsPage() {
  const [settings, setSettings] = useState<SystemSettings>(DEFAULT_SETTINGS);
  const [maxMessages, setMaxMessages] = useState(200_000_000);
  const [maxAlerts, setMaxAlerts] = useState(100_000_000);
  const [cleanupStats, setCleanupStats] = useState<any>(null);
  const [cleanupMessage, setCleanupMessage] = useState("");
  const [cleanupLoading, setCleanupLoading] = useState(false);

  // 全量数据迁移
  const [migrationStatus, setMigrationStatus] = useState<any>(null);
  const [fullExportLoading, setFullExportLoading] = useState(false);
  const [fullImportLoading, setFullImportLoading] = useState(false);
  const [importResult, setImportResult] = useState<string>("");
  const fullFileInputRef = useRef<HTMLInputElement>(null);

  // 配置文件导入导出
  const [configExporting, setConfigExporting] = useState(false);
  const [configImporting, setConfigImporting] = useState(false);
  const configFileInputRef = useRef<HTMLInputElement>(null);

  // 通用
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const [dbStatus, setDbStatus] = useState<DatabaseStatus | null>(null);
  const [dbStats, setDbStats] = useState<DatabaseStats | null>(null);
  const [dbConfig, setDbConfig] = useState<DbConfigInfo | null>(null);
  const [showDbPassword, setShowDbPassword] = useState(false);

  const [updateInfo, setUpdateInfo] = useState<{ current_version: string; current_commit: string; branch: string }>({ current_version: "-", current_commit: "-", branch: "-" });

  useEffect(() => {
    fetchSettings();
    fetchDatabaseInfo();
    fetchDbConfig();
    fetchUpdateInfo();
  }, []);

  // 轮询迁移状态
  const fetchMigrationStatus = async () => {
    try {
      const res = await fetch("/api/v1/migration/status");
      const data = await res.json();
      setMigrationStatus(data);
      if (data.result && data.status === "idle") {
        if (data.result.error) {
          setImportResult(`❌ ${data.result.error}`);
        } else if (data.result.stats) {
          const s = data.result.stats;
          setImportResult(`✅ 导入完成 - 表: ${s.tables_imported || 0}, 会话: ${s.sessions_restored || 0}, 配置: ${s.env_merged ? "已合并" : "跳过"}`);
        }
      }
    } catch {}
  };

  useEffect(() => {
    if (migrationStatus?.status !== "idle" && migrationStatus?.status) {
      const t = setTimeout(fetchMigrationStatus, 2000);
      return () => clearTimeout(t);
    }
  }, [migrationStatus]);

  // --- 数据获取 ---

  const fetchSettings = async () => {
    setLoading(true);
    try {
      const data = await api.settings.get();
      setSettings((prev) => ({
        ...prev,
        enable_realtime_monitoring: data.enable_realtime_monitoring ?? prev.enable_realtime_monitoring,
        enable_browser_notifications: data.enable_browser_notifications ?? prev.enable_browser_notifications,
        enable_sound_alerts: data.enable_sound_alerts ?? prev.enable_sound_alerts,
        minimum_alert_level: data.minimum_alert_level ?? prev.minimum_alert_level,
        enable_alert_notification_dedup: data.enable_alert_notification_dedup ?? prev.enable_alert_notification_dedup,
        alert_dedup_window_minutes: data.alert_dedup_window_minutes ?? prev.alert_dedup_window_minutes,
        notification_queue_workers: data.notification_queue_workers ?? prev.notification_queue_workers,
        notification_max_retries: data.notification_max_retries ?? prev.notification_max_retries,
        max_message_records: data.max_message_records ?? prev.max_message_records,
        max_alert_records: data.max_alert_records ?? prev.max_alert_records,
        max_database_size_gb: data.max_database_size_gb ?? prev.max_database_size_gb,
      }));
      setMaxMessages(data.max_message_records ?? DEFAULT_SETTINGS.max_message_records ?? 200_000_000);
      setMaxAlerts(data.max_alert_records ?? DEFAULT_SETTINGS.max_alert_records ?? 100_000_000);
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
    } catch (error) {
      console.error("Failed to fetch database info:", error);
    }
  };

  const fetchDbConfig = async () => {
    try {
      const res = await fetch("/api/v1/system/db-config");
      const data = await res.json();
      if (data.success) setDbConfig(data);
    } catch { /* ignore */ }
  };

  const fetchUpdateInfo = async () => {
    try {
      const data = await api.system.getInfo();
      setUpdateInfo({ current_version: data.version || "1.1.0", current_commit: "-", branch: "-" });
    } catch { /* ignore */ }
  };

  // --- 数据清理 ---

  const handleCleanupStats = async () => {
    setCleanupLoading(true);
    try {
      const params = new URLSearchParams({
        max_messages: maxMessages.toString(),
        max_alerts: maxAlerts.toString(),
      });
      const res = await fetch(`/api/v1/settings/cleanup/stats?${params}`);
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
    if (!dryRun && !confirm(`确定按当前数量上限清理超限数据吗？此操作不可撤销！`)) return;
    setCleanupLoading(true);
    try {
      const res = await fetch("/api/v1/settings/cleanup/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ max_messages: maxMessages, max_alerts: maxAlerts, dry_run: false }),
      });
      const data = await res.json();
      setCleanupMessage(data.message || "清理完成");
      handleCleanupStats();
    } catch {
      setCleanupMessage("清理失败");
    } finally {
      setCleanupLoading(false);
    }
  };

  // --- 配置文件导出 ---

  const handleConfigExport = async () => {
    setConfigExporting(true);
    try {
      const data = await api.settings.exportAll();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `tg-monitor-config-${new Date().toISOString().split("T")[0]}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Config export failed:", error);
      alert("导出失败");
    } finally {
      setConfigExporting(false);
    }
  };

  // --- 配置文件导入 ---

  const handleConfigImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!confirm("导入配置将覆盖现有系统设置，确定要继续吗？")) return;
    setConfigImporting(true);
    try {
      const text = await file.text();
      const data = JSON.parse(text);
      const result = await api.settings.importAll(data);
      let message = "导入完成！\n\n";
      if (result.details) {
        message += `系统设置: ${result.details.system_settings?.success ? "✓" : "✗"}\n`;
        const kg = result.details.keyword_groups;
        if (kg) message += `关键词组: 导入 ${kg.imported} 个，跳过 ${kg.skipped} 个\n`;
        const nc = result.details.notification_configs;
        if (nc) message += `通知配置: 导入 ${nc.imported} 个，跳过 ${nc.skipped} 个`;
      } else {
        message += "导入成功";
      }
      alert(message);
      fetchSettings();
    } catch (error) {
      console.error("Config import failed:", error);
      alert("导入失败：" + (error instanceof Error ? error.message : "未知错误"));
    } finally {
      setConfigImporting(false);
      if (configFileInputRef.current) configFileInputRef.current.value = "";
    }
  };

  // --- 全量数据导出 ---

  const handleFullExport = async () => {
    setFullExportLoading(true);
    setImportResult("");
    try {
      const res = await fetch("/api/v1/migration/export", { method: "POST" });
      const data = await res.json();
      if (data.error) { setImportResult(`❌ ${data.message}`); setFullExportLoading(false); return; }
      const poll = setInterval(async () => {
        const st = await (await fetch("/api/v1/migration/status")).json();
        setMigrationStatus(st);
        if (st.status === "idle") {
          clearInterval(poll);
          setFullExportLoading(false);
          if (st.result?.file) {
            window.location.href = "/api/v1/migration/export/download";
          }
        }
      }, 2000);
    } catch {
      setFullExportLoading(false);
      setImportResult("❌ 导出请求失败");
    }
  };

  // --- 全量数据导入 ---

  const handleFullImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setFullImportLoading(true);
    setImportResult("正在上传...");
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch("/api/v1/migration/import", { method: "POST", body: form });
      const data = await res.json();
      if (data.error) { setImportResult(`❌ ${data.message}`); setFullImportLoading(false); return; }
      setMigrationStatus({ status: "importing", progress: "导入中..." });
    } catch {
      setImportResult("❌ 上传失败");
      setFullImportLoading(false);
    }
    if (fullFileInputRef.current) fullFileInputRef.current.value = "";
  };

  // --- 设置保存/重置 ---

  const handleSave = async () => {
    setSaving(true);
    setSaveSuccess(false);
    try {
      await api.settings.update(settings);
      setMaxMessages(settings.max_message_records ?? maxMessages);
      setMaxAlerts(settings.max_alert_records ?? maxAlerts);
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
      setSettings({
        enable_realtime_monitoring: data.enable_realtime_monitoring ?? true,
        enable_browser_notifications: data.enable_browser_notifications ?? true,
        enable_sound_alerts: data.enable_sound_alerts ?? true,
        minimum_alert_level: data.minimum_alert_level ?? "low",
        enable_alert_notification_dedup: data.enable_alert_notification_dedup ?? true,
        alert_dedup_window_minutes: data.alert_dedup_window_minutes ?? 10,
        notification_queue_workers: data.notification_queue_workers ?? 2,
        notification_max_retries: data.notification_max_retries ?? 3,
        max_message_records: data.max_message_records ?? 200_000_000,
        max_alert_records: data.max_alert_records ?? 100_000_000,
        max_database_size_gb: data.max_database_size_gb ?? 900,
      });
      setHasChanges(true);
    } catch (error) {
      console.error("Failed to reset settings:", error);
      alert("重置设置失败");
    }
  };

  const updateSetting = <K extends keyof SystemSettings>(key: K, value: SystemSettings[K]) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
    setHasChanges(true);
  };

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

  const isMigrationBusy = migrationStatus?.status === "exporting" || migrationStatus?.status === "importing";

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
          {/* 数据采集 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Database size={20} />
                数据采集
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between py-2">
                <div>
                  <p>启用数据采集</p>
                  <p className="text-xs text-muted-foreground">开启后将自动监听和采集 Telegram 消息</p>
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
              <div className="flex items-center justify-between py-2">
                <div>
                  <p>同类告警通知降噪</p>
                  <p className="text-xs text-muted-foreground">同一会话、发送人、关键词在窗口内只推送一次通知</p>
                </div>
                <ToggleSwitch
                  enabled={settings.enable_alert_notification_dedup ?? true}
                  onChange={(value) => updateSetting("enable_alert_notification_dedup", value)}
                />
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-xs text-muted-foreground">降噪窗口(分钟)</label>
                  <input
                    type="number"
                    value={settings.alert_dedup_window_minutes ?? 10}
                    onChange={(e) => updateSetting("alert_dedup_window_minutes", Math.max(0, parseInt(e.target.value) || 0))}
                    min={0}
                    max={1440}
                    className="input-tech w-full px-3 py-2 rounded-lg text-sm"
                  />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">通知并发</label>
                  <input
                    type="number"
                    value={settings.notification_queue_workers ?? 2}
                    onChange={(e) => updateSetting("notification_queue_workers", Math.max(1, parseInt(e.target.value) || 1))}
                    min={1}
                    max={10}
                    className="input-tech w-full px-3 py-2 rounded-lg text-sm"
                  />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">失败重试</label>
                  <input
                    type="number"
                    value={settings.notification_max_retries ?? 3}
                    onChange={(e) => updateSetting("notification_max_retries", Math.max(0, parseInt(e.target.value) || 0))}
                    min={0}
                    max={10}
                    className="input-tech w-full px-3 py-2 rounded-lg text-sm"
                  />
                </div>
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
                <label className="text-sm font-medium">实时消息最大保留条数</label>
                <div className="flex items-center gap-3">
                  <input
                    type="number"
                    value={maxMessages}
                    onChange={(e) => {
                      const value = Math.max(1000, parseInt(e.target.value) || 200000000);
                      setMaxMessages(value);
                      updateSetting("max_message_records", value);
                    }}
                    min={1000}
                    max={1500000000}
                    step={10000}
                    className="input-tech w-40 px-3 py-2 rounded-lg text-sm"
                  />
                  <span className="text-sm text-muted-foreground">条</span>
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">告警最大保留条数</label>
                <div className="flex items-center gap-3">
                  <input
                    type="number"
                    value={maxAlerts}
                    onChange={(e) => {
                      const value = Math.max(1000, parseInt(e.target.value) || 100000000);
                      setMaxAlerts(value);
                      updateSetting("max_alert_records", value);
                    }}
                    min={1000}
                    max={1000000000}
                    step={10000}
                    className="input-tech w-40 px-3 py-2 rounded-lg text-sm"
                  />
                  <span className="text-sm text-muted-foreground">条</span>
                </div>
              </div>
              {cleanupStats && (
                <div className="bg-cyber-blue/5 border border-cyber-blue/20 rounded-lg p-3 space-y-1 text-sm">
                  <p>📊 数据库大小: <strong>{(cleanupStats.database_size_gb ?? cleanupStats.database_size_mb / 1024).toFixed(3)} GB</strong></p>
                  <p>📦 消息上限: <strong>{(cleanupStats.limits?.max_messages || maxMessages).toLocaleString()}</strong> 条，当前 <strong>{(cleanupStats.total?.messages || 0).toLocaleString()}</strong> 条</p>
                  <p>🚨 告警上限: <strong>{(cleanupStats.limits?.max_alerts || maxAlerts).toLocaleString()}</strong> 条，当前 <strong>{(cleanupStats.total?.alerts || 0).toLocaleString()}</strong> 条</p>
                  <p>🗑️ 将清理告警: <strong>{(cleanupStats.expired?.alerts || 0).toLocaleString()}</strong> 条</p>
                  <p>🗑️ 将清理消息: <strong>{(cleanupStats.expired?.messages || 0).toLocaleString()}</strong> 条</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    当前策略按数量上限清理最旧数据，容量上限 {(cleanupStats.limits?.max_database_size_gb || 900).toLocaleString()} GB，按当前平均行大小估算上限约 {(cleanupStats.estimated_limit_size_gb || 0).toLocaleString()} GB。
                  </p>
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

          {/* 数据迁移（统一） */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <HardDrive size={20} />
                数据迁移
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* 配置文件 */}
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <FileJson size={16} className="text-cyber-blue" />
                  <p className="text-sm font-medium">配置文件</p>
                </div>
                <p className="text-xs text-muted-foreground mb-2">
                  系统设置、关键词组、通知配置（JSON 格式，轻量快速）
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleConfigExport}
                    disabled={configExporting || configImporting}
                    className="flex-1 min-h-[40px]"
                  >
                    {configExporting ? (
                      <><Loader2 size={14} className="mr-1 animate-spin" />导出中...</>
                    ) : (
                      <><Download size={14} className="mr-1" />导出配置</>
                    )}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => configFileInputRef.current?.click()}
                    disabled={configExporting || configImporting}
                    className="flex-1 min-h-[40px]"
                  >
                    {configImporting ? (
                      <><Loader2 size={14} className="mr-1 animate-spin" />导入中...</>
                    ) : (
                      <><Upload size={14} className="mr-1" />导入配置</>
                    )}
                  </Button>
                  <input
                    ref={configFileInputRef}
                    type="file"
                    accept=".json"
                    className="hidden"
                    onChange={handleConfigImport}
                  />
                </div>
              </div>

              <div className="border-t border-cyber-blue/10" />

              {/* 全量数据 */}
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <Database size={16} className="text-cyber-purple" />
                  <p className="text-sm font-medium">全量数据</p>
                </div>
                <p className="text-xs text-muted-foreground mb-2">
                  数据库、Telegram 会话、系统配置（.tar.gz 格式，完整备份）
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleFullExport}
                    disabled={fullExportLoading || isMigrationBusy}
                    className="flex-1 min-h-[40px]"
                  >
                    {fullExportLoading || migrationStatus?.status === "exporting" ? (
                      <><Loader2 size={14} className="mr-1 animate-spin" />导出中...</>
                    ) : (
                      <><Download size={14} className="mr-1" />导出全量</>
                    )}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => fullFileInputRef.current?.click()}
                    disabled={fullImportLoading || isMigrationBusy}
                    className="flex-1 min-h-[40px]"
                  >
                    {fullImportLoading || migrationStatus?.status === "importing" ? (
                      <><Loader2 size={14} className="mr-1 animate-spin" />导入中...</>
                    ) : (
                      <><Upload size={14} className="mr-1" />导入全量</>
                    )}
                  </Button>
                  <input
                    ref={fullFileInputRef}
                    type="file"
                    accept=".tar.gz"
                    className="hidden"
                    onChange={handleFullImport}
                  />
                </div>
              </div>

              {/* 进度/状态 */}
              {(isMigrationBusy || importResult) && (
                <div className="text-sm space-y-1">
                  {migrationStatus?.progress && isMigrationBusy && (
                    <p className="text-muted-foreground">⏳ {migrationStatus.progress}</p>
                  )}
                  {importResult && (
                    <p className={importResult.startsWith("✅") ? "text-cyber-green" : importResult.startsWith("❌") ? "text-cyber-pink" : "text-muted-foreground"}>
                      {importResult}
                    </p>
                  )}
                </div>
              )}

              <div className="rounded-md bg-cyber-blue/5 border border-cyber-blue/20 p-3 text-xs text-muted-foreground">
                <p className="flex items-center gap-1 text-cyber-blue font-semibold mb-1">
                  <Info size={14} />
                  说明
                </p>
                <p>配置文件仅包含系统设置，适合快速迁移配置；全量数据包含所有历史记录和 Telegram 会话，适合完整迁移。导入操作均为合并模式，不会删除现有数据。</p>
              </div>
            </CardContent>
          </Card>

          {/* 数据库配置 */}
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Database size={20} />
                数据库配置
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {dbConfig ? (
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <p className="text-muted-foreground">主机</p>
                      <p className="font-semibold font-mono">{dbConfig.host}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">端口</p>
                      <p className="font-semibold font-mono">{dbConfig.port}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">用户名</p>
                      <p className="font-semibold font-mono">{dbConfig.user}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">数据库</p>
                      <p className="font-semibold font-mono">{dbConfig.database}</p>
                    </div>
                  </div>
                  <div className="text-sm">
                    <p className="text-muted-foreground">密码</p>
                    <div className="flex items-center gap-2">
                      <p className="font-semibold font-mono">
                        {showDbPassword ? dbConfig.password : "••••••••"}
                      </p>
                      <button
                        onClick={() => setShowDbPassword(!showDbPassword)}
                        className="text-muted-foreground hover:text-foreground transition-colors"
                      >
                        {showDbPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">加载中...</p>
              )}

              <div className="p-3 rounded bg-cyber-blue/10 border border-cyber-blue/20 text-xs text-muted-foreground">
                <p className="flex items-center gap-1 text-cyber-blue font-semibold mb-1">
                  <Info size={14} />
                  说明
                </p>
                <p>数据库配置在 .env 文件中修改，修改后重启服务生效。</p>
              </div>

              <div className="flex items-center gap-2 text-sm">
                <span className={`inline-block w-2 h-2 rounded-full ${dbStatus?.connected ? "bg-cyber-green" : "bg-cyber-pink"}`} />
                <span>{dbStatus?.connected ? "已连接" : "未连接"}</span>
                {dbStatus?.connection_info?.version && (
                  <span className="text-muted-foreground">MySQL {dbStatus.connection_info.version}</span>
                )}
              </div>
            </CardContent>
          </Card>

          {/* 版本信息 */}
          <div className="lg:col-span-2 text-center text-sm text-muted-foreground py-4 space-y-1">
            <p className="font-medium">
              听风追影–群组数据预警分析系统 V{updateInfo.current_version}
            </p>
            <p>
              Python (FastAPI) · TypeScript (React) · TailwindCSS · MySQL · Telethon
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

export default SettingsPage;
