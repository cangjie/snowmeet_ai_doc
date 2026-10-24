# 2026-10-23～24 扫码报到算已核验本人 + 测试订单 + 隐藏个人微信转账 + 养护代付 + SQL 转发改 5789：后端两次部署，小程序待下次提审

Mac mini（`/Users/cangjie/source/snowmeet/snowmeet_ai`）。接续 10-22～23 的扫码接待上线工作。改动落在 SnowmeetApi（`ai`，`33e1b2de` → `2d611b98`）和 snowmeet_wechat_mini（`ai`，`5de080ba` → `f8a1d17e`），都已推送；**后端当晚 18:46 部署到 mini（见第 8 节）**，小程序待下一次提审。

## 1. start-work

- 文档仓 `git pull` 走 22 端口 60 秒超时，改走 443（`ssh.github.com`，`HostKeyAlias=github.com`）。第一次被 kill 的拉取已把远端引用更新，导致 443 那次报 `cannot lock ref`，直接 `merge --ff-only origin/main` 快进到 `e28a804`。
- 四个仓库 fetch（443）：SnowmeetApi 落后 22（10-15～10-23 的食材 v4 / 七色米 / 扫码接待），小程序、公众号已同步，reqai 落后 18。
- 核实：10-16 下午那 4 个食材 v4 提交（到 `6e38f60d`）是已部署 `33e1b2de` 的祖先，**早已上线**，文档里的「待确认」可以划掉。
- `scan.py --check`：#5 #7 两个 reqai 会话未分析。

## 2. 扫码报到后，用券还要不要再核验身份

### 2.1 用户的问题

> 如果顾客在开单之前就识别身份了……使用了优惠券，他支付成功后，是不是就可以直接核销了？

### 2.2 核查结论（当时）

- 订单的「已核验本人」标识是 `order.wechat_unverified`（1 = 已核验，命名与字面相反）。写入点只有两处：`PaymentIdentity/VerifyWechatIdentity`（扫核验码）和 `DealSuccessPaidOrder`（本人微信付款）。
- 扫码报到只写 `scan_qrcode`（`scaner_member_id`、`cell`、`scan_time`），和订单没有关联。
- 按付款方式分：
  - 本人微信付款：付款即核验，本来就不用再扫；
  - 支付宝（养护）：先弹核验码（`order-payment/index.js` 第 193 行）；
  - 券卡全额 0 元单、储值：`WriteoffCareOrder` 要求已核验（后端 `OrderController.cs` 3526 行 + 前端 104 行）；
  - 租赁储值付租金、次卡销售：同一个标识。
- 顺带发现：「现金 / 其他」确认收款完全不做身份核验，券照样核销（已告知用户，未处理）。

### 2.3 用户拍板

> SnowmeetApi 已经pull，反正就是开单前的接待页面扫码了验证身份了，订单从一生成开始，wechat_unverified 就应该设置为1。

## 3. 实现：订单一生成就是「已核验本人」

### 3.1 第一版：小程序带报到码（`c5605156` / `6fc36470`）

- `recept_member` 跳 `recept_new` 时带 `checkinId`；`recept_new` 在 `SaveRentRecept`、`SaveCareRecept`、`PlaceOrder` 的 URL 上带它。
- 后端新文件 `Helpers/OrderVerifiedRules.cs`：
  - `CheckinVouches`：`rc_` 码、`IsVerified`（scaned=1 + 有会员 + 有手机号）、`staff_id` 是本店员、`scaner_member_id` 是订单会员、`scan_time` 在 60 分钟内（复用 `CUSTOMER_WAIT_MINUTES`）；
  - `ResolveOnSave`：担保 → 1；否则库里已是 1 且会员没换 → 1；其余 0。**不采信前端传来的值**（草稿接口把整单原样写库）；
  - `ResolveOnPaid`：本人微信付款 → 1；此前已核验且这次付款没改订单会员 → 保持 1；其余 0；
  - `ChangeLog`：取值变化写 `core_data_mod_log`（scene=开单）。
