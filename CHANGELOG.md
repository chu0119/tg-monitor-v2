# 更新日志 (Changelog)

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/) 规范。

---

## [2.0.0] - 2026-07-07

### 🚀 新增功能

#### 多Worker架构
- **API Worker**：独立处理HTTP请求，支持水平扩展
- **Monitor Worker**：独立运行Telegram监控，每个Worker管理3-5个账号
- **自动化部署脚本**：`deploy-auto.sh` 一键部署多Worker架构
- **Worker状态API**：`/status`、`/health` 端点监控Worker状态

#### 健康检查API
- `GET /api/v1/health/` - 基础探活
- `GET /api/v1/health/detailed` - 详细状态（数据库、Redis、系统、Telegram）
- `GET /api/v1/health/metrics` - 性能指标

#### 代码质量
- **统一错误处理**：`AppException` 异常体系，标准化错误响应
- **输入验证**：Pydantic验证器，防止无效输入
- **代码审查**：修复15个代码质量问题

### ⚡ 性能优化

#### Dashboard API 性能提升
| API | 优化前 | 优化后 | 提升倍数 |
|-----|--------|--------|----------|
| `/dashboard/stats` | 3.4秒 | 0.17ms | 20,000x |
| `/dashboard/sender-ranking` | 11秒 | 0.2ms | 55,000x |
| `/dashboard/conversation-activity` | 9秒 | 20ms | 450x |
| 串行加载总时间 | 15秒 | 0.24秒 | 62x |

#### 优化技术
- **预计算字段**：添加 `sender_count` 到 conversations 表
- **子查询优化**：避免大表JOIN
- **近似计数**：使用 `information_schema` 获取大表行数
- **Redis缓存**：所有API结果缓存60秒
- **虚拟滚动**：React Virtuoso 优化大列表

### 🐛 Bug修复

#### 严重Bug
- **修复 `database is locked` 错误**：SQLite session文件并发访问冲突
- **修复 Redis连接失败返回False**：导致TypeError崩溃
- **修复 worker_id=0 被忽略**：falsy值处理错误
- **修复端口冲突Bug**：Worker端口分配错误

#### 功能Bug
- **修复分页重置问题**：筛选条件改变时自动重置到第1页
- **修复代理配置问题**：socks5 → socks5h（DNS通过代理解析）
- **修复Session文件损坏**：添加文件锁保护

### 🔒 安全改进
- **APIKeyAuth中间件**：支持API密钥认证
- **统一异常处理**：避免暴露内部错误信息
- **输入验证**：防止SQL注入和XSS攻击

### 📝 代码优化
- **错误处理**：统一的AppException异常体系
- **日志优化**：添加Worker ID到日志格式
- **配置管理**：Worker配置独立管理

### 📦 部署改进
- **Systemd服务**：支持多Worker独立服务
- **Nginx配置**：负载均衡配置
- **自动化部署**：一键部署脚本

---

## [1.1.0] - 2026-06-25

### ⚡ 性能优化
- **Redis缓存**：Dashboard API添加Redis缓存
- **数据库索引**：添加组合索引优化查询
- **连接池优化**：调整MySQL连接池参数

### 🐛 Bug修复
- **修复消息不更新**：Telegram客户端重连逻辑优化
- **修复Session文件损坏**：添加asyncio.Lock保护

### 📝 功能改进
- **告警中心**：支持手机号筛选
- **大屏展示**：优化可视化效果
- **数据导出**：支持CSV导出

---

## [1.0.0] - 2026-04-15

### 🎉 首次发布

#### 核心功能
- **实时监控**：多账号并行监控Telegram群组
- **关键词告警**：多级告警 + 正则匹配
- **数据分析**：Dashboard + 大屏可视化
- **多渠道通知**：邮件/钉钉/企业微信/Webhook
- **系统管理**：账号管理/代理配置/备份恢复
- **一键部署**：自动化部署脚本

#### 技术栈
- 后端：FastAPI + SQLAlchemy + Telethon
- 前端：React + TypeScript + TailwindCSS
- 数据库：MySQL 8.0
- 缓存：Redis 7.x

---

## 版本说明

### 版本号格式
```
MAJOR.MINOR.PATCH
```
- **MAJOR**：不兼容的API变更
- **MINOR**：向下兼容的功能新增
- **PATCH**：向下兼容的问题修正

### 发布周期
- **MAJOR**：重大架构变更时发布
- **MINOR**：每月发布（如有新功能）
- **PATCH**：每周发布（如有Bug修复）

### 升级指南

#### 从 v1.x 升级到 v2.0
1. 备份数据库和配置文件
2. 拉取最新代码：`git pull`
3. 安装新依赖：`pip install -r requirements.txt`
4. 更新数据库：`python init_db.py`
5. 重新构建前端：`cd frontend && npm run build`
6. 重启服务：`systemctl restart tgmonitor-backend`

#### 配置变更
- 新增 `workers/config.json`：Worker配置
- 新增 `workers/deploy-auto.sh`：自动化部署脚本
- 修改 `.env`：无变更

---

## 贡献指南

### 提交规范
```
<type>(<scope>): <subject>

<body>

<footer>
```

**Type 类型：**
- `feat`：新功能
- `fix`：Bug修复
- `perf`：性能优化
- `refactor`：重构
- `docs`：文档更新
- `test`：测试相关
- `chore`：构建/工具相关

**示例：**
```
feat(dashboard): 添加Redis缓存

- 添加Dashboard统计API缓存
- 优化发送者排行查询
- 性能提升20倍

Closes #123
```

---

## 问题反馈

### GitHub Issues
- 提交Bug报告：https://github.com/chu0119/tg-monitor-v2/issues
- 功能建议：https://github.com/chu0119/tg-monitor-v2/issues

### 问题模板
```markdown
**描述**
简要描述问题

**复现步骤**
1. 访问 '...'
2. 点击 '...'
3. 看到错误

**期望行为**
描述期望的行为

**实际行为**
描述实际的行为

**环境信息**
- 操作系统：[例如 Ubuntu 22.04]
- Python版本：[例如 3.12]
- 浏览器：[例如 Chrome 120]
```

---

## 许可证

本项目采用 [MIT 许可证](LICENSE)。

---

**最后更新：2026-07-07**
