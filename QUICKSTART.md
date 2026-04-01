# 快速开始指南

## 5分钟快速部署

### 1. 安装依赖

```bash
./start.sh install
```

### 2. 配置数据库

#### 安装 MySQL
```bash
sudo apt update && sudo apt install mysql-server -y
sudo mysql_secure_installation
```

#### 创建数据库
```bash
sudo mysql -u root -p
```

```sql
CREATE DATABASE tg_monitor CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'tgmonitor'@'localhost' IDENTIFIED BY 'TgMonitor2026Secure';
GRANT ALL PRIVILEGES ON tg_monitor.* TO 'tgmonitor'@'localhost;
FLUSH PRIVILEGES;
```

### 3. 配置 Telegram API

1. 访问 https://my.telegram.org/apps
2. 创建应用获取 `api_id` 和 `api_hash`
3. 编辑 `backend/.env`：

```env
# 数据库配置
DATABASE_TYPE=mysql
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=tgmonitor
MYSQL_PASSWORD=TgMonitor2026Secure
MYSQL_DATABASE=tg_monitor

# Telegram API
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
```

### 4. 启动服务

```bash
./start.sh start
```

### 5. 访问应用

打开浏览器访问：http://localhost:5173

---

## 常用命令

```bash
./start.sh start            # 启动所有服务
./start.sh stop             # 停止所有服务
./start.sh restart          # 重启所有服务
./start.sh status           # 查看状态
./start.sh logs backend     # 查看后端日志
```

---

## 获取 Telegram API 凭据

1. 打开 Telegram，搜索 [@BotFather](https://t.me/BotFather)
2. 发送 `/newapp` 创建应用
3. 填写应用信息（任意名称）
4. 获得 `api_id` 和 `api_hash`

---

## 故障排查

### 端口被占用
```bash
lsof -i :8000  # 查看占用进程
```

### 查看错误日志
```bash
./start.sh logs error
```

### 重启服务
```bash
./start.sh restart
```
