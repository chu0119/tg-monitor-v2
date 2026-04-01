# TG Monitor v2 - 开发规格

## 项目目标
将现有的TG监控系统改造为"傻瓜式部署"版本：
1. 一键部署（start.sh）
2. Web配置（告别.env）
3. 内置代理内核（mihomo + 订阅解析）
4. 开机自启

## 现有项目结构（保留不变的部分）
```
backend/         # FastAPI后端
frontend/        # React+TypeScript前端
docker/          # Docker配置
```

## 新增/修改的部分

### 1. 代理模块 (backend/proxy/)

#### 文件结构
```
backend/proxy/
├── __init__.py
├── manager.py           # 代理管理器（启停mihomo、切换节点、获取状态）
├── subscribe_parser.py  # 多格式订阅解析器
├── config_generator.py  # 生成mihomo配置文件
└── models.py            # 数据库模型
```

#### subscribe_parser.py 订阅解析器
支持的格式：
1. **Clash YAML格式**：直接解析proxies节点列表
2. **Base64编码**：解码后逐行解析
3. **SS (Shadowsocks) URI**：`ss://BASE64(method:password)@server:port#name`
4. **SSR URI**：`ssr://BASE64(...)`
5. **VMess URI**：`vmess://BASE64(json)`
6. **Trojan URI**：`trojan://password@server:port#name`
7. **Hysteria2 URI**：`hysteria2://...`
8. **VLESS URI**：`vless://uuid@server:port?...#name`

解析流程：
```
订阅链接内容
    ↓
检测格式（YAML/Base64/URI）
    ↓
解析为统一节点格式 NodeInfo
    ↓
返回节点列表 [{name, type, server, port, ...}]
```

统一节点格式：
```python
@dataclass
class ProxyNode:
    name: str           # 节点名称
    type: str           # ss/ssr/vmess/trojan/hysteria2/vless
    server: str         # 服务器地址
    port: int           # 端口
    params: dict        # 协议参数（method, password, uuid等）
```

#### config_generator.py 配置生成
根据选定的节点生成mihomo的config.yaml：
```yaml
mixed-port: 7897
allow-lan: false
mode: rule
log-level: warning

proxies:
  - name: "选中节点"
    type: ss/vmess/trojan/...
    server: ...
    port: ...

proxy-groups:
  - name: GLOBAL
    type: select
    proxies:
      - "选中节点"

rules:
  - MATCH,GLOBAL
```

#### manager.py 代理管理
```python
class ProxyManager:
    def __init__(self):
        self.mihomo_path = "proxy/mihomo"  # 内核路径
        self.config_path = "proxy/config.yaml"
        self.pid_file = "proxy/mihomo.pid"
    
    async def parse_subscription(self, url: str) -> list[ProxyNode]:
        """解析订阅链接，返回节点列表"""
    
    async def select_node(self, node: ProxyNode) -> bool:
        """选择节点，生成配置，重启mihomo"""
    
    async def start(self) -> bool:
        """启动mihomo内核"""
    
    async def stop(self) -> bool:
        """停止mihomo内核"""
    
    async def restart(self) -> bool:
        """重启mihomo内核"""
    
    async def get_status(self) -> dict:
        """获取代理状态（运行中/已停止、当前节点、延迟）"""
    
    async def test_node(self, node: ProxyNode) -> int:
        """测试节点延迟（ms）"""
```

#### 内置mihomo内核
- 将 /usr/bin/verge-mihomo 复制到 backend/proxy/mihomo
- 给予执行权限
- 同时支持amd64和arm64（通过start.sh检测架构下载对应版本）

### 2. 配置存储 (backend/)

#### 新增数据库表

**settings表**：
```sql
CREATE TABLE settings (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**accounts表**（新增，补充现有的telegram_accounts）：
```sql
CREATE TABLE accounts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    api_id VARCHAR(50),
    api_hash VARCHAR(100),
    phone VARCHAR(20),
    session_file VARCHAR(200),
    status ENUM('active', 'inactive', 'error') DEFAULT 'active',
    proxy_node VARCHAR(200),  -- 使用的代理节点名（可选，走全局代理则为空）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP
);
```

**proxy_nodes表**（缓存解析的节点）：
```sql
CREATE TABLE proxy_nodes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(200),
    type VARCHAR(20),
    server VARCHAR(200),
    port INT,
    config_json TEXT,     -- 完整节点配置JSON
    selected BOOLEAN DEFAULT FALSE,
    subscription_url TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 新增API路由

