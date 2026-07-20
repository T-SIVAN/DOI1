# 备份与恢复

数据库保存对象归属、配额和 COS 路径，COS 保存原附件与产物；两者必须作为同一个恢复点管理。

## 建议策略

- TencentDB PostgreSQL 开启自动备份和时间点恢复，保留期按业务要求设置。
- COS 开启版本控制、服务端加密和生命周期策略；删除标记的保留时间应覆盖数据库备份窗口。
- 每日至少生成一次 PostgreSQL 自定义格式逻辑备份，并记录对应 COS 版本/清单。
- 备份写入独立私有存储桶或备份账号，定期做恢复演练；只有“备份成功”日志不算验收。

## 一致性备份

低流量维护窗口内暂停会话写入和后台清理（`docker compose stop cos-delete-worker`）后再备份，然后：

```bash
mkdir -p backup
pg_dump --format=custom --no-owner --no-acl \
  --file "backup/research_tools_$(date -u +%Y%m%dT%H%M%SZ).dump" \
  "$DATABASE_URL"
```

随后用腾讯云 COS 清单或 `coscli sync` 备份应用对象前缀，并保存备份时间、数据库备份名、桶名、区域和 COS 版本信息。完成后恢复写入并执行 `docker compose start cos-delete-worker`。

## 恢复演练

恢复是破坏性操作，先在隔离的新数据库和新 COS 前缀演练：

```bash
createdb research_tools_restore_test
pg_restore --exit-on-error --no-owner --no-acl \
  --dbname "$RESTORE_DATABASE_URL" backup/research_tools_TIMESTAMP.dump
```

再恢复对应 COS 版本/前缀，使用测试环境的 Secrets 指向恢复副本。检查：

- 表、迁移版本和 RLS 策略存在，应用账号不能绕过 RLS。
- 随机抽查附件/产物的数据库大小、对象长度和校验值。
- 每个账号的已用空间与实际归属对象一致。
- 已删除对象不会因数据库与 COS 恢复点错位而重新暴露。
- 签名下载 URL 只允许归属用户访问且约 10 分钟失效。

只有隔离恢复通过后，才在维护窗口切换生产连接。不要直接对正在运行的生产数据库使用 `pg_restore --clean`。

## 灾难恢复顺序

1. 停止应用写入并保留现场日志。
2. 恢复 PostgreSQL 到选定时间点。
3. 恢复同一时间点的 COS 对象版本/清单。
4. 执行只读一致性检查，修正孤立数据库行或孤立对象前先导出清单并人工复核。
5. 启动应用，依次验证认证、会话列表、附件、产物、删除和配额回收。
