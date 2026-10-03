# 2026-10-03 上传文件迁移 AWS S3：宁夏私有桶 + CloudFront + img.snowmeet.top，改代码、迁文件、改库

Windows 机（`D:\source\snowmeet\ai`）。会话从 start-work 开始，随后用户提出：「现在所有的文件上传接口，上传的文件放入 aws 的 S3 存储桶。请带着我一步步在 aws 当中设置，然后再修改程序，最后服务器上的文件也统统放入存储桶，并修改数据库。」改动落在 SnowmeetApi、snowmeet_wechat_mini、生产库和 AWS 中国宁夏账号。

## 1. start-work

- 文档仓 pull 正常（`73f9b20`）。GitHub 22 端口超时，改走 `ssh.github.com:443` 并加 `HostKeyAlias=github.com` 后，五个仓库都 fetch 成功（不加会报 Host key verification failed）。
- 状态：API `5a79820f` 与远端一致；小程序 `c4216875` 落后 2 个 show legacy 提交；公众号有 1 个未提交改动；reqai 干净；旧的 reqai 检出落后 6。`scan.py --check`：无未分析内容。

## 2. 摸底与方案

### 2.1 上传入口（SnowmeetApi）

- 5 处写文件：`UploadFile/UploadFileWithThumb`、`UploadFile/UploadFile`、`UploadFile/Upload/{sessionKey}`、`FnbMaterial/UploadPhoto`、`TicketPoster/Generate`（生成海报）。
- 都写 `Util.workingPath + /wwwroot/upload/yyyyMMdd/<毫秒时间戳>.<ext>`，`mini_upload.file_path_name` 存相对路径。
- 不在范围：导出 Excel 的报表、支付宝对账临时下载、`UploadMi7Sheet`（只读不存）、reqai 附件。

### 2.2 显示端

- 小程序 `utils/data.js` 的 `IMAGE_HOST`（当时是 mini）拼相对路径；多图上传组件 `multi-uploader` 把 `https://` + domainName + 路径的完整地址存库（`product_image.image_url` 等）；券模板页写死 mini；食材 H5 `mat.js` 写死 wanlonghuaxue。
- 没有代码按域名前缀反解路径，换域名安全。

### 2.3 AWS 中国区限制（查官方文档核实）

- 公开读 S3 需要账号关联 ICP；中国区 CloudFront 必须用已备案的自有域名，不能用 `*.cloudfront.cn` 对外；不支持 ACM，证书要传到 IAM；私有桶只能用 OAI（没有 OAC）。
- mini 服务器 161.189.64.210 属 AWS 宁夏（Ningxia West Cloud Data，AS135629）。

### 2.4 用户拍板

- 访问方式：**私有桶 + CloudFront + `img.snowmeet.top`**（另一个选项是 mini 的 nginx 反代 S3、旧地址不变）。
- 库里存法：**相对路径 + 集中配显示域名**，只改写写死旧域名的完整地址。
- wanlonghuaxue：「这个服务器已经注销了，图片也没有用了」。
- img 证书：用户自己申请；mini/wxoa/wl 三张 10-14 到期的证书：用户自己处理。

## 3. AWS 设置（用户在控制台操作）

### 3.1 桶与权限

- 桶 `snowmeet-uploads-673751646617-cn-northwest-1-an`（用户建，带账号区域命名空间后缀 `-an`）：ACL 禁用、阻止所有公开访问、版本控制开、SSE-S3。
- IAM 托管策略 `snowmeet-uploads-rw`：`s3:ListBucket` 给桶，`s3:GetObject/PutObject` 给 `桶/*`，没有删除权限。ARN 前缀是 `arn:aws-cn:`。
- 角色 `snowmeet-api-ec2`（EC2 可信实体）挂到实例 `i-0c2e59977055013fa`。服务器上 IMDS 能看到 instance profile；`aws s3 cp/ls/cp -` 往 `private/_test/` 读写测试通过。
- 内联策略 `upload-cloudfront-cert`：`iam:UploadServerCertificate/GetServerCertificate` 限 `server-certificate/cloudfront/*`，`ListServerCertificates` 给 `*`。

### 3.2 证书

