# 腾讯云香港生产部署

生产环境采用同地域部署：香港 CVM 运行 Docker Compose，腾讯云 PostgreSQL 使用 VPC 私网地址，附件与生成结果写入香港私有 COS。公网只开放 Nginx 的 `80/443`，Streamlit `8501` 仅在 Compose 私有网络中暴露。

## 1. 准备云资源

1. 在同一香港地域和 VPC 创建 CVM、TencentDB for PostgreSQL、私有 COS 存储桶。
2. PostgreSQL 安全组只允许 CVM 所在子网访问 `5432`；不要使用公网数据库地址。
3. COS 保持私有读写，创建最小权限 CAM 子账号，只授予目标存储桶前缀的读、写、删除和签名所需权限。
4. CVM 安全组只向公网开放 `80/443`，管理端口限制到可信 IP；不要开放 `8501`。
5. 准备 HTTPS 域名和证书。OIDC 正式环境不能使用 IP 或 HTTP 回调。

香港到中国大陆仍可能受跨境线路影响。上线后应从目标运营商网络实测，再决定是否增加腾讯云网络加速。

## 2. 配置 Authing

按 [Authing 配置说明](deploy/AUTHING.md) 创建 OIDC Web 应用并启用邮箱、PC 微信扫码、QQ Web。回调地址必须是：

```text
${APP_BASE_URL}/oauth2callback
```

例如 `APP_BASE_URL=https://research.example.com` 时，回调为 `https://research.example.com/oauth2callback`。Authing 控制台、`.env` 和 `.streamlit/secrets.toml` 中的域名必须完全一致。

## 3. 服务器配置

```bash
cp .env.example .env
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
mkdir -p deploy/certs
```

编辑 `.env` 和 `.streamlit/secrets.toml`，替换全部示例值。将证书放到：

```text
deploy/certs/fullchain.pem
deploy/certs/privkey.pem
```

Cookie Secret 至少使用 32 字节随机值，例如：

```bash
openssl rand -base64 48
```

LLM API Key 不配置在服务器 Secrets、环境变量或数据库中；它由用户每个浏览器会话输入并仅驻留内存。

## 4. 初始化数据库

先对迁移脚本做版本审阅，再严格按以下权限边界和顺序执行；不要用应用账号通配执行整个
`migrations/` 目录。

第一步，使用 Web 应用专属、非超级用户账号执行仅属于应用 schema 的 `001` 和 `002`：

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/001_research_cloud.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/002_cos_delete_outbox.sql
```

第二步，数据库管理员使用单独的管理连接执行 `003`，然后由管理员创建并授权 Worker
登录角色；Web 应用账号不得执行这一步，也不得获得 Worker 组角色：

```bash
psql "$DATABASE_ADMIN_URL" -v ON_ERROR_STOP=1 -f migrations/003_cos_delete_worker.sql
```

生产连接使用 TencentDB VPC 私网主机名或地址。RLS 依赖每个事务设置当前应用用户 ID；不要用绕过 RLS 的超级用户运行应用。`003_cos_delete_worker.sql` 涉及创建专用 `BYPASSRLS` 组角色，必须由具有 `CREATEROLE` 和表授权能力的数据库管理员单独执行。管理员随后创建 `NOINHERIT` 的专用 Worker 登录角色并授予该组角色；完整 SQL、最小权限核验、重试语义和监控见 [COS 删除队列 Worker](deploy/COS_DELETE_WORKER.md)。

## 5. 构建与启动

先验证 Compose 展开结果，确保没有意外发布 `8501`：

```bash
docker compose config
docker compose build --pull
docker compose up -d
docker compose ps
```

健康检查：

```bash
curl --fail https://research.example.com/_stcore/health
```

查看日志时避免复制包含令牌、邮件或对象路径的内容：

```bash
docker compose logs --tail=200 app cos-delete-worker nginx
```

## 6. 更新与回滚

1. 按 [备份与恢复](deploy/BACKUP_RESTORE.md) 创建 PostgreSQL 与 COS 一致性备份。
2. 拉取指定 Git 提交，构建但暂不删除旧镜像。
3. 先执行向后兼容的数据库迁移，再运行 `docker compose up -d --build`。
4. 完成登录、会话恢复、附件下载和绘图产物验收。
5. 回滚应用前检查数据库迁移是否向后兼容；不可逆迁移只能通过已验证的备份恢复。

## 7. 上线验收

- HTTP 自动跳转 HTTPS，证书链有效；公网无法访问 `:8501`。
- Authing 邮箱、微信、QQ 均能登录；未验证邮箱被拦截，绑定后的登录方式进入同一账号。
- `/oauth2callback` 成功返回应用，Streamlit WebSocket 不掉线。
- 侧栏仅出现 `PDF精读 / 文献检索 / 引用追踪 / 科研工具 / PPT汇报`。
- 科研工具只有一个多附件聊天输入入口；单文件 25MB、单次最多 10 个和总配额 200MB 均生效。
- 刷新、重新登录和另一设备可恢复会话、附件摘要与产物。
- PostgreSQL 使用 VPC 地址；COS 桶为私有，下载 URL 约 10 分钟失效。
- 两个测试账号互相不能读取、删除或下载会话与对象。
- PNG/SVG/PDF 下载、会话删除、额度回收和“删除全部数据”均通过。
- 桌面端、手机端、浅色和深色主题完成视觉检查。

本地开发可使用项目支持的开发认证/内存持久化模式，但不得把该模式用于公网生产环境。
