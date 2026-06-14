import { useState, useEffect, useCallback, Fragment } from "react";
import { Phone, Search, ChevronDown, ChevronRight, MessageSquare, AlertTriangle, User, RefreshCw, MapPin, Radio, Users, ExternalLink } from "lucide-react";
import { api } from "@/lib/api";

interface PhoneRecord {
  id: number;
  phone: string;
  phone_display: string;
  country_code: string;
  country: string;
  phone_location: string;
  carrier: string;
  source_type: "sender" | "message" | "alert";
  source_id: number;
  source_detail: string;
  conversation_id: number;
  first_seen_at: string;
  last_seen_at: string;
  occurrence_count: number;
  sender_name?: string;
  sender_user_id?: number;
}

interface SenderInfo {
  user_id: number;
  username: string;
  first_name: string;
  last_name: string;
  phone: string;
  country: string;
  phone_location: string;
  is_bot: boolean;
  is_verified: boolean;
  is_premium: boolean;
  message_count: number;
  created_at: string;
  conversations: { id: number; title: string; chat_id: number }[];
}

interface RelatedSender {
  user_id: number;
  username: string;
  first_name: string;
  last_name: string;
  phone: string;
  is_bot: boolean;
  is_verified: boolean;
  is_premium: boolean;
  message_count: number;
  created_at: string;
  source: "bound" | "mentioned";
  mention_count: number;
  conversations: { id: number; title: string; chat_id: number }[];
}

interface MessageCtx {
  match_message: {
    id: number;
    text: string;
    date: string;
    sender_name: string;
    conversation_title: string;
    message_type: string;
  };
  context_before: { id: number; text: string; date: string; sender_name: string; message_type: string }[];
  context_after: { id: number; text: string; date: string; sender_name: string; message_type: string }[];
}

interface PhoneDetail {
  base_info: { phone: string; phone_display: string; country_code: string; country: string; phone_location: string; carrier: string };
  records: { id: number; source_type: string; source_id: number; source_detail: string; conversation_id: number; first_seen_at: string; last_seen_at: string; occurrence_count: number }[];
  senders: SenderInfo[];
  related_senders: RelatedSender[];
  message_contexts: MessageCtx[];
  conversations: { id: number; title: string; chat_id: number }[];
  total_records: number;
}

const sourceLabels: Record<string, string> = { sender: "发送者账号", message: "消息正文", alert: "告警内容" };
const sourceColors: Record<string, string> = { sender: "text-cyan-400 bg-cyan-400/10", message: "text-green-400 bg-green-400/10", alert: "text-red-400 bg-red-400/10" };
const sourceIcons: Record<string, typeof Phone> = { sender: User, message: MessageSquare, alert: AlertTriangle };

