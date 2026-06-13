# 2026-06-05 支付宝手机号解密失败闭环：确认应用网关默认签名类型缺失

接续 6-4 的 sign_type 配置诊断，本场围绕 `submit_phone` 失败持续联调，目标是回答「为什么手机号不入库」。改动主要落在 `alipay_snowmeet/` 和 `SnowmeetApi/Controllers/Order/PaymentIdentityController.cs`，并补了可视化诊断链路。

## 1. 复现与定性

### 1.1 线上现象复现

- `ConfirmPayIdentity?action=submit_phone` 返回 `code=0`、`status=choose_identity`
- `scannerHasCell=false`，手机号未写入数据库
- 初始阶段 message 含：`isv.missing-default-signature-type`

### 1.2 离线解密定性

- 用用户现场 `encData.response` + 本地 `aes_key.txt` 离线解密
- 明文稳定得到：
  - `code=40001`
  - `subCode=isv.missing-default-signature-type`
  - `subMsg=应用未设置默认签名类型`
- 结论：本地 AES/base64 算法链路可用，问题是支付宝上游返回错误对象，而不是手机号数据

## 2. 联调改动

### 2.1 前端授权链路与诊断

- `alipay_snowmeet/components/pay-identity-confirm/index.axml`
  - 无手机号分支统一走 `open-type=getAuthorize scope=phoneNumber`
- `alipay_snowmeet/components/pay-identity-confirm/index.js`
  - `onGetAuthorize` 后再调用 `my.getPhoneNumber`
  - 增加 `onGetAuthorize meta` / `getPhoneNumber success meta` 诊断日志
  - 若 `response` 为错误 JSON，对应分支直接兜底，不再送后端解密
- `alipay_snowmeet/app.js`
  - `alipayUserId` 优先用 `sessionObj.alipay_payerid`，避免未注册会员时 `scannerId` 为空
  - 新增 runtime app 信息日志（`appId/envVersion`）用于环境自证

### 2.2 后端软失败降噪与诊断透出

- `SnowmeetApi/Controllers/Order/PaymentIdentityController.cs`
  - alipay submit_phone 软失败时不再污染前端主状态（`errorCode/errorMessage/message` 清空）
  - 返回 `data.debugInfo`，包含 `encMeta + ex` 摘要，便于无服务器日志场景联调
  - 增加结构化 `encMeta` 组装（shape/len/hasResponse/hasCode/signType/subCode）

## 3. 关键验证

### 3.1 本地接口回放

- 本地启动 `https://localhost:5000`
- 回放同一 `submit_phone` 请求，返回包含 `debugInfo`
- `debugInfo` 内 `ex` 与离线解密结果一致，均指向 `isv.missing-default-signature-type`

### 3.2 用户侧确认

- 用户最终确认：支付宝应用网关未配置默认签名类型
- 根因闭环完成

## 4. 结论与后续

- 当前手机号不入库是上游返回错误对象导致，行为符合软失败分支预期
- 配置补齐并生效后，预期 `submit_phone` 将返回真实手机号密文，后端可正常落库
- 若线上继续联调，建议先部署本场后端改动，以便直接从接口响应读取 `debugInfo`

## 关键改动文件

| 文件 | 改动 |
|---|---|
| `alipay_snowmeet/components/pay-identity-confirm/index.axml` | 改为 getAuthorize 授权链路 |
| `alipay_snowmeet/components/pay-identity-confirm/index.js` | 授权/手机号回调诊断日志 + 错误对象兜底 |
| `alipay_snowmeet/app.js` | `alipayUserId` 回填修正 + runtime appId/envVersion 诊断 |
| `SnowmeetApi/Controllers/Order/PaymentIdentityController.cs` | submit_phone 软失败降噪 + `debugInfo` + `encMeta` |
| `snowmeet_ai_doc/CLAUDE.md` | 追加 2026-06-05 会话总结 |
| `snowmeet_ai_doc/sessions/2026-06-05_alipay_phone_sign_type_root_cause.md` | 新增会话归档 |

## 学到的小知识

1. **`my.getAuthCode` 与 `my.getPhoneNumber` 是两条独立能力链**：前者可用不代表后者加签配置生效。
2. **解密后出现 `code/subCode` 是上游业务错误，不是本地解密错误**：应先从平台配置排障。
3. **联调应双端留痕**：前端回调 meta + 后端 encMeta 同时具备时，定位效率显著提升。
