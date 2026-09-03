import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"

// 获取仪表盘统计数据
export function useDashboardStats() {
  return useQuery({
    queryKey: ["dashboard", "stats"],
    queryFn: () => api.dashboard.getStats(),
    staleTime: 10000, // 10秒内数据被认为是新鲜的
    refetchInterval: 30000, // 30秒自动刷新
    refetchOnWindowFocus: false,
  })
}

// 获取关键词趋势
export function useKeywordTrend(days: number = 7, limit: number = 10) {
  return useQuery({
    queryKey: ["dashboard", "keywordTrend", days, limit],
    queryFn: () => api.dashboard.getKeywordTrend(days, limit),
    staleTime: 60000, // 1分钟缓存
    refetchOnWindowFocus: false,
  })
}

// 获取发送者排名
export function useSenderRanking(limit: number = 12, sortBy: "messages" | "alerts" = "alerts") {
  return useQuery({
    queryKey: ["dashboard", "senderRanking", limit, sortBy],
    queryFn: () => api.dashboard.getSenderRanking(limit, sortBy),
    staleTime: 60000,
    refetchOnWindowFocus: false,
  })
}

// 获取会话活动
export function useConversationActivity(limit: number = 12) {
  return useQuery({
    queryKey: ["dashboard", "conversationActivity", limit],
    queryFn: () => api.dashboard.getConversationActivity(limit),
    staleTime: 60000,
    refetchOnWindowFocus: false,
  })
}

// 获取最近告警
export function useRecentAlerts(limit: number = 12) {
  return useQuery({
    queryKey: ["dashboard", "recentAlerts", limit],
    queryFn: () => api.dashboard.getRecentAlerts(limit),
    staleTime: 30000, // 30秒缓存
    refetchOnWindowFocus: false,
  })
}
