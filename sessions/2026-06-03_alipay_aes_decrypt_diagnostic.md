# 2026-06-03（续）支付宝 my.getPhoneNumber AES 解密：诊断版后端 + 真机首轮 pending 回归

接续 6-2 留下的 alipay AES 解密 pending bug，以及同一天上午刚归档的 4 业务财年报表退款列扩展。本节切片只做诊断准备 + 部署排查，**未修根因**，等晚上真机回归。所有改动落在 `SnowmeetApi/` 仓库（`origin/ai bd0baa74`），`snowmeet_ai_doc/` 仓库本节只新增 sessions 和 CLAUDE.md dev log。

## 1. 切片前的状态

- 6-2 留下 pending：用户报 `手机号解析失败: The input is not a valid Base-64 string`，来自 [`PaymentIdentityController._extractPhone`](../SnowmeetApi/Controllers/Order/PaymentIdentityController.cs#L546) alipay 分支 `Util.AES_decrypt` 里的 `Convert.FromBase64String`。三处可能：`key`（aes_key.txt 内容）、`iv`（硬编码 `"AAAAAAAAAAAAAAAAAAAAAA=="`，长度合法可排除）、`encryptedDataStr`（body.encData = my.getPhoneNumber 返回的 res.response 字符串）
- 6-2 列的下次首要排查：①加诊断日志看入参形状 ②前端 res.response 是否 URL 编码 ③aes_key.txt 是否有 BOM/CRLF

## 2. 调查阶段

### 2.1 阅读关键代码

- [`PaymentIdentityController._extractPhone`](../SnowmeetApi/Controllers/Order/PaymentIdentityController.cs#L546) alipay 分支：
  - 取 `body.encData` → `Util.UrlDecode` → `Trim` → `Util.AES_decrypt(encResponse, aesKey, zeroIv)`
  - `aesKey = _loadAlipayAesKey()` 读 `AlipayCertificate/2021006157624571/aes_key.txt`，`.ReadToEnd().Trim()`（**不去 BOM**）
- [`Util.AES_decrypt`](../SnowmeetApi/Util.cs#L273) 三处 `Convert.FromBase64String`：key/iv/encryptedDataStr 任一非 base64 都抛 FormatException
- [`Util.UrlDecode`](../SnowmeetApi/Util.cs#L100) `HttpUtility.UrlDecode + Replace(" ", "+") + Trim` — base64 字符集对 URL decode 是 idempotent，理论上无副作用
- 前端 [`alipay_snowmeet/components/pay-identity-confirm/index.js`](../alipay_snowmeet/components/pay-identity-confirm/index.js) `_getPhoneThen`：`var encData = (res && (res.response || res.encryptedData)) || ''` → 直接当 base64 字符串透传，**未做 JSON 解包**

### 2.2 alipay_snowmeet 仓库部署状态

- 5-30 落 Phase A 后端 + 5-31 证书联调收尾。`AlipayCertificate/2021006157624571/` 目录有 6 个证书文件（CSR/私钥/公钥/根证书等），**但本地工作树没 aes_key.txt**（gitignored 或部署时单独放）
- 服务端 `_loadAlipayAesKey()` 文件不存在会抛"支付宝 AES 密钥文件不存在"，不是 base64 错；既然 6-2 用户报 base64 错，说明服务器上 aes_key.txt 实际**存在**

## 3. 实施：诊断版后端

### 3.1 改 _extractPhone alipay 分支

三处 base64 decode 分别包 try-catch + 上下文：

```csharp
string aesKey;
try { aesKey = _loadAlipayAesKey(); }
catch (Exception ex) { throw new Exception("aes_key.txt 读取失败: " + ex.Message); }

string aesKeyRepr = aesKey.Length <= 12 ? aesKey : aesKey.Substring(0, 12) + "...";
Console.WriteLine($"[_extractPhone:alipay] aesKey.Length={aesKey.Length} head12={aesKeyRepr} bom={(aesKey.Length > 0 && aesKey[0] == '﻿')}");

const string zeroIv = "AAAAAAAAAAAAAAAAAAAAAA==";
try { var _ = Convert.FromBase64String(aesKey); }
catch (FormatException fe) { throw new Exception("aesKey 不是合法 base64 (len=" + aesKey.Length + " head12=" + aesKeyRepr + "): " + fe.Message); }
try { var _ = Convert.FromBase64String(zeroIv); }
catch (FormatException fe) { throw new Exception("zeroIv 不是合法 base64 (硬编码 bug?): " + fe.Message); }
string encTrimmed = encResponse.Trim();
try { var _ = Convert.FromBase64String(encTrimmed); }
catch (FormatException fe) { throw new Exception("encData 不是合法 base64 (len=" + encTrimmed.Length + " head40=" + ... + "): " + fe.Message); }
```

期望：真机回归时前端 toast 显示 `手机号解析失败: aesKey/encData/aes_key.txt 不是合法 base64 (len=N head12=XXX): The input is not a valid Base-64 string ...` 直接定位是哪一段失败 + 实际入参形状。

### 3.2 编译 + commit + push

```bash
cd D:/snowmeet/SnowmeetApi
dotnet build  # 0 错 + 14 历史无关警告
git add Controllers/Order/PaymentIdentityController.cs
git commit -m "PaymentIdentity._extractPhone alipay 分支加诊断日志"
git push   # → origin/ai bd0baa74
```

## 4. 真机首轮回归（pending — 部署没到位）

### 4.1 实操步骤指导（给用户）

按 Linux + systemd 部署：
1. SSH 到服务器，`cd /home/ubuntu/webs/SnowmeetApi`
2. `sudo git pull --ff-only origin ai` 拉到 bd0baa74
3. `sudo dotnet publish -c Release -o /home/ubuntu/webs/SnowmeetApi`
4. `sudo systemctl restart mini.snowmeet.top.service`
5. `sudo systemctl status mini.snowmeet.top.service --no-pager | head -5` 验证 Started 时间是刚才
6. 真机 alipay_snowmeet 扫码 → 点身份按钮 → 同意手机号授权
7. 抓 toast / `sudo journalctl -u mini.snowmeet.top.service -f` 看 `[_extractPhone:alipay]` 三行

### 4.2 真机首次回归结果：服务器没部署到 bd0baa74

用户真机截图 toast 显示：
> 手机号解析失败: The input is not a valid Base-64 string as it contains a non-base 64 character, more than two padding characters, or an illegal character among the padding characters.

**关键诊断**：toast 里只有**原始 .NET FormatException 文本**，**没有** `aesKey 不是合法 base64 (len=N head12=...)` 或 `encData 不是合法 base64` 前缀 → 服务器跑的还是 6-2 `fecea2bb` 版本，bd0baa74 没生效。

部署排查 3 步骤（晚上回归用）：
- `git log -1 --oneline` 看本地 commit；若 ≠ bd0baa74 → `sudo git pull --ff-only origin ai`
- `ls -la SnowmeetApi.dll` 看时间戳；若不是 publish 时间 → 必须 `dotnet publish` 不是 `dotnet build`
- `systemctl status` 确认 Started 时间是刚 restart 的

### 4.3 systemd / journalctl 信息（用户告知）

- 服务名：`mini.snowmeet.top.service`
- 启动用户：`ubuntu`
- 内容根：`/home/ubuntu/webs/SnowmeetApi`
- ASP.NET listening on `http://[::]:5000`
- Hosting environment: Release
- 用户能 SSH，stdout 走 journald（默认 systemd 行为）

### 4.4 触发链确认

- **只刷新页面**：只调 `CheckPayerIdentity`（GET），决策 OK 时返 status=direct/choose_identity/...，不进 `_extractPhone`
- **点身份按钮**（"确认并继续"/"正常支付"/"替人代付"）：触发 `my.getPhoneNumber` → 同意 → `ConfirmPayIdentity action=submit_phone` 进 `_extractPhone` alipay 分支 → `body.encData` 走 base64 decode
- 用户首轮可能只刷新页面没点按钮 → journalctl 自然没新行；但 toast 出现 base64 错说明确实有触发 ConfirmPayIdentity，只是后端代码还是老版

## 5. 强假设（待真机日志验证）

alipay `my.getPhoneNumber` 新版 SDK 返 `res.response` 可能是 **JSON 包装**结构：

```json
{"response": "<base64 encrypted>", "sign": "...", "signType": "RSA2"}
```

而不是直接的 base64 加密串。如果命中，`encData head40={"response":"...` 而不是纯 base64 字符。前端 `_getPhoneThen` 把这 JSON 当成 base64 直传 → 后端炸 `not a valid Base-64 string`。

3 条候选修复路径（等日志定）：
- **A**（强假设）：前端 `_getPhoneThen` 用 `JSON.parse(res.response).response` 取内层；或后端 `_extractPhone` 兼容两种格式
- **B**（aes_key.txt BOM/CRLF）：`_loadAlipayAesKey` 加 `.TrimStart('﻿')` + 字符过滤 `[A-Za-z0-9+/=]`
- **C**（encData URL 编码污染）：`Util.UrlDecode` 不适合 base64；改纯字符清洗 `Replace("\r","").Replace("\n","").Replace(" ","+")`

## 关键改动文件

| 文件 | 改动 |
|---|---|
| `SnowmeetApi/Controllers/Order/PaymentIdentityController.cs` | _extractPhone alipay 分支：3 处 Convert.FromBase64String 分别 try-catch + 上下文塞入异常 message；_loadAlipayAesKey 异常透传；Console.WriteLine 打 length/head/BOM 标志 |

`SnowmeetApi` 仓库已 commit + push `bd0baa74` 到 `origin/ai`。

## 学到的小知识

1. **systemd 服务默认 stdout → journald**：ASP.NET Core `Console.WriteLine` 直接写 stdout，会被 systemd 捕获到 journald，用 `journalctl -u <svc>` 看。除非服务文件里 `StandardOutput=null` 或 ExecStart 有 `> /dev/null` 重定向
2. **dotnet publish vs dotnet build**：`build` 只产生 bin/Debug 的开发产物，**不会**更新 deploy 目录里的 .dll；production 必须 `dotnet publish -c Release -o <output>`。新手最容易踩的部署陷阱
3. **诊断信息塞异常 message 比 stdout 友好**：前端 toast 直接展示 `ex.Message`，用户无需 SSH 抓日志就能给你完整诊断。代价是异常 message 变长，正常用户看不友好——所以只在 debug 期这么做，根因定后再清理
4. **base64 错的 3 个嫌疑点是相互独立的**：key/iv/encryptedDataStr 任一非 base64 都会从 `Util.AES_decrypt` 抛同一种 FormatException。不分段 catch 就只能猜，分别 catch + 拼上下文一次定位
5. **alipay my.getPhoneNumber 在 SDK 不同版本里返回结构有差异**：老版 `encryptedData`、新版 `response`，且 `response` 可能是 JSON 包装也可能是直接 base64。前端代码光做 `(res.response || res.encryptedData)` 兼容字段名还不够，可能还要解 JSON 包装。等真机日志确认
6. **真机部署失败也有典型表征**：前端 toast 错误文本是「原始库异常 message」而不是「业务代码包装过的 message」，强提示后端没跑新代码。本次靠这个判断省一轮 SSH 排查
