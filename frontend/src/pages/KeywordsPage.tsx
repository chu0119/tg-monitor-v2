import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import {
  Key,
  Plus,
  Edit,
  Trash2,
  Upload,
  Search,
  FolderOpen,
  Tag,
} from "lucide-react";

interface KeywordGroup {
  id: number;
  name: string;
  description?: string;
  match_type: string;
  alert_level: string;
  is_active: boolean;
  total_keywords: number;
  total_matches: number;
  color?: string;
}

interface Keyword {
  id: number;
  group_id: number;
  word: string;
  is_active: boolean;
  match_count: number;
}

export function KeywordsPage() {
  const [groups, setGroups] = useState<KeywordGroup[]>([]);
  const [selectedGroup, setSelectedGroup] = useState<KeywordGroup | null>(null);
  const [keywords, setKeywords] = useState<Keyword[]>([]);
  const [loading, setLoading] = useState(true);
  const [showGroupModal, setShowGroupModal] = useState(false);
  const [showKeywordModal, setShowKeywordModal] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [editingKeyword, setEditingKeyword] = useState<Keyword | null>(null);
  const [editingGroup, setEditingGroup] = useState<KeywordGroup | null>(null);

  // 分页状态
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [totalCount, setTotalCount] = useState(0);

  useEffect(() => {
    fetchGroups();
  }, []);

  const fetchGroups = async () => {
    setLoading(true);
    try {
      const data = await api.keywords.listGroups();
      setGroups(data);
    } catch (error) {
      console.error("Failed to fetch keyword groups:", error);
    } finally {
      setLoading(false);
    }
  };

  const fetchKeywords = async (groupId: number, page: number = 1) => {
    try {
      // 后端关键词API可能不支持分页，这里在客户端分页
      const data = await api.keywords.listKeywords(groupId);
      setKeywords(data);
      setTotalCount(data.length);
    } catch (error) {
      console.error("Failed to fetch keywords:", error);
    }
  };

  const handleGroupClick = (group: KeywordGroup) => {
    setSelectedGroup(group);
    setCurrentPage(1);
    fetchKeywords(group.id);
  };

  const handleCreateGroup = async (data: any) => {
    try {
      await api.keywords.createGroup(data);
      fetchGroups();
      setShowGroupModal(false);
    } catch (error) {
      console.error("Failed to create group:", error);
    }
  };

  const handleUpdateGroup = async (data: any) => {
    if (!editingGroup) return;
    try {
      await api.keywords.updateGroup(editingGroup.id, data);
      fetchGroups();
      // 更新选中的组
      if (selectedGroup?.id === editingGroup.id) {
        setSelectedGroup({ ...selectedGroup, ...data });
      }
      setShowGroupModal(false);
      setEditingGroup(null);
    } catch (error) {
      console.error("Failed to update group:", error);
      alert("更新关键词组失败");
    }
  };

  const handleDeleteGroup = async (groupId: number) => {
    if (!confirm("确定要删除这个关键词组吗？组内的所有关键词也会被删除。")) {
      return;
    }
    try {
      await api.keywords.deleteGroup(groupId);
      fetchGroups();
      // 如果删除的是当前选中的组，清空选中状态
      if (selectedGroup?.id === groupId) {
        setSelectedGroup(null);
        setKeywords([]);
      }
    } catch (error) {
      console.error("Failed to delete group:", error);
      alert("删除关键词组失败");
    }
  };

  const handleEditGroup = (group: KeywordGroup) => {
    setEditingGroup(group);
    setShowGroupModal(true);
  };

  const handleCreateKeyword = async (word: string) => {
    if (!selectedGroup) return;
    try {
      await api.keywords.createKeyword({ group_id: selectedGroup.id, word });
      fetchKeywords(selectedGroup.id);
      fetchGroups();
      setShowKeywordModal(false);
    } catch (error) {
      console.error("Failed to create keyword:", error);
    }
  };

  const handleDeleteKeyword = async (id: number) => {
    if (!selectedGroup) return;
    try {
      await api.keywords.deleteKeyword(id);
      fetchKeywords(selectedGroup.id);
      fetchGroups();
    } catch (error) {
      console.error("Failed to delete keyword:", error);
    }
  };

  const handleEditKeyword = (keyword: Keyword) => {
    setEditingKeyword(keyword);
    setShowKeywordModal(true);
  };

  const handleUpdateKeyword = async (word: string) => {
    if (!selectedGroup || !editingKeyword) return;
    try {
      await api.keywords.updateKeyword(editingKeyword.id, { word });
      fetchKeywords(selectedGroup.id);
      fetchGroups();
      setShowKeywordModal(false);
      setEditingKeyword(null);
    } catch (error) {
      console.error("Failed to update keyword:", error);
      alert("更新关键词失败");
    }
  };

  const handleBatchImport = async (keywords: string[]) => {
    if (!selectedGroup) return;
    try {
      await api.keywords.batchImport({
        group_id: selectedGroup.id,
        keywords: keywords  // 直接传递字符串数组，不需要映射
      });
      fetchKeywords(selectedGroup.id);
      fetchGroups();
      setShowImportModal(false);
      alert(`成功导入 ${keywords.length} 个关键词`);
    } catch (error) {
      console.error("Failed to batch import keywords:", error);
      alert("批量导入失败，请检查格式");
    }
  };

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* 标题 */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold neon-text">关键词管理</h1>
          <p className="text-xs sm:text-sm text-muted-foreground mt-1">管理关键词组和关键词</p>
        </div>
        <Button variant="tech" onClick={() => setShowGroupModal(true)} className="w-full sm:w-auto min-h-[44px]">
          <Plus size={18} className="mr-2" />
          新建关键词组
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6">
        {/* 关键词组列表 */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <FolderOpen size={20} />
              关键词组
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="space-y-1 max-h-[600px] overflow-y-auto tech-scrollbar">
              {loading ? (
                <div className="p-4 text-center text-muted-foreground">加载中...</div>
              ) : groups.length === 0 ? (
                <div className="p-4 text-center text-muted-foreground">暂无关键词组</div>
              ) : (
                groups.map((group) => (
                  <div
                    key={group.id}
                    className={`group relative ${
                      selectedGroup?.id === group.id ? "bg-cyber-blue/20 border-l-2 border-cyber-blue" : ""
                    }`}
                  >
                    <button
                      onClick={() => handleGroupClick(group)}
                      className="w-full text-left px-4 py-3 hover:bg-cyber-blue/10 transition-colors"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <div
                              className="w-3 h-3 rounded-full"
                              style={{ backgroundColor: group.color || "#00f0ff" }}
                            />
                            <p className="font-medium truncate">{group.name}</p>
                          </div>
                          <p className="text-xs text-muted-foreground mt-0.5">
                            {group.total_keywords} 个关键词 · {group.total_matches} 次匹配
                          </p>
                        </div>
                        <Badge variant={group.is_active ? "success" : "outline"} className="ml-2">
                          {group.is_active ? "启用" : "禁用"}
                        </Badge>
                      </div>
                    </button>
                    {/* 编辑和删除按钮 */}
                    <div className="absolute right-2 top-1/2 -translate-y-1/2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 bg-background/80 hover:bg-background"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleEditGroup(group);
                        }}
                      >
                        <Edit size={14} />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 bg-background/80 hover:bg-cyber-pink/20"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteGroup(group.id);
                        }}
                      >
                        <Trash2 size={14} className="text-cyber-pink" />
                      </Button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>

        {/* 关键词列表 */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg flex items-center gap-2">
                <Tag size={20} />
                {selectedGroup?.name || "选择关键词组"}
              </CardTitle>
              {selectedGroup && (
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={() => setShowImportModal(true)}>
                    <Upload size={16} className="mr-2" />
                    批量导入
                  </Button>
                  <Button variant="tech" size="sm" onClick={() => setShowKeywordModal(true)}>
                    <Plus size={16} className="mr-2" />
                    添加关键词
                  </Button>
                </div>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {!selectedGroup ? (
              <div className="py-12 text-center text-muted-foreground">
                请先选择一个关键词组
              </div>
            ) : keywords.length === 0 ? (
              <div className="py-12 text-center text-muted-foreground">
                暂无关键词
              </div>
            ) : (
              <>
                <div className="space-y-2 max-h-[500px] overflow-y-auto tech-scrollbar pr-2 mb-4">
                  {keywords
                    .slice((currentPage - 1) * pageSize, currentPage * pageSize)
                    .map((keyword) => (
                      <div
                        key={keyword.id}
                        className="flex items-center justify-between p-3 rounded-lg bg-secondary/30 hover:bg-secondary/50 transition-colors"
                      >
                        <div className="flex items-center gap-3">
                          <Key size={18} className="text-cyber-blue" />
                          <span className={keyword.is_active ? "" : "text-muted-foreground line-through"}>
                            {keyword.word}
                          </span>
                          {keyword.match_count > 0 && (
                            <Badge variant="outline" className="text-xs">
                              匹配 {keyword.match_count} 次
                            </Badge>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          <Button variant="ghost" size="icon" onClick={() => handleEditKeyword(keyword)}>
                            <Edit size={16} />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleDeleteKeyword(keyword.id)}
                          >
                            <Trash2 size={16} className="text-cyber-pink" />
                          </Button>
                        </div>
                      </div>
                    ))}
                </div>

                {/* 分页控件 */}
                {totalCount > 0 && (
                  <div className="flex items-center justify-between pt-4 border-t border-cyber-blue/10">
                    <div className="text-sm text-muted-foreground">
                      共 {totalCount} 个关键词，第 {currentPage} 页
                    </div>
                    <div className="flex items-center gap-2">
                      <select
                        value={pageSize}
                        onChange={(e) => {
                          setPageSize(parseInt(e.target.value));
                          setCurrentPage(1);
                        }}
                        className="input-tech px-3 py-1.5 rounded-lg text-sm"
                      >
                        <option value="10">10条/页</option>
                        <option value="20">20条/页</option>
                        <option value="50">50条/页</option>
                        <option value="100">100条/页</option>
                      </select>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={currentPage === 1}
                        onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                      >
                        上一页
                      </Button>
                      <span className="text-sm">
                        第 {currentPage} / {Math.ceil(totalCount / pageSize)} 页
                      </span>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={currentPage >= Math.ceil(totalCount / pageSize)}
                        onClick={() => setCurrentPage(currentPage + 1)}
                      >
                        下一页
                      </Button>
                    </div>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* 创建/编辑关键词组弹窗 */}
      {showGroupModal && (
        <CreateGroupModal
          onClose={() => {
            setShowGroupModal(false);
            setEditingGroup(null);
          }}
          onSubmit={editingGroup ? handleUpdateGroup : handleCreateGroup}
          group={editingGroup}
        />
      )}

      {/* 添加/编辑关键词弹窗 */}
      {showKeywordModal && (
        <CreateKeywordModal
          onClose={() => {
            setShowKeywordModal(false);
            setEditingKeyword(null);
          }}
          onSubmit={editingKeyword ? handleUpdateKeyword : handleCreateKeyword}
          keyword={editingKeyword}
        />
      )}

      {/* 批量导入弹窗 */}
      {showImportModal && (
        <BatchImportModal onClose={() => setShowImportModal(false)} onSubmit={handleBatchImport} />
      )}
    </div>
  );
}

function CreateGroupModal({
  onClose,
  onSubmit,
  group
}: {
  onClose: () => void;
  onSubmit: (data: any) => void;
  group: KeywordGroup | null;
}) {
  const [name, setName] = useState(group?.name || "");
  const [description, setDescription] = useState(group?.description || "");
  const [matchType, setMatchType] = useState(group?.match_type || "contains");
  const [alertLevel, setAlertLevel] = useState(group?.alert_level || "medium");
  const [isActive, setIsActive] = useState(group?.is_active !== undefined ? group.is_active : true);

  const handleSubmit = () => {
    onSubmit({
      name,
      description,
      match_type: matchType,
      alert_level: alertLevel,
      is_active: isActive
    });
  };

  return (
    <Modal isOpen={true} onClose={onClose} title={group ? "编辑关键词组" : "创建关键词组"}>
      <div className="space-y-4">
        <div>
          <label className="text-sm text-muted-foreground">名称</label>
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="输入关键词组名称" />
        </div>
        <div>
          <label className="text-sm text-muted-foreground">描述</label>
          <Input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="输入描述（可选）"
          />
        </div>
        <div>
          <label className="text-sm text-muted-foreground">匹配类型</label>
          <select
            value={matchType}
            onChange={(e) => setMatchType(e.target.value)}
            className="input-tech w-full px-4 py-2 rounded-lg"
          >
            <option value="contains">包含匹配</option>
            <option value="exact">精确匹配</option>
            <option value="regex">正则表达式</option>
          </select>
        </div>
        <div>
          <label className="text-sm text-muted-foreground">告警级别</label>
          <select
            value={alertLevel}
            onChange={(e) => setAlertLevel(e.target.value)}
            className="input-tech w-full px-4 py-2 rounded-lg"
          >
            <option value="low">低</option>
            <option value="medium">中</option>
            <option value="high">高</option>
            <option value="critical">严重</option>
          </select>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="is_active"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
            className="w-4 h-4 rounded"
          />
          <label htmlFor="is_active" className="text-sm text-muted-foreground">
            启用此关键词组
          </label>
        </div>
        <div className="flex gap-3 pt-4">
          <Button variant="tech" className="flex-1" onClick={handleSubmit}>
            {group ? "更新" : "创建"}
          </Button>
          <Button variant="ghost" className="flex-1" onClick={onClose}>
            取消
          </Button>
        </div>
      </div>
    </Modal>
  );
}

function CreateKeywordModal({ onClose, onSubmit, keyword }: { onClose: () => void; onSubmit: (word: string) => void; keyword: Keyword | null }) {
  const [word, setWord] = useState(keyword?.word || "");

  const handleSubmit = () => {
    if (word.trim()) {
      onSubmit(word.trim());
    }
  };

  return (
    <Modal isOpen={true} onClose={onClose} title={keyword ? "编辑关键词" : "添加关键词"}>
      <div className="space-y-4">
        <div>
          <label className="text-sm text-muted-foreground">关键词</label>
          <Input
            value={word}
            onChange={(e) => setWord(e.target.value)}
            placeholder="输入关键词"
            onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
          />
        </div>
        <div className="flex gap-3 pt-4">
          <Button variant="tech" className="flex-1" onClick={handleSubmit}>
            {keyword ? "更新" : "添加"}
          </Button>
          <Button variant="ghost" className="flex-1" onClick={onClose}>
            取消
          </Button>
        </div>
      </div>
    </Modal>
  );
}

function BatchImportModal({ onClose, onSubmit }: { onClose: () => void; onSubmit: (keywords: string[]) => void }) {
  const [keywords, setKeywords] = useState("");

  const handleSubmit = () => {
    const keywordList = keywords
      .split("\n")
      .map(k => k.trim())
      .filter(k => k.length > 0);

    if (keywordList.length > 0) {
      onSubmit(keywordList);
    } else {
      alert("请输入至少一个关键词");
    }
  };

  return (
    <Modal isOpen={true} onClose={onClose} title="批量导入关键词">
      <div className="space-y-4">
        <div>
          <label className="text-sm text-muted-foreground">关键词列表</label>
          <p className="text-xs text-muted-foreground mb-2">每行一个关键词</p>
          <textarea
            value={keywords}
            onChange={(e) => setKeywords(e.target.value)}
            placeholder="关键词1&#10;关键词2&#10;关键词3"
            className="input-tech w-full h-48 px-4 py-3 rounded-lg resize-none"
          />
        </div>
        <div className="flex gap-3 pt-4">
          <Button variant="tech" className="flex-1" onClick={handleSubmit}>
            导入 {keywords.split("\n").filter(k => k.trim()).length} 个关键词
          </Button>
          <Button variant="ghost" className="flex-1" onClick={onClose}>
            取消
          </Button>
        </div>
      </div>
    </Modal>
  );
}
