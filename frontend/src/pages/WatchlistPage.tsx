import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { Input } from "@/components/ui/Input";
import { formatDate } from "@/lib/utils";
import {
  Plus,
  Filter,
  Edit,
  Trash2,
  UserCircle,
  Phone,
  Hash,
  AtSign,
} from "lucide-react";

interface WatchlistItem {
  id: number;
  item_type: string;
  value: string;
  name: string;
  threat_level: string;
  reason: string;
  added_by: string;
  status: string;
  created_at: string;
  updated_at: string;
}

const typeLabels: Record<string, string> = {
  user: "用户",
  phone: "手机号",
  username: "用户名",
  group: "群组",
  keyword: "关键词",
};

const typeIcons: Record<string, any> = {
  user: UserCircle,
  phone: Phone,
  username: AtSign,
  group: Hash,
  keyword: Hash,
};

const threatLabels: Record<string, string> = {
  low: "低",
  medium: "中",
  high: "高",
  critical: "严重",
};

const threatColors: Record<string, string> = {
  low: "default",
  medium: "default",
  high: "destructive",
  critical: "destructive",
};

const statusLabels: Record<string, string> = {
  active: "活跃",
  inactive: "已停用",
  expired: "已过期",
};

export function WatchlistPage() {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState({ item_type: "", threat_level: "", status: "" });
  const [showCreate, setShowCreate] = useState(false);
  const [editItem, setEditItem] = useState<WatchlistItem | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [totalCount, setTotalCount] = useState(0);

  useEffect(() => {
    fetchItems();
  }, [filter, currentPage, pageSize]);

  const fetchItems = async () => {
    setLoading(true);
    try {
      const params: any = { page: currentPage, page_size: pageSize };
      if (filter.item_type) params.item_type = filter.item_type;
      if (filter.threat_level) params.threat_level = filter.threat_level;
      if (filter.status) params.status = filter.status;
      const data = await api.watchlist.list(params);
      if (data && typeof data === "object" && "items" in data) {
        setItems(data.items || []);
        setTotalCount(data.total || 0);
      } else if (Array.isArray(data)) {
        setItems(data);
        setTotalCount(data.length);
      }
    } catch (error) {
      console.error("Failed to fetch watchlist:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (formData: any) => {
    try {
      await api.watchlist.create(formData);
      setShowCreate(false);
      fetchItems();
    } catch (error) {
      console.error("Failed to create watchlist item:", error);
      alert("添加失败");
    }
  };

  const handleUpdate = async (formData: any) => {
    if (!editItem) return;
    try {
      await api.watchlist.update(editItem.id, formData);
      setEditItem(null);
      fetchItems();
    } catch (error) {
      console.error("Failed to update watchlist item:", error);
      alert("更新失败");
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("确定删除此条目？")) return;
    try {
      await api.watchlist.delete(id);
      fetchItems();
    } catch (error) {
      console.error("Failed to delete watchlist item:", error);
      alert("删除失败");
    }
  };

  return (
    <div className="space-y-4 sm:space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold neon-text">重点关注名单</h1>
          <p className="text-xs sm:text-sm text-muted-foreground mt-1">管理重点关注的用户、手机号和群组</p>
        </div>
        <Button variant="tech" onClick={() => setShowCreate(true)} className="w-full sm:w-auto min-h-[44px]">
          <Plus size={18} className="mr-2" />
          添加到名单
        </Button>
      </div>

      <Card>
        <CardContent className="pt-4 sm:pt-6">
          <div className="flex flex-col sm:flex-row flex-wrap items-stretch sm:items-center gap-3">
            <select
              value={filter.item_type}
              onChange={(e) => { setFilter({ ...filter, item_type: e.target.value }); setCurrentPage(1); }}
              className="input-tech px-4 py-2 rounded-lg min-h-[44px]"
            >
              <option value="">全部类型</option>
              <option value="user">用户</option>
              <option value="phone">手机号</option>
              <option value="username">用户名</option>
              <option value="group">群组</option>
              <option value="keyword">关键词</option>
            </select>
            <select
              value={filter.threat_level}
              onChange={(e) => { setFilter({ ...filter, threat_level: e.target.value }); setCurrentPage(1); }}
              className="input-tech px-4 py-2 rounded-lg min-h-[44px]"
            >
              <option value="">全部威胁级别</option>
              <option value="low">低</option>
              <option value="medium">中</option>
              <option value="high">高</option>
              <option value="critical">严重</option>
            </select>
            <select
              value={filter.status}
              onChange={(e) => { setFilter({ ...filter, status: e.target.value }); setCurrentPage(1); }}
              className="input-tech px-4 py-2 rounded-lg min-h-[44px]"
            >
              <option value="">全部状态</option>
              <option value="active">活跃</option>
              <option value="inactive">已停用</option>
              <option value="expired">已过期</option>
            </select>
            <Button variant="tech" onClick={fetchItems} className="min-h-[44px]">
              <Filter size={18} className="mr-2" />
              刷新
            </Button>
          </div>
        </CardContent>
      </Card>

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin w-8 h-8 border-2 border-cyber-blue border-t-transparent rounded-full" />
        </div>
      ) : items.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">暂无记录</CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {items.map((item) => {
            const Icon = typeIcons[item.item_type] || Hash;
            return (
              <Card key={item.id} className="hover:shadow-[0_0_20px_rgba(0,240,255,0.15)] transition-all">
                <CardContent className="p-4 sm:p-6">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3 flex-1 min-w-0">
                      <div className="w-10 h-10 rounded-lg bg-cyber-purple/20 flex items-center justify-center shrink-0">
                        <Icon size={20} className="text-cyber-purple" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          <Badge variant="outline" className="text-xs">{typeLabels[item.item_type] || item.item_type}</Badge>
                          <Badge variant={threatColors[item.threat_level] as any || "default"} className="text-xs">
                            威胁: {threatLabels[item.threat_level] || item.threat_level}
                          </Badge>
                          <Badge variant="outline" className="text-xs">{statusLabels[item.status] || item.status}</Badge>
                        </div>
                        <p className="text-sm sm:text-base font-medium">{item.name || item.value}</p>
                        {item.name && <p className="text-xs text-muted-foreground mt-0.5 font-mono">{item.value}</p>}
                        {item.reason && <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{item.reason}</p>}
                        <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                          <span>添加人: {item.added_by || "系统"}</span>
                          <span>{formatDate(item.created_at)}</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <Button variant="ghost" size="sm" onClick={() => setEditItem(item)} className="min-h-[44px] min-w-[44px]">
                        <Edit size={16} />
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => handleDelete(item.id)} className="min-h-[44px] min-w-[44px] text-red-400 hover:text-red-300">
                        <Trash2 size={16} />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {totalCount > 0 && (
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-4 border-t border-cyber-blue/10">
          <div className="text-xs sm:text-sm text-muted-foreground text-center sm:text-left">
            共 {totalCount} 条，第 {currentPage} 页
          </div>
          <div className="flex items-center justify-center gap-2">
            <select
              value={pageSize}
              onChange={(e) => { setPageSize(parseInt(e.target.value)); setCurrentPage(1); }}
              className="input-tech px-3 py-1.5 rounded-lg text-sm min-h-[44px]"
            >
              <option value="10">10条/页</option>
              <option value="20">20条/页</option>
              <option value="50">50条/页</option>
            </select>
            <Button variant="outline" size="sm" disabled={currentPage === 1} onClick={() => setCurrentPage(currentPage - 1)} className="min-h-[44px] px-3">上一页</Button>
            <span className="text-sm px-2">第 {currentPage} / {Math.ceil(totalCount / pageSize)} 页</span>
            <Button variant="outline" size="sm" disabled={currentPage >= Math.ceil(totalCount / pageSize)} onClick={() => setCurrentPage(currentPage + 1)} className="min-h-[44px] px-3">下一页</Button>
          </div>
        </div>
      )}

      {showCreate && <WatchlistFormModal onClose={() => setShowCreate(false)} onSubmit={handleCreate} title="添加到名单" />}
      {editItem && <WatchlistFormModal onClose={() => setEditItem(null)} onSubmit={handleUpdate} title="编辑条目" initialData={editItem} />}
    </div>
  );
}

function WatchlistFormModal({ onClose, onSubmit, title, initialData }: { onClose: () => void; onSubmit: (data: any) => void; title: string; initialData?: WatchlistItem }) {
  const [form, setForm] = useState({
    item_type: initialData?.item_type || "user",
    value: initialData?.value || "",
    name: initialData?.name || "",
    threat_level: initialData?.threat_level || "medium",
    reason: initialData?.reason || "",
    status: initialData?.status || "active",
  });

  const handleSubmit = () => {
    if (!form.value.trim()) { alert("请输入标识值"); return; }
    onSubmit(form);
  };

  return (
    <Modal isOpen={true} onClose={onClose} title={title}>
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm text-muted-foreground">类型</label>
            <select value={form.item_type} onChange={(e) => setForm({ ...form, item_type: e.target.value })} className="input-tech w-full px-4 py-2 rounded-lg mt-1 min-h-[44px]">
              <option value="user">用户</option>
              <option value="phone">手机号</option>
              <option value="username">用户名</option>
              <option value="group">群组</option>
              <option value="keyword">关键词</option>
            </select>
          </div>
          <div>
            <label className="text-sm text-muted-foreground">威胁级别</label>
            <select value={form.threat_level} onChange={(e) => setForm({ ...form, threat_level: e.target.value })} className="input-tech w-full px-4 py-2 rounded-lg mt-1 min-h-[44px]">
              <option value="low">低</option>
              <option value="medium">中</option>
              <option value="high">高</option>
              <option value="critical">严重</option>
            </select>
          </div>
        </div>
        <div>
          <label className="text-sm text-muted-foreground">标识值 *</label>
          <Input value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} className="mt-1 min-h-[44px]" placeholder="用户ID/手机号/用户名等" />
        </div>
        <div>
          <label className="text-sm text-muted-foreground">名称</label>
          <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="mt-1 min-h-[44px]" placeholder="备注名称" />
        </div>
        <div>
          <label className="text-sm text-muted-foreground">原因</label>
          <textarea value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} className="input-tech w-full px-4 py-2 rounded-lg mt-1 min-h-[80px]" rows={3} placeholder="添加原因" />
        </div>
        {initialData && (
          <div>
            <label className="text-sm text-muted-foreground">状态</label>
            <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })} className="input-tech w-full px-4 py-2 rounded-lg mt-1 min-h-[44px]">
              <option value="active">活跃</option>
              <option value="inactive">已停用</option>
            </select>
          </div>
        )}
        <div className="flex gap-3 pt-4">
          <Button variant="tech" className="flex-1 min-h-[44px]" onClick={handleSubmit}>{initialData ? "保存" : "添加"}</Button>
          <Button variant="ghost" className="flex-1 min-h-[44px]" onClick={onClose}>取消</Button>
        </div>
      </div>
    </Modal>
  );
}