- 「店员输手机号、店长授权」进入时 `recept_member` 也拿到同一个 `checkinId`，但那张码 `scaned=0`，`IsVerified` 不通过，自然排除。
- `DealSuccessPaidOrder` 原规则（6-15 用户定的「其余一律 0」）会把已核验的单在支付宝付款后冲回 0，与「从生成开始就是 1」冲突，改为 `ResolveOnPaid`。
- 收银组件 wxml：已核验时按钮改「确认核销 / 确认储值扣款」，原来写着「微信核验会员本人并核销」，点了却直接核销，文案误导。

### 3.2 用户追问「为什么需要修改小程序」

- 回答：报到和订单没关联，只有店员手机知道这张单从哪个报到来的，所以让小程序带。**但这不是唯一办法**：后端可以自己查「这位店员 60 分钟内、被本单会员本人扫码验证过的报到」，条件和传参几乎等价。
- 关键点：扫码报到页面本身在未上传的 `5de080ba` 里，小程序无论如何要上传；后端自己查的好处是部署即生效，手动录入页、找回中断单开的单也能覆盖。
- 用户：「上一个问题改成后段自己查吧」。

### 3.3 第二版：后端自己查（`902af2ed` / `1d51fac0`）

- `QrCodeController.ResolveReceptOrderVerified(order, staffId)` 返回 `(库里原值, 新值, 担保的报到码 id)`：
  - 已是 1 且会员没换 → 直接返回，不查报到（草稿每改一次就保存一次）；
  - 否则查 `scan_qrcode` 里 `staff_id`=本店员、`scaner_member_id`=订单会员、`scaned=1`、`scan_time` 在 60 分钟内的候选，用 `OrderVerifiedRules.PickVouchingCheckin` 取最近一条。
- 三个接口去掉 `checkinId` 参数；小程序 `recept_member`、`recept_new` 撤掉传参。

## 4. 「这是测试订单」（`bfe9d020` / `0d65bbb2`）

- 用户要求顾客信息页加勾选，勾了下单时 `order.is_test=1`。
- 现有规则：租赁/养护草稿新建时按域名（不是 `mini.snowmeet.top` 就是测试单），零售 `PlaceOrder` 按店员 28/31/34；两处都覆盖前端值；`PlaceRentOrder` / `PlaceCareOrder` 不动 `is_test`。
- 做法：勾选行放在店铺和业务类型之间（自定义勾选框，勾上变红）；`isTest=1` 带到 `recept_new`，三接口加 `isTest` 参数，「勾了就是测试单」叠加在原规则上。零售 `PlaceOrder` 只认店员会话（顾客自己买次卡也走它）。
- 只加在 `recept_member`，`recept_entry` 是否要加问了用户，未答复。

## 5. 隐藏个人微信转账（`2d611b98`）

- 用户：「这些以微信转账结尾的支付方式，全部隐藏，暂时不允许个人微信转账。」截图圈了苍杰微信转账、王政微信转账、肖志强工作微信转账。
- 列表来源：`Order/GetUnCommonPayMethod` 取历史收款成功的 `pay_method` 去重，前端再加「京东收银 / POS机刷卡 / 现金」和「手工填写」。新版 `order-payment`、旧版 `payment.js`、`legacy` 都用它。
- 改动：`Helpers/PayMethodRules.IsPersonalWechatTransfer`（`EndsWith("微信转账")`）；列表接口过滤；`EffectUnpaidOrder` 在作废旧待支付单之前拒绝（`!payLater` 时），提示「暂不允许个人微信转账收款」，堵住「手工填写」。
- 就叫「微信转账」的那一项用户没圈，按「全部」字面一并隐藏，已告知可以排除。
- 核实前端只 `encodeURIComponent` 一次，ASP.NET 自动解码，后端判断有效。

## 6. 养护详情页打印按钮移位（`f8a1d17e`）

- 用户截图：「这两个打印按钮，应该放到装备信息之后，养护任务之前。」
- `care_order_detail.wxml` 把「打印」块从卡片底部（发板核销之后）移到「养护任务」标题之前；间距沿用（按钮行和子标题上边距都是 24rpx）。编辑模式下按钮在编辑面板下面。

