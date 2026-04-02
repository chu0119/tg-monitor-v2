import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/Table";
import {
  Globe,
  Play,
  Square,
  RefreshCw,
  Zap,
  Server,
  Clock,
  Trash2,
  CheckCircle,
  XCircle,
  Link,
  Plus,
} from "lucide-react";

interface ProxyStatus {
  running: boolean;
  pid?: number;
  current_node?: string;
  proxy_port?: number;
  latency_ms?: number;
}

interface ProxyNode {
  id: number;
  name: string;
  type: string;
  server: string;
  port: number;
  latency_ms?: number;
  is_selected?: boolean;
}

interface SubscribeSource {
  url: string;
  nodes: ProxyNode[];
}

export function ProxyPage() {
  const [status, setStatus] = useState<ProxyStatus | null>(null);
  const [nodes, setNodes] = useState<ProxyNode[]>([]);
  const [subscribeSources, setSubscribeSources] = useState<SubscribeSource[]>([]);
  const [subscribeUrl, setSubscribeUrl] = useState("");
  const [importText, setImportText] = useState("");
  const [loading, setLoading] = useState(true);
  const [testingNodes, setTestingNodes] = useState<Set<string>>(new Set());
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const [abortController, setAbortController] = useState<AbortController | null>(null);

  const [savingStep, setSavingStep] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    const fetchStatus = async () => {
      if (controller.signal.aborted) return;
      try {
        const data = await api.proxy.getStatus();
        if (!controller.signal.aborted) {
          setStatus(data.status || data);
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          console.error("Failed to fetch proxy status:", error);
        }
      }
    };

    const fetchNodes = async () => {
      if (controller.signal.aborted) return;
      setLoading(true);
      try {
        const data = await api.proxy.getNodes();
        if (!controller.signal.aborted) {
          setNodes(data.nodes || []);
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          console.error("Failed to fetch nodes:", error);
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    };

    fetchStatus();
    fetchNodes();

    return () => {
      controller.abort();
    };
  }, []);

  const fetchStatus = async () => {
    try {
      const data = await api.proxy.getStatus();
      // API返回 {success, status: {...}}，前端需要的是内层的status对象
      setStatus(data.status || data);
    } catch (error) {
      console.error("Failed to fetch proxy status:", error);
    }
  };

  const fetchNodes = async () => {
    setLoading(true);
    try {
      const data = await api.proxy.getNodes();
      setNodes(data.nodes || []);
    } catch (error) {
      console.error("Failed to fetch nodes:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleParseSubscribe = async () => {
    if (!subscribeUrl.trim()) {
      alert("请输入订阅链接");
      return;
    }

    setActionLoading("parse");
    try {
      const data = await api.proxy.parseSubscribe(subscribeUrl);
      const newNodes = data.nodes || [];

      // 添加到订阅源列表
      setSubscribeSources((prev) => [
        ...prev,
        { url: subscribeUrl, nodes: newNodes },
      ]);

      // 合并节点到总列表（去重）
      setNodes((prev) => {
        const existingIds = new Set(prev.map((n) => n.id));
        const uniqueNewNodes = newNodes.filter(
          (n: ProxyNode) => !existingIds.has(n.id)
        );
        return [...prev, ...uniqueNewNodes];
      });

      setSubscribeUrl("");
      alert(`成功解析 ${newNodes.length} 个节点`);
    } catch (error: any) {
      alert(error.message || "解析订阅失败");
    } finally {
      setActionLoading(null);
    }
  };

  const handleRemoveSubscribe = (url: string) => {
    setSubscribeSources((prev) => prev.filter((s) => s.url !== url));
  };

  const handleImportNodes = async () => {
    if (!importText.trim()) {
      alert("请粘贴节点链接");
      return;
    }

    setActionLoading("import");
    try {
      const data = await api.proxy.importNodes(importText);
      const saved = data.saved_nodes || 0;
      setImportText("");
      await fetchNodes();
      alert(`成功导入 ${saved} 个节点`);
    } catch (error: any) {
      alert(error.message || "导入节点失败");
    } finally {
      setActionLoading(null);
    }
  };

  const handleSelectNode = async (id: string) => {
    setActionLoading(`select-${id}`);
    try {
      await api.proxy.selectNode(id);
      await fetchStatus();
      // 如果代理正在运行，自动重启以应用新节点
      if (status?.running) {
        setActionLoading("restart");
        await api.proxy.restart();
        await fetchStatus();
      }
      alert("节点已切换");
    } catch (error: any) {
      alert(error.message || "切换节点失败");
    } finally {
      setActionLoading(null);
    }
  };

  const handleTestNode = async (id: string) => {
    setTestingNodes((prev) => new Set(prev).add(id));
    try {
      const data = await api.proxy.testNode(id);
      setNodes((prev) =>
        prev.map((n) =>
          n.id === id ? { ...n, latency_ms: data.latency_ms } : n
        )
      );
    } catch (error: any) {
      alert(error.message || "测试节点失败");
    } finally {
      setTestingNodes((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  };

  const handleStart = async () => {
    if (!status?.current_node) {
      alert("请先选择一个节点");
      return;
    }
    setActionLoading("start");
    try {
      await api.proxy.start();
      await fetchStatus();
      alert("代理已启动");
    } catch (error: any) {
      alert(error.message || "启动代理失败");
    } finally {
      setActionLoading(null);
    }
  };

  const handleStop = async () => {
    setActionLoading("stop");
    try {
      await api.proxy.stop();
      await fetchStatus();
      alert("代理已停止");
    } catch (error: any) {
      alert(error.message || "停止代理失败");
    } finally {
      setActionLoading(null);
    }
  };

  const handleRestart = async () => {
    setActionLoading("restart");
    try {
      await api.proxy.stop();
      await new Promise((r) => setTimeout(r, 1000));
      await api.proxy.start();
      await fetchStatus();
      alert("代理已重启");
    } catch (error: any) {
      alert(error.message || "重启代理失败");
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* 标题 */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold neon-text">代理管理</h1>
          <p className="text-xs sm:text-sm text-muted-foreground mt-1">
            管理代理节点和订阅源
          </p>
        </div>
      </div>

      {/* 状态卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="card-hover">
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div
                className={`w-12 h-12 rounded-lg flex items-center justify-center ${
                  status?.running
                    ? "bg-green-500/20 text-green-400"
                    : "bg-red-500/20 text-red-400"
                }`}
              >
                {status?.running ? (
                  <CheckCircle size={24} />
                ) : (
                  <XCircle size={24} />
                )}
              </div>
              <div>
                <p className="text-sm text-muted-foreground">代理状态</p>
                <p className="text-lg font-bold">
                  {status?.running ? "运行中" : "已停止"}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="card-hover">
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-lg bg-cyber-blue/20 text-cyber-blue flex items-center justify-center">
                <Server size={24} />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">当前节点</p>
                <p className="text-lg font-bold truncate max-w-[150px]">
                  {status?.current_node || "未选择"}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="card-hover">
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-lg bg-cyber-purple/20 text-cyber-purple flex items-center justify-center">
                <Globe size={24} />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">代理端口</p>
                <p className="text-lg font-bold">
                  {status?.proxy_port || "-"}
                </p>
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
                <p className="text-sm text-muted-foreground">延迟</p>
                <p className="text-lg font-bold">
                  {status?.latency_ms ? `${status.latency_ms}ms` : "-"}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 操作按钮 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">代理控制</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            <Button
              variant="tech"
              onClick={handleStart}
              disabled={status?.running || actionLoading !== null}
            >
              {actionLoading === "start" ? (
                <RefreshCw size={18} className="mr-2 animate-spin" />
              ) : (
                <Play size={18} className="mr-2" />
              )}
              启动代理
            </Button>
            <Button
              variant="outline"
              onClick={handleStop}
              disabled={!status?.running || actionLoading !== null}
            >
              {actionLoading === "stop" ? (
                <RefreshCw size={18} className="mr-2 animate-spin" />
              ) : (
                <Square size={18} className="mr-2" />
              )}
              停止代理
            </Button>
            <Button
              variant="outline"
              onClick={handleRestart}
              disabled={!status?.running || actionLoading !== null}
            >
              {actionLoading === "restart" ? (
                <RefreshCw size={18} className="mr-2 animate-spin" />
              ) : (
                <RefreshCw size={18} className="mr-2" />
              )}
              重启代理
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 订阅管理 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">订阅管理</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-col sm:flex-row gap-3">
            <Input
              value={subscribeUrl}
              onChange={(e) => setSubscribeUrl(e.target.value)}
              placeholder="粘贴订阅链接..."
              className="flex-1"
            />
            <Button
              variant="tech"
              onClick={handleParseSubscribe}
              disabled={actionLoading === "parse"}
              className="w-full sm:w-auto"
            >
              {actionLoading === "parse" ? (
                <RefreshCw size={18} className="mr-2 animate-spin" />
              ) : (
                <Link size={18} className="mr-2" />
              )}
              解析订阅
            </Button>
          </div>

          {/* 订阅源列表 */}
          {subscribeSources.length > 0 && (
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">已添加的订阅源：</p>
              <div className="space-y-2">
                {subscribeSources.map((source, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between p-3 rounded-lg bg-secondary/30 border border-cyber-blue/10"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm truncate">{source.url}</p>
                      <p className="text-xs text-muted-foreground">
                        {source.nodes.length} 个节点
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleRemoveSubscribe(source.url)}
                    >
                      <Trash2 size={16} className="text-red-400" />
                    </Button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 手动导入节点 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">手动导入节点</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <textarea
            value={importText}
            onChange={(e) => setImportText(e.target.value)}
            placeholder={"每行粘贴一个节点链接，支持格式：\nss://...\nvmess://...\ntrojan://...\nvless://...\nhysteria2://..."}
            className="w-full h-28 rounded-lg border border-cyber-blue/20 bg-secondary/30 px-3 py-2 text-sm resize-none focus:outline-none focus:ring-1 focus:ring-cyber-blue/50 placeholder:text-muted-foreground"
          />
          <div className="flex gap-3">
            <Button
              variant="tech"
              onClick={handleImportNodes}
              disabled={actionLoading === "import"}
              className="flex-1 sm:flex-none"
            >
              {actionLoading === "import" ? (
                <RefreshCw size={18} className="mr-2 animate-spin" />
              ) : (
                <Plus size={18} className="mr-2" />
              )}
              导入节点
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 节点列表 */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">节点列表</CardTitle>
            <Button variant="outline" size="sm" onClick={fetchNodes}>
              <RefreshCw size={16} className="mr-2" />
              刷新
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center py-12">
              <div className="animate-spin w-8 h-8 border-2 border-cyber-blue border-t-transparent rounded-full" />
            </div>
          ) : nodes.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <p>暂无节点</p>
              <p className="text-sm mt-2">请添加订阅链接以获取节点</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>名称</TableHead>
                    <TableHead>类型</TableHead>
                    <TableHead>服务器</TableHead>
                    <TableHead>延迟</TableHead>
                    <TableHead>操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {nodes.map((node) => (
                    <TableRow key={node.id}>
                      <TableCell className="font-medium">
                        <div className="flex items-center gap-2">
                          {node.name}
                          {node.is_selected && (
                            <Badge variant="success" className="text-xs">
                              当前
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{node.type}</Badge>
                      </TableCell>
                      <TableCell>
                        {node.server}:{node.port}
                      </TableCell>
                      <TableCell>
                        {testingNodes.has(node.id) ? (
                          <span className="text-yellow-400">测试中...</span>
                        ) : node.latency_ms ? (
                          <span
                            className={
                              node.latency_ms < 100
                                ? "text-green-400"
                                : node.latency_ms < 300
                                ? "text-yellow-400"
                                : "text-red-400"
                            }
                          >
                            {node.latency_ms}ms
                          </span>
                        ) : (
                          <span className="text-muted-foreground">-</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleSelectNode(node.id)}
                            disabled={actionLoading?.startsWith("select")}
                          >
                            {actionLoading === `select-${node.id}` ? (
                              <RefreshCw size={14} className="animate-spin" />
                            ) : (
                              <CheckCircle size={14} />
                            )}
                            <span className="ml-1 hidden sm:inline">选择</span>
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleTestNode(node.id)}
                            disabled={testingNodes.has(node.id)}
                          >
                            {testingNodes.has(node.id) ? (
                              <RefreshCw size={14} className="animate-spin" />
                            ) : (
                              <Zap size={14} />
                            )}
                            <span className="ml-1 hidden sm:inline">测试</span>
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default ProxyPage;
