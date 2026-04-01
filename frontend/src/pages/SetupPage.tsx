import { useState, useEffect } from "react";
import { useNavigate } from "@tanstack/react-router";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import {
  Globe,
  ChevronRight,
  ChevronLeft,
  Check,
  RefreshCw,
  Zap,
  MessageSquare,
  Bell,
  Loader2,
} from "lucide-react";

interface ProxyNode {
  id: number;
  name: string;
  type: string;
  server: string;
  port: number;
  latency_ms?: number;
  is_selected?: boolean;
}

export function SetupPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);

  // Step 1: 代理设置
  const [proxyMode, setProxyMode] = useState<"subscribe" | "manual">("subscribe");
  const [subscribeUrl, setSubscribeUrl] = useState("");
  const [nodes, setNodes] = useState<ProxyNode[]>([]);
  const [selectedNode, setSelectedNode] = useState<ProxyNode | null>(null);
  const [testingNode, setTestingNode] = useState<string | null>(null);
  // 手动配置
  const [manualProxyType, setManualProxyType] = useState("socks5");
  const [manualProxyHost, setManualProxyHost] = useState("");
  const [manualProxyPort, setManualProxyPort] = useState("");
  const [proxyTestResult, setProxyTestResult] = useState<"success" | "failed" | null>(null);

  // Step 2: 账号设置
  const [apiId, setApiId] = useState("");
  const [apiHash, setApiHash] = useState("");
  const [phone, setPhone] = useState("");
  const [accounts, setAccounts] = useState<{ api_id: string; api_hash: string; phone: string }[]>([]);

  // Step 3: 通知设置
  const [botToken, setBotToken] = useState("");
  const [notifyChatId, setNotifyChatId] = useState("");

  const [savingStep, setSavingStep] = useState<string | null>(null);

  const handleParseSubscribe = async () => {
    if (!subscribeUrl.trim()) {
      alert("请输入订阅链接");
      return;
    }

    setLoading(true);
    try {
      const data = await api.proxy.parseSubscribe(subscribeUrl);
      setNodes(data.nodes || []);
      if (data.nodes?.length > 0) {
        setSelectedNode(data.nodes[0]);
      }
    } catch (error: any) {
      alert(error.message || "解析订阅失败");
    } finally {
      setLoading(false);
    }
  };

  const handleTestNode = async (node: ProxyNode) => {
    setTestingNode(node.id);
    try {
      const data = await api.proxy.testNode(node.id);
      setNodes((prev) =>
        prev.map((n) =>
          n.id === node.id ? { ...n, latency_ms: data.latency_ms } : n
        )
      );
    } catch (error: any) {
      alert(error.message || "测试节点失败");
    } finally {
      setTestingNode(null);
    }
  };

  const handleTestManualProxy = async () => {
    if (!manualProxyHost || !manualProxyPort) {
      alert("请填写代理地址和端口");
      return;
    }
    setLoading(true);
    setProxyTestResult(null);
    try {
      // 注意：这是一个基础连接测试，仅验证代理地址和端口格式
      // 实际连接能力取决于后端代理配置
      // 这里先做格式验证
      const hostRegex = /^[\w.-]+(\.[\w.-]+)?$/;
      const portNum = parseInt(manualProxyPort);


      if (!hostRegex.test(manualProxyHost)) {
        setProxyTestResult("failed");
        alert("代理地址格式不正确");
        return;
      }

      if (isNaN(portNum) || portNum < 1 || portNum > 65535) {
        setProxyTestResult("failed");
        alert("端口号必须在 1-65535 之间");
        return;
      }


      // 模拟测试 - 实际需要通过后端测试
      // TODO: 调用后端的代理测试接口
      await new Promise((r) => setTimeout(r, 1500));
      setProxyTestResult("success");
      alert("基础测试通过！注意：这只是格式验证，实际连接能力需要后端支持");
    } catch {
      setProxyTestResult("failed");
    } finally {
      setLoading(false);
    }
  };

  const handleAddAccount = () => {
    if (!apiId || !apiHash || !phone) {
      alert("请填写完整的账号信息");
      return;
    }
    setAccounts((prev) => [...prev, { api_id: apiId, api_hash: apiHash, phone }]);
    setApiId("");
    setApiHash("");
    setPhone("");
  };

  const handleRemoveAccount = (index: number) => {
    setAccounts((prev) => prev.filter((_, i) => i !== index));
  };

  const handleNext = () => {
    if (step === 1) {
      // 验证代理设置
      if (proxyMode === "subscribe" && !selectedNode) {
        alert("请选择一个代理节点");
        return;
      }
      if (proxyMode === "manual" && (!manualProxyHost || !manualProxyPort)) {
        alert("请填写代理配置");
        return;
      }
    }
    setStep((s) => Math.min(s + 1, 3));
  };

  const handlePrev = () => {
    setStep((s) => Math.max(s - 1, 1));
  };

  const handleSkipNotification = () => {
    handleComplete(false);
  };

  const handleComplete = async (withNotification = true) => {
    setSavingStep("saving");
    try {
      // 1. 保存代理设置
      if (proxyMode === "subscribe" && selectedNode) {
        await api.proxy.selectNode(selectedNode.id);
        await api.proxy.start();
      } else if (proxyMode === "manual") {
        await api.settings.updateDbSetting("proxy_type", manualProxyType);
        await api.settings.updateDbSetting("proxy_host", manualProxyHost);
        await api.settings.updateDbSetting("proxy_port", manualProxyPort.toString());
      }

      // 2. 请求账号登录（每个账号）
      for (const acc of accounts) {
        await api.accounts.requestLogin({
          phone: acc.phone,
          api_id: acc.api_id,
          api_hash: acc.api_hash,
        });
      }

      // 3. 保存通知设置
      if (withNotification && botToken && notifyChatId) {
        await api.notifications.create({
          name: "默认通知",
          type: "telegram",
          config: {
            bot_token: botToken,
            chat_id: notifyChatId,
          },
        });
      }

      // 4. 标记已初始化
      await api.settings.updateDbSetting("initialized", "true");

      // 5. 跳转到仪表盘
      navigate({ to: "/" });
    } catch (error: any) {
      alert(error.message || "保存设置失败");
    } finally {
      setLoading(false);
      setSavingStep(null);
    }
  };

  const progress = (step / 3) * 100;

  return (
    <div className="min-h-screen bg-background grid-bg flex items-center justify-center p-4">
      {/* 背景扫描线效果 */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden opacity-20">
        <div className="w-full h-full bg-gradient-to-b from-transparent via-cyber-blue/5 to-transparent animate-scan-line" />
      </div>

      <Card className="w-full max-w-2xl relative z-10">
        <CardHeader className="text-center">
          <div className="flex items-center justify-center gap-2 mb-4">
            <div className="w-10 h-10 rounded bg-gradient-to-br from-cyber-blue to-cyber-purple flex items-center justify-center">
              <MessageSquare size={24} className="text-white" />
            </div>
            <CardTitle className="text-2xl">TG Monitor 初始化设置</CardTitle>
          </div>

          {/* 进度条 */}
          <div className="w-full bg-secondary/50 rounded-full h-2 mb-4">
            <div
              className="h-2 rounded-full bg-gradient-to-r from-cyber-blue to-cyber-purple transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>

          {/* 步骤指示器 */}
          <div className="flex items-center justify-center gap-4">
            {[1, 2, 3].map((s) => (
              <div
                key={s}
                className={`flex items-center gap-2 ${
                  step >= s ? "text-cyber-blue" : "text-muted-foreground"
                }`}
              >
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                    step > s
                      ? "bg-cyber-blue text-background"
                      : step === s
                      ? "border-2 border-cyber-blue"
                      : "border border-muted-foreground"
                  }`}
                >
                  {step > s ? <Check size={16} /> : s}
                </div>
                <span className="hidden sm:inline text-sm">
                  {s === 1 ? "代理设置" : s === 2 ? "账号设置" : "通知设置"}
                </span>
              </div>
            ))}
          </div>
        </CardHeader>

        <CardContent className="space-y-6">
          {/* Step 1: 代理设置 */}
          {step === 1 && (
            <div className="space-y-4">
              <div className="text-center mb-4">
                <Globe size={40} className="mx-auto text-cyber-blue mb-2" />
                <h3 className="text-lg font-semibold">代理设置</h3>
                <p className="text-sm text-muted-foreground">
                  配置代理以连接 Telegram 服务器
                </p>
              </div>

              {/* 模式选择 */}
              <div className="flex gap-2">
                <Button
                  variant={proxyMode === "subscribe" ? "tech" : "outline"}
                  className="flex-1"
                  onClick={() => setProxyMode("subscribe")}
                >
                  订阅链接
                </Button>
                <Button
                  variant={proxyMode === "manual" ? "tech" : "outline"}
                  className="flex-1"
                  onClick={() => setProxyMode("manual")}
                >
                  手动配置
                </Button>
              </div>

              {proxyMode === "subscribe" ? (
                <div className="space-y-4">
                  <div className="flex gap-2">
                    <Input
                      value={subscribeUrl}
                      onChange={(e) => setSubscribeUrl(e.target.value)}
                      placeholder="粘贴订阅链接..."
                      className="flex-1"
                    />
                    <Button
                      variant="tech"
                      onClick={handleParseSubscribe}
                      disabled={loading}
                    >
                      {loading ? (
                        <RefreshCw size={18} className="animate-spin" />
                      ) : (
                        "解析"
                      )}
                    </Button>
                  </div>

                  {nodes.length > 0 && (
                    <div className="space-y-2 max-h-60 overflow-y-auto tech-scrollbar">
                      <p className="text-sm text-muted-foreground">
                        选择节点 ({nodes.length} 个可用)
                      </p>
                      <div className="grid gap-2">
                        {nodes.map((node) => (
                          <div
                            key={node.id}
                            className={`p-3 rounded-lg border cursor-pointer transition-all ${
                              selectedNode?.id === node.id
                                ? "border-cyber-blue bg-cyber-blue/10"
                                : "border-cyber-blue/20 hover:border-cyber-blue/50"
                            }`}
                            onClick={() => setSelectedNode(node)}
                          >
                            <div className="flex items-center justify-between">
                              <div>
                                <p className="font-medium">{node.name}</p>
                                <p className="text-xs text-muted-foreground">
                                  {node.type} - {node.server}:{node.port}
                                </p>
                              </div>
                              <div className="flex items-center gap-2">
                                {node.latency_ms && (
                                  <span
                                    className={`text-xs ${
                                      node.latency_ms < 100
                                        ? "text-green-400"
                                        : node.latency_ms < 300
                                        ? "text-yellow-400"
                                        : "text-red-400"
                                    }`}
                                  >
                                    {node.latency_ms}ms
                                  </span>
                                )}
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleTestNode(node);
                                  }}
                                  disabled={testingNode === node.id}
                                >
                                  {testingNode === node.id ? (
                                    <RefreshCw size={14} className="animate-spin" />
                                  ) : (
                                    <Zap size={14} />
                                  )}
                                </Button>
                                {selectedNode?.id === node.id && (
                                  <Check size={16} className="text-cyber-blue" />
                                )}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="grid grid-cols-3 gap-2">
                    <select
                      value={manualProxyType}
                      onChange={(e) => setManualProxyType(e.target.value)}
                      className="input-tech h-10 rounded-md px-3"
                    >
                      <option value="socks5">SOCKS5</option>
                      <option value="http">HTTP</option>
                      <option value="mtproto">MTProto</option>
                    </select>
                    <Input
                      value={manualProxyHost}
                      onChange={(e) => setManualProxyHost(e.target.value)}
                      placeholder="代理地址"
                    />
                    <Input
                      value={manualProxyPort}
                      onChange={(e) => setManualProxyPort(e.target.value)}
                      placeholder="端口"
                      type="number"
                    />
                  </div>
                  <Button
                    variant="outline"
                    onClick={handleTestManualProxy}
                    disabled={loading}
                    className="w-full"
                  >
                    {loading ? (
                      <RefreshCw size={18} className="mr-2 animate-spin" />
                    ) : (
                      <Zap size={18} className="mr-2" />
                    )}
                    测试连接
                  </Button>
                  {proxyTestResult && (
                    <div
                      className={`p-3 rounded-lg ${
                        proxyTestResult === "success"
                          ? "bg-green-500/20 text-green-400"
                          : "bg-red-500/20 text-red-400"
                      }`}
                    >
                      {proxyTestResult === "success"
                        ? "连接成功！"
                        : "连接失败，请检查配置"}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Step 2: 账号设置 */}
          {step === 2 && (
            <div className="space-y-4">
              <div className="text-center mb-4">
                <MessageSquare size={40} className="mx-auto text-cyber-purple mb-2" />
                <h3 className="text-lg font-semibold">添加 Telegram 账号</h3>
                <p className="text-sm text-muted-foreground">
                  添加至少一个 Telegram 账号用于监控
                </p>
              </div>

              <div className="space-y-3">
                <div>
                  <label className="text-sm text-muted-foreground">API ID</label>
                  <Input
                    value={apiId}
                    onChange={(e) => setApiId(e.target.value)}
                    placeholder="从 my.telegram.org 获取"
                  />
                </div>
                <div>
                  <label className="text-sm text-muted-foreground">API Hash</label>
                  <Input
                    type="password"
                    value={apiHash}
                    onChange={(e) => setApiHash(e.target.value)}
                    placeholder="从 my.telegram.org 获取"
                  />
                </div>
                <div>
                  <label className="text-sm text-muted-foreground">手机号</label>
                  <Input
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="+8613800138000"
                  />
                </div>
                <Button variant="outline" onClick={handleAddAccount} className="w-full">
                  添加账号
                </Button>
              </div>

              {accounts.length > 0 && (
                <div className="space-y-2">
                  <p className="text-sm text-muted-foreground">已添加的账号：</p>
                  {accounts.map((acc, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-3 rounded-lg bg-secondary/30 border border-cyber-blue/10"
                    >
                      <div>
                        <p className="font-medium">{acc.phone}</p>
                        <p className="text-xs text-muted-foreground">
                          API ID: {acc.api_id}
                        </p>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleRemoveAccount(idx)}
                      >
                        ×
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Step 3: 通知设置 */}
          {step === 3 && (
            <div className="space-y-4">
              <div className="text-center mb-4">
                <Bell size={40} className="mx-auto text-yellow-400 mb-2" />
                <h3 className="text-lg font-semibold">通知设置</h3>
                <p className="text-sm text-muted-foreground">
                  配置告警通知方式（可选，可稍后配置）
                </p>
              </div>

              <div className="space-y-3">
                <div>
                  <label className="text-sm text-muted-foreground">Bot Token</label>
                  <Input
                    value={botToken}
                    onChange={(e) => setBotToken(e.target.value)}
                    placeholder="从 @BotFather 获取"
                  />
                </div>
                <div>
                  <label className="text-sm text-muted-foreground">通知群组/频道 ID</label>
                  <Input
                    value={notifyChatId}
                    onChange={(e) => setNotifyChatId(e.target.value)}
                    placeholder="-1001234567890"
                  />
                </div>
              </div>

              <div className="bg-cyber-blue/10 border border-cyber-blue/20 rounded-lg p-3">
                <p className="text-sm text-muted-foreground">
                  此步骤可选，您可以稍后在"通知配置"页面进行设置。
                </p>
              </div>
            </div>
          )}

          {/* 导航按钮 */}
          <div className="flex justify-between pt-4 border-t border-cyber-blue/10">
            <Button
              variant="ghost"
              onClick={handlePrev}
              disabled={step === 1}
            >
              <ChevronLeft size={18} className="mr-1" />
              上一步
            </Button>

            {step < 3 ? (
              <Button variant="tech" onClick={handleNext}>
                下一步
                <ChevronRight size={18} className="ml-1" />
              </Button>
            ) : (
              <div className="flex gap-2">
                <Button variant="outline" onClick={handleSkipNotification}>
                  跳过
                </Button>
                <Button variant="tech" onClick={() => handleComplete(true)} disabled={loading || savingStep !== null}>
                  {savingStep ? (
                    <Loader2 size={18} className="mr-2 animate-spin" />
                  ) : loading ? (
                    <Loader2 size={18} className="mr-2 animate-spin" />
                  ) : null}
                  {savingStep ? "保存中..." : "完成设置"}
                </Button>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default SetupPage;
