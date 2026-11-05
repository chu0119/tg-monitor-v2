/**
 * API 配置 - 自动适配任何部署环境
 *
 * 支持的访问方式：
 * 1. localhost:5173 -> 通过 Vite 代理访问 localhost:8000
 * 2. 192.168.1.187:5173 -> 通过 Vite 代理访问 localhost:8000
 * 3. example.com:5173 -> 通过 Vite 代理访问 localhost:8000
 * 4. example.com -> 直接访问 example.com:8000（需要配置 VITE_API_BASE_URL）
 */

/**
 * 获取 API 基础路径
 * 优先级：
 * 1. 环境变量 VITE_API_BASE_URL（生产环境显式配置）
 * 2. 相对路径 /api/v1（通过 Vite 代理，适配大多数场景）
 */
const getApiBase = (): string => {
  // 如果环境变量显式配置了 API 地址，使用它
  const envApiBase = import.meta.env.VITE_API_BASE_URL;
  if (envApiBase && envApiBase.trim() !== "") {
    return `${envApiBase}/api/v1`;
  }

  // 默认使用相对路径，通过 Vite 代理
  // 这样无论用什么地址访问（localhost/IP/域名），API 请求都会转发到正确的后端
  return "/api/v1";
};

const API_BASE = getApiBase();

/**
 * 获取 WebSocket URL
 * 自动根据当前访问方式选择正确的 WebSocket 地址
 */
function getWebSocketURL(): string {
  const envApiBase = import.meta.env.VITE_API_BASE_URL;

  if (envApiBase && envApiBase.trim() !== "") {
    // 环境变量显式配置了后端地址
    try {
      const url = new URL(envApiBase);
      const wsProtocol = url.protocol === "https:" ? "wss:" : "ws:";
      return `${wsProtocol}//${url.host}/ws`;
    } catch {
      // URL 解析失败，降级到默认方式
    }
  }

  // 使用当前页面的协议和主机，构建 WebSocket URL
  // 这样可以适配任何访问方式（localhost/IP/域名）
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = window.location.host;
  return `${protocol}//${host}/ws`;
}

// 统一的错误处理（带10秒超时）
async function handleResponse(res: Response): Promise<any> {
  if (!res.ok) {
    let errorMessage = `HTTP ${res.status}: ${res.statusText}`;
    try {
      const errorData = await res.json();
      const detail = errorData.detail;
      if (typeof detail === "string") {
        errorMessage = detail;
      } else if (Array.isArray(detail) && detail.length > 0) {
        errorMessage = detail.map((d: any) => d.msg || JSON.stringify(d)).join("; ");
      } else if (detail && typeof detail === "object") {
        errorMessage = detail.message || JSON.stringify(detail);
      } else if (errorData.message) {
        errorMessage = errorData.message;
      }
    } catch {
      // 如果无法解析 JSON，使用默认错误消息
    }
    throw new Error(errorMessage);
  }
  return res.json();
}

// 带超时的 fetch 包装（10秒 AbortController 超时）
export function fetchWithTimeout(url: string, options: RequestInit = {}, timeoutMs = 10000): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  return globalThis.fetch(url, { ...options, signal: controller.signal }).finally(() => clearTimeout(timer));
}

