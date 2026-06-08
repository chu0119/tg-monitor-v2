import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Cloud } from "lucide-react";

interface WordCloudProps {
  conversationId?: number;
  senderId?: number;
  days?: number;
  width?: number;
  height?: number;
}

export function WordCloud({ conversationId, senderId, days = 7, width = 800, height = 400 }: WordCloudProps) {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchWordCloud = async () => {
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams({
        days: days.toString(),
        width: width.toString(),
        height: height.toString(),
      });

      if (conversationId) params.append("conversation_id", conversationId.toString());
      if (senderId) params.append("sender_id", senderId.toString());

      const response = await fetch(`/api/v1/analysis/wordcloud/image?${params}`);
      const data = await response.json();

      if (data.image) {
        setImageUrl(data.image);
      } else {
        setError("无法生成词云，请确保后端已安装必要的依赖");
      }
    } catch (err) {
      console.error("获取词云失败:", err);
      setError("获取词云失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWordCloud();
  }, [conversationId, senderId, days]);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            <Cloud size={20} />
            词云分析
          </CardTitle>
          <Button variant="outline" size="sm" onClick={fetchWordCloud}>
            刷新
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex items-center justify-center" style={{ height: `${height}px` }}>
            <div className="animate-spin w-8 h-8 border-2 border-cyber-blue border-t-transparent rounded-full" />
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center text-muted-foreground" style={{ height: `${height}px` }}>
            <Cloud size={48} className="mb-4 opacity-50" />
            <p>{error}</p>
            <p className="text-sm mt-2">请安装: pip install wordcloud jieba matplotlib</p>
          </div>
        ) : imageUrl ? (
          <div className="flex justify-center">
            <img
              src={imageUrl}
              alt="Word Cloud"
              className="max-w-full rounded-lg"
              style={{ maxHeight: `${height}px` }}
            />
          </div>
        ) : (
          <div className="flex items-center justify-center text-muted-foreground" style={{ height: `${height}px` }}>
            暂无数据
          </div>
        )}
      </CardContent>
    </Card>
  );
}
