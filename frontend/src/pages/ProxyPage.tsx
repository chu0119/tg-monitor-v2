import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { CheckCircle, Clock, Globe, RefreshCw, XCircle } from "lucide-react";

interface ProxyStatus {
  enabled: boolean;
  protocol: "http" | "https" | "socks5";
  host: string;
  port: number;
  username?: string;
  configured: boolean;
  applied: boolean;
}

export function ProxyPage() {
  const [status, setStatus] = useState<ProxyStatus | null>(null);
  const [protocol, setProtocol] = useState<"http" | "https" | "socks5">("socks5");
  const [host, setHost] = useState("");
  const [port, setPort] = useState("1080");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [latency, setLatency] = useState<{ ms: number | null; message: string } | null>(null);

  const fetchStatus = async () => {
    try {
      const data = await api.proxy.getStatus();
      const next = data.status || data;
      setStatus(next);
      setProtocol(next.protocol || "socks5");
      setHost(next.host || "");
      setPort(next.port ? String(next.port) : "1080");
      setUsername(next.username || "");
      setPassword("");
    } catch (error) {
      console.error("Failed to fetch proxy status:", error);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const handleSave = async () => {
    if (!host.trim()) {
      alert("请输入代理 IP/域名");
      return;
    }

    const portNum = Number(port);
    if (!Number.isInteger(portNum) || portNum < 1 || portNum > 65535) {
      alert("端口必须是 1-65535 的整数");
      return;
    }

    setLoading(true);
    try {
      await api.proxy.saveConfig({
        enabled: status?.enabled ?? true,
        protocol,
        host: host.trim(),
        port: portNum,
        username: username.trim() || undefined,
        password: password.trim() || undefined,
      });
      await fetchStatus();
      alert("代理配置已保存");
    } catch (error: any) {
      alert(error.message || "保存失败");
    } finally {
      setLoading(false);
    }
  };

  const handleTest = async () => {
    const portNum = Number(port);
    if (!host.trim() || !Number.isInteger(portNum)) {
      alert("请先填写正确的代理地址与端口");
      return;
    }

    setTesting(true);
    try {
      const data = await api.proxy.testConfig({ protocol, host: host.trim(), port: portNum });
      setLatency({ ms: data.latency_ms ?? null, message: data.message || "" });
      if (!data.success) {
        alert(data.message || "测试失败");
      }
    } catch (error: any) {
      alert(error.message || "测试失败");
    } finally {
      setTesting(false);
    }
  };

  const handleToggle = async (enabled: boolean) => {
    setLoading(true);
    try {
      if (enabled) {
        await api.proxy.enable();
      } else {
        await api.proxy.disable();
      }
      await fetchStatus();
    } catch (error: any) {
      alert(error.message || "操作失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold neon-text">代理管理</h1>
        <p className="text-sm text-muted-foreground mt-1">
          已移除内置 Clash/Mihomo，仅保留基础代理参数配置（协议/IP/端口）。
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="card-hover">
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${status?.enabled ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"}`}>
                {status?.enabled ? <CheckCircle size={24} /> : <XCircle size={24} />}
              </div>
              <div>
                <p className="text-sm text-muted-foreground">代理状态</p>
                <p className="text-lg font-bold">{status?.enabled ? "已启用" : "已禁用"}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="card-hover">
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-lg bg-cyber-blue/20 text-cyber-blue flex items-center justify-center">
                <Globe size={24} />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">当前代理</p>
                <p className="text-lg font-bold">{status?.host ? `${status.protocol}://${status.host}:${status.port}` : "未配置"}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="card-hover">
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-lg bg-yellow-500/20 text-yellow-400 flex items-center justify-center">
                <Clock size={24} />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">连通性</p>
                <p className="text-lg font-bold">{latency?.ms ? `${latency.ms}ms` : latency?.message || "-"}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">代理参数</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="text-sm text-muted-foreground">协议</label>
              <select
                className="mt-1 w-full rounded-lg border border-cyber-blue/20 bg-secondary/30 px-3 py-2 text-sm"
                value={protocol}
                onChange={(e) => setProtocol(e.target.value as any)}
              >
                <option value="socks5">SOCKS5</option>
                <option value="http">HTTP</option>
                <option value="https">HTTPS</option>
              </select>
            </div>
            <div>
              <label className="text-sm text-muted-foreground">端口</label>
              <Input value={port} onChange={(e) => setPort(e.target.value)} placeholder="1080" />
            </div>
            <div>
              <label className="text-sm text-muted-foreground">代理 IP/域名</label>
              <Input value={host} onChange={(e) => setHost(e.target.value)} placeholder="127.0.0.1" />
            </div>
            <div>
              <label className="text-sm text-muted-foreground">用户名（可选）</label>
              <Input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="username" />
            </div>
            <div>
              <label className="text-sm text-muted-foreground">密码（可选）</label>
              <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="password" />
            </div>
          </div>

          <div className="flex flex-wrap gap-3">
            <Button variant="tech" onClick={handleSave} disabled={loading}>
              {loading ? <RefreshCw size={16} className="mr-2 animate-spin" /> : null}
              保存配置
            </Button>
            <Button variant="outline" onClick={handleTest} disabled={testing}>
              {testing ? <RefreshCw size={16} className="mr-2 animate-spin" /> : null}
              测试连通性
            </Button>
            <Button variant="outline" onClick={() => handleToggle(true)} disabled={loading || status?.enabled}>
              启用代理
            </Button>
            <Button variant="outline" onClick={() => handleToggle(false)} disabled={loading || !status?.enabled}>
              禁用代理
            </Button>
            <Badge variant={status?.applied ? "success" : "warning"}>
              {status?.applied ? "运行时已应用" : "运行时未应用"}
            </Badge>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