```
# 设置
GET    /api/settings                    # 获取所有配置
PUT    /api/settings                    # 更新配置（批量）
GET    /api/settings/:key               # 获取单个配置
PUT    /api/settings/:key               # 更新单个配置

# 账号管理
GET    /api/accounts                    # 账号列表
POST   /api/accounts                    # 添加账号
PUT    /api/accounts/:id                # 更新账号
DELETE /api/accounts/:id                # 删除账号
POST   /api/accounts/:id/toggle         # 启用/禁用账号

# 代理管理
GET    /api/proxy/status                # 代理状态
POST   /api/proxy/subscribe             # 解析订阅链接
GET    /api/proxy/nodes                 # 节点列表
POST   /api/proxy/nodes/:id/select      # 选择节点
POST   /api/proxy/nodes/:id/test        # 测试节点延迟
POST   /api/proxy/start                 # 启动代理
POST   /api/proxy/stop                  # 停止代理
POST   /api/proxy/restart               # 重启代理

# 系统
GET    /api/system/status               # 系统状态（环境、服务、DB）
POST   /api/system/init-db              # 初始化数据库
POST   /api/system/test-connection      # 测试数据库连接
```

### 3. 后端启动逻辑改造

现有启动流程（backend/main.py或类似入口）需要改造：
```python
# 原来的流程：
# 读.env → 连接DB → 启动监控

# 新流程：
# 1. 检查DB是否存在 → 不存在则自动创建
# 2. 读settings表 → 获取配置
# 3. 如果没有配置（首次启动）→ 后端正常启动API，但不启动监控
# 4. 如果有配置 → 启动代理（如果配置了）→ 启动监控
# 5. API始终可用（即使没有配置，也可以访问设置页面）
```

### 4. 前端改动

#### 新增页面

**设置向导页** (`/setup`)：
- 首次启动自动跳转
- Step 1: 代理设置（订阅链接 + 节点选择 + 测试连接）
- Step 2: 添加TG账号（API ID/Hash/手机号）
- Step 3: 通知设置（Bot Token，可跳过）
- 完成后跳转Dashboard

**代理管理页** (`/settings/proxy`)：
- 当前状态显示（运行中/已停止、当前节点、延迟）
- 订阅链接管理（添加/更新/删除多个订阅）
- 节点列表（名称、类型、延迟、选中状态）
- 一键测试所有节点延迟
- 代理端口设置

**账号管理页改版** (`/settings/accounts`)：
- 账号列表（手机号、状态、最后活跃时间）
- 添加账号表单（API ID、API Hash、手机号）
- 删除账号
- 启用/禁用

**系统设置页** (`/settings/general`)：
- 监控相关设置
- 通知相关设置
- 日志级别
- 数据保留天数

#### 首次启动检测
```typescript
// App.tsx 或路由守卫
const { data: settings } = useQuery('/api/settings')
const isInitialized = settings?.initialized === 'true'

if (!isInitialized) {
  navigate('/setup')
}
```

#### 侧边栏导航更新
新增菜单项：
- ⚙️ 系统设置
  - 🌐 代理管理
  - 👤 账号管理  
  - 🔔 通知设置
  - 📊 系统状态

### 5. start.sh 一键部署脚本