export function PhoneIntelPage() {
  const [records, setRecords] = useState<PhoneRecord[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [loading, setLoading] = useState(true);
  const [searchPhone, setSearchPhone] = useState("");
  const [filterSource, setFilterSource] = useState("");
  const [filterProvince, setFilterProvince] = useState("");
  const [filterCity, setFilterCity] = useState("");
  const [provinces, setProvinces] = useState<{name: string; count: number}[]>([]);
  const [cities, setCities] = useState<{name: string; count: number}[]>([]);
  const [expandedRecordId, setExpandedRecordId] = useState<number | null>(null);
  const [detail, setDetail] = useState<PhoneDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = { page, page_size: pageSize };
      if (searchPhone) params.phone = searchPhone;
      if (filterSource) params.source_type = filterSource;
      if (filterProvince) params.province = filterProvince;
      if (filterCity) params.city = filterCity;
      const data = await api.phoneRecords.list(params);
      setRecords(data.items || []);
      setTotal(data.total || 0);
    } catch (e) { console.error(e); } finally { setLoading(false); }
  }, [page, pageSize, searchPhone, filterSource, filterProvince, filterCity]);

  const fetchStats = useCallback(async () => {
    try { setStats(await api.phoneRecords.stats()); } catch (e) { console.error(e); }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);
  useEffect(() => { fetchStats(); }, [fetchStats]);

  // Fetch provinces on mount
  useEffect(() => {
    fetch("/api/v1/phone-records/provinces").then(r => r.json()).then(data => setProvinces(data)).catch(() => {});
  }, []);

  // Fetch cities when province changes
  useEffect(() => {
    if (filterProvince) {
      fetch(`/api/v1/phone-records/cities?province=${encodeURIComponent(filterProvince)}`).then(r => r.json()).then(data => setCities(data)).catch(() => {});
    } else {
      setCities([]);
      setFilterCity("");
    }
  }, [filterProvince]);

  const handleExpand = async (recordId: number, phone: string) => {
    if (expandedRecordId === recordId) { setExpandedRecordId(null); setDetail(null); return; }
    setExpandedRecordId(recordId);
    setDetailLoading(true);
    try { setDetail(await api.phoneRecords.getPhone(phone)); } catch (e) { console.error(e); } finally { setDetailLoading(false); }
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Phone className="w-6 h-6 text-cyber-blue" />
          <h1 className="text-2xl font-bold text-white">手机号信息</h1>
        </div>
        <button onClick={() => { fetchData(); fetchStats(); }} className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border bg-secondary/50 text-gray-300 hover:text-white text-sm">
          <RefreshCw className="w-4 h-4" /> 刷新
        </button>
      </div>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="rounded-xl border border-border bg-secondary/30 p-4">
            <div className="text-sm text-gray-400">手机号总数</div>
            <div className="text-2xl font-bold text-white mt-1">{stats.total?.toLocaleString()}</div>
          </div>
          <div className="rounded-xl border border-border bg-secondary/30 p-4">
            <div className="text-sm text-gray-400">国内号码</div>
            <div className="text-2xl font-bold text-cyber-blue mt-1">{stats.domestic?.toLocaleString()}</div>
          </div>
          <div className="rounded-xl border border-border bg-secondary/30 p-4">
            <div className="text-sm text-gray-400">有详细归属地</div>
            <div className="text-2xl font-bold text-green-400 mt-1">{stats.location_detail_ratio || 0}%</div>
          </div>
          <div className="rounded-xl border border-border bg-secondary/30 p-4">
            <div className="text-sm text-gray-400">Top 归属地</div>
            <div className="text-sm text-white mt-1">{stats.top_locations?.[0]?.name || "-"}</div>
          </div>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input type="text" placeholder="搜索手机号..." value={searchPhone}
            onChange={(e) => setSearchPhone(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && (setPage(1), fetchData())}
            className="w-full pl-10 pr-4 py-2 rounded-lg border border-border bg-secondary/50 text-white placeholder-gray-500 focus:border-cyber-blue focus:outline-none text-sm" />
        </div>
        <select value={filterSource} onChange={(e) => { setFilterSource(e.target.value); setPage(1); }}
          className="px-3 py-2 rounded-lg border border-border bg-secondary/50 text-white text-sm focus:border-cyber-blue focus:outline-none">
          <option value="">全部来源</option>
          <option value="sender">发送者账号</option>
          <option value="message">消息正文</option>
          <option value="alert">告警内容</option>
        </select>
        <select value={filterProvince} onChange={(e) => { setFilterProvince(e.target.value); setFilterCity(""); setPage(1); }}
          className="px-3 py-2 rounded-lg border border-border bg-secondary/50 text-white text-sm focus:border-cyber-blue focus:outline-none">
          <option value="">全部省份</option>
          {provinces.map(p => <option key={p.name} value={p.name}>{p.name} ({p.count.toLocaleString()})</option>)}
        </select>
        {filterProvince && cities.length > 0 && (
          <select value={filterCity} onChange={(e) => { setFilterCity(e.target.value); setPage(1); }}
            className="px-3 py-2 rounded-lg border border-border bg-secondary/50 text-white text-sm focus:border-cyber-blue focus:outline-none">
            <option value="">全部城市</option>
            {cities.map(c => <option key={c.name} value={c.name}>{c.name.replace(filterProvince, "")} ({c.count.toLocaleString()})</option>)}
          </select>
        )}
      </div>

      <div className="rounded-xl border border-border bg-secondary/20 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-secondary/50">
                <th className="px-4 py-3 text-left text-gray-400 font-medium w-8"></th>
                <th className="px-4 py-3 text-left text-gray-400 font-medium">手机号</th>
                <th className="px-4 py-3 text-left text-gray-400 font-medium">归属地</th>
                <th className="px-4 py-3 text-left text-gray-400 font-medium">运营商</th>
                <th className="px-4 py-3 text-left text-gray-400 font-medium">来源</th>
                <th className="px-4 py-3 text-left text-gray-400 font-medium">发送者</th>
                <th className="px-4 py-3 text-left text-gray-400 font-medium">次数</th>
                <th className="px-4 py-3 text-left text-gray-400 font-medium">最后出现</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-500"><RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2" />加载中...</td></tr>
              ) : records.length === 0 ? (
                <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-500">暂无数据</td></tr>
              ) : records.map((r) => {
                const Icon = sourceIcons[r.source_type] || Phone;
                const isExpanded = expandedRecordId === r.id;
                return (
                  <Fragment key={r.id}>
                    <tr className="border-b border-border/50 hover:bg-secondary/30 cursor-pointer transition-colors" onClick={() => handleExpand(r.id, r.phone)}>
                      <td className="px-4 py-3">{isExpanded ? <ChevronDown className="w-4 h-4 text-gray-400" /> : <ChevronRight className="w-4 h-4 text-gray-400" />}</td>
                      <td className="px-4 py-3 text-white font-mono">{r.phone_display || r.phone}</td>
                      <td className="px-4 py-3 text-gray-300">{r.phone_location || <span className="text-gray-600">-</span>}</td>
                      <td className="px-4 py-3 text-gray-300">{r.carrier || <span className="text-gray-600">-</span>}</td>
                      <td className="px-4 py-3"><span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs ${sourceColors[r.source_type]}`}><Icon className="w-3 h-3" />{sourceLabels[r.source_type]}</span></td>
                      <td className="px-4 py-3 text-gray-300 text-xs">{r.sender_name || <span className="text-gray-600">-</span>}</td>
                      <td className="px-4 py-3 text-gray-300">{r.occurrence_count}</td>
                      <td className="px-4 py-3 text-gray-400 text-xs">{r.last_seen_at ? new Date(r.last_seen_at).toLocaleString("zh-CN") : "-"}</td>
                    </tr>
                    {isExpanded && (
                      <tr><td colSpan={8} className="px-6 py-6 bg-secondary/10">
                        {detailLoading ? (
                          <div className="text-center text-gray-500 py-4">加载详情中...</div>
                        ) : detail ? (
                          <div className="space-y-6">
                            {/* 基础信息卡片 */}
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                              <div className="p-3 rounded-lg bg-secondary/30 border border-border/50">
                                <div className="text-xs text-gray-400">手机号</div>
                                <div className="text-white font-mono mt-1">{detail.base_info.phone_display || detail.base_info.phone}</div>
                              </div>
                              <div className="p-3 rounded-lg bg-secondary/30 border border-border/50">
                                <div className="text-xs text-gray-400">归属地</div>
                                <div className="text-white mt-1 flex items-center gap-1"><MapPin className="w-3 h-3 text-cyber-blue" />{detail.base_info.phone_location || "未知"}</div>
                              </div>
                              <div className="p-3 rounded-lg bg-secondary/30 border border-border/50">
                                <div className="text-xs text-gray-400">运营商</div>
                                <div className="text-white mt-1 flex items-center gap-1"><Radio className="w-3 h-3 text-cyber-blue" />{detail.base_info.carrier || "未知"}</div>
                              </div>
                              <div className="p-3 rounded-lg bg-secondary/30 border border-border/50">
                                <div className="text-xs text-gray-400">国家</div>
                                <div className="text-white mt-1">{detail.base_info.country || "未知"}</div>
                              </div>
                            </div>

                            {/* 关联的发送者 */}
                            {detail.senders.length > 0 && (
                              <div>
                                <h4 className="text-sm font-medium text-gray-300 mb-3 flex items-center gap-2"><User className="w-4 h-4" />关联的 Telegram 账号 ({detail.senders.length})</h4>
                                <div className="space-y-2">
                                  {detail.senders.map((s) => (
                                    <div key={s.user_id} className="p-3 rounded-lg bg-secondary/30 border border-border/50">
                                      <div className="flex items-center gap-3 mb-2">
                                        <span className="text-white font-medium">{s.first_name} {s.last_name}</span>
                                        {s.username && <span className="text-gray-400 text-sm">@{s.username}</span>}
                                        {s.is_verified && <span className="text-xs px-1.5 py-0.5 rounded bg-blue-400/10 text-blue-400">已验证</span>}
                                        {s.is_premium && <span className="text-xs px-1.5 py-0.5 rounded bg-yellow-400/10 text-yellow-400">Premium</span>}
                                        {s.is_bot && <span className="text-xs px-1.5 py-0.5 rounded bg-purple-400/10 text-purple-400">Bot</span>}
                                      </div>
                                      <div className="text-xs text-gray-400 space-y-1">
                                        <div>用户ID: {s.user_id} | 消息数: {s.message_count} | 注册: {s.created_at ? new Date(s.created_at).toLocaleDateString("zh-CN") : "-"}</div>
                                        {s.conversations.length > 0 && (
                                          <div className="flex flex-wrap gap-1 mt-1">
                                            <span className="text-gray-500">所在群聊:</span>
                                            {s.conversations.map((c) => (
                                              <span key={c.id} className="px-1.5 py-0.5 rounded bg-secondary/50 text-gray-300">{c.title || `群聊#${c.id}`}</span>
                                            ))}
                                          </div>
                                        )}
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}

                            {/* 关联的群聊 */}
                            {detail.conversations.length > 0 && (
                              <div>
                                <h4 className="text-sm font-medium text-gray-300 mb-3 flex items-center gap-2"><Users className="w-4 h-4" />关联的群聊 ({detail.conversations.length})</h4>
                                <div className="flex flex-wrap gap-2">
                                  {detail.conversations.map((c) => (
                                    <span key={c.id} className="px-3 py-1.5 rounded-lg bg-secondary/30 border border-border/50 text-sm text-gray-300">{c.title || `群聊#${c.id}`}</span>
                                  ))}
                                </div>
                              </div>
                            )}

                            {/* 关联个人 */}
                            {detail.related_senders && detail.related_senders.length > 0 && (
                              <div>
                                <h4 className="text-sm font-medium text-gray-300 mb-3 flex items-center gap-2"><User className="w-4 h-4" />关联的 Telegram 账号 ({detail.related_senders.length})</h4>
                                <div className="space-y-2">
                                  {detail.related_senders.map((s) => (
                                    <div key={s.user_id} className="p-3 rounded-lg bg-secondary/30 border border-border/50">
                                      <div className="flex items-center gap-3 mb-2">
                                        <span className="text-white font-medium">{s.first_name} {s.last_name}</span>
                                        {s.username && <span className="text-gray-400 text-sm">@{s.username}</span>}
                                        <span className={`text-xs px-1.5 py-0.5 rounded ${s.source === 'bound' ? 'bg-cyan-400/10 text-cyan-400' : 'bg-yellow-400/10 text-yellow-400'}`}>
                                          {s.source === 'bound' ? '绑定手机号' : `消息提及 x${s.mention_count}`}
                                        </span>
                                        {s.is_verified && <span className="text-xs px-1.5 py-0.5 rounded bg-blue-400/10 text-blue-400">已验证</span>}
                                        {s.is_premium && <span className="text-xs px-1.5 py-0.5 rounded bg-yellow-400/10 text-yellow-400">Premium</span>}
                                        {s.is_bot && <span className="text-xs px-1.5 py-0.5 rounded bg-purple-400/10 text-purple-400">Bot</span>}
                                      </div>
                                      <div className="text-xs text-gray-400 space-y-1">
                                        <div>用户ID: {s.user_id} | 消息数: {s.message_count} | 注册: {s.created_at ? new Date(s.created_at).toLocaleDateString("zh-CN") : "-"}</div>
                                        {s.conversations.length > 0 && (
                                          <div className="flex flex-wrap gap-1 mt-1">
                                            <span className="text-gray-500">所在群聊:</span>
                                            {s.conversations.map((c) => (
                                              <span key={c.id} className="px-1.5 py-0.5 rounded bg-secondary/50 text-gray-300">{c.title || `群聊#${c.id}`}</span>
                                            ))}
                                          </div>
                                        )}
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}

                            {/* 消息记录（含上下文） */}
                            {detail.message_contexts && detail.message_contexts.length > 0 && (
                              <div>
                                <h4 className="text-sm font-medium text-gray-300 mb-3 flex items-center gap-2"><MessageSquare className="w-4 h-4" />消息记录 ({detail.message_contexts.length}条匹配)</h4>
                                <div className="space-y-4 max-h-96 overflow-y-auto">
                                  {detail.message_contexts.map((mc, idx) => (
                                    <div key={idx} className="rounded-lg bg-secondary/20 border border-border/30 overflow-hidden">
                                      {mc.context_before.length > 0 && (
                                        <div className="px-3 py-1.5 bg-secondary/10 border-b border-border/20">
                                          {mc.context_before.map((ctx, i) => (
                                            <div key={i} className="text-xs text-gray-500 py-0.5 flex gap-2">
                                              <span className="text-gray-600 flex-shrink-0">{ctx.sender_name || '未知'}</span>
                                              <span className="truncate">{ctx.text || '(无文本)'}</span>
                                            </div>
                                          ))}
                                        </div>
                                      )}
                                      <div className="px-3 py-2 bg-cyber-blue/5 border-l-2 border-cyber-blue">
                                        <div className="flex items-center gap-2 mb-1">
                                          <span className="text-xs font-medium text-cyber-blue">{mc.match_message.sender_name || '未知'}</span>
                                          <span className="text-xs text-gray-500">{mc.match_message.conversation_title}</span>
                                          <span className="text-xs text-gray-600">{mc.match_message.date ? new Date(mc.match_message.date).toLocaleString("zh-CN") : ""}</span>
                                        </div>
                                        <div className="text-sm text-white whitespace-pre-wrap break-words">{mc.match_message.text}</div>
                                      </div>
                                      {mc.context_after.length > 0 && (
                                        <div className="px-3 py-1.5 bg-secondary/10 border-t border-border/20">
                                          {mc.context_after.map((ctx, i) => (
                                            <div key={i} className="text-xs text-gray-500 py-0.5 flex gap-2">
                                              <span className="text-gray-600 flex-shrink-0">{ctx.sender_name || '未知'}</span>
                                              <span className="truncate">{ctx.text || '(无文本)'}</span>
                                            </div>
                                          ))}
                                        </div>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}

                            {/* 出现记录 */}
                            <div>
                              <h4 className="text-sm font-medium text-gray-300 mb-3">出现记录 ({detail.total_records}条)</h4>
                              <div className="space-y-2 max-h-64 overflow-y-auto">
                                {detail.records.map((rec) => {
                                  const RecIcon = sourceIcons[rec.source_type] || Phone;
                                  return (
                                    <div key={rec.id} className="flex items-start gap-3 p-2 rounded-lg bg-secondary/20 border border-border/30">
                                      <RecIcon className={`w-4 h-4 mt-0.5 flex-shrink-0 ${sourceColors[rec.source_type]?.split(" ")[0]}`} />
                                      <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2">
                                          <span className={`text-xs px-1.5 py-0.5 rounded ${sourceColors[rec.source_type]}`}>{sourceLabels[rec.source_type]}</span>
                                          <span className="text-xs text-gray-500">{rec.first_seen_at ? new Date(rec.first_seen_at).toLocaleString("zh-CN") : ""}</span>
                                          {rec.occurrence_count > 1 && <span className="text-xs text-yellow-400">x{rec.occurrence_count}</span>}
                                        </div>
                                        {rec.source_detail && <div className="text-xs text-gray-400 mt-1 truncate">{rec.source_detail}</div>}
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          </div>
                        ) : <div className="text-center text-gray-500 text-sm">无详情数据</div>}
                      </td></tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <div className="text-sm text-gray-400">共 {total.toLocaleString()} 条，第 {page}/{totalPages} 页</div>
          <div className="flex items-center gap-2">
            <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page <= 1}
              className="px-3 py-1.5 rounded-lg border border-border bg-secondary/50 text-gray-300 hover:text-white disabled:opacity-50 text-sm">上一页</button>
            <button onClick={() => setPage(Math.min(totalPages, page + 1))} disabled={page >= totalPages}
              className="px-3 py-1.5 rounded-lg border border-border bg-secondary/50 text-gray-300 hover:text-white disabled:opacity-50 text-sm">下一页</button>
          </div>
        </div>
      )}
    </div>
  );
}
