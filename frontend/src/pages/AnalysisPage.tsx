import { useEffect, useState } from "react";
import { SentimentAnalysis } from "@/components/ui/SentimentAnalysis";
import { ReportViewer } from "@/components/ui/ReportViewer";
import { api } from "@/lib/api";

interface ConvOption {
  id: number;
  title: string;
}

export function AnalysisPage() {
  const [activeTab, setActiveTab] = useState<"sentiment" | "report">("sentiment");
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [conversations, setConversations] = useState<ConvOption[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (activeTab !== "sentiment" || conversations.length > 0) return;
    setLoading(true);
    api.conversations
      .list({ page_size: 200 })
      .then((res: any) => {
        const items = Array.isArray(res) ? res : res.items || [];
        setConversations(
          items
            .filter((c: any) => c && c.id != null && c.title)
            .map((c: any) => ({ id: c.id, title: c.title }))
        );
      })
      .catch(() => setConversations([]))
      .finally(() => setLoading(false));
  }, [activeTab, conversations.length]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">数据分析</h1>
        <p className="text-muted-foreground mt-1">情感分析、词云和报告</p>
      </div>

      <div className="flex gap-2">
        <button
          onClick={() => setActiveTab("sentiment")}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            activeTab === "sentiment"
              ? "bg-primary text-primary-foreground"
              : "bg-muted hover:bg-muted/80"
          }`}
        >
          情感分析
        </button>
        <button
          onClick={() => setActiveTab("report")}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            activeTab === "report"
              ? "bg-primary text-primary-foreground"
              : "bg-muted hover:bg-muted/80"
          }`}
        >
          报告查看
        </button>
      </div>

      <div className="rounded-lg border p-4">
        {activeTab === "sentiment" ? (
          <>
            <div className="mb-4 flex items-center gap-2">
              <label className="text-sm text-muted-foreground shrink-0">选择会话：</label>
              <select
                value={conversationId ?? ""}
                onChange={(e) => setConversationId(e.target.value ? Number(e.target.value) : null)}
                className="flex-1 rounded-md border bg-background px-3 py-2 text-sm"
              >
                <option value="">{loading ? "加载中..." : "-- 请选择会话 --"}</option>
                {conversations.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.title}
                  </option>
                ))}
              </select>
            </div>
            {conversationId ? (
              <SentimentAnalysis conversationId={conversationId} />
            ) : (
              <div className="text-center text-muted-foreground py-8">
                请先选择一个会话查看情感分析
              </div>
            )}
          </>
        ) : (
          <ReportViewer reportType="daily" />
        )}
      </div>
    </div>
  );
}
