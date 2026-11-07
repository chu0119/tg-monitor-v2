import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ShieldAlert, Shield, AlertTriangle, Smile, Info, Frown } from "lucide-react";

interface SentimentAnalysisProps {
  conversationId: number;
  days?: number;
}

interface SentimentPayload {
  total_messages: number;
  risk_count: number;
  negative_count: number;
  positive_count: number;
  normal_count: number;
  average_score: number;
  risk_ratio: number;
  top_risk_keywords: Array<{ word: string; count: number }>;
  by_day: Array<{ date: string; risk: number; negative: number; positive: number; normal: number; total: number; risk_ratio: number }>;
  method: string;
  description: string;
}

export function SentimentAnalysis({ conversationId, days = 7 }: SentimentAnalysisProps) {
  const [sentiment, setSentiment] = useState<SentimentPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSentiment = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(
        `/api/v1/analysis/sentiment/conversation/${conversationId}?days=${days}`
      );
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      setSentiment(await response.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "请求失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSentiment();
  }, [conversationId, days]);

  if (loading) {
    return (
      <Card>
        <CardContent className="py-12">
          <div className="flex justify-center">
            <div className="animate-spin w-8 h-8 border-2 border-cyber-blue border-t-transparent rounded-full" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || !sentiment) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-muted-foreground">
          {error ? `加载失败：${error}` : "暂无分析数据"}
        </CardContent>
      </Card>
    );
  }

  if (sentiment.total_messages === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-muted-foreground">
          该会话在最近 {days} 天内没有文本消息
        </CardContent>
      </Card>
    );
  }

  const pct = (n: number) =>
    sentiment.total_messages > 0 ? Math.round((n / sentiment.total_messages) * 100) : 0;

  const riskPct = pct(sentiment.risk_count);
  const negPct = pct(sentiment.negative_count);
  const posPct = pct(sentiment.positive_count);
  const normalPct = pct(sentiment.normal_count);

  const level =
    sentiment.risk_ratio >= 0.3
      ? { label: "高风险会话", variant: "destructive" as const }
      : sentiment.risk_ratio >= 0.1
        ? { label: "中风险会话", variant: "default" as const }
        : { label: "低风险会话", variant: "success" as const };

  const maxDayTotal = Math.max(1, ...sentiment.by_day.map((d) => d.total));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <ShieldAlert size={20} />
          内容风险分析
          <Badge variant={level.variant} className="ml-2">
            {level.label}
          </Badge>
          <span className="ml-auto text-xs text-muted-foreground font-normal">
            风险命中 {(sentiment.risk_ratio * 100).toFixed(1)}% · 近 {days} 天 {sentiment.total_messages} 条
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* 构成横条 */}
        <div className="flex h-3 rounded-full overflow-hidden bg-secondary">
          <div className="bg-cyber-pink" style={{ width: `${riskPct}%` }} title={`风险 ${riskPct}%`} />
          <div className="bg-amber-400" style={{ width: `${negPct}%` }} title={`情感负面 ${negPct}%`} />
          <div className="bg-gray-400" style={{ width: `${normalPct}%` }} title={`正常 ${normalPct}%`} />
          <div className="bg-cyber-green" style={{ width: `${posPct}%` }} title={`正面 ${posPct}%`} />
        </div>

        {/* 构成明细 */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="text-center">
            <p className="text-2xl font-bold text-cyber-pink">{sentiment.risk_count}</p>
            <p className="text-xs text-muted-foreground flex items-center justify-center gap-1">
              <AlertTriangle size={12} /> 风险命中 {riskPct}%
            </p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-amber-400">{sentiment.negative_count}</p>
            <p className="text-xs text-muted-foreground flex items-center justify-center gap-1">
              <Frown size={12} /> 情感负面 {negPct}%
            </p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold">{sentiment.normal_count}</p>
            <p className="text-xs text-muted-foreground flex items-center justify-center gap-1">
              <Meh size={12} /> 正常 {normalPct}%
            </p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-cyber-green">{sentiment.positive_count}</p>
            <p className="text-xs text-muted-foreground flex items-center justify-center gap-1">
              <Smile size={12} /> 正面 {posPct}%
            </p>
          </div>
        </div>

        {/* 命中风险词 TOP —— 可解释性的核心 */}
        {sentiment.top_risk_keywords.length > 0 && (
          <div>
            <p className="text-sm text-muted-foreground mb-2">命中风险词 TOP（来自本系统关键词库的真实匹配）</p>
            <div className="flex flex-wrap gap-2">
              {sentiment.top_risk_keywords.map((k) => (
                <Badge key={k.word} variant="outline" className="text-cyber-pink border-cyber-pink/40">
                  {k.word} ×{k.count}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* 按天趋势 */}
        {sentiment.by_day.length > 1 && (
          <div>
            <p className="text-sm text-muted-foreground mb-2">按天消息量与风险占比</p>
            <div className="space-y-1.5">
              {sentiment.by_day.slice(-7).map((d) => (
                <div key={d.date} className="flex items-center gap-2 text-xs">
                  <span className="w-20 text-muted-foreground shrink-0">{d.date.slice(5)}</span>
                  <div className="flex-1 h-4 bg-secondary/50 rounded overflow-hidden flex">
                    <div
                      className="bg-cyber-pink/80 h-full"
                      style={{ width: `${(d.risk / maxDayTotal) * 100}%` }}
                      title={`风险 ${d.risk}`}
                    />
                    <div
                      className="bg-amber-400/70 h-full"
                      style={{ width: `${(d.negative / maxDayTotal) * 100}%` }}
                      title={`负面 ${d.negative}`}
                    />
                    <div
                      className="bg-gray-400/50 h-full"
                      style={{ width: `${((d.normal + d.positive) / maxDayTotal) * 100}%` }}
                      title={`正常+正面 ${d.normal + d.positive}`}
                    />
                  </div>
                  <span className="w-24 text-right text-muted-foreground shrink-0">
                    风险率 {((d.risk_ratio || 0) * 100).toFixed(0)}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 判定规则说明 —— 诚实透明 */}
        <div className="flex items-start gap-2 p-3 rounded-lg bg-secondary/30 border border-border/50">
          <Info size={14} className="mt-0.5 shrink-0 text-cyber-blue" />
          <p className="text-xs text-muted-foreground leading-relaxed">
            {sentiment.description} 分析器版本：{sentiment.method}。风险词命中直接来自本系统关键词库的匹配结果（与告警同源），
            情感判定基于词典与否定/程度词规则，不使用黑盒模型。
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
