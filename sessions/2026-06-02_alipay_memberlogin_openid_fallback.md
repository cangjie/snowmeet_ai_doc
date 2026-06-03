# 2026-06-02 alipay MemberLogin：oauth.token 成功但仅返 open_id，旧逻辑误判失败

用户执行 `start-work` 后，转而排查支付宝小程序 `MiniAppHelper/MemberLogin?openIdType=alipay_payerid`。表象是支付宝开发工具里实时 `my.getAuthCode` 触发的请求仍返回：

```json
{
  "code": 1,
  "data": null,
  "message": "支付宝 oauth.token 失败："
}
```

## 1. 第一轮定位：把空错误改成可定位错误

原代码在 [`SnowmeetApi/Controllers/MiniAppHelperController.cs`](../SnowmeetApi/Controllers/MiniAppHelperController.cs) 的 `_alipayMemberLogin` 中，只要 `tokenResp.IsError || AccessToken 为空 || UserId 为空` 就统一报：

```csharp
result.message = "支付宝 oauth.token 失败：" + (tokenResp.SubMsg ?? tokenResp.Msg);
```

而这次 `Msg/SubMsg` 也为空，所以用户只能看到一个空冒号。先做了两处增强：

1. `catch(Exception e)` 时把异常类型、`InnerException` 一并拼回 message
2. 失败分支把 `Code / SubCode / Msg / SubMsg / Body` 摘要一起回给前端

这样用户重新部署后，第二次就贴回了真实 body。

## 2. 第二轮定位：token 实际成功，只是没有 user_id

用户新贴回的错误里，body 明确包含：

- `access_token`
- `refresh_token`
- `open_id`

但没有 `user_id`。

这直接说明：

- `alipay.system.oauth.token` **已经成功**
- 旧逻辑把“缺 `UserId`”误当成“oauth.token 失败”

根因是 `_alipayMemberLogin` 的成功条件写得过窄：

```csharp
if (tokenResp.IsError || string.IsNullOrEmpty(tokenResp.AccessToken) || string.IsNullOrEmpty(tokenResp.UserId))
```

而支付宝小程序 `auth_base` 场景下，这次实际返回的是 `open_id`，SDK 对象的 `UserId` 没值。

## 3. 修复策略：payerId = user_id ?? open_id

修复定调：`alipay_payerid` 在业务上代表“支付宝付款方唯一标识”，不应绑死成必须是 `user_id`。

因此在 [`MiniAppHelperController.cs`](../SnowmeetApi/Controllers/MiniAppHelperController.cs) 做了以下修改：

1. 先从 SDK 字段取 `AccessToken`、`UserId`
2. 再从 `tokenResp.Body` 解析：
   - `alipay_system_oauth_token_response.user_id`
   - `alipay_system_oauth_token_response.open_id`
3. 计算：`payerId = user_id ?? open_id`
4. 成功条件改为：`!IsError && accessToken 非空 && payerId 非空`
5. `member_social_account(type='alipay_payerid')` 查询同时兼容 `payerId/userId/openId`
6. `mini_session.wechat_openid` 复用列、返回对象 `alipay_payerid`、`GetStaffBySocialNum` 全部统一改用 `payerId`

## 4. 验证

本地执行：

```bash
cd SnowmeetApi
dotnet build
```

结果：编译通过，仅保留仓库原有 warnings，无新增 errors。

## 5. 结论

这次不是：

- auth_code 过期
- 开发工具没实时发码
- appId 不一致
- 证书/签名又坏了

而是更具体的兼容性问题：**oauth.token 成功，但返回的是 open_id，旧代码只接受 user_id，导致成功响应被误判成失败**。

部署该修复后，预期 `MemberLogin` 返回 `code=0`，并把 `access_token` 作为 `session_key` 写入 `mini_session(session_type='alipay_payerid')`。未注册用户的 `member=null` 仍属于设计内行为，后续由 PaymentIdentity 流程负责建会员。