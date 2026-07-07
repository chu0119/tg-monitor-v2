import { useEffect, useState, useRef, useCallback } from "react"

interface WebSocketMessage {
  type: string
  data?: any
}

const MAX_MESSAGES = 200
const RECONNECT_DELAY = 3000
const MAX_RECONNECT_ATTEMPTS = 999

export function useWebSocket(url: string = "/ws") {
  const [isConnected, setIsConnected] = useState(false)
  const [messages, setMessages] = useState<WebSocketMessage[]>([])
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectAttemptsRef = useRef(0)
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
      if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttemptsRef.current++
        reconnectTimeoutRef.current = setTimeout(() => connect(), RECONNECT_DELAY)
      }
    }
    wsRef.current = ws
  }, [url, batchProcess])

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current)
    if (wsRef.current) wsRef.current.close()
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
