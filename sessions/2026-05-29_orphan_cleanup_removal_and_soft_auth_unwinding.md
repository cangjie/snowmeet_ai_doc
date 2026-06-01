# 2026-05-29（续）MemberLogin 孤儿清理 + socialAccountForJob 强制覆盖删除 + pay-identity-confirm 软授权方案反复

接续 5-29 主线（MemberLogin 不再建 stub）。用户反馈"过去会员没验证手机号、支付新单时旧 openid/unionid MSA 被失效、又新生成会员"，给出案例 member id 41104 / 41105。本会话定位到两段历史遗留逻辑互相协同造成的死循环，给出修复；同时围绕 pay-identity-confirm 的"软授权 UX"反复迭代后回退到"按钮直接弹微信原生授权页"。

## 1. paymentId=42561 显示「支付成功」根因（未修，留作下次治理）

用户问：`https://snowmeet.wanlonghuaxue.com/api/Order/GetOrderFromPaymentByCustomer/42561?sessionKey=...` 返回的 `orderStatus` 为何是 "支付成功"，而 payment 实际为「待支付」。

### 1.1 启用本地 SnowmeetApi 排查

- 本地 5000 端口已有用户跑的 SnowmeetA（PID 5391），DB 连接配置 `config.sqlServer` 写的是 `161.189.64.210`（早已不通），但端口连接对应业务依赖未启用，因此 `curl localhost:5000` 返回 `SqlException`。
- 临时把 `config.sqlServer` 改成 prod IP `100.28.143.19`（CLAUDE.md「生产数据库」记的真实地址，`nc -vz` 端口 1433 通），起新进程在 5051 端口（不动用户的 5000）。
- 拉 `http://localhost:5051/api/Order/GetOrderFromPaymentByCustomer/42561?sessionKey=...` → 实际 JSON：

| 字段 | 值 |
|---|---|
| orderStatus | "支付成功" |
| paidAmount | 0.01 |
| totalCharge | 0 |
| total_amount | 0 |
| paying_amount | 0.01 |
| type | 租赁 |
| member_id | null |
| payments[0] | id=42559, status=支付成功, amount=0.01 |
| payments[1] | id=42561, status=待支付, amount=0.01 |

### 1.2 后端算法层面"正确"，前端屏蔽逻辑用错聚合