## 7. 部署讨论

- 用户问：「如果现在部署服务器端，旧的小程序客户端还可以安全运行吗？之前提交的小程序还没有通过审核。」
- 逐项核对：
  - 新参数都是可选的，返回格式不变；
  - 线上旧版没有报到页面，后端查不到报到，行为不变；草稿阶段旧版本来不会合法地写 1；
  - 支付回调只影响「已扫核验码、再用支付宝 / 代付」的单，结果是不再要求重复核验；
  - 个人微信转账：旧版列表同样看不到；手工填写被拒、订单保持未付，但旧组件 `.catch` 固定弹「处理失败」，盖掉后端原因；
  - 审核中的版本：带不带 `checkinId` 后端都能处理（多余参数被忽略）；其收银组件「已核验就直接核销」的逻辑本来就有，只是按钮文案旧。
- 结论：可以单独先部署后端。**用户决定：「现在不要部署，等现在审核的小程序通过审核后，我们再来部署。到时候我通知你。」**

## 关键改动文件

| 文件 | 改动 |
|---|---|
| [`SnowmeetApi/Helpers/OrderVerifiedRules.cs`](../../SnowmeetApi/Helpers/OrderVerifiedRules.cs) | 新建：报到担保、挑报到、草稿保存取值、支付成功取值、变化日志 |
| [`SnowmeetApi/Helpers/PayMethodRules.cs`](../../SnowmeetApi/Helpers/PayMethodRules.cs) | 新建：以「微信转账」结尾即个人微信转账 |
| `SnowmeetApi/Controllers/QrCodeController.cs` | 新增 `ResolveReceptOrderVerified`（后端查报到） |
| `SnowmeetApi/Controllers/RentController.cs` | `SaveRentRecept`：后端定已核验 + `isTest` |
| `SnowmeetApi/Controllers/CareController.cs` | `SaveCareRecept`：同上 |
| `SnowmeetApi/Controllers/OrderController.cs` | `PlaceOrder` 已核验 + `isTest`；`DealSuccessPaidOrder` 改 `ResolveOnPaid`；`GetUnCommonPayMethod` 过滤；`EffectUnpaidOrder` 拒绝个人微信转账 |
| `SnowmeetApi/SnowmeetApi.Tests/OrderVerifiedRulesTests.cs`、`PayMethodRulesTests.cs` | 新增单测 15 + 12 项 |
| `snowmeet_wechat_mini/pages/admin/reception/recept_member.{js,wxml,wxss}` | 「这是测试订单」勾选，带 `isTest=1` |
| `snowmeet_wechat_mini/pages/admin/reception/recept_new.js` | `_receptQuery` 给三个建单请求带 `isTest` |
| `snowmeet_wechat_mini/components/order-payment/index.wxml` | 已核验单的核销按钮文案 |
| `snowmeet_wechat_mini/pages/admin/care/care_order_detail/care_order_detail.wxml` | 打印按钮移到装备信息之后 |

## 学到的小知识

1. **报到和订单的关联可以由后端推断**：同一店员 + 同一会员 + 短时间窗，几乎等价于前端显式传报到 id，还能覆盖其他开单入口，且不依赖小程序发版。
2. **草稿接口原样写库会让「状态字段」被前端旧值覆盖**：`recept_new` 去结算后把上一单 `...rentOrder` 展开成新草稿，旧的 `wechat_unverified` 会被带进去。状态类字段要由后端决定。
3. **改规则前先看谁会把它冲掉**：只在建单时置 1 不够，`DealSuccessPaidOrder` 每次付款成功都会重算，非本人微信付款会冲回 0。
4. **Node 24 的 `node --test` 子进程通信报 `Unable to deserialize cloned data`**：加 `--test-isolation=none` 在同进程跑；顺带暴露出一个用例结束后仍有异步回调的旧测试。
5. **只隐藏选项不等于禁止**：有「手工填写」时，必须在确认收款接口里再拦一次。
6. **旧客户端的错误提示可能被覆盖**：`performWebRequest` 先弹后端 message，调用方 `.catch` 再弹「处理失败」，后者覆盖前者。

