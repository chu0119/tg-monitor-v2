import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { Input } from "@/components/ui/Input";
import { formatDate } from "@/lib/utils";
import {
  Briefcase,
  Plus,
  Filter,
  ChevronRight,
  AlertTriangle,
  Users,
} from "lucide-react";

interface Case {
  id: number;
  case_number: string;
  name: string;
  case_type: string;
  status: string;
  assignee: string;
  priority: string;
  alert_count: number;
  person_count: number;
  description: string;
  created_at: string;
  updated_at: string;
}

const statusLabels: Record<string, string> = {
  open: "进行中",
  closed: "已关闭",
  archived: "已归档",
};

const priorityLabels: Record<string, string> = {
  low: "低",
  medium: "中",
  high: "高",
  urgent: "紧急",
};

const priorityColors: Record<string, string> = {
  low: "default",
  medium: "default",
  high: "destructive",
  urgent: "destructive",
};

const caseTypeLabels: Record<string, string> = {
  fraud: "诈骗",
  terrorism: "恐怖主义",
  drug: "毒品",
  cybercrime: "网络犯罪",
  other: "其他",
};

export function CasesPage() {
  const [cases, setCases] = useState<Case[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState({ status: "", case_type: "", priority: "" });
  const [showCreate, setShowCreate] = useState(false);
  const [selectedCase, setSelectedCase] = useState<Case | null>(null);
  const [showDetail, setShowDetail] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [totalCount, setTotalCount] = useState(0);

  useEffect(() => {
    fetchCases();
  }, [filter, currentPage, pageSize]);

  const fetchCases = async () => {
    setLoading(true);
    try {
      const params: any = { page: currentPage, page_size: pageSize };
      if (filter.status) params.status = filter.status;
      if (filter.case_type) params.case_type = filter.case_type;
      if (filter.priority) params.priority = filter.priority;
      const data = await api.cases.list(params);
      if (data && typeof data === "object" && "items" in data) {
        setCases(data.items || []);
        setTotalCount(data.total || 0);
      } else if (Array.isArray(data)) {
        setCases(data);
        setTotalCount(data.length);
      }
    } catch (error) {
      console.error("Failed to fetch cases:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (formData: any) => {
    try {
      await api.cases.create(formData);
      setShowCreate(false);
      fetchCases();
    } catch (error) {
      console.error("Failed to create case:", error);
      alert("创建案件失败");
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("确定删除此案件？")) return;
    try {
      await api.cases.delete(id);
      fetchCases();
    } catch (error) {
      console.error("Failed to delete case:", error);
      alert("删除案件失败");
    }
  };

  const viewDetail = (c: Case) => {
    setSelectedCase(c);
    setShowDetail(true);
  };

  return (
    <div className="space-y-4 sm:space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold neon-text">案件管理</h1>
          <p className="text-xs sm:text-sm text-muted-foreground mt-1">管理调查案件与关联告警</p>
        </div>
        <Button variant="tech" onClick={() => setShowCreate(true)} className="w-full sm:w-auto min-h-[44px]">
          <Plus size={18} className="mr-2" />
          新建案件
        </Button>
      </div>

      <Card>
        <CardContent className="pt-4 sm:pt-6">
          <div className="flex flex-col sm:flex-row flex-wrap items-stretch sm:items-center gap-3">
            <select
              value={filter.status}
              onChange={(e) => { setFilter({ ...filter, status: e.target.value }); setCurrentPage(1); }}
              className="input-tech px-4 py-2 rounded-lg min-h-[44px]"
            >
              <option value="">全部状态</option>
              <option value="open">进行中</option>
              <option value="closed">已关闭</option>
              <option value="archived">已归档</option>
            </select>
            <select
              value={filter.case_type}
              onChange={(e) => { setFilter({ ...filter, case_type: e.target.value }); setCurrentPage(1); }}
              className="input-tech px-4 py-2 rounded-lg min-h-[44px]"
            >
              <option value="">全部类型</option>
              <option value="fraud">诈骗</option>
              <option value="terrorism">恐怖主义</option>
              <option value="drug">毒品</option>
              <option value="cybercrime">网络犯罪</option>
              <option value="other">其他</option>
            </select>
            <select
              value={filter.priority}
              onChange={(e) => { setFilter({ ...filter, priority: e.target.value }); setCurrentPage(1); }}
              className="input-tech px-4 py-2 rounded-lg min-h-[44px]"
            >
              <option value="">全部优先级</option>
              <option value="low">低</option>
              <option value="medium">中</option>
              <option value="high">高</option>
              <option value="urgent">紧急</option>
            </select>
            <Button variant="tech" onClick={fetchCases} className="min-h-[44px]">
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
      ) : cases.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">暂无案件</CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {cases.map((c) => (
            <Card key={c.id} className="hover:shadow-[0_0_20px_rgba(0,240,255,0.15)] transition-all cursor-pointer" onClick={() => viewDetail(c)}>
              <CardContent className="p-4 sm:p-6">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3 flex-1 min-w-0">
                    <div className="w-10 h-10 rounded-lg bg-cyber-blue/20 flex items-center justify-center shrink-0">
                      <Briefcase size={20} className="text-cyber-blue" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <span className="text-sm font-mono text-cyber-blue">{c.case_number}</span>
                        <Badge variant={priorityColors[c.priority] as any || "default"} className="text-xs">
                          {priorityLabels[c.priority] || c.priority}
                        </Badge>
                        <Badge variant="outline" className="text-xs">
                          {statusLabels[c.status] || c.status}
                        </Badge>
                      </div>
                      <p className="text-sm sm:text-base font-medium truncate">{c.name}</p>
                      <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground flex-wrap">
                        <span>{caseTypeLabels[c.case_type] || c.case_type}</span>
                        <span>主办: {c.assignee || "未分配"}</span>
                        <span className="flex items-center gap-1"><AlertTriangle size={12} /> {c.alert_count || 0} 告警</span>
                        <span className="flex items-center gap-1"><Users size={12} /> {c.person_count || 0} 人员</span>
                        <span>{formatDate(c.created_at)}</span>
                      </div>
                    </div>
                  </div>
                  <ChevronRight size={20} className="text-muted-foreground shrink-0" />
                </div>
              </CardContent>
            </Card>
          ))}
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

      {showCreate && <CreateCaseModal onClose={() => setShowCreate(false)} onSubmit={handleCreate} />}
      {showDetail && selectedCase && (
        <CaseDetailSidebar
          caseData={selectedCase}
          onClose={() => { setShowDetail(false); setSelectedCase(null); }}
        />
      )}
    </div>
  );
}

