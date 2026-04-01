import { useEffect, useState, useRef, useCallback } from "react";

interface WebSocketMessage {
  type: string;
  data?: any;
}

const MAX_MESSAGES = 100; // 限制消息数量，防止内存泄漏
const RECONNECT_DELAY = 3000; // 重连延迟 3 秒
const MAX_RECONNECT_ATTEMPTS = 999; // 几乎无限重连（永久重连）

// 请求浏览器通知权限
if (typeof window !== "undefined" && "Notification" in window && Notification.permission === "default") {
  Notification.requestPermission();
}

function sendBrowserNotification(message: WebSocketMessage) {
  if (typeof window === "undefined" || !("Notification" in window)) return;
  if (Notification.permission !== "granted") return;
  // 只在页面不可见时发送桌面通知，避免重复打扰
  if (document.visibilityState === "visible") return;

  const data = message.data;
  if (message.type === "new_alert") {
    new Notification("🚨 新告警", {
      body: data?.sender_username
        ? `${data.sender_username}: ${data.text?.substring(0, 100) || "匹配关键词"}`
        : data?.text?.substring(0, 100) || "关键词匹配告警",
      tag: `alert-${data?.id || Date.now()}`,
    });
  } else if (message.type === "new_message") {
    new Notification("💬 新消息", {
      body: data?.sender_username
        ? `${data.sender_username}: ${data.text?.substring(0, 100) || "(非文本消息)"}`
        : data?.text?.substring(0, 100) || "(非文本消息)",
      tag: `msg-${data?.id || Date.now()}`,
    });
  }
}

export function useWebSocket(url: string = "/ws") {
  const [isConnected, setIsConnected] = useState(false);
  const [messages, setMessages] = useState<WebSocketMessage[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);

  const connect = useCallback(() => {
    // 清除之前的重连定时器
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}${url}`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setIsConnected(true);
      reconnectAttemptsRef.current = 0; // 重置重连计数
      console.log("WebSocket connected");
    };

    ws.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data);
        setMessages((prev) => {
          const newMessages = [...prev, message];
          return newMessages.slice(-MAX_MESSAGES);
        });
        // 浏览器桌面通知
        if (message.type === "new_alert" || message.type === "new_message") {
          sendBrowserNotification(message);
        }
      } catch (e) {
        console.error("WebSocket message parse error:", e);
      }
    };

    ws.onerror = (error) => {
      console.error("WebSocket error:", error);
    };

    ws.onclose = () => {
      setIsConnected(false);
      console.log("WebSocket disconnected");

      // 自动重连逻辑
      if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttemptsRef.current++;
        console.log(`Reconnecting... Attempt ${reconnectAttemptsRef.current}/${MAX_RECONNECT_ATTEMPTS}`);
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, RECONNECT_DELAY);
      } else {
        console.log("Max reconnect attempts reached. Giving up.");
      }
    };

    wsRef.current = ws;
  }, [url]);

  const disconnect = useCallback(() => {
    // 清除重连定时器
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    // 关闭连接
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  const sendMessage = useCallback((message: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  return {
    isConnected,
    messages,
    sendMessage,
    clearMessages,
  };
}