## 8. 部署（10-23 晚，用户通知审核已通过）

- 用户：「现在可以部署服务器端了。」
- 部署前检查（经 `ssh -p 2222 ubuntu@44.207.251.65`）：
  - 磁盘 34G 用 27G，剩 7.4G；
  - `.git`、`.git/objects`、`Controllers` 属于 www-data 但权限 777；`Helpers`、`SnowmeetApi.Tests` 属于 ubuntu；这次要改的文件都不属于 root；
  - 以 ubuntu `git fetch origin ai` 成功，落后 4 个提交；
  - **1433 iptables 白名单为空**：`uptime -s` 显示 10-23 04:30:15 重启过，10-22 的临时规则没了。errorlog 末尾 200 行有 36 条 `sa` 登录失败，最近一条 05:46，来源 `[CLIENT: 44.207.251.65]`——美国服务器的公网 1433 转发。
- 先单独 `git pull --ff-only origin ai`：HEAD `2d611b98`，4 个新文件都在、ubuntu 所有，已跟踪文件无本地改动。
- 基线：`GetUnCommonPayMethod` 返回 10 项：苍杰微信转账、苍杰支付宝、储值支付、多拉宝、王政微信转账、微信转账、肖志强工作微信转账、银行转账、支付宝布乖、支付宝转账。
- 跑原命令 `ssh ... 'cd /home/ubuntu/webs/SnowmeetApi && ./republish.sh'`（后台，不加脱离会话的包装）：退出码 0，git pull「Already up to date」，构建只有既有警告。
- 验收：
  - 停机 18:44:21（Stopping）～18:46:12（Started），约 1 分 51 秒；
  - active / running、`NRestarts=0`、MainPID 39099，`SnowmeetApi.dll` 18:46:03；启动后 journal 无 exception / fail；
  - `GetUnCommonPayMethod` 返回 6 项：苍杰支付宝、储值支付、多拉宝、银行转账、支付宝布乖、支付宝转账；
  - `SaveRentRecept?sessionKey=invalid&isTest=true` 返回「没有权限」；公网 `https://mini.snowmeet.top/api/Order/GetUnCommonPayMethod` 200。
- 没做：已核验本人要等报到页面随新版小程序上线后真机验证；没改任何防火墙规则。
- 建议用户（待决定）：美国服务器 1433 转发限制来源或停用；mini 的 AWS 安全组只放行美国服务器；换 `sa` 密码或停用 `sa`。

---

以下为 10-24 同一会话的续篇（Mac mini）。

## 9. 两个手机号是不是会员、有没有储值（只读）

- 用户问 17811898285、13817928285 哪个是会员手机号、哪个有储值。
- 规则：手机号对应会员只认 `member_social_account.type='cell'`（`contact` 是联系方式快照，不算）。储值看 `deposit_account`（`income_amount - consume_amount`，`valid=1`）。
- 结果：17811898285 → 会员 15828（王先生），有效、未合并，名下 0 个储值账户；唯一一张订单 2026-01-24。13817928285 带前缀模糊查也没有，订单联系电话里也没有。
- 连库：`sqlcmd -S 44.207.251.65,1433`（当时还是 1433），密码经 `SQLCMDPASSWORD` 从 `config.sqlServer` 读。

## 10. `WF_YH_261024_00001` 结算时二维码没显示

- 订单 72043：会员 2472（赵先生）、应付 200（230 减 30）、`wechat_unverified=1`、**没有任何支付记录**。
- nginx 日志（店员手机 60.8.110.98，正式版 392）：10:07:09 出报到码 → 10:07:17 顾客扫码报到 → 10:08:18 `PlaceCareOrder` → 10:08:20 进结算页拉了两次订单和「其他支付」列表 → **之后再没有任何请求**。
- 顾客报到页 10:07:19～10:08:23 每 2 秒轮询，10:08:23 起停（只在页面隐藏/卸载时停，是顾客离开了页面）。
- 对照：10:14 开发者工具给 72044 点微信，`GetWepayPayment` → `LogShowWechatQrCode` → `GetQRCode` 全部正常。`4f0d2956` 只改了结算页 settle，没改收银组件。
- 结论：生成支付的请求根本没发出。可能是没点支付方式、点了「其他支付」、或网络不通（会弹「网络不通」）。待店员回忆。

