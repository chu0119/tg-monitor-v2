import React, { useEffect, useRef, useCallback, useMemo } from "react"
import { Virtuoso } from "react-virtuoso"
import { useMonitoringStore } from "../stores/monitoringStore"
import { useWebSocket } from "../hooks/useWebSocket"
import { api } from "../api"

const MessageItem = React.memo(({ message }: { message: any }) => (
  <div className="p-3 border-b hover:bg-gray-50 dark:hover:bg-gray-800">
    <div className="flex items-center gap-2 text-sm">
      <span className="font-medium text-blue-600">
        {message.sender_username || message.sender_first_name || "未知"}
      </span>
      <span className="text-gray-400 text-xs">
        {new Date(message.date).toLocaleTimeString()}
      </span>
    </div>
    <p className="text-gray-700 mt-1 text-sm line-clamp-3">
      {message.text || "(非文本消息)"}
    </p>
  </div>
), (prev, next) => prev.message.id === next.message.id)

const ConversationItem = React.memo(({ 
  conversation, isSelected, hasNewMessages, badgeCount, onClick 
}: { 
  conversation: any; isSelected: boolean; hasNewMessages: boolean; 
  badgeCount: number; onClick: () => void 
}) => (
  <div
    className={`p-3 border-b cursor-pointer transition-colors ${
      isSelected ? "bg-blue-50 border-l-4 border-l-blue-500" : "hover:bg-gray-50"
    }`}
    onClick={onClick}
  >
    <div className="flex items-center justify-between">
      <span className="font-medium text-gray-900 truncate">
        {conversation.title || "会话 " + conversation.id}
      </span>
      {hasNewMessages && (
        <span className="bg-red-500 text-white text-xs px-1.5 py-0.5 rounded-full">
          {badgeCount > 99 ? "99+" : badgeCount}
        </span>
      )}
    </div>
    <p className="text-gray-500 text-xs mt-1">
      {conversation.total_messages || 0} 条消息
    </p>
  </div>
), (prev, next) => 
  prev.conversation.id === next.conversation.id &&
  prev.isSelected === next.isSelected &&
  prev.hasNewMessages === next.hasNewMessages
)

export default function MonitoringPageOptimized() {
  const store = useMonitoringStore()
  const { messages: wsMessages, clearMessages } = useWebSocket()
  const pendingMessages = useRef<any[]>([])
  const batchUpdateRef = useRef<number | null>(null)
  
  const batchUpdateMessages = useCallback(() => {
    if (pendingMessages.current.length === 0) return
    const batch = [...pendingMessages.current]
    pendingMessages.current = []
    batch.forEach(msg => {
      if (store.selectedConversation && !store.globalSearch && msg.conversation_id === store.selectedConversation) {
        store.addMessage(msg)
      }
    })
    batchUpdateRef.current = null
  }, [store.selectedConversation, store.globalSearch])
  
  useEffect(() => {
    if (wsMessages.length > 0) {
      wsMessages.forEach(msg => {
        if (msg.type === "new_message" && msg.data) {
          pendingMessages.current.push(msg.data)
        }
      })
      if (batchUpdateRef.current === null) {
        batchUpdateRef.current = requestAnimationFrame(batchUpdateMessages)
      }
      clearMessages()
    }
  }, [wsMessages, batchUpdateMessages, clearMessages])
  
  useEffect(() => {
    const loadData = async () => {
      try {
        const [conversations, stats] = await Promise.all([
          api.conversations.list({ status: "active", page_size: 500 }),
          api.dashboard.getStats()
        ])
        const conversationList = Array.isArray(conversations) ? conversations : conversations.items || []
        store.setConversations(conversationList)
        store.setGlobalStats(stats)
        if (conversationList.length > 0) {
          store.setSelectedConversation(conversationList[0].id)
        }
      } catch (error) {
        console.error("Load data failed:", error)
      }
    }
    loadData()
  }, [])
  
  useEffect(() => {
    const loadMessages = async () => {
      if (!store.selectedConversation) return
      try {
        const response = await api.messages.list({
          conversation_id: store.selectedConversation,
          page: 1,
          page_size: 100,
        })
        const messages = Array.isArray(response) ? response : response.items || []
        store.setMessages(messages)
      } catch (error) {
        console.error("Load messages failed:", error)
      }
    }
    loadMessages()
  }, [store.selectedConversation])
  
  const filteredConversations = useMemo(() => {
    if (!store.searchQuery.trim()) return store.conversations
    const query = store.searchQuery.toLowerCase().trim()
    return store.conversations.filter(conv => 
      conv.title?.toLowerCase().includes(query) || conv.id.toString().includes(query)
    )
  }, [store.conversations, store.searchQuery])
  
  const filteredMessages = useMemo(() => {
    if (!store.filter.trim()) return store.messages
    const query = store.filter.toLowerCase().trim()
    return store.messages.filter(msg => 
      msg.text?.toLowerCase().includes(query) || msg.sender_username?.toLowerCase().includes(query)
    )
  }, [store.messages, store.filter])
  
  return (
    <div className="flex h-full">
      <div className="w-80 border-r bg-gray-50 flex flex-col">
        <div className="p-3 border-b">
          <input
            type="text"
            placeholder="搜索会话..."
            value={store.searchQuery}
            onChange={(e) => store.setSearchQuery(e.target.value)}
            className="w-full px-3 py-2 border rounded-lg text-sm"
          />
        </div>
        <div className="flex-1 overflow-hidden">
          <Virtuoso
            data={filteredConversations}
            itemContent={(index, conversation) => (
              <ConversationItem
                conversation={conversation}
                isSelected={conversation.id === store.selectedConversation}
                hasNewMessages={store.conversationsWithNewMessages.has(conversation.id)}
                badgeCount={store.showNewMessageBadge[conversation.id] || 0}
                onClick={() => store.setSelectedConversation(conversation.id)}
              />
            )}
          />
        </div>
      </div>
      <div className="flex-1 flex flex-col">
        <div className="flex-1 overflow-hidden">
          <Virtuoso
            data={filteredMessages}
            itemContent={(index, message) => (
              <MessageItem message={message} />
            )}
            followOutput="smooth"
          />
        </div>
      </div>
    </div>
  )
}