- 用户给了 TrustAsia LiteSSL 证书 zip（Nginx 格式）。核对：CN/SAN `img.snowmeet.top`，2027-01-01 到期，链 3 张，私钥 RSA 2048 且与证书 modulus 一致。
- 拆成正文（第 1 张）和链（后 2 张），scp 到服务器 700 目录，`aws iam upload-server-certificate --region cn-northwest-1 --path /cloudfront/ --server-certificate-name img.snowmeet.top-20270101`。
- 第一次被拒：内联策略还没加。第二次报 `InvalidClientTokenId`：漏了 `--region`，CLI 去了海外 IAM 端点。第三次成功，随后 `shred` 删掉服务器和本机的私钥副本。

### 3.3 CloudFront

- 分配 `E2O9W3Y5WRBYD2`，域名 `d1x1fz9csk27wg.cloudfront.cn`，源为桶的 REST 端点（不是 s3-website），备用域名 `img.snowmeet.top` 审核通过。
- 桶策略报 `Invalid principal`：用户填的 `E2O9W3Y5WRBYD2` 是分配 ID，「来源访问」页显示 0 个 OAI。补建 OAI，在源上把「来源访问」从「公开」改为「遗留访问身份」并选 OAI，再按 OAI ID 写桶策略（只放行 `upload/*`）。
- 边缘一直返回 `CN=internal.cloudfront.cn`：分配「设置」里根本没有「自定义 SSL 证书」项，建分配时用的是默认证书。用户编辑设置选上 `img.snowmeet.top-20270101` 后，后台轮询约 10 分钟见到新证书。

### 3.4 DNS

- 阿里云 `img` CNAME → `d1x1fz9csk27wg.cloudfront.cn`（权重模式）。服务器起初还解析到 mini 是泛解析 `*.snowmeet.top` 的缓存；权威、223.5.5.5、114 都已返回 CNAME。本机 nslookup 仍是旧 IP，因为本机有代理接管 DNS（198.18.x）。

### 3.5 验证（全部从 mini 服务器 curl）

- `https://img.snowmeet.top/upload/...` 200、证书校验通过；与原文件 MD5 一致；第二次 `x-cache: Hit from cloudfront`、缓存头 1 年。
- `/private/_test/s3test.txt` 403；不存在的文件 403（OAI 没有 List 权限）；直接访问桶 403；HTTP 301 到 HTTPS。

## 4. 代码改动

### 4.1 SnowmeetApi `534aad0c`

- 新增 [`Services/Storage/FileStorage.cs`](../../SnowmeetApi/Services/Storage/FileStorage.cs)：
  - `IFileStorage`：`SaveAsync` 返回相对路径；`ReadAsync` 读 S3，`NotFound` 时回退本机磁盘；`PublicUrl`。
  - `S3FileStorage` 走默认凭证链（EC2 角色），`PutObject` 设 Content-Type 和 `public, max-age=31536000, immutable`；`LocalFileStorage` 保留旧行为。
  - `UploadPaths`：新文件名 GUID（旧的毫秒时间戳可被猜）；后缀只留字母数字、≤10 位；对象键拒绝 `..`；`is_web=0` → `private/`。
  - `FileStorageOptions` 默认值即生产配置（服务器 appsettings 不用加项），`FileStorage:Provider=Local` 可退回磁盘。
  - `UseUploadRedirect`：放在 `UseStaticFiles` 之后，磁盘上没有的 GET/HEAD `/upload/...` 302 到 img（带 query）。
- `UploadFileController` 三个接口、`FnbMaterial/UploadPhoto`（`[FromServices]`）、`TicketPoster/Generate`（封面从存储读，海报写存储，返回 `PublicUrl`）。
- `wwwroot/fnb/mat_expire/mat.js`：上传改同源 `API_BASE`，显示 `IMG_HOST=https://img.snowmeet.top`。原来上传到已注销的 wanlonghuaxue，线上一直是坏的。
- `AWSSDK.S3` 4.0.104.1。`FileStorageTests` 29 例（后缀、路径、对象键、URL、DispatchProxy 假 S3、本地回退、TestHost 测 302）；全量单元 420/420（排除两组需要库的集成测试）。

### 4.2 小程序 `f0afbf7d`（已 rebase 到 origin/ai）

- `IMAGE_HOST = 'https://img.snowmeet.top'`；`uploadFilePromise`、`uploadMatExpirePhotoPromise` 上传走 `requestPrefix`。
- `multi-uploader` 存 `IMAGE_HOST + 路径`；券模板页封面用 `IMAGE_HOST`，不再传 uploadHost。
- 雪票详情两张静态图从 wanlonghuaxue 改到 `mini.snowmeet.top/images/`（文件在 SnowmeetApi `wwwroot/images/`）。
- 测试 194/194，改动文件 `node --check` 通过。

