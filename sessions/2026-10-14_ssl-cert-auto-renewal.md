# 2026-10-14 证书自动续期：mini/wxoa/wl/mini.snowmeet.com/img 五个域名改为 Let's Encrypt，每 75 天续一次

在 Intel Mac 笔记本（`/Users/cangjie/Projects/snowmeet/snowmeet_ai/`）上进行，跨 10-14 晚到 10-15 中午。起点是 start-work 提到「三张证书今天到期」，用户问能否自动续。改动全部在 mini 服务器（161.189.64.210）和 AWS 中国区控制台，**没有改任何代码仓库**。

## 1. start-work

- 文档仓 `git pull --ff-only` 无更新（`1c86956`）。
- 第一次 fetch 五个仓库全部「失败」，原因是脚本里用了 `timeout`，macOS 没有这个命令；去掉后正常：
  - SnowmeetApi `ai@9c5d46c` 落后 2（`fe4eb6c`、`76246c6`，即 10-12、10-13 已上线的食材改动），只 fetch 没合并。
  - reqai `~/Projects/snowmeet/reqai` 落后 3（归档 / 不读摘要），只 fetch。
  - 小程序 0/0，但有 118 个 `legacy/` 生成文件改动（10-02 那批，原来在这台机器上）。
  - 公众号 0/0，走 443 才 fetch 成功。
- reqai 归档：#5 #7 两个会话未分析。
- 汇报时把「三张证书今天下午到期」放在最前面；当时本机连不上这三个域名的 443，到美国服务器的 22 也超时，没能核实。

## 2. 用户问「证书续期，能否自动续？」

### 2.1 第一次登录被拦

- 先测端口：美国服务器 22 和 2222 都通了（之前的超时是暂时的）。
- `ssh -p 2222` 报 `Host key verification failed`：known_hosts 里没有 `[44.207.251.65]:2222` 这一项。没有直接接受未知密钥，而是用 `-o HostKeyAlias=161.189.64.210` 让它按 known_hosts 里 mini 的主机密钥校验；本机 `~/.ssh/id_rsa` 可以登录。
- 读证书和 nginx 配置的命令被 auto 模式以「Production Reads」拦下。按规则停下，向用户说明想做什么、需要什么授权。
- 此时已是北京时间 21:33，三张证书的到期时间都已过。

### 2.2 方案

- 阿里云免费证书没有自动续期，「自动部署」只能部署到阿里云自己的产品。
- 方案：mini 服务器上用 ACME 客户端 + Let's Encrypt。两种验证方式：A. 80 端口文件验证（不需要密钥）；B. 阿里云 DNS 验证（要 DNS 子账号密钥，能签通配符）。推荐 A。
- 用户回复：「1 马上按照上面的方案做；2，你可以操作mini服务器；3，选A」。

## 3. mini / wxoa / wl 三张（10-14 21:35～21:40）

### 3.1 现状

- 三张都已过期（notAfter 06:59 / 07:59 / 11:59 UTC），issuer TrustAsia LiteSSL。
- nginx：`sites-available/default` 里三个域名各有 443 块；**只有 wxoa 有 80 块**（直接转发 5001 给公众号服务，不跳转）。mini 和 wl 的 http 请求落到 `conf.d/mini.snowmeet.com.conf` 的 80 块（它是第一个 `listen 80`），被 301 到 `https://$host`。
- 私钥文件 777，有的属 www-data。磁盘约 920 MB 可用。
- 从美国服务器访问：三个域名都解析到 161.189.64.210，80 端口外网可达。

### 3.2 实施

- 备份旧证书和 nginx 配置到 `/home/ubuntu/cert-renew-20261014/`。
- `apt-get install certbot`（Ubuntu 源 1.21.0，自带 `certbot.timer`）。原先说用 acme.sh，改用 certbot 是因为不必从 GitHub 下载、自带定时器，汇报时已说明。
- nginx：新增 `conf.d/snowmeet-top-http80.conf`（mini、wl：`/.well-known/acme-challenge/` 指向 `/var/www/acme`，其余 `return 301`）；wxoa 的 80 块在 `location /` 前插入验证路径（先核对行号内容再 `sed` 插入）。`nginx -t` 通过后 reload，从美国服务器测三个域名都能取到测试文件，原有跳转和 wxoa 转发不变。
- 部署钩子 `/usr/local/bin/snowmeet-cert-install.sh`：按 `$RENEWED_DOMAINS` 把 `fullchain.pem` / `privkey.pem` 用 `install -m 600 -o ubuntu` 写回原路径，再 `nginx -t -q && systemctl reload nginx`。
- `certbot certonly --webroot -w /var/www/acme --agree-tos --register-unsafely-without-email --key-type rsa --rsa-key-size 2048 --deploy-hook …`，三张逐个签发，到期 2027-01-12。注册时接受了 Let's Encrypt 用户协议，没留邮箱（用户邮箱不外传）。