export const api = {
  // 账号管理
  accounts: {
    list: () => fetchWithTimeout(`${API_BASE}/accounts`).then(handleResponse),
    get: (id: number) => fetchWithTimeout(`${API_BASE}/accounts/${id}`).then(handleResponse),
    requestLogin: (data: { phone: string; api_id?: number; api_hash?: string; proxy_config?: any }) =>
      fetchWithTimeout(`${API_BASE}/accounts/login/request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then(handleResponse),
    submitLogin: (data: { phone: string; code: string; api_id?: number; api_hash?: string; password?: string }) =>
      fetchWithTimeout(`${API_BASE}/accounts/login/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then(handleResponse),
    update: (id: number, data: any) =>
      fetchWithTimeout(`${API_BASE}/accounts/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then(handleResponse),
    delete: (id: number) =>
      fetchWithTimeout(`${API_BASE}/accounts/${id}`, { method: "DELETE" }).then(handleResponse),
    getDialogs: (id: number) =>
      fetchWithTimeout(`${API_BASE}/accounts/${id}/dialogs`, {
        method: "POST",
      }).then(handleResponse),
    disconnect: (id: number) =>
      fetchWithTimeout(`${API_BASE}/accounts/${id}/disconnect`, {
        method: "POST",
      }).then(handleResponse),
    toggle: (id: number) =>
      fetchWithTimeout(`${API_BASE}/accounts/${id}/toggle`, {
        method: "POST",
      }).then(handleResponse),
    add: (data: { api_id: string; api_hash: string; phone: string }) =>
      fetchWithTimeout(`${API_BASE}/accounts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then(handleResponse),
  },

  // 会话管理
  conversations: {
    list: async (params?: { status?: string; chat_type?: string; page?: number; page_size?: number }) => {
      const cleanParams = Object.fromEntries(
        Object.entries(params || {}).filter(([_, v]) => v !== undefined)
      );
      const searchParams = new URLSearchParams(cleanParams as any);
      const res = await fetchWithTimeout(`${API_BASE}/conversations?${searchParams}`);
      return await handleResponse(res);
    },
    get: (id: number) => fetchWithTimeout(`${API_BASE}/conversations/${id}`).then(handleResponse),
    create: (data: any) =>
      fetchWithTimeout(`${API_BASE}/conversations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then(handleResponse),
    batchCreate: (data: any[], force = false) =>
      fetchWithTimeout(`${API_BASE}/conversations/batch?force=${force}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then(handleResponse),
    update: (id: number, data: any) =>
      fetchWithTimeout(`${API_BASE}/conversations/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then(handleResponse),
    batchUpdate: (conversationIds: number[], data: any) =>
      fetchWithTimeout(`${API_BASE}/conversations/batch-update`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ conversation_ids: conversationIds, update_data: data }),
      }).then(handleResponse),
    delete: (id: number) =>
      fetchWithTimeout(`${API_BASE}/conversations/${id}`, { method: "DELETE" }).then(handleResponse),
    batchDelete: (conversationIds: number[]) =>
      fetchWithTimeout(`${API_BASE}/conversations/batch`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ conversation_ids: conversationIds }),
      }).then(handleResponse),
    pullHistory: (id: number, days?: number, limit?: number) =>
      fetchWithTimeout(`${API_BASE}/conversations/${id}/pull-history?days=${days || ""}&limit=${limit || ""}`, {
        method: "POST",
      }).then(handleResponse),
    batchSync: (accountId: number) =>
      fetchWithTimeout(`${API_BASE}/conversations/batch-sync?account_id=${accountId}`, {
        method: "POST",
      }).then(handleResponse),
    getStats: (id: number) => fetchWithTimeout(`${API_BASE}/conversations/${id}/stats`).then(handleResponse),
  },

  // 消息查询
  messages: {
    list: async (params: {
      conversation_id?: number;
      sender_id?: number;
      keyword?: string;
      message_type?: string;
      has_alert?: boolean;
      start_date?: string;
      end_date?: string;
      page?: number;
      page_size?: number;
    }) => {
      const cleanParams = Object.fromEntries(
        Object.entries(params || {}).filter(([_, v]) => v !== undefined)
      );
      const searchParams = new URLSearchParams(cleanParams as any);
      const res = await fetchWithTimeout(`${API_BASE}/messages?${searchParams}`);
      return handleResponse(res);
    },
    get: (id: number) => fetchWithTimeout(`${API_BASE}/messages/${id}`).then(handleResponse),
    export: (data: any) =>
      fetchWithTimeout(`${API_BASE}/messages/export`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then(handleResponse),
  },

  // 关键词管理
  keywords: {
    listGroups: () => fetchWithTimeout(`${API_BASE}/keywords/groups`).then(handleResponse),
    getGroup: (id: number) => fetchWithTimeout(`${API_BASE}/keywords/groups/${id}`).then(handleResponse),
    createGroup: (data: any) =>
      fetchWithTimeout(`${API_BASE}/keywords/groups`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then(handleResponse),
    updateGroup: (id: number, data: any) =>
      fetchWithTimeout(`${API_BASE}/keywords/groups/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then(handleResponse),
    deleteGroup: (id: number) =>
      fetchWithTimeout(`${API_BASE}/keywords/groups/${id}`, { method: "DELETE" }).then(handleResponse),
    listKeywords: (groupId: number) =>
      fetchWithTimeout(`${API_BASE}/keywords/groups/${groupId}/keywords`).then(handleResponse),
    createKeyword: (data: any) =>
      fetchWithTimeout(`${API_BASE}/keywords/keywords`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then(handleResponse),
    updateKeyword: (id: number, data: any) =>
      fetchWithTimeout(`${API_BASE}/keywords/keywords/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then(handleResponse),
    deleteKeyword: (id: number) =>
      fetchWithTimeout(`${API_BASE}/keywords/keywords/${id}`, { method: "DELETE" }).then(handleResponse),
    batchImport: (data: any) =>
      fetchWithTimeout(`${API_BASE}/keywords/keywords/batch-import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then(handleResponse),
    importPreview: (data: any) =>
      fetchWithTimeout(`${API_BASE}/keywords/import-preview`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then(handleResponse),
    qualityReport: () => fetchWithTimeout(`${API_BASE}/keywords/quality-report`).then(handleResponse),
    recentMatchPreview: (data: any, limit = 100) =>
      fetchWithTimeout(`${API_BASE}/keywords/recent-match-preview?limit=${limit}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then(handleResponse),
    testMatch: (text: string, keywordIds: number[]) =>
      fetchWithTimeout(`${API_BASE}/keywords/test-match`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, keyword_ids: keywordIds }),
      }).then(handleResponse),
  },

  // 告警管理
  alerts: {
    list: async (params?: {
      status?: string;
      alert_level?: string;
      keyword_group_id?: number;
      conversation_id?: number;
      sender_id?: number;
      keyword?: string;
      page?: number;
      page_size?: number;
    }) => {
      // 过滤掉 undefined 值
      const cleanParams = Object.fromEntries(
        Object.entries(params || {}).filter(([_, v]) => v !== undefined)
      );
      const searchParams = new URLSearchParams(cleanParams as any);
      const res = await fetchWithTimeout(`${API_BASE}/alerts?${searchParams}`);
      const data = await handleResponse(res);
      // 返回完整的分页响应对象 { items: [], total: number, page: number, ... }
      return data;
    },
    get: (id: number) => fetchWithTimeout(`${API_BASE}/alerts/${id}`).then(handleResponse),
    handle: (id: number, data: { status: string; handler_note?: string }, handler: string) =>
      fetchWithTimeout(`${API_BASE}/alerts/${id}/handle?handler=${handler}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then(handleResponse),
    updateStatus: (id: number, status: string) =>
      fetchWithTimeout(`${API_BASE}/alerts/${id}/status`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      }).then(handleResponse),
    delete: (id: number) =>
      fetchWithTimeout(`${API_BASE}/alerts/${id}`, { method: "DELETE" }).then(handleResponse),
    getStats: () => fetchWithTimeout(`${API_BASE}/alerts/stats`).then(handleResponse),
    batchUpdateStatus: (alertIds: number[], data: { status: string; handler_note?: string }) =>
      fetchWithTimeout(`${API_BASE}/alerts/batch-status`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ alert_ids: alertIds, ...data }),
      }).then(handleResponse),
    exportCSV: async (params?: {
      status?: string;
      alert_level?: string;
      keyword_group_id?: number;
      conversation_id?: number;
      sender_id?: number;
      keyword?: string;
      start_date?: string;
      end_date?: string;
    }) => {
      // 过滤掉 undefined 值
      const cleanParams = Object.fromEntries(
        Object.entries(params || {}).filter(([_, v]) => v !== undefined)
      );
      const searchParams = new URLSearchParams(cleanParams as any);
      const response = await fetchWithTimeout(`${API_BASE}/alerts/export/csv?${searchParams}`);
      if (!response.ok) throw new Error("导出失败");

      // 下载文件
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = response.headers.get("Content-Disposition")?.match(/filename=(.+)/)?.[1] || `alerts_export_${new Date().toISOString().split("T")[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      return { success: true };
    },
  },

  // 通知配置
  notifications: {
    list: () => fetchWithTimeout(`${API_BASE}/notifications`).then(handleResponse),
    get: (id: number) => fetchWithTimeout(`${API_BASE}/notifications/${id}`).then(handleResponse),
    create: (data: any) =>
      fetchWithTimeout(`${API_BASE}/notifications`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then(handleResponse),
    update: (id: number, data: any) =>
      fetchWithTimeout(`${API_BASE}/notifications/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then(handleResponse),
    delete: (id: number) =>
      fetchWithTimeout(`${API_BASE}/notifications/${id}`, { method: "DELETE" }).then(handleResponse),
    test: (data: { config_id: number; test_message?: string }) =>
      fetchWithTimeout(`${API_BASE}/notifications/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then(handleResponse),
    getTypes: () => fetchWithTimeout(`${API_BASE}/notifications/types`).then(handleResponse),
  },

  // 仪表盘
  dashboard: {
    getStats: () => fetchWithTimeout(`${API_BASE}/dashboard/stats`).then(handleResponse),
    getMessageTrend: (days?: number, conversationId?: number) =>
      fetchWithTimeout(`${API_BASE}/dashboard/message-trend?days=${days || 7}&conversation_id=${conversationId || ""}`).then(
        handleResponse
      ),
    getKeywordTrend: (days?: number, limit?: number) =>
      fetchWithTimeout(`${API_BASE}/dashboard/keyword-trend?days=${days || 7}&limit=${limit || 10}`).then(handleResponse),
    getSenderRanking: (limit?: number, sortBy: "messages" | "alerts" = "messages") =>
      fetchWithTimeout(`${API_BASE}/dashboard/sender-ranking?limit=${limit || 20}&sort_by=${sortBy}`).then(handleResponse),
    getConversationActivity: (limit?: number) =>
      fetchWithTimeout(`${API_BASE}/dashboard/conversation-activity?limit=${limit || 10}`).then(handleResponse),
    getRecentAlerts: (limit?: number) =>
      fetchWithTimeout(`${API_BASE}/dashboard/alerts/recent?limit=${limit || 20}`).then(handleResponse),
  },

  // 系统设置
  settings: {
    get: () => fetchWithTimeout(`${API_BASE}/settings`).then(handleResponse),
    update: (data: any) =>
      fetchWithTimeout(`${API_BASE}/settings`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then(handleResponse),
    updateDbSetting: (key: string, value: string) =>
      fetchWithTimeout(`${API_BASE}/settings/db/${encodeURIComponent(key)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value }),
      }).then(handleResponse),
    reset: () =>
      fetchWithTimeout(`${API_BASE}/settings/reset`, {
        method: "POST",
      }).then(handleResponse),
    exportAll: () => fetchWithTimeout(`${API_BASE}/settings/export`).then(handleResponse),
    importAll: (data: any) =>
      fetchWithTimeout(`${API_BASE}/settings/import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then(handleResponse),
    exportKeywords: () => fetchWithTimeout(`${API_BASE}/settings/export/keywords`).then(handleResponse),
    importKeywords: (data: any) =>
      fetchWithTimeout(`${API_BASE}/settings/import/keywords`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then(handleResponse),
  },

  // 数据库管理
  database: {
    getStatus: () => fetchWithTimeout(`${API_BASE}/database/status`).then(handleResponse),
    getStats: () => fetchWithTimeout(`${API_BASE}/database/stats`).then(handleResponse),
    testConnection: (config: {
      host: string;
      port: number;
      user: string;
      password: string;
      database: string;
    }) =>
      fetchWithTimeout(`${API_BASE}/database/test-connection`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      }).then(handleResponse),
    configure: (config: {
      host: string;
      port: number;
      user: string;
      password: string;
      database: string;
      save_config: boolean;
    }) =>
      fetchWithTimeout(`${API_BASE}/database/configure`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      }).then(handleResponse),
    init: () =>
      fetchWithTimeout(`${API_BASE}/database/init`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      }).then(handleResponse),
    clear: () =>
      fetchWithTimeout(`${API_BASE}/database/clear`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      }).then(handleResponse),
  },

  // 监控管理
  monitoring: {
    getStatus: () => fetchWithTimeout(`${API_BASE}/monitoring/status`).then(handleResponse),
    start: (conversationId: number) =>
      fetchWithTimeout(`${API_BASE}/monitoring/start/${conversationId}`, { method: "POST" }).then(handleResponse),
    stop: (conversationId: number) =>
      fetchWithTimeout(`${API_BASE}/monitoring/stop/${conversationId}`, { method: "POST" }).then(handleResponse),
    restart: () =>
      fetchWithTimeout(`${API_BASE}/monitoring/restart`, { method: "POST" }).then(handleResponse),
  },

  // 代理管理
  proxy: {
    getStatus: () => fetchWithTimeout(`${API_BASE}/proxy/status`).then(handleResponse),
    saveConfig: (data: {
      enabled: boolean;
      protocol: "http" | "https" | "socks5";
      host: string;
      port: number;
      username?: string;
      password?: string;
    }) =>
      fetchWithTimeout(`${API_BASE}/proxy/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then(handleResponse),
    testConfig: (data: {
      protocol: "http" | "https" | "socks5";
      host: string;
      port: number;
      timeout_sec?: number;
    }) =>
      fetchWithTimeout(`${API_BASE}/proxy/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then(handleResponse),
    enable: () =>
      fetchWithTimeout(`${API_BASE}/proxy/enable`, {
        method: "POST",
      }).then(handleResponse),
    disable: () =>
      fetchWithTimeout(`${API_BASE}/proxy/disable`, {
        method: "POST",
      }).then(handleResponse),
    testLatency: () =>
      fetchWithTimeout(`${API_BASE}/proxy/latency`).then(handleResponse),
    // 兼容旧页面调用
    start: () =>
      fetchWithTimeout(`${API_BASE}/proxy/enable`, {
        method: "POST",
      }).then(handleResponse),
    stop: () =>
      fetchWithTimeout(`${API_BASE}/proxy/disable`, {
        method: "POST",
      }).then(handleResponse),
    restart: () =>
      fetchWithTimeout(`${API_BASE}/proxy/enable`, {
        method: "POST",
      }).then(handleResponse),
  },

  // 系统状态
  system: {
    getStatus: () => fetchWithTimeout(`${API_BASE}/system/status`).then(handleResponse),
    getInfo: () => fetchWithTimeout(`${API_BASE}/system/info`).then(handleResponse),
    getUpdateStatus: () => fetchWithTimeout(`${API_BASE}/system/update-status`).then(handleResponse),
    checkUpdate: () => fetchWithTimeout(`${API_BASE}/system/check-update`).then(handleResponse),
    performUpdate: () =>
      fetchWithTimeout(`${API_BASE}/system/perform-update`, { method: "POST" }).then(handleResponse),
    getUpdateProgress: () => fetchWithTimeout(`${API_BASE}/system/update-progress`).then(handleResponse),
  },

  // 备份管理
  backups: {
    list: () => fetchWithTimeout(`${API_BASE}/backups/list`).then(handleResponse),
    create: (name?: string) =>
      fetchWithTimeout(`${API_BASE}/backups/create${name ? `?name=${encodeURIComponent(name)}` : ""}`, {
        method: "POST",
      }).then(handleResponse),
    restore: (name: string) =>
      fetchWithTimeout(`${API_BASE}/backups/restore/${encodeURIComponent(name)}`, {
        method: "POST",
      }).then(handleResponse),
    delete: (name: string) =>
      fetchWithTimeout(`${API_BASE}/backups/delete/${encodeURIComponent(name)}`, {
        method: "DELETE",
      }).then(handleResponse),
    status: () => fetchWithTimeout(`${API_BASE}/backups/status`).then(handleResponse),
  },

  // 数据分析
  analysis: {
    getTopWords: (conversationId?: number, senderId?: number, days?: number, limit?: number) => {
      const params = new URLSearchParams();
      if (conversationId) params.append("conversation_id", conversationId.toString());
      if (senderId) params.append("sender_id", senderId.toString());
      if (days) params.append("days", days.toString());
      if (limit) params.append("limit", limit.toString());
      return fetchWithTimeout(`${API_BASE}/analysis/wordcloud/words?${params}`).then(handleResponse);
    },
    getKeywordTrend: (keyword: string, days?: number, interval?: string) =>
      fetchWithTimeout(`${API_BASE}/analysis/wordcloud/trend?keyword=${encodeURIComponent(keyword)}&days=${days || 30}&interval=${interval || "day"}`).then(handleResponse),
    getMessageSentiment: (messageId: number) =>
      fetchWithTimeout(`${API_BASE}/analysis/sentiment/message/${messageId}`).then(handleResponse),
    getConversationSentiment: (conversationId: number, days?: number) =>
      fetchWithTimeout(`${API_BASE}/analysis/sentiment/conversation/${conversationId}?days=${days || 7}`).then(handleResponse),
    getSentimentTrend: (conversationId: number, days?: number) =>
      fetchWithTimeout(`${API_BASE}/analysis/sentiment/trend/${conversationId}?days=${days || 30}`).then(handleResponse),
    getDailyReport: (date?: string) => {
      const params = date ? `?date=${date}` : "";
      return fetchWithTimeout(`${API_BASE}/analysis/report/daily${params}`).then(handleResponse);
    },
    getWeeklyReport: (startDate?: string) => {
      const params = startDate ? `?start_date=${startDate}` : "";
      return fetchWithTimeout(`${API_BASE}/analysis/report/weekly${params}`).then(handleResponse);
    },
    downloadDailyReportPDF: (date?: string) => {
      const params = date ? `?date=${date}` : "";
      return fetchWithTimeout(`${API_BASE}/analysis/report/pdf/daily${params}`).then((resp) => resp.blob());
    },
    downloadWeeklyReportPDF: (startDate?: string) => {
      const params = startDate ? `?start_date=${startDate}` : "";
      return fetchWithTimeout(`${API_BASE}/analysis/report/pdf/weekly${params}`).then((resp) => resp.blob());
    },
  },

  // 人员档案
  personnel: {
    search: (q: string) =>
      fetchWithTimeout(`${API_BASE}/personnel/search?q=${encodeURIComponent(q)}`).then(handleResponse),
    getProfile: (senderId: number) =>
      fetchWithTimeout(`${API_BASE}/personnel/${senderId}/profile`).then(handleResponse),
    getMessages: (senderId: number, params: {
      group_by?: string;
      conversation_id?: number;
      date_from?: string;
      date_to?: string;
      keyword?: string;
      page?: number;
      page_size?: number;
      offset?: number;
      limit?: number;
    }) => {
      const cleanParams: Record<string, any> = {};
      if (params?.group_by !== undefined) cleanParams.group_by = params.group_by;
      if (params?.conversation_id !== undefined) cleanParams.conversation_id = params.conversation_id;
      if (params?.date_from !== undefined) cleanParams.date_from = params.date_from;
      if (params?.date_to !== undefined) cleanParams.date_to = params.date_to;
      if (params?.keyword !== undefined) cleanParams.keyword = params.keyword;
      // 支持 page/page_size 或 offset/limit 两种分页方式
      if (params?.offset !== undefined) {
        cleanParams.offset = params.offset;
        cleanParams.limit = params.limit ?? 50;
      } else if (params?.page !== undefined) {
        cleanParams.offset = params.page * (params.page_size ?? 50);
        cleanParams.limit = params.page_size ?? 50;
      }
      const searchParams = new URLSearchParams(cleanParams as any);
      return fetchWithTimeout(`${API_BASE}/personnel/${senderId}/messages?${searchParams}`).then(handleResponse);
    },
  } ,
  phoneRecords: {
    list: (params?: Record<string, any>) =>
      fetchWithTimeout(`${API_BASE}/phone-records?${new URLSearchParams(params || {}).toString()}`).then(handleResponse),
    stats: () =>
      fetchWithTimeout(`${API_BASE}/phone-records/stats`).then(handleResponse),
    getPhone: (phone: string) =>
      fetchWithTimeout(`${API_BASE}/phone-records/phone/${encodeURIComponent(phone)}`).then(handleResponse),
    provinces: () =>
      fetchWithTimeout(`${API_BASE}/phone-records/provinces`).then(handleResponse),
    cities: (province: string) =>
      fetchWithTimeout(`${API_BASE}/phone-records/cities?province=${encodeURIComponent(province)}`).then(handleResponse),
  },

  // 案件管理
  cases: {
    list: (params?: { status?: string; case_type?: string; priority?: string; page?: number; page_size?: number }) => {
      const cleanParams = Object.fromEntries(
        Object.entries(params || {}).filter(([_, v]) => v !== undefined)
      );
      const searchParams = new URLSearchParams(cleanParams as any);
      return fetchWithTimeout(`${API_BASE}/cases?${searchParams}`).then(handleResponse);
    },
    get: (id: number) => fetchWithTimeout(`${API_BASE}/cases/${id}`).then(handleResponse),
    create: (data: any) =>
      fetchWithTimeout(`${API_BASE}/cases`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then(handleResponse),
    update: (id: number, data: any) =>
      fetchWithTimeout(`${API_BASE}/cases/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then(handleResponse),
    delete: (id: number) =>
      fetchWithTimeout(`${API_BASE}/cases/${id}`, { method: "DELETE" }).then(handleResponse),
    addAlert: (caseId: number, alertId: number) =>
      fetchWithTimeout(`${API_BASE}/cases/${caseId}/alerts/${alertId}`, { method: "POST" }).then(handleResponse),
    removeAlert: (caseId: number, alertId: number) =>
      fetchWithTimeout(`${API_BASE}/cases/${caseId}/alerts/${alertId}`, { method: "DELETE" }).then(handleResponse),
    getAlerts: (caseId: number) =>
      fetchWithTimeout(`${API_BASE}/cases/${caseId}/alerts`).then(handleResponse),
  },

  // 重点关注名单
  watchlist: {
    list: (params?: { item_type?: string; threat_level?: string; status?: string; page?: number; page_size?: number }) => {
      const cleanParams = Object.fromEntries(
        Object.entries(params || {}).filter(([_, v]) => v !== undefined)
      );
      const searchParams = new URLSearchParams(cleanParams as any);
      return fetchWithTimeout(`${API_BASE}/watchlist?${searchParams}`).then(handleResponse);
    },
    get: (id: number) => fetchWithTimeout(`${API_BASE}/watchlist/${id}`).then(handleResponse),
    create: (data: any) =>
      fetchWithTimeout(`${API_BASE}/watchlist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then(handleResponse),
    update: (id: number, data: any) =>
      fetchWithTimeout(`${API_BASE}/watchlist/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then(handleResponse),
    delete: (id: number) =>
      fetchWithTimeout(`${API_BASE}/watchlist/${id}`, { method: "DELETE" }).then(handleResponse),
  },

  // 审计日志
  audit: {
    list: (params?: { operator?: string; action_type?: string; target_type?: string; start_date?: string; end_date?: string; page?: number; page_size?: number }) => {
      const cleanParams = Object.fromEntries(
        Object.entries(params || {}).filter(([_, v]) => v !== undefined)
      );
      const searchParams = new URLSearchParams(cleanParams as any);
      return fetchWithTimeout(`${API_BASE}/audit?${searchParams}`).then(handleResponse);
    },
    getStats: () =>
      fetchWithTimeout(`${API_BASE}/audit/stats`).then(handleResponse),
  },
};

// WebSocket 连接
export function createWebSocket() {
  const wsUrl = getWebSocketURL();
  const ws = new WebSocket(wsUrl);

  return {
    on: (event: string, callback: (data: any) => void) => {
      ws.addEventListener("message", (e) => {
        const data = JSON.parse(e.data);
        if (data.type === event) {
          callback(data.data);
        }
      });
    },
    send: (data: any) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(data));
      }
    },
    close: () => ws.close(),
  };
}