## 11. 养护详情页加「去收款」（小程序 `84c8b865`）

- 用户：「未收款的养护订单，需要在订单详情页中增加收款按钮，点击按钮，可以跳转到订单收款页。」
- 照零售详情页口径：`valid==1 && dealed!=1 && closed!=1 && paidAmount==0` 才显示；文案「去收款 ¥xx / 去储值扣款 ¥xx（pay_with_deposit）/ 去核销（0 元——养护里不用权益的 0 元单下单即生效，未生效的 0 元单必然用了权益）」。
- 放在支付信息卡片的汇总格下面，`btn btn--primary btn--block`；`onShow` 会重新拉单，付完返回按钮自动消失。
- 小程序工作区当时有别的会话的未提交改动（`app.js`、`pages/index/index.js`、`tests/entry_navigation.test.js`，店员入口修复），只提交了养护详情页两个文件。测试 286 项通过（多出的 31 项来自那个入口测试）。

## 12. 会员养护单为什么不能让别人代付 → 放开（`9f9f8217`，已部署）

- 截图：付款页提示「请用订单会员本人的微信扫码支付」。扫码的是会员 4264（王）和 41204（苍），不是订单会员。
- 来源：7-14 用户要求「如果选择微信支付，则需要通过当前会员绑定的微信号扫码」，并约定「微信支付本身就视为核验会员本人」。代码（`PaymentIdentityController` 331 行）只要「养护 + 微信 + 有会员 + 非本人」就拦，不看有没有用权益、是否已核验。
- 用户：「通过了身份验证的订单，是允许别人代付并且核销掉他的权益的。但是没有经过身份验证的订单，还是遵循之前的规则，如果使用账户里的权益则必须本人支付。这样做和过去的规则不冲突吧？」→ 不冲突；指出三点：没用权益的未核验单以前也被拦（现在放开）、养护单代付必须仍归原会员、支付宝门槛在前端要等下一版。用户：「确认，直接修改部署吧。」
- 实现：
  - `OrderVerifiedRules.CareUsesBenefit`（券 `ticket_code`、卡 `use_card`、储值 `pay_with_deposit`；手动减免不算）、`CareRequiresMemberPayer(usesBenefit, verified) = usesBenefit && !verified`、`KeepOrderMemberOnPaid(type, memberId)`（已挂会员的养护单）。
  - `_resolveStatus`：只有 `CareRequiresMemberPayer` 为真才返回 `care_member_required`，否则走原来的 `choose_identity`（保留游客建会员、手机号授权等既有流程）。
  - `_applyChoice`：养护单选「self」改为「proxy」，付款记录标代付、记代付人手机号。
  - `DealSuccessPaidOrder`：`KeepOrderMemberOnPaid` 为真时不改 `order.member_id`，兜住支付宝等其他路径（支付宝回调只改 `payment.member_id`）。没在回调里改 `is_proxy_pay`：调用方可能已跟踪同一条付款记录，`Entry().State=Modified` 有撞键风险。
- 单测新增 3 项，后端 549 过 / 43 跳过。部署：`git pull --ff-only` 核对 `9f9f8217` → `republish.sh`（11:09:55～11:12:19）→ active、`NRestarts=0`、启动后无异常；`CheckPayerIdentity`（不带身份）对 72043 的待支付单 42814 返回 `choose_identity`。
- 留给下一版小程序：付款页对养护单只给「替人代付」；收银组件支付宝核验门槛改为「用了权益且没核验」。

## 13. 1433 暴力破解 → 转发改 5789