function CreateCaseModal({ onClose, onSubmit }: { onClose: () => void; onSubmit: (data: any) => void }) {
  const [form, setForm] = useState({
    name: "",
    case_type: "fraud",
    priority: "medium",
    assignee: "",
    description: "",
  });

  const handleSubmit = () => {
    if (!form.name.trim()) { alert("请输入案件名称"); return; }
    onSubmit(form);
  };

  return (
    <Modal isOpen={true} onClose={onClose} title="新建案件">
      <div className="space-y-4">
        <div>
          <label className="text-sm text-muted-foreground">案件名称 *</label>
          <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="mt-1 min-h-[44px]" placeholder="输入案件名称" />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm text-muted-foreground">案件类型</label>
            <select value={form.case_type} onChange={(e) => setForm({ ...form, case_type: e.target.value })} className="input-tech w-full px-4 py-2 rounded-lg mt-1 min-h-[44px]">
              <option value="fraud">诈骗</option>
              <option value="terrorism">恐怖主义</option>
              <option value="drug">毒品</option>
              <option value="cybercrime">网络犯罪</option>
              <option value="other">其他</option>
            </select>
          </div>
          <div>
            <label className="text-sm text-muted-foreground">优先级</label>
            <select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })} className="input-tech w-full px-4 py-2 rounded-lg mt-1 min-h-[44px]">
              <option value="low">低</option>
              <option value="medium">中</option>
              <option value="high">高</option>
              <option value="urgent">紧急</option>
            </select>
          </div>
        </div>
        <div>
          <label className="text-sm text-muted-foreground">主办人</label>
          <Input value={form.assignee} onChange={(e) => setForm({ ...form, assignee: e.target.value })} className="mt-1 min-h-[44px]" placeholder="输入主办人" />
        </div>
        <div>
          <label className="text-sm text-muted-foreground">案件描述</label>
          <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="input-tech w-full px-4 py-2 rounded-lg mt-1 min-h-[80px]" rows={3} placeholder="输入案件描述" />
        </div>
        <div className="flex gap-3 pt-4">
          <Button variant="tech" className="flex-1 min-h-[44px]" onClick={handleSubmit}>创建案件</Button>
          <Button variant="ghost" className="flex-1 min-h-[44px]" onClick={onClose}>取消</Button>
        </div>
      </div>
    </Modal>
  );
}