### 3.3 验收

- 本机 443 按 SNI 握手：三张都是 Let's Encrypt（YR1/YR2），到期 2027-01-12。
- 私钥与证书模数一致；文件 600。
- 美国服务器 curl 严格校验：`ssl_verify=0`。
- 证书链：叶子 → YR2 → ISRG Root YR → 由 ISRG Root X1 交叉签名。
- `certbot renew --dry-run`：后台跑了几分钟才出结果——没有终端时 certbot 会先随机等最多 8 分钟。三张全部成功。

## 4. mini.snowmeet.com 加入，节奏改为 75 天（10-14 22:00 前后）

- 用户：「mini.snowmeet.com 也加进自动续期，每75天一次。」理解为整套续期节奏，4 张都改。
- 它的 80 块是 server 层 `return 301`，location 永远轮不到。改成验证路径 + `location / { return 301 … }`（用 Python 做精确替换，先断言只匹配一处）。
- 部署钩子加 `.com` 分支：写回 `/etc/ssl/certs/…`（root 644）和 `/etc/ssl/private/…`（root 600）。
- 签发到期 2027-01-12 21:03；4 张续期配置都把注释行 `# renew_before_expiry = 30 days` 改成 `renew_before_expiry = 15 days`。
- 验收：外网严格校验通过；`certbot renew --no-random-sleep-on-renew` 实跑 4 张都是 not yet due；`--dry-run` 4 张成功。

## 5. img.snowmeet.top 加入（10-14 23:00～10-15 12:48）

### 5.1 调查

- 当前证书 TrustAsia，2027-01-01 到期，挂在 CloudFront 分配 `E2O9W3Y5WRBYD2` 上（DNS CNAME 到 `d1x1fz9csk27wg.cloudfront.cn`）。
- http 被 CloudFront 301 到 https；https 下 `.well-known/...` 返回 403（桶策略只放行 `upload/*`）。
- mini 的实例角色能列出、读取 IAM 服务器证书，有上传权限；**不能** `GetDistributionConfig`、`ListRolePolicies`、`GetBucketPolicy`。

### 5.2 方案

- 验证：certbot manual 模式，钩子把验证文件写进 S3 桶的 `.well-known/acme-challenge/`，经 CloudFront 读取。Let's Encrypt 跟随 http→https 跳转且不校验证书，所以旧证书不影响验证。
- 部署：钩子上传 IAM → 改分配的 `IAMCertificateId`（`Certificate` 字段同步）→ 删除更早的 img 证书、保留刚被替换的一张。
- 先把三个脚本写到服务器（语法检查通过；`py_compile` 因 `/usr/local/bin/__pycache__` 无写权限失败，改用 `ast.parse`）。

### 5.3 用户在控制台改的两处

- 角色 `snowmeet-api-ec2` 加内联策略 `img-cert-auto-renew`：CloudFront `GetDistributionConfig`/`UpdateDistribution`（只限这一个分配）、IAM `Upload/Get/DeleteServerCertificate`（只限 `img.snowmeet.top-*`）、S3 `PutObject`/`DeleteObject`（只限 `.well-known/acme-challenge/*`）。
- 桶策略：用户贴出原文（只有一条 `CloudFrontReadUploadOnly`，OAI `E21701J9MYS92X`），问「那句话是你要找的？」。改成原条一字不动、另加 `CloudFrontReadAcmeChallenge`，方便以后单独删除。
- 改完后验证：能读分配配置（当时证书 `ASCAZZXV2IGM2ADAC7IL2`）；验证目录可写可删；测试文件经 CloudFront（https 和 http 跟随跳转）都能读到。

### 5.4 签发与验收

