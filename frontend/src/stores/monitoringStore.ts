import { create } from 'zustand'

export interface Message {
  id: number
  text?: string
  date: string
  conversation_id: number
  sender_id?: number
  sender_username?: string
  sender_first_name?: string
  alert_id?: number
  message_type?: string
}

export interface Conversation {
  id: number
  title?: string
  chat_type?: string
  status: string
  total_messages?: number
  last_message_at?: string
  account_phone?: string
  keyword_groups?: number[]
  enable_all_keywords?: boolean
}

export interface MonitoringState {
  // 消息相关
  messages: Message[]
  selectedConversation: number | null
  
  // 会话相关
  conversations: Conversation[]
  
  // UI状态
  filter: string
  searchQuery: string
  globalSearch: boolean
  autoScroll: boolean
  soundEnabled: boolean
  
  // 统计
  globalStats: any
  
  // 新消息标记
  conversationsWithNewMessages: Set<number>
  showNewMessageBadge: Record<number, number>
  
  // 排序
  sortField: 'title' | 'total_messages' | 'status' | 'last_message_at' | 'custom'
  sortOrder: 'asc' | 'desc'
  customOrder: number[]
  
  // Actions
  setMessages: (messages: Message[] | ((prev: Message[]) => Message[])) => void
  addMessage: (message: Message) => void
  setSelectedConversation: (id: number | null) => void
  setConversations: (conversations: Conversation[]) => void
  updateConversation: (id: number, data: Partial<Conversation>) => void
  setFilter: (filter: string) => void
  setSearchQuery: (query: string) => void
  setGlobalSearch: (search: boolean) => void
  setAutoScroll: (auto: boolean) => void
  setSoundEnabled: (enabled: boolean) => void
  setGlobalStats: (stats: any) => void
  addConversationWithNewMessage: (id: number) => void
  removeConversationWithNewMessage: (id: number) => void
  incrementBadge: (id: number) => void
  clearBadge: (id: number) => void
  setSortField: (field: MonitoringState['sortField']) => void
  setSortOrder: (order: MonitoringState['sortOrder']) => void
  setCustomOrder: (order: number[]) => void
  reset: () => void
}

const initialState = {
  messages: [],
  selectedConversation: null,
  conversations: [],
  filter: '',
  searchQuery: '',
  globalSearch: false,
  autoScroll: true,
  soundEnabled: true,
  globalStats: null,
  conversationsWithNewMessages: new Set<number>(),
  showNewMessageBadge: {} as Record<number, number>,
  sortField: 'custom' as const,
  sortOrder: 'asc' as const,
  customOrder: [],
}

export const useMonitoringStore = create<MonitoringState>((set, get) => ({
  ...initialState,
  
  setMessages: (messages) => set((state) => ({
    messages: typeof messages === 'function' ? messages(state.messages) : messages
  })),
  
  addMessage: (message) => set((state) => {
    // 防止重复
    if (state.messages.some(m => m.id === message.id)) {
      return state
    }
    return {
      messages: [message, ...state.messages].slice(0, 200)
    }
  }),
  
  setSelectedConversation: (id) => set({ selectedConversation: id }),
  
  setConversations: (conversations) => set({ conversations }),
  
  updateConversation: (id, data) => set((state) => ({
    conversations: state.conversations.map(conv =>
      conv.id === id ? { ...conv, ...data } : conv
    )
  })),
  
  setFilter: (filter) => set({ filter }),
  
  setSearchQuery: (query) => set({ searchQuery: query }),
  
  setGlobalSearch: (search) => set({ globalSearch: search }),
  
  setAutoScroll: (auto) => set({ autoScroll: auto }),
  
  setSoundEnabled: (enabled) => set({ soundEnabled: enabled }),
  
  setGlobalStats: (stats) => set({ globalStats: stats }),
  
  addConversationWithNewMessage: (id) => set((state) => {
    const newSet = new Set(state.conversationsWithNewMessages)
    newSet.add(id)
    return { conversationsWithNewMessages: newSet }
  }),
  
  removeConversationWithNewMessage: (id) => set((state) => {
    const newSet = new Set(state.conversationsWithNewMessages)
    newSet.delete(id)
    return { conversationsWithNewMessages: newSet }
  }),
  
  incrementBadge: (id) => set((state) => ({
    showNewMessageBadge: {
      ...state.showNewMessageBadge,
      [id]: (state.showNewMessageBadge[id] || 0) + 1
    }
  })),
  
  clearBadge: (id) => set((state) => {
    const newBadge = { ...state.showNewMessageBadge }
    delete newBadge[id]
    return { showNewMessageBadge: newBadge }
  }),
  
  setSortField: (field) => set({ sortField: field }),
  
  setSortOrder: (order) => set({ sortOrder: order }),
  
  setCustomOrder: (order) => set({ customOrder: order }),
  
  reset: () => set(initialState),
}))
