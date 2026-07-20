# Authing OIDC 配置

## 创建应用

1. 在 Authing 创建“自建应用 / Web 应用”，协议选择 OIDC。
2. 授权模式启用 Authorization Code，Scope 至少包含 `openid profile email`。
3. 将允许的回调地址设置为 `${APP_BASE_URL}/oauth2callback`，登出后跳转地址设置为 `${APP_BASE_URL}`。
4. 将 Client ID、Client Secret 和 OIDC Discovery 地址写入服务器 `.streamlit/secrets.toml` 的 `[auth.authing]`，不要提交到 Git。
5. `redirect_uri` 必须与 Authing 控制台逐字符一致，包括 `https`、域名、端口和路径。

## 登录连接

- 邮箱：启用邮箱验证码登录，并要求完成邮箱验证。
- 微信：配置微信开放平台“网站应用”的 App ID/Secret，面向 PC 使用微信扫码。
- QQ：配置 QQ 互联 Web 应用的 App ID/Key。

微信和 QQ 的开放平台凭据需要单独申请；仅在 Authing 打开按钮不能代替开放平台审核。

## 主账号与绑定规则

1. 以已验证邮箱账号作为主账号。
2. 启用 Authing 的“询问绑定”，不要按昵称或未验证邮箱静默合并。
3. 微信或 QQ 首次登录后必须补充并验证邮箱，再绑定到邮箱主账号。
4. 测试同一用户分别用邮箱、微信、QQ 登录时，OIDC 最终身份进入同一主账号。
5. 应用以 `issuer + sub` 的哈希作为内部用户 ID，不以可修改的邮箱或昵称作为主键。

应用必须检查 ID Token/UserInfo 中的邮箱及验证状态；缺失邮箱或 `email_verified` 不为真时，只显示完成绑定/验证提示，不进入业务页面。身份绑定由 Authing 处理，应用数据库中的“删除我的全部数据”不删除 Authing 身份。

## 安全检查

- 正式环境只允许 HTTPS 回调，Cookie Secret 使用高熵随机值并定期轮换。
- Client Secret、社会化登录密钥和 Cookie Secret 只保存在服务器 Secrets 管理中。
- 禁止将 access token、ID token、Authorization 请求参数写入应用或 Nginx 日志。
- 修改域名后同时更新 Authing 回调、`APP_BASE_URL`、Nginx `server_name` 和 Streamlit `redirect_uri`。