function CaseDetailSidebar({ caseData, onClose }: { caseData: Case; onClose: () => void }) {
  const [alerts, setAlerts] = useState<any[]>([]);
  const [loadingAlerts, setLoadingAlerts] = useState(true);

  useEffect(() => {
    loadAlerts();
  }, [caseData.id]);

  const loadAlerts = async () => {
    try {
      const data = await api.cases.getAlerts(caseData.id);
      setAlerts(Array.isArray(data) ? data : data?.items || []);
    } catch {
      setAlerts([]);
    } finally {
      setLoadingAlerts(false);
    }
  };

  return (
    <Modal isOpen={true} onClose={onClose} title="案件详情">
      <div className="space-y-4 max-h-[70vh] overflow-y-auto">
        <div className="flex items-center gap-2">
          <span className="text-sm font-mono text-cyber-blue">{caseData.case_number}</span>
          <Badge variant={priorityColors[caseData.priority] as any || "default"}>
            {priorityLabels[caseData.priority] || caseData.priority}
          </Badge>
          <Badge variant="outline">{statusLabels[caseData.status] || caseData.status}</Badge>
        </div>
        <h3 className="text-lg font-semibold">{caseData.name}</h3>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div><span className="text-muted-foreground">类型:</span> {caseTypeLabels[caseData.case_type] || caseData.case_type}</div>
          <div><span className="text-muted-foreground">主办人:</span> {caseData.assignee || "未分配"}</div>
          <div><span className="text-muted-foreground">告警数:</span> {caseData.alert_count || 0}</div>
          <div><span className="text-muted-foreground">人员数:</span> {caseData.person_count || 0}</div>
          <div><span className="text-muted-foreground">创建时间:</span> {formatDate(caseData.created_at)}</div>
          <div><span className="text-muted-foreground">更新时间:</span> {formatDate(caseData.updated_at)}</div>
        </div>
        {caseData.description && (
          <div>
            <label className="text-sm text-muted-foreground">描述</label>
            <p className="text-sm mt-1 bg-secondary/50 p-3 rounded">{caseData.description}</p>
          </div>
        )}
        <div>
          <label className="text-sm text-muted-foreground">关联告警</label>
          {loadingAlerts ? (
            <div className="flex justify-center py-4">
              <div className="animate-spin w-6 h-6 border-2 border-cyber-blue border-t-transparent rounded-full" />
            </div>
          ) : alerts.length === 0 ? (
            <p className="text-sm text-muted-foreground mt-1">暂无关联告警</p>
          ) : (
            <div className="space-y-2 mt-2">
              {alerts.map((a: any) => (
                <div key={a.id} className="flex items-center gap-2 p-2 bg-secondary/30 rounded text-sm">
                  <AlertTriangle size={14} className="text-yellow-500 shrink-0" />
                  <span className="truncate">{a.keyword_text || a.matched_text || `告警 #${a.id}`}</span>
                  <Badge variant="outline" className="ml-auto shrink-0 text-xs">{a.alert_level}</Badge>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="flex gap-3 pt-4">
          <Button variant="ghost" className="flex-1 min-h-[44px]" onClick={onClose}>关闭</Button>
        </div>
      </div>
    </Modal>
  );
}
