# 管理员后台「优惠券管理」

日期：2026-08-15
状态：已实现，待部署验证

## 背景

后台原本**没有跨会员的优惠券视图**——只有 `GetMemberTicketsByStaff`（必须传 memberId、无分页）和三个老页面（模板打印、扫码核销入口、某顾客未用券列表）。想回答「这批券发出去多少、核销了多少、有没有被转来转去」只能连库查。

新增后台页面：按发放时间 / 模板 / 核销状态 / 是否被转赠过筛选，「按券明细」和「按会员汇总」两种视图同页切换，标注每张券的转赠次数。权限 `title_level >= 100`。

## ⚠️ 规划期发现：转赠判定式错了 245 倍（已修）

调研「转赠次数怎么算」时发现，`ticket_log` 有 5 个写入方，只有 1 个是真转赠：

| 写入点 | sender_open_id | accepter_open_id | memo |
|---|---|---|---|
| `TicketController:401` AcceptTicketCore | 原持有人 | 接受人 | 分享获得 / 扫码关注公众号后自动接受 |
| `TicketController:528` CancelShare | 本人 | `""` | 撤回分享 |
| **`TicketController:813` Use（核销）** | **`""`** | **店员** | 核销 |
| `ExperienceController:353` 体验订单发券 | 店员 | 顾客 | 体验订单获得,ID:x |
| `MaintainLogsController:774` 养护订单发券 | 店员 | 顾客 | 养护订单获得,ID:x |

生产库实测：

| 判定式 | 计入条数 |
|---|---|
| `accepter<>'' && accepter<>sender`（2026-08-14 刚上线的那个） | 4158 |
| 加 `sender<>''`（排掉核销） | 3580 |
| 再加 memo 黑名单（排掉发券） | **17 条 / 12 张券** |

这个判定式当时被写进了 `GetMySharedTickets` 和 `FillDisplayTime`，后果：

1. **店员账号的「已分享」tab 被污染**——实测三个店员号的候选券分别是 1352 / 1227 / 376 张，全是他们开单发给顾客的券，一张都不是自己转赠的
2. **转赠出去又被核销的券会从「已分享」消失**——核销日志（sender 是空串）成为该券"最新一条转赠记录"，`sender == myOpenId` 判定失败（实测 2 张）

修复后：全库「被认为转赠过」的券 **4131 → 12 张**，三个店员号的候选 **全部归零**。

口径收敛到 `TicketTransferRules.TransferLogFilter()`（Expression，EF 和单测共用同一份），`GetMySharedTickets` 两处 + `FillDisplayTime` 一处全部换用它。

## 后端

新建 `SnowmeetApi/Controllers/TicketAdminController.cs`（`MIN_LEVEL = 100`）。不塞进 `TicketController`（1200+ 行、顾客侧店员侧混杂），也不塞进 `MemberAdminController`（那份全文 `MIN_LEVEL = 200`，混进去迟早有人抄错常量）。

三个接口，筛选逻辑共用 `BuildFilteredQuery(...)`——「筛选两视图共用」是靠这个方法满足的，不是靠合并接口：

- `SearchTicketsByStaff` → `{ items, total, wastedTotal, invalidCount }`
- `SearchTicketMembersByStaff` → `{ items, total, ticketTotal }`（入参与上面逐字相同）
- `GetTemplateOptions` → 模板下拉。不复用 `MemberAdmin/GetCouponTemplates`（门槛 200，店员会被拒）也不复用 `Ticket/GetTemplateList`（零鉴权 + 返回整实体）

**拆两个接口而不是一个带 `groupBy`**：`total` 的分页单位一个是券、一个是会员，同名不同义必然把 `totalPages` 算错。
**自检点**：同一组筛选下 `ticketTotal` 必须等于明细的 `total`（已验证 3078 == 3078）。

### 转赠次数的三种算法

| 场景 | 写法 | 理由 |
|---|---|---|
| 作为筛选条件 | `q.Where(t => transferLogs.Any(l => l.code == t.code))` | 翻成 EXISTS，必须在 Skip/Take 之前，否则 total 和分页都错 |
| 明细每张券 | 分页后按 code 批量 GroupBy | 贴 `FillDisplayTime` 已有范式，顺带白送 lastTransferTime |
| 汇总每会员 | 先按会员分页，再 join + group by member_id | 不能按 code 捞：20 个会员名下可能上千张券，`Contains` 参数会爆 |

⚠️ 已核销必须用 `t.used == 1`，**不能用 `used_time != null`**——`TicketController.Cancel` 把券退回未使用时反而写了 `used_time`。

### 默认范围「未过期 ∪ 已核销」

新增两个 EF 可翻译谓词到 `TicketTransferRules`：

```csharp
NotExpiredFilter(now)  // t.expire_date == null || t.expire_date >= now.Date
NotWastedFilter(now)   // t.used == 1 || 上面那条
```

不在列上套 `.Date`（会翻成 `CONVERT(date, …)` 废掉索引），改成先把 `now` 切到当天 00:00 再比列，语义等价。`includeWasted == true` 时**整条谓词不加**（不是加反向谓词），保证「开 = 关的超集」。

生产实测：总 12252 张 / 已核销 958 / 废券 9174 → **默认范围 3078 张**。

### `valid` / `is_active`：默认不过滤

生产实测 `valid=0` 88 张、`is_active=0` 271 张。`BuildFilteredQuery` **不含** 这两个条件——这是审计视图，价值恰恰是能看到顾客端看不到的券。过滤掉等于把要排查的对象藏起来，重演 2026-07-09「admin 券列表看得到、开单选不出」那次事故的反面。

取而代之：每行下发 `valid`/`isActive` 打「无效」「未激活」徽标，顶部 `invalidCount` 提示条明说"顾客端看不到"。`is_active=0` 是雪票券取卡前的正常业务态。

## 前端

`snowmeet_wechat_mini/pages/admin/ticket/coupon_admin/`（4 件套），以 `punchcard_sales` 为骨架（筛选即时生效无查询按钮、chip 单选、展示文案全在 js 派生）。

- 顶部 segmented 切视图，**筛选共用、切视图回第 1 页**
- 默认日期区间 = **本雪季至今**，不是「今天」——盘存性质的页面默认今天会一片空白
- `onShow` 保参重查 + `title_level < 100` 时 toast + `navigateBack`
- 时间一律服务端格式化成字符串下发（iOS `new Date('2026-08-16 10:30:00')` 是 Invalid Date）

菜单入口挂在 `admin.wxml` 已有的「优惠券」分组下（`admin.js` 的 `nav()` + `app.json` 三处接线）。

## 测试

xUnit 共 **79 个用例全绿**，本次新增：

- `TransferLogFilterTests`（12 个）—— 拿 5 个写入方当用例表，**核销日志判 false** 那条是本次 bug 的回归防线
- `NotWastedFilterTests`（7 个）—— 4 象限 + null + 当天到期 + 昨天到期
- `NotExpiredFilterConsistencyTests` —— Expression 版与内存版 `IsNotExpired` 逐项等价（含 `DateTime.MaxValue` 哨兵）
- `DescribeStateTests`（7 个）—— 状态优先级 已核销 > 已过期 > 分享中 > 未使用
- `ClampPagingTests`（4 个）

生产数据复算校验：默认范围 3078 / 开关后 12252（超集 ✓）/ 汇总 ticketTotal == 明细 total ✓ / 三态 7+3071=3078 互补 ✓ / 会员 15506 明细逐张求和 10 == 汇总 join 聚合 10（无重复计数）✓

## 无库表变更

不需要任何 DDL。
