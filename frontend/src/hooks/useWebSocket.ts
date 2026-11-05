import { useEffect, useState, useRef, useCallback } from "react"

interface WebSocketMessage {
  type: string
  data?: any
}

const MAX_MESSAGES = 200
const RECONNECT_DELAY_BASE = 3000
const RECONNECT_DELAY_MAX = 60000
const MAX_RECONNECT_ATTEMPTS = 999

export function useWebSocket(url: string = "/ws") {
  const [isConnected, setIsConnected] = useState(false)
  const [messages, setMessages] = useState<WebSocketMessage[]>([])
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectAttemptsRef = useRef(0)
  // 主动关闭标记：disconnect 后 onclose 不再触发重连，避免组件卸载后无限重连
  const intentionalCloseRef = useRef(false)
  const pendingMessages = useRef<WebSocketMessage[]>([])
  const batchUpdateRef = useRef<number | null>(null)

  const batchProcess = useCallback(() => {
    if (pendingMessages.current.length === 0) return
    const batch = [...pendingMessages.current]
    pendingMessages.current = []
    setMessages(prev => [...prev, ...batch].slice(-MAX_MESSAGES))
    batchUpdateRef.current = null
  }, [])

  const connect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    intentionalCloseRef.current = false
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:"
    const wsUrl = `${protocol}//${window.location.host}${url}`
    const ws = new WebSocket(wsUrl)
    ws.onopen = () => {
      setIsConnected(true)
      reconnectAttemptsRef.current = 0
    }
    ws.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data)
        pendingMessages.current.push(message)
        if (batchUpdateRef.current === null) {
          batchUpdateRef.current = requestAnimationFrame(batchProcess)
        }
      } catch (e) {
        console.error("WebSocket message parse error:", e)
      }
    }
    ws.onerror = (error) => console.error("WebSocket error:", error)
    ws.onclose = () => {
      setIsConnected(false)
      if (intentionalCloseRef.current) return
      if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttemptsRef.current++
        // 指数退避重连：3s → 6s → 12s ... 上限 60s
        const delay = Math.min(RECONNECT_DELAY_BASE * 2 ** reconnectAttemptsRef.current, RECONNECT_DELAY_MAX)
        reconnectTimeoutRef.current = setTimeout(() => connect(), delay)
      }
    }
    wsRef.current = ws
  }, [url, batchProcess])

  const disconnect = useCallback(() => {
    intentionalCloseRef.current = true
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    if (wsRef.current) wsRef.current.close()
    wsRef.current = null
  }, [])

  useEffect(() => {
    connect()
    return disconnect
  }, [connect, disconnect])

  const sendMessage = useCallback((message: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    }
  }, [])

  const clearMessages = useCallback(() => setMessages([]), [])

  return { isConnected, messages, sendMessage, clearMessages }
}