```bash
#!/bin/bash
# TG Monitor v2 - 一键部署脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 检测标记
MARKER_FILE=".deployed"

if [ "$1" = "--reset" ]; then
    rm -f $MARKER_FILE
    echo -e "${YELLOW}已重置部署状态${NC}"
fi

echo "================================"
echo "  TG Monitor v2 - 自动部署"
echo "================================"

# Step 1: 检测环境
echo -e "\n${YELLOW}[1/6] 检测环境...${NC}"

check_command() {
    if command -v $1 &> /dev/null; then
        echo -e "  ${GREEN}✅ $1 $(($1 --version 2>/dev/null | head -1))${NC}"
        return 0
    else
        echo -e "  ${RED}❌ $1 未安装${NC}"
        return 1
    fi
}

NEED_INSTALL=""
check_command python3 || NEED_INSTALL="$NEED_INSTALL python3"
check_command node || NEED_INSTALL="$NEED_INSTALL node"
check_command npm || NEED_INSTALL="$NEED_INSTALL npm"
check_command mysql || NEED_INSTALL="$NEED_INSTALL mysql-server"

# Step 2: 安装缺失依赖
if [ -n "$NEED_INSTALL" ]; then
    echo -e "\n${YELLOW}[2/6] 安装缺失依赖...${NC}"
    sudo apt-get update
    for pkg in $NEED_INSTALL; do
        echo -e "  ${YELLOW}⏳ 安装 $pkg...${NC}"
        sudo apt-get install -y $pkg
        echo -e "  ${GREEN}✅ $pkg 已安装${NC}"
    done
else
    echo -e "\n${GREEN}[2/6] 依赖检查通过${NC}"
fi

# Step 3: Python/Node依赖
echo -e "\n${YELLOW}[3/6] 安装项目依赖...${NC}"
[ ! -f backend/venv ] && python3 -m venv backend/venv
source backend/venv/bin/activate
pip install -r backend/requirements.txt -q
cd frontend && npm install --silent && cd ..
echo -e "${GREEN}  ✅ 依赖安装完成${NC}"

# Step 4: 数据库初始化
echo -e "\n${YELLOW}[4/6] 初始化数据库...${NC}"
# 自动创建数据库和表
python3 backend/init_db.py
echo -e "${GREEN}  ✅ 数据库初始化完成${NC}"

# Step 5: 下载mihomo内核
echo -e "\n${YELLOW}[5/6] 检查代理内核...${NC}"
ARCH=$(uname -m)
if [ "$ARCH" = "x86_64" ]; then
    MARCH="amd64"
elif [ "$ARCH" = "aarch64" ]; then
    MARCH="arm64"
fi
if [ ! -f backend/proxy/mihomo ]; then
    echo -e "  ${YELLOW}⏳ 下载mihomo ($MARCH)...${NC}"
    # 从GitHub releases下载
    curl -sL "https://github.com/MetaCubeX/mihomo/releases/download/v1.19.21/mihomo-linux-$MARCH-v1.19.21.gz" | gunzip > backend/proxy/mihomo
    chmod +x backend/proxy/mihomo
fi
echo -e "${GREEN}  ✅ 代理内核就绪${NC}"

# Step 6: 配置systemd
echo -e "\n${YELLOW}[6/6] 配置服务...${NC}"
PROJECT_DIR=$(pwd)
# 生成并安装service文件
cat > /tmp/tgmonitor-backend.service << EOF
[Unit]
Description=TG Monitor Backend
After=network.target mysql.service
[Service]
Type=simple
WorkingDirectory=$PROJECT_DIR/backend
ExecStart=$PROJECT_DIR/backend/venv/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
EOF
sudo cp /tmp/tgmonitor-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable tgmonitor-backend
echo -e "${GREEN}  ✅ 开机自启已配置${NC}"

# 启动服务
echo -e "\n${YELLOW}启动服务...${NC}"
sudo systemctl start tgmonitor-backend
# 前端用pm2或简单nohup
cd frontend && nohup npm run dev > /dev/null 2>&1 &
echo -e "${GREEN}  ✅ 服务已启动${NC}"

# 标记已部署
touch $MARKER_FILE

echo -e "\n================================"
echo -e "${GREEN}✅ 部署完成！${NC}"
echo -e "🌐 http://localhost:3000"
echo -e "================================"
```

### 6. 不需要改的部分
- 现有的监控逻辑（Telegram消息采集、告警、关键词匹配等）
- 现有的数据库模型（大部分保留）
- Docker配置（保留，但不是主要部署方式）

## 开发优先级

P0（必须完成）：
1. settings表 + settings API
2. accounts API（增删改查）
3. 代理模块（subscribe_parser + config_generator + manager）
4. 代理API
5. 前端设置向导
6. 前端代理管理页
7. 前端账号管理页
8. start.sh部署脚本

P1（重要）：
9. systemd服务自动配置
10. 节点延迟测试
11. 多订阅源管理
12. 系统状态页

P2（锦上添花）：
13. 代理日志查看
14. 流量统计
15. 自动选择最快节点
