import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { Check, ChevronLeft, ChevronRight, Globe, Loader2, MessageSquare, Bell } from "lucide-react";

export function SetupPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);

  // Step 1: 代理设置（仅基础参数）
  const [proxyEnabled, setProxyEnabled] = useState(true);
  const [proxyType, setProxyType] = useState<"http" | "https" | "socks5">("socks5");
  const [proxyHost, setProxyHost] = useState("");
  const [proxyPort, setProxyPort] = useState("1080");
  const [proxyTestResult, setProxyTestResult] = useState<"success" | "failed" | null>(null);

  // Step 2: 账号设置
  const [apiId, setApiId] = useState("");
  const [apiHash, setApiHash] = useState("");
  const [phone, setPhone] = useState("");
  const [accounts, setAccounts] = useState<{ api_id: string; api_hash: string; phone: string }[]>([]);

  // Step 3: 通知设置
  const [botToken, setBotToken] = useState("");
  const [notifyChatId, setNotifyChatId] = useState("");

  const handleTestProxy = async () => {
    if (!proxyHost.trim() || !proxyPort.trim()) {
      alert("请填写代理地址和端口");
      return;
    }

    const portNum = Number(proxyPort);
    if (!Number.isInteger(portNum) || portNum < 1 || portNum > 65535) {
      alert("端口号必须在 1-65535 之间");
      return;
    }

    setLoading(true);
    setProxyTestResult(null);
    try {
      const res = await api.proxy.testConfig({
        protocol: proxyType,
        host: proxyHost.trim(),
        port: portNum,
      });
      setProxyTestResult(res.success ? "success" : "failed");
      alert(res.message || (res.success ? "测试成功" : "测试失败"));
    } catch (error: any) {
      setProxyTestResult("failed");
      alert(error.message || "测试失败");
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
      if (!proxyHost || !proxyPort) {
        alert("请填写代理配置");
        return;
      }
    }
    setStep((s) => Math.min(s + 1, 3));
  };

  const handlePrev = () => setStep((s) => Math.max(s - 1, 1));

  const handleComplete = async (withNotification = true) => {
    setLoading(true);
    try {
      await api.proxy.saveConfig({
        enabled: proxyEnabled,
        protocol: proxyType,
        host: proxyHost.trim(),
        port: Number(proxyPort),
      });

      for (const acc of accounts) {
        await api.accounts.requestLogin({
          phone: acc.phone,
          api_id: Number(acc.api_id),
          api_hash: acc.api_hash,
        });
      }

      if (withNotification && botToken && notifyChatId) {
        await api.notifications.create({
          name: "默认通知",
          type: "telegram",
          config: { bot_token: botToken, chat_id: notifyChatId },
        });
      }

      await api.settings.updateDbSetting("initialized", "true");
      navigate({ to: "/" });
    } catch (error: any) {
      alert(error.message || "保存设置失败");
    } finally {
      setLoading(false);
    }
  };

  const progress = (step / 3) * 100;

  return (
    <div className="min-h-screen bg-background grid-bg flex items-center justify-center p-4">
      <Card className="w-full max-w-2xl relative z-10">
        <CardHeader className="text-center">
          <div className="flex items-center justify-center gap-2 mb-4">
            <div className="w-10 h-10 rounded bg-gradient-to-br from-cyber-blue to-cyber-purple flex items-center justify-center">
              <MessageSquare size={24} className="text-white" />
            </div>
            <CardTitle className="text-2xl">TG Monitor 初始化设置</CardTitle>
          </div>

          <div className="w-full bg-secondary/50 rounded-full h-2 mb-4">
            <div className="h-2 rounded-full bg-gradient-to-r from-cyber-blue to-cyber-purple transition-all duration-300" style={{ width: `${progress}%` }} />
          </div>

          <div className="flex items-center justify-center gap-4">
            {[1, 2, 3].map((s) => (
              <div key={s} className={`flex items-center gap-2 ${step >= s ? "text-cyber-blue" : "text-muted-foreground"}`}>
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${step > s ? "bg-cyber-blue text-background" : step === s ? "border-2 border-cyber-blue" : "border border-muted-foreground"}`}>
                  {step > s ? <Check size={16} /> : s}
                </div>
                <span className="hidden sm:inline text-sm">{s === 1 ? "代理设置" : s === 2 ? "账号设置" : "通知设置"}</span>
              </div>
            ))}
          </div>
        </CardHeader>

        <CardContent className="space-y-6">
          {step === 1 && (
            <div className="space-y-4">
              <div className="text-center mb-4">
                <Globe size={40} className="mx-auto text-cyber-blue mb-2" />
                <h3 className="text-lg font-semibold">代理设置</h3>
                <p className="text-sm text-muted-foreground">仅保留协议 / IP / 端口配置，不再使用内置 Clash 节点。</p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="text-sm text-muted-foreground">协议</label>
                  <select className="mt-1 w-full rounded-lg border border-cyber-blue/20 bg-secondary/30 px-3 py-2 text-sm" value={proxyType} onChange={(e) => setProxyType(e.target.value as any)}>
                    <option value="socks5">SOCKS5</option>
                    <option value="http">HTTP</option>
                    <option value="https">HTTPS</option>
                  </select>
                </div>
                <div>
                  <label className="text-sm text-muted-foreground">端口</label>
                  <Input value={proxyPort} onChange={(e) => setProxyPort(e.target.value)} placeholder="1080" />
                </div>
                <div className="md:col-span-2">
                  <label className="text-sm text-muted-foreground">代理地址</label>
                  <Input value={proxyHost} onChange={(e) => setProxyHost(e.target.value)} placeholder="127.0.0.1" />
                </div>
              </div>

              <div className="flex items-center gap-3">
                <Button variant={proxyEnabled ? "tech" : "outline"} onClick={() => setProxyEnabled(true)}>启用代理</Button>
                <Button variant={!proxyEnabled ? "tech" : "outline"} onClick={() => setProxyEnabled(false)}>禁用代理</Button>
                <Button variant="outline" onClick={handleTestProxy} disabled={loading}>
                  {loading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                  测试连通
                </Button>
                {proxyTestResult && <Badge variant={proxyTestResult === "success" ? "success" : "destructive"}>{proxyTestResult === "success" ? "测试通过" : "测试失败"}</Badge>}
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-4">
              <div className="text-center mb-4">
                <MessageSquare size={40} className="mx-auto text-cyber-purple mb-2" />
                <h3 className="text-lg font-semibold">账号设置</h3>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <Input placeholder="API ID" value={apiId} onChange={(e) => setApiId(e.target.value)} />
                <Input placeholder="API Hash" value={apiHash} onChange={(e) => setApiHash(e.target.value)} />
                <Input placeholder="手机号" value={phone} onChange={(e) => setPhone(e.target.value)} />
              </div>

              <Button variant="tech" onClick={handleAddAccount}>添加账号</Button>
              <div className="space-y-2">
                {accounts.map((acc, idx) => (
                  <div key={`${acc.phone}-${idx}`} className="flex items-center justify-between p-3 rounded-lg bg-secondary/30">
                    <span className="text-sm">{acc.phone}</span>
                    <Button variant="ghost" size="sm" onClick={() => handleRemoveAccount(idx)}>移除</Button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-4">
              <div className="text-center mb-4">
                <Bell size={40} className="mx-auto text-yellow-400 mb-2" />
                <h3 className="text-lg font-semibold">通知设置（可选）</h3>
              </div>
              <Input placeholder="Telegram Bot Token" value={botToken} onChange={(e) => setBotToken(e.target.value)} />
              <Input placeholder="通知 Chat ID" value={notifyChatId} onChange={(e) => setNotifyChatId(e.target.value)} />
            </div>
          )}

          <div className="flex justify-between pt-4">
            <Button variant="outline" onClick={handlePrev} disabled={step === 1 || loading}>
              <ChevronLeft className="w-4 h-4 mr-1" /> 上一步
            </Button>

            {step < 3 ? (
              <Button variant="tech" onClick={handleNext} disabled={loading}>
                下一步 <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            ) : (
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => handleComplete(false)} disabled={loading}>跳过通知并完成</Button>
                <Button variant="tech" onClick={() => handleComplete(true)} disabled={loading}>
                  {loading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                  完成初始化
                </Button>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
