# 2026-10-02 旧版演示 API 部署：为已完成的旧版小程序分包建立独立后端

本次接续 10-02 旧版演示分包工作。用户明确客户端已经完成、不需要改动，只需部署服务端，并要求 `legacy` 登录在 `legacy` 库内可对所有表 CRUD、不能访问其他数据库。部署到 `mini.snowmeet.com`；整个过程未修改小程序源码或 `.top` 生产服务。

## 1. 目标与服务器预检

- 固定提交：`9b4d35f19b4c1c1f06065e89071d155450d8bf69`，是 `migrate_to_new_season` 最后提交，也是 `ai` 分支分叉点。
- `mini.snowmeet.com` 和 `mini.snowmeet.top` 均解析至 `161.189.64.210`。
- 主机为 Ubuntu 22.04，安装 .NET 9.0.9；Nginx、SQL Server 与三个既有服务正常。
- 生产 API 是 `mini.snowmeet.top.service`，工作目录 `/home/ubuntu/webs/SnowmeetApi`，端口 5000；公众号/其他服务使用 5001、5002。
- 根盘部署前约剩 1.8 GB。检查未发现可用 `.bak`、`.bacpac` 或 schema 备份文件。
- 证书 ZIP 内含 `mini.snowmeet.com_cert_chain.pem` 与 `mini.snowmeet.com_key.key`；SAN 为 `mini.snowmeet.com`，有效期 2026-10-01 至 2026-12-30，证书公钥与私钥匹配。

## 2. 数据库权限

- 最初以 `legacy` 登录查询用户表得到 0 张，这是 metadata visibility 受限所致，不代表数据库为空。
- SA 只读检查确认 `legacy` 有 102 张用户表；未读取或复制其他库业务数据。
- SA 在 `legacy` 库将用户 `legacy` 加入 `db_datareader` 与 `db_datawriter`，没有加入 `db_owner`。
- 最终以 `legacy` 登录验证：102 张表 CRUD 缺权数为 0；`db_owner=0`、`sysadmin=0`；`HAS_DBACCESS` 对 `legacy` 为 1，对 `snowmeet` 和 `snowmeet_new` 均为 0。
- SQL Server 密码未记录在本文或项目仓库。

## 3. 固定版本构建与隔离

- 本机通过 `git archive` 从目标 hash 构建，未切换或改写 SnowmeetApi 工作区；Release 构建成功，有 875 条编译警告。
- 发布包约 278 MB，先暂存于本机临时目录，再传至 `/home/ubuntu/webs/SnowmeetApiLegacy/releases/9b4d35f1`。
- 独立 systemd unit：`snowmeet-legacy-demo.service`，工作目录为该 release，监听 `127.0.0.1:5003`，已启用开机启动。
- `config.sqlServer` 指向同机 `legacy` 数据库，权限为 `0600 ubuntu:ubuntu`；未复制生产连接串。
- 按用户要求，生产 `appsettings.json` 已复制到 release，权限 `0600 ubuntu:ubuntu`，SHA-256 与生产文件一致。
- TLS 私钥位于 `/etc/ssl/private/mini.snowmeet.com_key.key`，权限 `0600 root:root`。

## 4. Nginx 与验收

- 新增独立 `/etc/nginx/conf.d/mini.snowmeet.com.conf`，不修改 `/etc/nginx/sites-available/default` 中的 `.top` 生产配置。
- HTTP 自动跳转 HTTPS；HTTPS 和 WebSocket `/ws` 代理到 `127.0.0.1:5003`。
- `nginx -t` 通过；本机与公网 `mini.snowmeet.com/swagger/v2/swagger.json` 均返回 200，`curl` TLS 校验结果为 0。
- HTTP→HTTPS 返回 301；WebSocket 握手返回 `101 Switching Protocols`。
- `mini.snowmeet.top` Swagger 仍返回 200，生产 API unit 保持 active。
- 演示与生产 `appsettings.json` 一致，含线上微信/第三方服务配置。因此**不可用此演示环境执行真实支付、退款、订票或其他有副作用的外部调用**，后续需先确认沙箱或禁用方案。
- 部署结束根盘约 95% 已用、仅剩 1.5 GB；建议尽快清理或扩容。

## 5. 遗留与回滚

- 旧版演示小程序仍未在微信开发者工具编译、上传或点测；客户端源码本次未修改。
- 发布前核验小程序后台 request/uploadFile `https://mini.snowmeet.com`、socket `wss://mini.snowmeet.com` 合法域名。
- 安全点测前确认真实支付、退款、订票及外部商户接口已隔离；不要扫描可能关联生产数据的二维码。
- 回滚只针对演示资源：`systemctl disable --now snowmeet-legacy-demo.service`，移除 `/etc/nginx/conf.d/mini.snowmeet.com.conf`，`nginx -t` 通过后 reload；再按需删除演示 unit、release 与 `.com` 证书文件。不得改动 `.top` 生产服务或其数据库。

## 学到的小知识

1. `db_datareader`/`db_datawriter` 可覆盖数据库全部用户表的数据读写；对象元数据不可见时，普通登录查询 `sys.tables` 可能误显 0 表，应由有权账号核对 schema，再以应用登录验证对象权限。
2. SSH 本地转发的 `127.0.0.1:14330` 只存在于发起 SSH 的 Mac；在远端 Ubuntu shell 运行本机安装的 `sqlcmd` 会得到 command not found。
3. TLS 证书应按 SNI 实测；本机 Python CA 包可能与 curl 系统 CA 不同，WebSocket 协议握手与严格证书校验应分开验证。

## 关键改动文件

| 文件/路径 | 改动 |
|---|---|
| `snowmeet_ai_doc/CLAUDE.md` | 更新演示服务部署状态、风险和下一步 |
| `/home/ubuntu/webs/SnowmeetApiLegacy/releases/9b4d35f1` | 独立固定版本 API 发布目录 |
| `/etc/systemd/system/snowmeet-legacy-demo.service` | 新增演示 API unit |
| `/etc/nginx/conf.d/mini.snowmeet.com.conf` | 新增 `.com` TLS/API/WebSocket vhost |
| `/etc/ssl/certs/mini.snowmeet.com_cert_chain.pem` | 安装证书链 |
| `/etc/ssl/private/mini.snowmeet.com_key.key` | 安装 root-only 私钥 |
| `snowmeet_ai_doc/artifacts/testing/qa-20261001-common02-yesterday-113751-6bb721/` | 工作区原有 QA 结果与截图，随 end-work 提交归档 |