## 5. 生产库扫描与改写

### 5.1 只读扫描（586 个字符串列）

- `mini_upload` 145,983 行：145,981 条相对路径，2 条 http 开头，`is_web=0` 只有 1 条（2022）。用途：滑雪学校 129,313、空 10,236、养护开单 4,982 等。
- 存完整 mini 地址的：`care.images` 7,779、`product_image.image_url` 3、`rent_list.guarantee_credit_photos` 5、`rent_list_detail.images` 15、`rent_product_image.image_url` 1。
- 指向 wanlonghuaxue 的图片 3 行（`mini_upload` 88999/89023 的 thumb、`rent_product_image` 306），文件已没了，不动。`order_payment.notify` 等的 wanlonghuaxue 是历史回调地址，与图片无关。
- 相对路径的其他列（滑雪学校视频/图片、`school_staff.avatar`、`ski_pass.card_image_url`）不用改。

### 5.2 改写（用户「可以改库」后执行）

- 脚本 [sql/2026-10-03_upload_urls_to_img_host.sql](../sql/2026-10-03_upload_urls_to_img_host.sql)，用 pyodbc 执行：先 `SELECT INTO bak_20261003_*` 备份并核对行数（单独提交），再在一个事务里 `REPLACE` 域名。
- 结果：改写 7,803 行，剩余旧地址 0，与备份逐行比对不一致 0，COMMIT。抽 6 条改后地址访问全部 200。

## 6. 文件迁移

- mini 的 `wwwroot/upload`：**4,326 个文件、1.3 GB、169 个日期目录，从 2024-11-07 开始**；没有 `is_web=0` 的目录；磁盘 29G 用了 96%。
- `aws s3 sync ... --cache-control "public, max-age=31536000, immutable"` 后台跑完：桶里 4,326 个对象、1,364,372,454 字节，与本地一致；抽查 Content-Type、加密正确。
- 对照库：库里引用的文件在 mini 上的只有 4,285 个；磁盘上 41 个没人引用（多是生成的券海报）。缺失的主要是滑雪学校全部、2025–26 养护开单约 5,000 张、养护取板 525、零售开单 85——推断随 wanlonghuaxue 一起没了，用户说不要。
- 发布后补同步：首次同步后没有新文件落盘，仍为 4,326 个，完全一致。

## 7. 发布 SnowmeetApi

- 推送 API `5a79820f..534aad0c`、小程序 `023f7858..f0afbf7d`（都走 443）。
- 服务器 `/home/ubuntu/webs/SnowmeetApi` 是 git 检出 + 发布目录，`.git` 属于 www-data；root 没有 GitHub 密钥。用 `sudo GIT_SSH_COMMAND="ssh -i /home/ubuntu/.ssh/id_rsa ..." git -c safe.directory=... pull --ff-only` 拉到 `534aad0`。
- ⚠️ 第一次 `sudo dotnet publish`：root 首次运行 dotnet、没有 NuGet 缓存，下载全部依赖，**磁盘写满到 100%**。查到 `/root/.nuget`（1.2G）、`/root/.local/share/NuGet`（270M）、`/root/.dotnet` 都是 14:27–14:28 刚建的，删掉后恢复到 1.5G；服务没被替换，一直正常。
- 第二次用 ubuntu `dotnet publish`：NETSDK1152（目录里旧的 `deps.json`/`runtimeconfig.json` 重名）。查 bash_history 找到标准脚本 `republish.sh`（ubuntu 运行，停服务 → 删 bin/obj → 删 `SnowmeetApi.*.json` → self-contained publish → 启服务）。
- 按该脚本写了 `deploy_s3_20261003.sh`，加了旧 dll/json 备份和失败回退，nohup 后台跑：14:33:11 停 → 14:34:30 PUBLISH_OK → 启动 active，**停机约 80 秒**。
- 验证：swagger 本机/公网 200；磁盘上的老图仍直接返回 200；缺失的 `/upload/20210306/...` 302 到 img 并保留 query。

## 8. 实传验证

- 用户在线上小程序传了一张（`mini_upload` 157724，养护开单，员工 28）：原图和缩略图都是 GUID 名，S3 有（268,884 字节、image/png、1 年缓存），磁盘上没有（连 `upload/20261003` 目录都没生成），img 200，mini 地址 302 到 img。
- 原图和缩略图一样大，说明这次前端没生成缩略图、传了两份原图，是以前就有的行为。

