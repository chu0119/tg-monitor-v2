import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Heart, Smile, Meh, Frown } from "lucide-react";

interface SentimentAnalysisProps {
  conversationId: number;
  days?: number;
}

export function SentimentAnalysis({ conversationId, days = 7 }: SentimentAnalysisProps) {
  const [sentiment, setSentiment] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const fetchSentiment = async () => {
    setLoading(true);
    try {
      const response = await fetch(
        `/api/v1/analysis/sentiment/conversation/${conversationId}?days=${days}`
      );
      const data = await response.json();
      setSentiment(data);
    } catch (err) {
      console.error("获取情感分析失败:", err);
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

  if (!sentiment) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-muted-foreground">
          暂无情感分析数据
        </CardContent>
      </Card>
    );
  }

  const positivePercent = sentiment.total_messages > 0
    ? Math.round((sentiment.positive_count / sentiment.total_messages) * 100)
    : 0;
  const negativePercent = sentiment.total_messages > 0
    ? Math.round((sentiment.negative_count / sentiment.total_messages) * 100)
    : 0;
  const neutralPercent = sentiment.total_messages > 0
    ? Math.round((sentiment.neutral_count / sentiment.total_messages) * 100)
    : 0;

  const avgScore = sentiment.average_score || 0.5;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <Heart size={20} />
          情感分析
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* 总体情绪 */}
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">总体情绪倾向</span>
          <div className="flex items-center gap-2">
            {avgScore > 0.6 ? (
              <Badge variant="success" className="flex items-center gap-1">
                <Smile size={14} />
                积极
              </Badge>
            ) : avgScore < 0.4 ? (
              <Badge variant="destructive" className="flex items-center gap-1">
                <Frown size={14} />
                消极
              </Badge>
            ) : (
              <Badge variant="outline" className="flex items-center gap-1">
                <Meh size={14} />
                中性
              </Badge>
            )}
            <span className="text-lg font-bold">
              {(avgScore * 100).toFixed(0)}%
            </span>
          </div>
        </div>

        {/* 情感分布 */}
        <div className="space-y-3">
          <div>
            <div className="flex justify-between text-sm mb-1">
              <span className="text-cyber-green">积极</span>
              <span>{sentiment.positive_count} ({positivePercent}%)</span>
            </div>
            <div className="h-2 bg-secondary rounded-full overflow-hidden">
              <div
                className="h-full bg-cyber-green transition-all"
                style={{ width: `${positivePercent}%` }}
              />
            </div>
          </div>

          <div>
            <div className="flex justify-between text-sm mb-1">
              <span className="text-gray-400">中性</span>
              <span>{sentiment.neutral_count} ({neutralPercent}%)</span>
            </div>
            <div className="h-2 bg-secondary rounded-full overflow-hidden">
              <div
                className="h-full bg-gray-400 transition-all"
                style={{ width: `${neutralPercent}%` }}
              />
            </div>
          </div>

          <div>
            <div className="flex justify-between text-sm mb-1">
              <span className="text-cyber-pink">消极</span>
              <span>{sentiment.negative_count} ({negativePercent}%)</span>
            </div>
            <div className="h-2 bg-secondary rounded-full overflow-hidden">
              <div
                className="h-full bg-cyber-pink transition-all"
                style={{ width: `${negativePercent}%` }}
              />
            </div>
          </div>
        </div>

        {/* 统计 */}
        <div className="grid grid-cols-3 gap-4 pt-4 border-t border-cyber-blue/10">
          <div className="text-center">
            <p className="text-2xl font-bold text-cyber-green">{sentiment.positive_count}</p>
            <p className="text-xs text-muted-foreground">积极消息</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold">{sentiment.neutral_count}</p>
            <p className="text-xs text-muted-foreground">中性消息</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-cyber-pink">{sentiment.negative_count}</p>
            <p className="text-xs text-muted-foreground">消极消息</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