- 12:46 签发成功，到期 2027-01-13；钩子日志：上传 IAM `img.snowmeet.top-20270113-124642`（`ASCAZZXV2IGMUMAMYVW6E`），CloudFront 已切换。IAM 里两张 img 证书都在（旧的留作回滚）。
- 续期配置 `renew_before_expiry = 15 days`；`--dry-run` 成功、验证目录无残留；5 张续期检查全部 not yet due。
- 查分配部署状态用的 `GetDistribution` 不在授权里（脚本用不到），改为直接查各边缘节点返回的证书：mini 解析到的 52.82.132.x 和美国服务器解析到的 118.193.97.x 都已是 Let's Encrypt，`ssl_verify=0`。
- 取一张真实上传图片 `upload/20261006/345ad70b0a3e4c479b1e4501af0ae91a.jpg`：200，image/jpeg，2.5 MB。把这个地址给了用户自己在浏览器验证。

## 6. 到期提醒任务

- 用户要求列出 5 个域名，并「届时提醒我检查证书是否更换」。
- 用 Claude 桌面应用的定时任务建了一次性任务 `ssl-cert-renewal-check`，2026-12-30 10:00（5 张的续期窗口最晚 12-29 中午打开，服务器每天检查两次）。
- 任务提示词自包含：背景、登录命令、检查步骤（服务器本机 SNI、`certbot certificates`、日志、IAM 证书列表、美国服务器外网校验）、判断标准（剩余 ≥60 天且外网一致）、只报告不动服务器、失败时给人工检查的 5 个地址；全部续上时读自身 SKILL.md 建下一轮（最晚到期日前 14 天）。
- 保存为自动模式。已告诉用户：应用关着会在下次打开补跑；无人值守时登录生产服务器、建下一轮都可能被拦。

## 关键改动（全部在服务器和 AWS 上）

| 位置 | 改动 |
|---|---|
| mini `/etc/nginx/conf.d/snowmeet-top-http80.conf` | 新增：mini、wl 的 80 端口验证路径 + 301 |
| mini `/etc/nginx/sites-available/default` | wxoa 80 块加验证路径 |
| mini `/etc/nginx/conf.d/mini.snowmeet.com.conf` | 80 块改成 location 结构并加验证路径 |
| mini `/usr/local/bin/snowmeet-cert-install.sh` | 新增：nginx 4 个域名的部署钩子 |
| mini `/usr/local/bin/snowmeet-img-acme-{auth,cleanup}.sh` | 新增：img 验证文件写入 / 删除 S3 |
| mini `/usr/local/bin/snowmeet-img-cert-deploy.py` | 新增：img 上传 IAM + 切 CloudFront + 清旧证书 |
| mini `/etc/letsencrypt/renewal/*.conf` | 5 张，`renew_before_expiry = 15 days` |
| mini `/home/ubuntu/*_key.key` 等 | 换成新证书，权限 600 |
| AWS IAM 角色 `snowmeet-api-ec2` | 内联策略 `img-cert-auto-renew`（用户加） |
| AWS S3 桶策略 | 新增 `CloudFrontReadAcmeChallenge`（用户加） |
| 笔记本 Claude 桌面应用 | 定时任务 `ssl-cert-renewal-check`（12-30 10:00） |

## 学到的小知识

1. **certbot 后台运行会随机等最多 8 分钟**：没有终端时 `renew` 先 sleep，手动验证加 `--no-random-sleep-on-renew`。`--dry-run` 不执行部署钩子。
2. **server 层的 `return` 先于 location 匹配执行**：要在一个只做跳转的 80 块里放行验证路径，必须把 `return` 挪进 `location /`。
3. **没有专属 80 块的域名会落到默认块**：默认块是配置里第一个 `listen 80`（`conf.d` 先于 `sites-enabled`，按文件名排序）。
4. **Let's Encrypt 的 HTTP-01 会跟随跳转到 https，且不校验证书**：所以 CloudFront「http 强制跳 https」、旧证书即将过期都不妨碍验证。
5. **中国区 CloudFront 证书只能走 IAM**：上传到 `/cloudfront/` 路径，再改分配的 `IAMCertificateId`；新证书上传后要等一会儿 CloudFront 才接受。
6. **ssh 经端口转发连目标机时用 `HostKeyAlias`**：known_hosts 里只有目标机自己的地址，用别名按它的主机密钥校验，不要直接接受新密钥。
7. **zsh 不对变量分词**：把 `ssh -o … -p 2222` 放进变量再 `$S` 执行会报 command not found。
