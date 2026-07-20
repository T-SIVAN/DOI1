# COS 删除队列后台 Worker

附件或产物的数据库记录与 COS 对象不能处于同一个事务。应用先在删除事务中写入
`cos_delete_outbox`，再删除业务记录并回收配额。`cos-delete-worker` 独立消费这些持久化
删除标记，因此即使用户执行“删除我的全部数据”后永不再次登录，COS 删除仍会继续重试。

## 权限模型

- Web 应用继续使用 `DATABASE_URL` 的普通应用账号，并受所有业务表 RLS 限制。
- Worker 必须使用单独的 `COS_DELETE_WORKER_DATABASE_URL`，不得复用应用账号。
- `migrations/003_cos_delete_worker.sql` 创建 `research_cos_delete_worker`：这是
  `NOLOGIN BYPASSRLS` 组角色，只拥有 outbox 必要列的 `SELECT/UPDATE`，没有业务表权限，
  也没有 outbox 的 `INSERT/DELETE` 权限。
- Worker 登录角色必须为 `NOINHERIT`；进程每个事务显式 `SET LOCAL ROLE`，避免权限意外常驻。

Web 应用账号只执行 `001_research_cloud.sql` 和 `002_cos_delete_outbox.sql`。随后，`003` 由具有
`CREATEROLE` 和修改该表授权能力的腾讯云数据库管理员使用单独管理连接执行。不要让 Web
应用账号执行 `003`，也不要授予 Web 应用账号 Worker 组角色或 `BYPASSRLS`。执行 `003` 后，
仍由数据库管理员用生成的随机密码单独创建并授权登录角色（示例中的密码只是占位符，不能原样使用）：

```sql
CREATE ROLE research_cos_delete_worker_login
    LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION
    PASSWORD '<generated-secret>';
GRANT research_cos_delete_worker TO research_cos_delete_worker_login;
REVOKE CREATE ON SCHEMA public FROM research_cos_delete_worker_login;
```

将该登录连接串仅写入服务器 `.env` 的 `COS_DELETE_WORKER_DATABASE_URL`。确认角色边界：

```sql
SELECT rolname, rolcanlogin, rolbypassrls
FROM pg_roles
WHERE rolname IN ('research_cos_delete_worker', 'research_cos_delete_worker_login');
```

预期组角色 `rolcanlogin=false, rolbypassrls=true`，登录角色
`rolcanlogin=true, rolbypassrls=false`。登录角色只能通过获准的 `SET ROLE` 使用组角色权限。

## 处理语义

- 使用 `FOR UPDATE SKIP LOCKED` 并发抢占，每个任务有默认 5 分钟租约；进程崩溃后租约到期可重试。
- COS 删除是幂等操作。对象删除成功但数据库确认失败时，下一次重复删除是安全的。
- 失败按 30 秒起步指数退避，默认最长 1 小时；数据库不可用时按轮询间隔重试。
- SIGTERM/SIGINT 会停止领取和处理新任务并关闭连接池；尚未完成的租约会自动到期。
- 日志只记录任务 ID、次数、计数和异常类型，不记录数据库连接串、COS 对象键或凭据。

对应参数均可在 `.env` 中调整：

```text
COS_DELETE_WORKER_POLL_SECONDS=10
COS_DELETE_WORKER_BATCH_SIZE=100
COS_DELETE_WORKER_LEASE_SECONDS=300
COS_DELETE_WORKER_RETRY_BASE_SECONDS=30
COS_DELETE_WORKER_RETRY_MAX_SECONDS=3600
```

## 启动与监控

Worker 已在 Compose 中作为无端口服务配置：

```bash
docker compose up -d --build cos-delete-worker
docker compose ps cos-delete-worker
docker compose logs --tail=200 cos-delete-worker
```

建议由数据库管理员使用只读监控连接执行以下查询；不要将 outbox 的 `object_key` 输出到普通日志：

```sql
SELECT count(*) AS pending,
       min(created_at) AS oldest_pending,
       max(attempts) AS max_attempts
FROM cos_delete_outbox
WHERE processed_at IS NULL;

SELECT count(*) AS failed_or_waiting
FROM cos_delete_outbox
WHERE processed_at IS NULL AND last_error <> '';
```

建议对“最旧待处理超过 15 分钟”“最大尝试次数超过 10”及容器持续重启告警。已处理记录用于审计，
如需清理，应由管理员另行制定保留期并执行；不要扩大 Worker 的 `DELETE` 权限。

维护或一致性备份时先执行 `docker compose stop cos-delete-worker`，完成后执行
`docker compose start cos-delete-worker`。恢复演练必须同时验证未处理 tombstone 会继续删除恢复后的
COS 对象。
