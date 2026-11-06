# TG Monitor v2 — 产品深度剖析与商用化重构方案

> 版本：v3.0 路线图（2026-11-06）
> 依据：5 份深度代码审计（约 200 个问题）+ 服务器运行时证据 + 前端全页面走查
> 目标：**可商用交付**——数据零丢失、系统稳定运行、功能符合设计预期、面向大屏演示与移动端查看

---

## 一、产品定位

Telegram 群组/频道监控告警系统，核心价值链：

```
TG 群消息 → 实时采集(多账号) → 关键词匹配 → 告警产生 → 通知送达(TG Bot/邮件/Webhook)
                                        ↘ 消息入库 → 手机号情报提取 → 人员档案(一人一档)
                                        ↘ 大屏展示 / 仪表盘 / 数据分析 / 案件管理
```

**用户场景**（按重要性排序）：
1. 情报人员日常盯告警、处理告警（Web 端，/alerts /monitoring /personnel /phone-intel）
2. 领导展示（/bigscreen 大屏 + /dashboard）
3. 移动端随时查看告警（响应式，目前未专门优化）
4. 系统管理员（/accounts /settings /notifications /audit）

---

## 二、功能清单审计

### ✅ 核心可用（保住并强化）
| 功能 | 状态 | 备注 |
|---|---|---|
| 多账号 TG 监控 | ⚠️ 可用但带病 | session 跨进程冲突（已修主入口）；291 监控运行中 |
| 消息采集入库 | ⚠️ 带病 | **跨会话消息 ID 碰撞静默丢消息**（P0，需迁移）；编辑消息不更新 |
| 关键词匹配告警 | ⚠️ 带病 | 批路径 caption 不匹配（已修）；同义词生产不生效；ReDoS 风险 |
| 告警管理/工作流 | ✅ 基本可用 | 升级降级 Bug（已修）；PUT/POST 双指派端点（已修兼容） |
| 通知发送 | ⚠️ 带病 | HTML 转义缺失致部分消息永发失败（已修）；重试无痕迹；内存队列重启丢 |
| 手机号情报 | ⚠️ 严重残缺 | 实时路径不提取（已修）；phone_records 无唯一索引同号膨胀；详情页群聊恒空（已修） |
| 人员档案 | ✅ 可用 | ILIKE 慢查询需优化 |
| 会话管理 | ✅ 可用 | 批量操作计数丢失（已修）；跨页搜索失效（待修） |

### ⚠️ 残缺功能（要么修完，要么明确砍掉）
| 功能 | 现状 | 决策 |
|---|---|---|
| **初始化向导 /setup** | 页面存在但路由未注册 → **不可达**，全新部署无法初始化 | **修复**：补路由 + 初始化检查 |
| **数据分析页 /analysis** | 情感分析 Tab 因 conversationId 永远为 null 不可用；导航无入口 | **修复**：补会话选择器 + 导航入口 |
| **案件管理 /cases** | API 完整但前端刚起步；编号并发冲突；无 FK 约束 | **保留**：补 unique 约束 |
| **布控名单 /watchlist** | 基础 CRUD 可用，缺唯一约束同实体重复上榜 | **保留**：补约束 |
| **审计日志 /audit** | 可用（统计卡已修）；三套审计写入实现并存 | **收敛**到 audit_service |
| **代理管理 /proxy** | 新版订阅/节点端点已下线(410)，页面还展示旧 UI | **简化**：只保留代理配置+测试+延迟 |
| **在线更新 /system/perform-update** | git pull+pip+npm+systemctl 全自动，等于 RCE 接口；Windows 下必挂 | **重写**：保守化+强制鉴权 |
| **数据库管理 /database** | test-connection 失效（已修）；clear 全库无二次防护 | **加固** |
| **迁移导入导出 /migration** | 导出含 .env 明文密钥；导入内存爆炸 | **已修安全项**；导出排除敏感行（待做） |

### 🗑️ 死代码/孤儿（删除）
| 项 | 位置 |
|---|---|
| 旧单进程入口 main.py 与 4 个启动脚本 | backend/app/main.py、start-optimized.sh、start-gunicorn.sh（与 worker 架构双轨冲突，README 还指向它） |
| health_detailed.py | 未注册的死模块（api_worker 用内联版） |
| users/roles/user_roles/audit_logs 模型 + auth_service | JWT 体系从未接线（SECRET_KEY Bug 就是它带的），真鉴权是 API Key 中间件 |
| SessionFileLock | 死代码且引用未导入的 fcntl |
| redis_cache.py（同步 Redis） | 无消费方，还会阻塞事件循环 |
| MonitoringPageOptimized.tsx / DashboardOptimized.tsx | 死页面（引用不存在的模块） |
| routes/ 目录 18 个死文件（除 personnel.tsx） | 手写路由树未引用 |
| createWebSocket() in api.ts | 与 useWebSocket 双实现，on() 叠加 listener 泄漏 |
| 旧字段 assignee/assignee_note（长期） | 双写兼容一版后删列 |
| telegram_accounts 冗余索引 idx_user_id、senders 重复索引 | 线上重复索引 |

