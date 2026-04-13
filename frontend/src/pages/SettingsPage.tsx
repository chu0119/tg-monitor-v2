import { useState, useEffect, useRef } from "react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import {
  Database,
  Bell,
  Save,
  CheckCircle,
  RotateCcw,
  HardDrive,
  Download,
  Upload,
  FileJson,
  Trash2,
  BarChart3,
  RefreshCw,
  Rocket,
  Loader2,
  GitBranch,
  Eye,
  EyeOff,
  Info,
  ExternalLink,
  ArrowDown,
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

interface BackupInfoItem {
  name: string;
  created_at?: string;
  size_mb: number;
  db_size: number;
  session_count: number;
}

interface SystemSettings {
  enable_realtime_monitoring: boolean;
  enable_browser_notifications: boolean;
  enable_sound_alerts: boolean;
  minimum_alert_level: string;
}

const DEFAULT_SETTINGS: SystemSettings = {
  enable_realtime_monitoring: true,
  enable_browser_notifications: true,
  enable_sound_alerts: true,
  minimum_alert_level: "low",
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
  const [cleanupDays, setCleanupDays] = useState(30);
  const [cleanupStats, setCleanupStats] = useState<any>(null);
  const [cleanupMessage, setCleanupMessage] = useState("");
  const [cleanupLoading, setCleanupLoading] = useState(false);

  // 数据迁移
  const [migrationStatus, setMigrationStatus] = useState<any>(null);
  const [exportLoading, setExportLoading] = useState(false);
  const [importLoading, setImportLoading] = useState(false);
  const [importResult, setImportResult] = useState<string>("");
  const fileInputRef = useRef<HTMLInputElement>(null);

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
    if (migrationStatus?.status !== "idle") {
      const t = setTimeout(fetchMigrationStatus, 2000);
      return () => clearTimeout(t);
    }
  }, [migrationStatus]);

  const handleExport = async () => {
    setExportLoading(true);
    try {
      const res = await fetch("/api/v1/migration/export", { method: "POST" });
      const data = await res.json();
      if (data.error) { setImportResult(`❌ ${data.message}`); return; }
      // 轮询等待完成
      const poll = setInterval(async () => {
        const st = await (await fetch("/api/v1/migration/status")).json();
        setMigrationStatus(st);
        if (st.status === "idle") {
          clearInterval(poll);
          setExportLoading(false);
          if (st.result?.file) {
            window.location.href = "/api/v1/migration/export/download";
          }
        }
      }, 2000);
    } catch { setExportLoading(false); setImportResult("❌ 导出请求失败"); }
  };

  const handleMigrationImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImportLoading(true);
    setImportResult("正在上传...");
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch("/api/v1/migration/import", { method: "POST", body: form });
      const data = await res.json();
      if (data.error) { setImportResult(`❌ ${data.message}`); setImportLoading(false); return; }
      setMigrationStatus({ status: "importing", progress: "导入中..." });
    } catch { setImportResult("❌ 上传失败"); setImportLoading(false); }
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

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

  const [dbStatus, setDbStatus] = useState<DatabaseStatus | null>(null);
  const [dbStats, setDbStats] = useState<DatabaseStats | null>(null);
  const [dbConfig, setDbConfig] = useState<DbConfigInfo | null>(null);
  const [showDbPassword, setShowDbPassword] = useState(false);

  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [backups, setBackups] = useState<BackupInfoItem[]>([]);
  const [backupLoading, setBackupLoading] = useState(false);
  const [backupName, setBackupName] = useState("");
  const [mergeResult, setMergeResult] = useState<any>(null);

  const [updateInfo, setUpdateInfo] = useState<{ current_version: string; current_commit: string; branch: string }>({ current_version: "-", current_commit: "-", branch: "-" });
  const [checkingUpdate, setCheckingUpdate] = useState(false);
  const [updateResult, setUpdateResult] = useState<any>(null);
  const [updating, setUpdating] = useState(false);
  const [updateProgress, setUpdateProgress] = useState<any>(null);
  const [updateDone, setUpdateDone] = useState<{ success: boolean; error?: string } | null>(null);
  const [progressTimer, setProgressTimer] = useState<any>(null);

  useEffect(() => {
    fetchSettings();
    fetchDatabaseInfo();
    fetchDbConfig();
    fetchBackups();
    fetchUpdateInfo();
    return () => { if (progressTimer) clearInterval(progressTimer); };
  }, []);

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
      }));
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

  const fetchUpdateInfo = async () => {
    try {
      const data = await api.system.getUpdateStatus();
      setUpdateInfo(data);
    } catch { /* ignore */ }
  };

  const handleCheckUpdate = async () => {
    setCheckingUpdate(true);
    setUpdateResult(null);
    setUpdateDone(null);
    try {
      const data = await api.system.checkUpdate();
      setUpdateResult(data);
    } catch (error: any) {
      setUpdateResult(null);
      alert("检查更新失败: " + (error.message || "未知错误"));
    } finally {
      setCheckingUpdate(false);
    }
  };

  const handlePerformUpdate = async () => {
    if (!confirm("确定要执行系统更新吗？更新期间服务将暂时不可用。")) return;
    setUpdating(true);
    setUpdateDone(null);
    setUpdateProgress({ progress: "开始更新...", log: [] });

    const timer = setInterval(async () => {
      try {
        const p = await api.system.getUpdateProgress();
        setUpdateProgress(p);
      } catch { /* ignore */ }
    }, 2000);
    setProgressTimer(timer);

    try {
      await api.system.performUpdate();
      setUpdateDone({ success: true });
    } catch (error: any) {
      setUpdateDone({ success: false, error: error.message || "未知错误" });
    } finally {
      clearInterval(timer);
      setProgressTimer(null);
      setUpdating(false);
      try {
        const p = await api.system.getUpdateProgress();
        setUpdateProgress(p);
      } catch { /* ignore */ }
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

  const handleDownloadBackup = async (name: string) => {
    try {
      const res = await fetch(`/api/v1/backups/download/${encodeURIComponent(name)}`);
      if (!res.ok) throw new Error("下载失败");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = name;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error: any) {
      alert(error.message || "下载失败");
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

  const handleUploadMergeBackup = async (file: File) => {
    if (!confirm(`上传备份文件 "${file.name}" 将与现有数据合并（不会覆盖），确定继续吗？`)) return;
    setBackupLoading(true);
    setMergeResult(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch("/api/v1/backups/upload-merge", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (data.success) {
        setMergeResult(data);
      } else {
        alert("合并失败: " + (data.detail || "未知错误"));
      }
    } catch (error: any) {
      alert("上传合并失败: " + (error.message || "未知错误"));
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
      setSettings({
        enable_realtime_monitoring: data.enable_realtime_monitoring ?? true,
        enable_browser_notifications: data.enable_browser_notifications ?? true,
        enable_sound_alerts: data.enable_sound_alerts ?? true,
        minimum_alert_level: data.minimum_alert_level ?? "low",
      });
      setHasChanges(true);
    } catch (error) {
      console.error("Failed to reset settings:", error);
      alert("重置设置失败");
    }
  };

  const handleExportAll = async () => {
    setExporting(true);
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
      alert("配置导出成功！");
    } catch (error) {
      console.error("Export failed:", error);
      alert("导出失败");
    } finally {
      setExporting(false);
    }
  };

  const handleImport = async (file: File) => {
    if (!confirm("导入配置将覆盖现有系统设置，确定要继续吗？")) return;
    setImporting(true);
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
          {/* 数据采集设置 - 简化 */}
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

          {/* 通知设置 - 保持原样 */}
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

          {/* 数据清理 - 保持原样 */}
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

          {/* 数据导入导出 - 简化 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <FileJson size={20} />
                配置导入导出
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Button
                variant="outline"
                size="sm"
                className="w-full justify-start"
                onClick={handleExportAll}
                disabled={exporting || importing}
              >
                <Download size={16} className="mr-2" />
                {exporting ? "导出中..." : "导出所有配置"}
              </Button>
              <p className="text-xs text-muted-foreground">
                将系统设置、关键词组、通知配置等导出为 JSON 文件
              </p>

              <div className="border-t border-cyber-blue/10 pt-4">
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
                  上传 JSON 配置文件，合并覆盖现有设置
                </p>
              </div>
            </CardContent>
          </Card>

          {/* 数据备份与恢复 - 增强 */}
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <HardDrive size={20} />
                数据备份与恢复
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <Input
                  placeholder="备份名称（可选）"
                  value={backupName}
                  onChange={(e) => setBackupName(e.target.value)}
                  className="flex-1"
                />
                <Button variant="tech" onClick={handleCreateBackup} disabled={backupLoading}>
                  创建备份
                </Button>
                <Button variant="outline" onClick={fetchBackups} disabled={backupLoading}>
                  <RefreshCw size={16} className="mr-1" />
                  刷新
                </Button>
                <label>
                  <input
                    type="file"
                    accept=".sql,.sql.gz,.bak"
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) {
                        handleUploadMergeBackup(file);
                        e.target.value = "";
                      }
                    }}
                    disabled={backupLoading}
                  />
                  <Button variant="outline" onClick={() => (document.querySelectorAll('input[type="file"]')[1] as HTMLInputElement)?.click()} disabled={backupLoading}>
                    <Upload size={16} className="mr-1" />
                    上传合并
                  </Button>
                </label>
              </div>

              {mergeResult && (
                <div className="bg-cyber-green/10 border border-cyber-green/30 rounded-lg p-3 text-sm">
                  <p className="font-semibold text-cyber-green mb-1">✓ 合并完成</p>
                  <p>新增: {mergeResult.stats?.inserted || 0} 条</p>
                  <p>更新: {mergeResult.stats?.updated || 0} 条</p>
                  <p>跳过: {mergeResult.stats?.skipped || 0} 条</p>
                  {mergeResult.message && <p className="text-xs text-muted-foreground mt-1">{mergeResult.message}</p>}
                </div>
              )}

              <div className="space-y-2 max-h-64 overflow-auto">
                {backupLoading && !backups.length ? (
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
                            时间: {b.created_at || "未知"} · 大小: {b.size_mb} MB
                          </p>
                        </div>
                        <div className="flex gap-2">
                          <Button size="sm" variant="outline" onClick={() => handleRestoreBackup(b.name)}>
                            恢复
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => handleDownloadBackup(b.name)}>
                            <Download size={14} />
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => handleDeleteBackup(b.name)}>
                            <Trash2 size={14} />
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>

          {/* 系统更新 - 修复 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Rocket size={20} />
                系统更新
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">当前版本</p>
                  <p className="text-lg font-bold">v{updateInfo.current_version}</p>
                  <p className="text-xs text-muted-foreground font-mono">{updateInfo.current_commit?.slice(0, 7)}</p>
                </div>
                <div className="flex items-center gap-1 text-xs text-muted-foreground">
                  <GitBranch size={12} />
                  {updateInfo.branch}
                </div>
              </div>

              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={handleCheckUpdate}
                  disabled={checkingUpdate || updating}
                  className="flex-1 min-h-[44px]"
                >
                  {checkingUpdate ? <Loader2 size={16} className="mr-2 animate-spin" /> : <RefreshCw size={16} className="mr-2" />}
                  {checkingUpdate ? "检查中..." : "检查更新"}
                </Button>
                {updateResult?.has_update && (
                  <Button
                    variant="tech"
                    onClick={handlePerformUpdate}
                    disabled={updating}
                    className="flex-1 min-h-[44px]"
                  >
                    {updating ? <Loader2 size={16} className="mr-2 animate-spin" /> : <Rocket size={16} className="mr-2" />}
                    {updating ? "更新中..." : "立即更新"}
                  </Button>
                )}
              </div>

              {updateResult && !updateResult.has_update && (
                <p className="text-sm text-cyber-green flex items-center gap-1">
                  <CheckCircle size={14} /> 已是最新版本
                </p>
              )}

              {updateResult?.has_update && updateResult.changelog?.length > 0 && (
                <div className="bg-cyber-blue/5 border border-cyber-blue/20 rounded-lg p-3">
                  <p className="text-sm font-semibold mb-2">更新日志（{updateResult.commits_behind} 个提交）</p>
                  <div className="space-y-1 max-h-40 overflow-auto text-xs text-muted-foreground">
                    {updateResult.changelog.map((c: string, i: number) => (
                      <p key={i} className="font-mono">{c}</p>
                    ))}
                  </div>
                </div>
              )}

              {updating && updateProgress && (
                <div className="bg-cyber-blue/5 border border-cyber-blue/20 rounded-lg p-3 space-y-1">
                  <p className="text-sm font-semibold">更新进度</p>
                  <p className="text-xs text-muted-foreground">{updateProgress.progress}</p>
                  <div className="max-h-32 overflow-auto text-xs text-muted-foreground space-y-0.5">
                    {updateProgress.log.map((l: string, i: number) => (
                      <p key={i} className="font-mono">• {l}</p>
                    ))}
                  </div>
                </div>
              )}

              {updateDone && (
                <p className={`text-sm ${updateDone.success ? "text-cyber-green" : "text-cyber-pink"}`}>
                  {updateDone.success ? "✓ 更新完成，服务正在重启..." : `✗ 更新失败: ${updateDone.error || "未知错误"}`}
                </p>
              )}
            </CardContent>
          </Card>

          {/* 数据库配置 - 新增 */}
          <Card>
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

              <div className="flex gap-2">
                <div className="flex-1 flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <span className={`inline-block w-2 h-2 rounded-full ${dbStatus?.connected ? "bg-cyber-green" : "bg-cyber-pink"}`} />
                    <span>{dbStatus?.connected ? "已连接" : "未连接"}</span>
                    {dbStatus?.connection_info?.version && (
                      <span className="text-muted-foreground">MySQL {dbStatus.connection_info.version}</span>
                    )}
                  </div>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => document.getElementById('migration-section')?.scrollIntoView({ behavior: 'smooth' })}
                >
                  <ArrowDown size={14} className="mr-1" />
                  数据迁移
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* 数据迁移 */}
          <Card id="migration-section" className="lg:col-span-2">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Download size={18} />
                数据迁移
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                一键导出系统所有数据（配置、历史记录、Telegram会话），可在新服务器上导入恢复。
              </p>
              <div className="flex flex-wrap gap-3">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleExport}
                  disabled={exportLoading || migrationStatus?.status === "exporting"}
                >
                  {exportLoading || migrationStatus?.status === "exporting" ? (
                    <><Loader2 size={14} className="mr-1 animate-spin" />导出中...</>
                  ) : (
                    <><Download size={14} className="mr-1" />导出数据</>
                  )}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={importLoading || migrationStatus?.status === "importing"}
                >
                  {importLoading || migrationStatus?.status === "importing" ? (
                    <><Loader2 size={14} className="mr-1 animate-spin" />导入中...</>
                  ) : (
                    <><Upload size={14} className="mr-1" />导入数据</>
                  )}
                </Button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".tar.gz"
                  className="hidden"
                  onChange={handleMigrationImport}
                />
              </div>
              {(migrationStatus?.status !== "idle" || importResult) && (
                <div className="text-sm space-y-1">
                  {migrationStatus?.progress && migrationStatus.status !== "idle" && (
                    <p className="text-muted-foreground">⏳ {migrationStatus.progress}</p>
                  )}
                  {importResult && (
                    <p className={importResult.startsWith("✅") ? "text-cyber-green" : importResult.startsWith("❌") ? "text-cyber-pink" : "text-muted-foreground"}>
                      {importResult}
                    </p>
                  )}
                </div>
              )}
              <div className="rounded-md bg-yellow-500/10 border border-yellow-500/20 p-3 text-xs text-yellow-200">
                ⚠️ 导入将合并数据，不会删除现有记录。导入前请确保目标服务器已部署完成。
              </div>
            </CardContent>
          </Card>

          {/* 版本信息 */}
          <div className="lg:col-span-2 text-center text-sm text-muted-foreground py-4 space-y-1">
            <p className="font-medium">
              听风追影–群组数据预警分析系统 v{updateInfo.current_version}
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
