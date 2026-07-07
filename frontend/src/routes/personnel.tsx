import { useState, useEffect, useCallback } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { api } from "../lib/api";
import { Search, MessageSquare, Clock, Users, TriangleAlert, Loader, Send, ChevronLeft, ChevronRight } from "lucide-react";

interface Sender {
  sender_id: number;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  phone: string | null;
  sender_name: string;
  message_count: number;
  group_count: number;
}

interface SenderProfile {
  sender_id: number;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  phone: string | null;
  sender_name: string;
  total_messages: number;
  alert_count: number;
  group_count: number;
  message_types: Record<string, number>;
  groups: { conversation_id: number; title: string; message_count: number; last_message_at: string }[];
}

interface SenderMessage {
  id: number;
  conversation_id: number;
  content: string | null;
  message_type: string;
  created_at: string;
  group_title: string;
  is_alert: boolean;
  alert_level: string | null;
}

function SearchBar({ onSelect }: { onSelect: (id: number) => void }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Sender[]>([]);
  const [loading, setLoading] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);

  useEffect(() => {
    if (query.length < 2) { setResults([]); setShowDropdown(false); return; }
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const data = await api.personnel.search(query);
        setResults(data);
        setShowDropdown(true);
      } catch (e) { console.error(e); }
      setLoading(false);
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  const handleClick = (senderId: number) => {
    onSelect(senderId);
    setShowDropdown(false);
    setQuery("");
  };

  return (
    <div className="relative">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={"搜索用户名、姓名、手机号……"}
          className="w-full pl-10 pr-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
          onFocus={() => results.length > 0 && setShowDropdown(true)}
          onBlur={() => setTimeout(() => setShowDropdown(false), 200)}
        />
        {loading && <Loader className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 animate-spin" />}
      </div>
      {showDropdown && results.length > 0 && (
        <div className="absolute z-50 mt-1 w-full bg-gray-700 border border-gray-600 rounded-lg shadow-xl max-h-80 overflow-y-auto">
          {results.map((s) => (
            <button key={s.sender_id} onClick={() => handleClick(s.sender_id)}
              className="w-full px-4 py-3 text-left hover:bg-gray-600 border-b border-gray-600 last:border-0">
              <div className="text-white font-medium">{s.sender_name}</div>
              <div className="text-sm text-gray-400">
                {s.username ? "@" + s.username : ""} | {s.message_count} 消息 | {s.group_count} 群组
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function ProfileCard({ profile }: { profile: SenderProfile }) {
  return (
    <div className="bg-gray-700 rounded-lg p-6">
      <div className="flex items-center gap-4 mb-4">
        <div className="w-16 h-16 rounded-full bg-blue-600 flex items-center justify-center text-2xl font-bold text-white">
          {profile.sender_name?.[0] || "?"}
        </div>
        <div>
          <h2 className="text-xl font-bold text-white">{profile.sender_name}</h2>
          {profile.username && <p className="text-gray-400">@{profile.username}</p>}
          {profile.phone && <p className="text-gray-400">{profile.phone}</p>}
        </div>
      </div>
      <div className="grid grid-cols-3 gap-4">
        <div className="text-center p-3 bg-gray-600 rounded-lg">
          <div className="text-2xl font-bold text-blue-400">{profile.total_messages}</div>
          <div className="text-sm text-gray-400">总消息数</div>
        </div>
        <div className="text-center p-3 bg-gray-600 rounded-lg">
          <div className="text-2xl font-bold text-orange-400">{profile.alert_count}</div>
          <div className="text-sm text-gray-400">告警消息</div>
        </div>
        <div className="text-center p-3 bg-gray-600 rounded-lg">
          <div className="text-2xl font-bold text-green-400">{profile.group_count}</div>
          <div className="text-sm text-gray-400">参与群组</div>
        </div>
      </div>
    </div>
  );
}

function MessageList({ messages, loading, hasMore, onNextPage, onPrevPage, page }: {
  messages: SenderMessage[]; loading: boolean; hasMore: boolean;
  onNextPage: () => void; onPrevPage: () => void; page: number;
}) {
  return (
    <div className="space-y-2">
      {loading ? (
        <div className="text-center py-8"><Loader className="w-6 h-6 animate-spin mx-auto text-gray-400" /></div>
      ) : messages.length === 0 ? (
        <div className="text-center py-8 text-gray-400">暂无消息</div>
      ) : (
        <>
          {messages.map((msg) => (
            <div key={msg.id} className={`p-3 rounded-lg border ${msg.is_alert ? 'bg-red-900/20 border-red-700' : 'bg-gray-700 border-gray-600'}`}>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs text-gray-400">{msg.group_title}</span>
                <span className="text-xs text-gray-500">{new Date(msg.created_at).toLocaleString('zh-CN')}</span>
                {msg.is_alert && <span className="px-1.5 py-0.5 text-xs bg-red-600 text-white rounded">告警</span>}
                <span className="px-1.5 py-0.5 text-xs bg-gray-600 text-gray-300 rounded">{msg.message_type}</span>
              </div>
              <p className="text-sm text-gray-200">{msg.content || '(无文本内容)'}</p>
            </div>
          ))}
          <div className="flex justify-center items-center gap-4 pt-2">
            <button onClick={onPrevPage} disabled={page === 0}
              className="px-3 py-1 bg-gray-600 rounded text-sm disabled:opacity-50"><ChevronLeft className="w-4 h-4 inline" /> 上一页</button>
            <span className="text-sm text-gray-400">第 {page + 1} 页</span>
            <button onClick={onNextPage} disabled={!hasMore}
              className="px-3 py-1 bg-gray-600 rounded text-sm disabled:opacity-50">下一页 <ChevronRight className="w-4 h-4 inline" /></button>
          </div>
        </>
      )}
    </div>
  );
}

export function PersonnelComponent() {
  const [senderId, setSenderId] = useState<number | null>(null);
  const [profile, setProfile] = useState<SenderProfile | null>(null);
  const [messages, setMessages] = useState<SenderMessage[]>([]);
  const [groupBy, setGroupBy] = useState<"group" | "timeline">("group");
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!senderId) return;
    setLoading(true);
    api.personnel.getProfile(senderId)
      .then((data) => { setProfile(data); setPage(0); })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [senderId]);

  const loadMessages = useCallback(async () => {
    if (!senderId) return;
    setLoading(true);
    try {
      const data = await api.personnel.getMessages(senderId, { group_by: groupBy, offset: page * 50, limit: 50 });
      setMessages(data.messages || []);
      setHasMore((data.messages || []).length === 50);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [senderId, groupBy, page]);

  useEffect(() => { loadMessages(); }, [loadMessages]);

  const handleSelectSender = (id: number) => { setSenderId(id); setPage(0); };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">人员档案</h1>
      <SearchBar onSelect={handleSelectSender} />
      {senderId && (
        <div className="space-y-6">
          {loading && !profile ? (
            <div className="text-center py-8"><Loader className="w-8 h-8 animate-spin mx-auto text-gray-400" /></div>
          ) : profile ? (
            <ProfileCard profile={profile} />
          ) : null}
          <div className="flex gap-2">
            <button onClick={() => setGroupBy("group")}
              className={`px-4 py-2 rounded-lg text-sm flex items-center gap-1 ${groupBy === 'group' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300'}`}>
              <Users className="w-4 h-4" /> 按群组
            </button>
            <button onClick={() => setGroupBy("timeline")}
              className={`px-4 py-2 rounded-lg text-sm flex items-center gap-1 ${groupBy === 'timeline' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300'}`}>
              <Clock className="w-4 h-4" /> 按时间
            </button>
          </div>
          <MessageList messages={messages} loading={loading} hasMore={hasMore} page={page}
            onNextPage={() => setPage(p => p + 1)} onPrevPage={() => setPage(p => Math.max(0, p - 1))} />
        </div>
      )}
      {!senderId && (
        <div className="text-center py-16 text-gray-400">
          <Search className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>搜索并选择一个人员查看详情</p>
        </div>
      )}
    </div>
  );
}
