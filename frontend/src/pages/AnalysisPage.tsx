import { useState } from "react";
import { SentimentAnalysis } from "@/components/ui/SentimentAnalysis";
import { ReportViewer } from "@/components/ui/ReportViewer";

export function AnalysisPage() {
  const [activeTab, setActiveTab] = useState<"sentiment" | "report">("sentiment");
  const [conversationId, setConversationId] = useState<number | null>(null);

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
          conversationId ? (
            <SentimentAnalysis conversationId={conversationId} />
          ) : (
            <div className="text-center text-muted-foreground py-8">
              请在监控页面选择会话后查看情感分析
            </div>
          )
        ) : (
          <ReportViewer />
        )}
      </div>
    </div>
  );
}