### ➕ 建议新增（面向商用与演示）
1. **告警 WebSocket 实时推送**（后端已具备 publish 链路，补 new_alert 事件 + 前端订阅）→ 大屏告警零延迟
2. **大屏轮询分级 + 自动适配**（stats 15s / 排行 60s / 告警走 WS）+ 演示模式隐藏敏感手机号（领导屏防泄露）
3. **移动端响应式**：MainLayout 侧边栏折叠、告警卡片化、关键页（alerts/monitoring/dashboard）手机可用
4. **数据自动归档**：alerts 226 万行/10.5GB（78% 已删空间未回收）→ 清理任务 + `OPTIMIZE TABLE` 定期归档压缩；message_preview 截断 500 字符（当前全文存储是表膨胀根因）
5. **备份可用性**：首次备份逻辑修复 + 备份成功/失败通知到 TG Bot（灾备可感知）
6. **系统健康页**：把 /health/detailed 的管道健康（matched_without_alert、通知失败率）做成前端页面，出问题运维先知道
7. **告警通知失败补偿**：启动时扫描 notification_sent=0 的近 1h 告警重新入队

---

## 三、已完成的修复（本仓库 4 个提交，均为高危项）

见 `git log e44b81e..d48685f`：监控管道 5 项、API 安全 7 项、服务层 9 项、前端 4 项。
关键点：**session 跨进程冲突三大入口已堵**（账号归属过滤 + /monitoring 控制转发 + 订阅失败不再带崩）、**SetupPage 无法初始化已修**、**迁移/备份三个安全漏洞已修**。

---

## 〇、迭代状态

| 迭代 | 状态 | 内容 |
|---|---|---|
| 迭代1（2026-11-06 已上线 60ce65d） | ✅ | 时区口径统一（+08:00锚定/SQL NOW()比较/序列化分流）、通知可靠性（原子计数/失败痕迹/补偿扫描）、性能快赢（stats缓存4.8s→2.9ms/键集分页导出/冗余列）、前端竞态修复、safe_optimize.sh |
| 迭代2 | 待做 | 消息主键长期迁移（自增PK+UNIQUE(conv,tg_id)，需停机窗口）、alerts OPTIMIZE（用 scripts/safe_optimize.sh 手动执行）、键集分页全覆盖 |
| 迭代3 | 待做 | 移动端深度适配、大屏演示模式（手机号脱敏开关）、系统健康可视化页 |

时区口径约定（后续开发必读）：
- `created_at`/`updated_at`/`handled_at` 等服务器列 = DB NOW() 口径（+08:00）→ 序列化用 `datetime_to_local_iso`，比较用 SQL `NOW() - INTERVAL`
- `messages.date`/`keywords.last_matched_at` = UTC → 序列化用 `datetime_to_iso`，比较用 Python `now_utc()`
- 连接时区已由 init_command 锚定，勿在会话里再 SET time_zone

## 四、阶段计划

### 阶段 2：架构收敛与数据正确性（本地改造）
1. **删除死代码**（上表 🗑️ 全部）——README/启动脚本同步改为 worker 架构
2. **消息 ID 碰撞修复**（P0）：短期方案——查重与插入冲突判定全部补上 conversation_id 维度，跨会话碰撞时生成替代 ID（`conv_slot * 10^10 + tg_msg_id`），不动表结构零风险；长期（自增 PK + UNIQUE(conversation_id, tg_message_id)）列入迁移脚本
3. **编辑消息更新**：事件带 event_type，已存在消息走 UPDATE 分支 + 重跑匹配
4. **时区统一**：DB 连接级 `SET time_zone=+00:00`，全服务统一 `db_now()`，序列化收敛为一个函数（展示层转 +08:00）
5. **DB 治理脚本**（一次性，部署时执行）：补缺失索引（alerts(status,created_at) 等 8 项）、删重复索引、phone_records 加 UNIQUE(phone)、case_alerts/watchlist/conversations 唯一约束、alerts 表 OPTIMIZE 回收 8GB、清理阈值默认值统一
6. **灾备链路**：备份管道化防 OOM、首次备份即时执行、备份结果通知、清理任务回扣计数器

### 阶段 3：体验与商用化
1. 大屏：WS 告警推送 + 轮询分级 + 手机号脱敏开关
2. 移动端响应式（MainLayout 折叠导航 + alerts/dashboard 适配）
3. 功能补全：/setup 路由、/analysis 修复、导航补全
4. 前端字段/参数统一走 buildParams（空串过滤）、204 处理

### 阶段 4：验证与交付
1. 后端全量 py_compile + import 冒烟；前端 build + 关键页手测清单
2. 服务器部署：**先 mysqldump 全量备份 + git 快照** → 分步重启（api → monitor）→ /health 与监控数验证 → 观察期 24h（database is locked 应归零）
3. 回滚预案：git reset + 备份 SQL 恢复，10 分钟内可回退

---

## 五、风险与硬约束

- **历史数据零丢失**：所有 DB 变更脚本先备份再执行；消息表迁移采用增量兼容方案，不做破坏性重建
- **线上监控不断流**：部署选低峰窗口，monitor_worker 重启期间消息靠 Telethon catch_up 补拉（已启用）
- **服务器访问 GitHub 慢**：继续走 bundle + SFTP 同步