## 9. 其他发现

- mini/wxoa/wl 三张 `.top` 证书都是 TrustAsia 90 天免费证书，**2026-10-14 到期**，服务器没有自动续期；三个私钥文件权限 777。用户说自己处理。
- 阿里云 DNS 里 `media` 仍指向已注销的 60.8.110.78。
- `AliController.TestUniPay` 的 notify URL 还写着 wanlonghuaxue，是测试接口，没动。

## 关键改动文件

| 文件 | 改动 |
|---|---|
| [`SnowmeetApi/Services/Storage/FileStorage.cs`](../../SnowmeetApi/Services/Storage/FileStorage.cs) | 新增：S3/Local 存储、路径规则、302 中间件 |
| [`SnowmeetApi/Startup.cs`](../../SnowmeetApi/Startup.cs) | 注册存储；`UseUploadRedirect` |
| [`SnowmeetApi/Controllers/UploadFileController.cs`](../../SnowmeetApi/Controllers/UploadFileController.cs) | 三个上传接口改走存储 |
| [`SnowmeetApi/Controllers/Fnb/FnbMaterialController.cs`](../../SnowmeetApi/Controllers/Fnb/FnbMaterialController.cs) | `UploadPhoto` 改走存储 |
| [`SnowmeetApi/Controllers/TicketPosterController.cs`](../../SnowmeetApi/Controllers/TicketPosterController.cs) | 封面读存储、海报写存储 |
| [`SnowmeetApi/wwwroot/fnb/mat_expire/mat.js`](../../SnowmeetApi/wwwroot/fnb/mat_expire/mat.js) | 同源上传，显示走 img |
| [`SnowmeetApi/SnowmeetApi.Tests/FileStorageTests.cs`](../../SnowmeetApi/SnowmeetApi.Tests/FileStorageTests.cs) | 新增 29 例 |
| [`snowmeet_wechat_mini/utils/data.js`](../../snowmeet_wechat_mini/utils/data.js) | `IMAGE_HOST` → img；上传走 API |
| [`snowmeet_wechat_mini/components/uploader/multi-uploader.js`](../../snowmeet_wechat_mini/components/uploader/multi-uploader.js) | 存 `IMAGE_HOST` 地址 |
| [`snowmeet_wechat_mini/pages/admin/ticket/template_edit/template_edit.js`](../../snowmeet_wechat_mini/pages/admin/ticket/template_edit/template_edit.js) | 封面用 `IMAGE_HOST` |
| [`snowmeet_wechat_mini/pages/ski_pass/skipass_detail_new.js`](../../snowmeet_wechat_mini/pages/ski_pass/skipass_detail_new.js) | 静态图改到 mini |
| [`sql/2026-10-03_upload_urls_to_img_host.sql`](../sql/2026-10-03_upload_urls_to_img_host.sql) | 改库脚本（已执行） |
| `.claude/skills/start-work/SKILL.md`、`.claude/skills/end-work/SKILL.md` | 22 端口超时先走 443 重试 |

## 学到的小知识

1. **中国区 CloudFront**：不能用 `*.cloudfront.cn` 对外；证书只能命令行传 IAM（路径 `/cloudfront/`）；建分配没选证书时，「设置」里不会出现「自定义 SSL 证书」项，边缘返回 `internal.cloudfront.cn`。
2. **分配 ID 和 OAI ID 都是 E 开头 14 位**：桶策略报 `Invalid principal` 先去「来源访问」页核对 ID；兜底写法 `{"CanonicalUser": "<S3 规范用户 ID>"}`。
3. **全局服务也要带中国区 region**：`aws iam ...` 不带 `--region cn-northwest-1` 会打到海外端点，报 `InvalidClientTokenId`，看着像凭证坏了。
4. **`sudo dotnet` 会用 root 的 HOME**：首次运行重下全部 NuGet 包，小磁盘会被写满。发布前先看部署目录文件的属主和服务器 bash_history 里的标准做法。
5. **输出目录 = 项目目录时**，旧的 `*.deps.json`/`*.runtimeconfig.json` 会和新产物重名（NETSDK1152），所以 `republish.sh` 先删它们。
6. **会删文件再重建的发布要后台跑并带回退**：SSH 断在「已停服务」和「已启动」之间会让线上一直停着。
7. **302 兜底让迁移不必和客户端同步发布**：磁盘上有的文件仍直接返回，没有的跳到新域名，旧版小程序和库里遗留地址都不受影响。
