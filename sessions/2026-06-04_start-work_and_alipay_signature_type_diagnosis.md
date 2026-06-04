# 2026-06-04 start-work 与支付宝签名配置诊断：ConfirmPayIdentity 软失败降噪

本场会话先执行 start-work（读取上下文 + 盘点多仓库状态），随后定位 `PaymentIdentity/ConfirmPayIdentity` 返回 `choose_identity` 且 message 包含 `isv.missing-default-signature-type` 的原因，并完成一处后端降噪修复。

## 1. start-work 执行

### 1.1 上下文与仓库状态

- 读取项目主上下文：[`snowmeet_ai_doc/CLAUDE.md`](../CLAUDE.md)
- 多仓库状态：
- `alipay_snowmeet`：`main`，behind 1，改动 [`alipay_snowmeet/app.js`](../alipay_snowmeet/app.js)
- `snowmeet_wechat_mini`：`ai`，behind 2，改动 [`snowmeet_wechat_mini/components/order-payment/index.js`](../snowmeet_wechat_mini/components/order-payment/index.js)
- `SnowmeetApi`：`ai`，干净
- `snowmeet_ai_doc`：`main`，干净（开始时）

## 2. 手机号解析失败根因

### 2.1 现象

- 接口返回 `code=0`，`status=choose_identity`
- message 含：`支付宝 getPhoneNumber 解密失败: Missing Required Arguments (code=40001, subCode=isv.missing-default-signature-type)`

### 2.2 定位结论

- 这不是“用户账号没绑定手机号”导致
- 是支付宝侧返回的业务错误对象（缺默认签名方式配置）
- 后端 helper 会透传该错误：[`SnowmeetApi/Helpers/AlipayPhoneDecryptHelper.cs`](../SnowmeetApi/Helpers/AlipayPhoneDecryptHelper.cs)

### 2.3 配置侧排查点

- 小程序 appId `2021006157624571` 的默认签名方式是否已配置 `RSA2`
- 应用公钥/支付宝公钥证书链是否完整且生效
- 手机号授权能力是否已开通
- 部署环境 `AlipayCertificate/{appId}/aes_key.txt` 是否存在且内容有效

## 3. 本次代码修复

### 3.1 变更内容

- 修改文件：[`SnowmeetApi/Controllers/Order/PaymentIdentityController.cs`](../SnowmeetApi/Controllers/Order/PaymentIdentityController.cs)
- 修改点：alipay `submit_phone` 软失败分支返回 `message=""`，不再把底层技术错误文案显示给用户
- 诊断信息仍保留在服务端日志（`Console.WriteLine`）

### 3.2 验证

- 本地编译：`dotnet build SnowmeetApi.csproj -nologo`
- 结果：通过（0 error，12 条历史 warning）

## 关键改动文件

| 文件 | 改动 |
|---|---|
| [`SnowmeetApi/Controllers/Order/PaymentIdentityController.cs`](../SnowmeetApi/Controllers/Order/PaymentIdentityController.cs) | alipay submit_phone 软失败返回文案降噪（message 置空） |
| [`snowmeet_ai_doc/CLAUDE.md`](../CLAUDE.md) | 追加 2026-06-04 会话总结与待办 |
| [`snowmeet_ai_doc/sessions/2026-06-04_start-work_and_alipay_signature_type_diagnosis.md`](2026-06-04_start-work_and_alipay_signature_type_diagnosis.md) | 本次会话归档 |

## 学到的小知识

1. **`isv.missing-default-signature-type` 是配置错，不是手机号未绑定**：账号侧手机号状态正常，也会因应用签名配置缺失而失败。
2. **`choose_identity` 与手机号授权失败可并存**：当前流程将 submit_phone 作为软依赖，失败后仍可继续身份选择分支。
3. **用户端与诊断端要分层**：前端不应暴露底层解密报错，排障信息应留在服务端日志。