订单 [Order.cs:693-761](../SnowmeetApi/Models/Order/Order.cs#L693) `orderStatus` getter 逻辑：`totalCharge == 0 && paidAmount > 0` → `paidAmount >= totalCharge` 命中 → status="支付成功"。

42561 所属 order 71704 (`WT_ZL_260529_00011`) 上同时有另一笔 42559 已支付（¥0.01 测试单尾巴），导致整张订单聚合层面"全付完"，但当前 42561 这笔仍待付。

[`payment_entry.wxml:51`](../snowmeet_wechat_mini/pages/order/payment_entry.wxml#L51) 用 `order.orderStatus == '支付成功'` 来屏蔽身份验证/支付按钮，把这笔继承到错状态。

### 1.3 修复方向（待后续处理）

```xml
<!-- 改前 -->
<view wx:if="{{order.orderStatus=='支付成功'}}" class="pay-success">

<!-- 改后：以当前 payment 为准 -->
<view wx:if="{{payment && payment.status=='支付成功'}}" class="pay-success">
```

本次未改 — 用户随即聚焦到 41104/41105 根因，UI 屏蔽问题留作下次。

## 2. 41104/41105 死循环：MemberLogin 两段历史逻辑互相协同打回 PaymentIdentity 建的真实会员

### 2.1 DB 直查时间线

用户给出会员 id 41104 / 41105，sqlcmd 查 prod：

```sql
SELECT id, real_name, source, create_date, valid FROM member WHERE id IN (41104, 41105);
SELECT id, member_id, type, num, valid, create_date, update_date
FROM member_social_account WHERE member_id IN (41104, 41105) ORDER BY member_id, id;
SELECT * FROM social_account_for_job WHERE wechat_mini_openid = 'oHdTn5e...';
SELECT id, real_name, source, valid FROM member WHERE id = 40649;
```

| 时间 | 事件 |
|---|---|
| 2026-03-12 20:06:15 | `social_account_for_job.id=55` 创建：openid=oHdTn5e..., member_id=**40649**（脏数据，40649 member 不存在/已删） |
| 22:50:57.723 | PaymentIdentity 散客分支建 **41104**（valid=1, no cell） |
| 22:50:57.800 | 41104 的 wechat_mini_openid MSA 创建（valid=1） |
| 22:50:57.877 | 41104 的 wechat_unionid MSA 创建（valid=1） |
| 22:54:40.270 | **41104 的 2 条 MSA 同时 update_date=22:54:40.270 → valid=0**（MemberLogin 孤儿清理） |
| 22:54:40.270 | 41104.valid → 0 |
| 22:54:49.100 | PaymentIdentity submit_phone 再次走散客分支 → 建 **41105**（cell + openid + unionid 三条 MSA） |

### 2.2 根因链

1. 用户用同一 openid 触发 MemberLogin（新订单换 sessionKey）
2. [`MiniAppHelperController.cs:181-195`](../SnowmeetApi/Controllers/MiniAppHelperController.cs#L181) unionid 反查到 41104 → `memberId = 41104`
3. **[`line 190-194`](../SnowmeetApi/Controllers/MiniAppHelperController.cs#L190) `socialAccountForJob` 强制覆盖**：`memberId = jobAccount.member_id = 40649`（指向不存在的死会员）
4. `GetWholeMemberById(40649)` 返 null → `member = null` → `session.member_id = null`
5. **[`line 258-294` 孤儿清理 try/catch 块](../SnowmeetApi/Controllers/MiniAppHelperController.cs#L258)**：`oldMsaList = MSA where num==openid && member_id != 40649 && valid==1` → 命中 41104 的 wechat_mini_openid + wechat_unionid → 全部 valid=0 + 41104.valid=0 + 41104 的 orders 转给死会员 40649
6. 之后 PaymentIdentity `_resolveStatus` 反查 scanner：`GetWholeMemberByNum(openid, wechat_mini_openid)` 只匹配 valid=1 → 41104 的 MSA 已死 → null → 散客分支建 41105

这两段历史逻辑（jobAccount 强制覆盖 + 孤儿清理）协同把 PaymentIdentity 刚建的真实会员立刻打回失效，触发新一轮散客流，永久循环。

### 2.3 修复（必修 1+2，用户拍板）

| 文件 | 改动 |
|---|---|
| [`MiniAppHelperController.cs:190-201`](../SnowmeetApi/Controllers/MiniAppHelperController.cs#L190) | `socialAccountForJob` 覆盖加 `if (memberId == null)` 兜底守卫,不再无条件覆盖 unionid 反查结果 |
| [`MiniAppHelperController.cs:258-294`](../SnowmeetApi/Controllers/MiniAppHelperController.cs#L258) | 整段「孤儿清理」try/catch 删除 + 末尾 `await _db.SaveChangesAsync()` 一并删（仅服务该 try/catch 的写入） |

dotnet build 0 error / 12 warning（全为历史无关项）。

**数据修复用户明确不做**（id=55 脏数据、41104/41105 不动）— 等代码部署后,新流程不再重复制造问题，存量靠业务侧逐步会员合并即可。

## 3. pay-identity-confirm 软授权 UX 反复（最后回退到「按钮直接弹微信原生授权页」）

围绕「散客 vs 会员+无 cell 两种场景的「确认并继续」按钮行为」反复迭代：

### 3.1 迭代路径

1. **初始版**（5-29 morning）：`wx:if="{{!result.scannerMemberId || !result.scannerHasCell}}"` 加 `open-type=getPhoneNumber` → 两种场景都直接弹微信原生授权页（散客和会员无 cell 一致）
2. **散客硬授权 + 会员无 cell 软授权 popup**：用户先要求「会员无 cell 时弹提示」→ 我设计了底部滑入卡片（标题「建议授权手机号」+ 三按钮「授权 / 跳过 / 取消」）。散客保留硬流程
3. **用户拍板「客户端一致」**：「散客和会员+无 cell 客户端呈现都应该一样,差异在服务器端」→ 两个场景统一走软授权 popup
4. **解决 git 冲突**：远端 d8a3f2c "confirm" 跟我的统一 popup 冲突（远端是 `!scannerMemberId` 老版本），保留 HEAD（统一 popup）
5. **去掉「取消」按钮**：用户「支付是没有取消选项的」→ 删 popup 里的「取消」+ 去掉遮罩点击关闭，只剩「授权 / 跳过」二选一
6. **最终回退**：用户「我要微信原生的认证手机号的页面,就是新顾客用的那种!你 Y 怎么那么钟情于自己做个弹窗,又让顾客多点一次?」→ **删整个 popup,回到 1 的形态**：按钮直接 `open-type=getPhoneNumber`，无中间步骤

### 3.2 最终状态

[`pay-identity-confirm/index.wxml`](../snowmeet_wechat_mini/components/pay-identity-confirm/index.wxml)：
```xml
<button wx:if="{{!result.scannerHasCell}}"
        class="btn btn-primary"
        open-type="getPhoneNumber"
        bindgetphonenumber="onGetPhoneNumberAndConfirmDirect"
        disabled="{{busy}}">
  确认并继续
</button>
<button wx:else
        class="btn btn-primary"
        bindtap="onConfirmDirect"
        disabled="{{busy}}">
  确认并继续
</button>
```

- 散客 + 会员无 cell → 同一按钮（直接微信原生授权页）
- 会员有 cell → 普通 bindtap=onConfirmDirect 直接付
- 用户同意微信原生授权 → `onGetPhoneNumberAndConfirmDirect` 串 `submit_phone → confirm_direct` → 后端 `_submitPhone` 按 scanner 自动分流（null=建新会员,非 null=BindMemberMainCellNum 补 cell）
- 用户拒绝 → 走 `confirm_direct` 兜底,仍能支付

[`pay-identity-confirm/index.js`](../snowmeet_wechat_mini/components/pay-identity-confirm/index.js)：
- 删 `softAuthShow` data + `onConfirmTapNeedAuth` / `onSkipPhoneAndConfirm` / `onCloseSoftAuth` 三个 handler
- `onGetPhoneNumberAndConfirmDirect` 保持（散客 + 会员无 cell 共用）

[`pay-identity-confirm/index.wxss`](../snowmeet_wechat_mini/components/pay-identity-confirm/index.wxss)：删 `.soft-auth-*` 全部样式 + `.btn-ghost`

### 3.3 教训

- **微信原生 `getPhoneNumber` 授权页本身就是用户选择 UI**（同意/拒绝两按钮 + 一键授权提示），自己再套一层"软授权 popup"是多此一举,反而让用户多点一次
- 设计 phoneAuth UX 时，应先想清楚"微信原生页能否满足需求"，再决定是否需要自定义 wrapper
- 用户拍板「散客和会员无 cell 客户端一致」时，最简洁的实现是统一按钮条件（`!scannerHasCell`），无 popup
- 三次反复（加 popup → 删取消 → 删整个 popup）大幅消耗时间和耐心；下次类似 UX 需求先用截图/简描确认"用户期望的微信原生页是不是合需"

## 关键改动文件

| 文件 | 改动 |
|---|---|
| [`SnowmeetApi/Controllers/MiniAppHelperController.cs`](../SnowmeetApi/Controllers/MiniAppHelperController.cs) | `socialAccountForJob` 覆盖加 `memberId==null` 兜底守卫;删整段「孤儿清理」try/catch + 末尾多余 SaveChangesAsync |
| [`SnowmeetApi/config.sqlServer`](../SnowmeetApi/config.sqlServer) | (临时)改 IP 161.189.64.210 → 100.28.143.19（CLAUDE.md 记录的 prod；本次为本地排查方便,**未入库,机器本地**） |
| [`snowmeet_wechat_mini/components/pay-identity-confirm/index.{wxml,js,wxss}`](../snowmeet_wechat_mini/components/pay-identity-confirm/) | 反复迭代后最终：删整个 softAuth popup,按钮直接 `open-type=getPhoneNumber`;散客和会员无 cell 走同一按钮（`!scannerHasCell`） |

## 学到的小知识

1. **`social_account_for_job` 是历史员工/工作账号绑定表，存在指向已删 member 的脏数据**：member 表 0 行 / member_social_account 表 0 行 / social_account_for_job.id=55 仍指 member_id=40649。任何把它作为「权威 memberId 源」的逻辑都要先看 jobAccount.member_id 指向的 member 是否真的存在并 valid=1，盲目覆盖会把上游正确的反查结果污染掉

2. **MemberLogin 孤儿清理（line 258-294）的设计前提已经不成立**：原意是「同一 openid 应只能挂在一个 member 上,扫到多个时把旧的失效掉」。但 PaymentIdentity 改造后,新的散客会员是合法的"正在使用"的会员,不能因为旧的 jobAccount 或某条历史记录就被当作"老 openid"清理掉。5-29 拍板「scanner 优先,不动 MSA」原则下,这种主动清理必然冲突,不该再做

3. **`order.orderStatus` 是订单聚合状态,不能用来屏蔽单笔 payment 的支付 UI**：一张订单可以有多笔 OrderPayment（包括已付的、待付的、作废的）。用 `paidAmount >= totalCharge` 判断整单"已支付"在某些场景（如 totalCharge=0 + 任意小额支付）会误判。前端屏蔽支付按钮的条件应该基于「当前这笔 payment 的 status」,不是聚合的 orderStatus

4. **微信原生 `getPhoneNumber` 授权页本身就是用户决策 UI**：自己再画"软授权 popup"是多此一举的中间层。如果有"提示用户验证手机号"的需求,最直接的实现是让按钮 `open-type=getPhoneNumber`，让微信弹原生页（同意/拒绝都有原生回调），用户拒绝时 JS 走兜底分支即可。不要在 JS 层再画 popup 让用户多点一次

5. **`config.sqlServer` 的 IP 跨机不一致**：CLAUDE.md「生产数据库」记的是 `100.28.143.19`，但本机 `config.sqlServer` 存的是 `161.189.64.210`（早已不通的老 IP）。这个文件在 .gitignore 里，跨机/跨开发环境时不一致是常态；本地起 SnowmeetApi 排查 prod 数据前先 `nc -vz 100.28.143.19 1433` 验通后改 config.sqlServer,记得别 commit 该文件

6. **本机 DB 连接需要 VPN/隧道**：`ifconfig` 看到多个 `utun*` 接口（VPN tunnel）。直接 `ping 100.28.143.19` 超时（ICMP 被防火墙拦），但 `nc -vz` 端口 1433 通 → 说明 TCP 路径 OK，可以用 sqlcmd 直连。排查时优先用 `nc` 测端口，别被 ping 超时误导

7. **会员的 cell/wechatMiniOpenId 计算属性依赖 MSA valid=1**：`Member.cell` 是 `[NotMapped]` 计算属性，getter 遍历 `memberSocialAccounts` 找 `type='cell' AND valid=1`。任何让 MSA valid 落 0 的逻辑都会让计算属性返 null → `scannerHasCell=false` → 引发"明明绑了为什么查不到"的死循环。5-29 已发现 BindMemberMainCellNum 漏 valid=1，本会话又发现 MemberLogin 主动 invalidate 的副作用，两者叠加是死循环根因

8. **会话进度 vs 用户耐心**：本会话历时较长，多轮反复（popup 加→改→删；payment 42561 未修；UX 三次反弹）显著消耗用户耐心。下次类似 UX 需求,先用一句话确认"用户期望什么"(eg「您想要微信原生授权页弹出来,还是要我们自己画一个 popup?」),再动手,避免猜错方向后多次反弹