- 用户问每天 04:30 重启导致白名单失效怎么办。只读排查：
  - `last -x`：10-22、23、24 都是 04:30 重启；来自 `/etc/crontab:29` `30 4 * * * root reboot`（不是 unattended-upgrades，自动重启那项是注释掉的）。
  - mini 上 1433 只有 `127.0.0.1` 的连接；errorlog（当前 + 上一份）1157 次 `sa` 失败**全部** `[CLIENT: 44.207.251.65]`，没有一条来自其他公网 IP → mini 安全组已挡直连，攻击全经美国服务器的公网转发；mini 上放行 44.207.251.65 的白名单本身挡不住。
  - 美国服务器 `snowmeet-forward-1433.socket` 监听 `0.0.0.0:1433`，无其他服务依赖，ufw 未启用、iptables 全 ACCEPT。
  - SSH 隧道 `ssh -N -L 14330:127.0.0.1:1433 -p 2222 ubuntu@44.207.251.65` 实测可查库。
- 建议：关掉公网转发改走 SSH 隧道 + 换 `sa` 密码 / 只读账号；白名单持久化可选；每天重启的 cron 不动、问用户。
- 用户：「如果修改美国的服务器的端口映射，从美国服务器的 5789 端口映射到中国服务器的 1433，这样试试可以吗？」→ 可以，但说明换端口只是藏门：全端口扫描（masscan / Shodan）迟早找到，届时仍是撞 `sa`；建议搭配来源 IP 限制或换密码 / 只读账号。
- 用户在美国区安全组放行 5789 后执行：备份 socket / service 到 `/home/ubuntu/forward-5789-20261024/`；`sed` 改 `ListenStream=0.0.0.0:5789` 和描述；`daemon-reload` → 停 service → 重启 socket；`ss` 只剩 5789、2222。本机 `nc` 测 1433 关闭，`sqlcmd -S 44.207.251.65,5789` 查库正常。
- 对照基线：换端口前当天 errorlog 734 次失败，最后一次 11:44:31。CLAUDE.md 的端口映射、连库说明已改成 5789。

## 关键改动文件（10-24）

| 文件 | 改动 |
|---|---|
| [`SnowmeetApi/Helpers/OrderVerifiedRules.cs`](../../SnowmeetApi/Helpers/OrderVerifiedRules.cs) | 新增 `CareUsesBenefit`、`CareRequiresMemberPayer`、`KeepOrderMemberOnPaid` |
| `SnowmeetApi/Controllers/Order/PaymentIdentityController.cs` | `_resolveStatus` 养护拦截加条件；`_applyChoice` 养护强制代付 |
| `SnowmeetApi/Controllers/OrderController.cs` | `DealSuccessPaidOrder` 不改已挂会员养护单的会员 |
| `SnowmeetApi/SnowmeetApi.Tests/OrderVerifiedRulesTests.cs` | 新增 3 项 |
| `snowmeet_wechat_mini/pages/admin/care/care_order_detail/care_order_detail.{js,wxml}` | 去收款按钮 |
| 美国服务器 `/etc/systemd/system/snowmeet-forward-1433.socket` | `ListenStream` 1433 → 5789 |

## 学到的小知识（10-24）

1. **「二维码没出来」先看服务器收没收到请求**：nginx 日志按店员 IP / 登录凭证筛一遍，就能分清是前端没发、发了失败，还是后端出错。
2. **按登录凭证追人要先 URL 解码**：日志里的 sessionKey 可能被编码一到两次（`%252B`），解码到不含 `%` 再去 `mini_session` 匹配；输出里只显示前几位。
3. **暴力破解看来源分布**：`grep "Login failed" | grep -o "CLIENT: [0-9.]*" | sort | uniq -c` 一眼看出攻击走哪条路；全部来自转发机就说明该在转发机上处理。
4. **systemd socket 改端口**：只改 `.socket` 的 `ListenStream`，`daemon-reload` 后先停对应 `.service` 再重启 `.socket`，否则旧进程还拿着老监听。
5. **换端口不等于加固**：能降噪，挡不住全端口扫描；真正收口要靠来源限制、隧道或最小权限账号。
