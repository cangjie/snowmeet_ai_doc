# 2026-07-04 会员管理增强日：合并权限收紧 + contact 联系手机号原则 + 开卡礼包 + 充值四字段 + 储值账户管理系统

按主题整理。本场会话从 start-work 开始，围绕会员管理体系连续落地 6 组功能/修复，跨 `SnowmeetApi` + `snowmeet_wechat_mini` + 生产库一次数据修复。**本场特殊：代码已全部 commit + push 到两仓 origin/ai**（SnowmeetApi 至 `cea1f3d4`、snowmeet_wechat_mini 至 `0bd5df79`），待 publish 后端 + 重编小程序。

## 1. 会员合并权限收紧到系统管理员（title_level ≥ 300）

### 1.1 title_level 体系首次系统性摸清（DB 实查 + 代码语义）

- 生产 staff 表分布：`0`(29人,valid仅1) / `50`(2) / `100`(16,店员) / `200`(1,HR) / `300`(10,管理层：崔洋/王倩/布乖/寇芳/张新健/白雪景/苍杰×2/段春敏/李源) / `1000`(1,王奕轩超管)
- 代码语义锚点：[admin.js](../../snowmeet_wechat_mini/pages/admin/admin.js) `<=100 isStaff / <=200 isManager / else isAdmin`；前端既有 `>= 300` 先例 [category_tree.js:770](../../snowmeet_wechat_mini/pages/admin/rent/settings/category_tree.js)
- 结论：**「系统管理员」= title_level ≥ 300**

### 1.2 实施

- 后端 [MemberAdminController.cs](../../SnowmeetApi/Controllers/MemberAdminController.cs)：加 `const int ADMIN_LEVEL = 300;`，`MergeMemberByStaff` 鉴权 `MIN_LEVEL(200)` → `ADMIN_LEVEL(300)`
- 前端 [member_detail.js](../../snowmeet_wechat_mini/pages/admin/member/member_detail.js)：data 加 `isAdmin`，onLoad `app.loginPromiseNew.then` 取 `staff.title_level >= 300`（沿用 category_tree 写法）；「合并」按钮 `wx:if="{{isAdmin}}"` + `onMergeOpen` 入口守卫 toast「仅系统管理员可操作」

### 1.3 途中发现：本机 snowmeet_wechat_mini 落后 origin/ai 33 commits

- 这台机器没有 `pages/admin/member/` 目录——6-30/7-2 的会员管理前端在另一台机做的、已推远端但本机没拉
- 本地 `project.config.json`/`project.private.config.json` 有工具自动写的改动挡住 pull → `git stash push` 两文件后 `pull --ff-only` 到 `d524beb6`
- 教训重申：多机协作先 fetch/pull 再动手，别假设本机是最新

## 2. 会员合并 MSA 规则改造：cell → contact

用户规则：**合并时不迁移源会员的微信/支付宝等社交账号**（现状本就只失效不迁移，确认无需改）；**源会员手机号挂到目标会员时 type 改为 `contact`**（联系手机号），不作为主手机号。

- [MemberController.MergeMember](../../SnowmeetApi/Controllers/MemberController.cs) 第 240 段：新建 MSA `type="cell"` → `type="contact"`，memo「批量合并用户时添加的联系手机号」；查重条件扩为 `type ∈ {cell, contact}` 且 valid=1 同号（对齐既有 `currentContactNum` 写 contact 的先例 [MemberController.cs:549](../../SnowmeetApi/Controllers/MemberController.cs)）
- `contact` 是系统既有 type，非新造

## 3. 「13501177897 搜出 15506」→ contact 不参与搜索原则 + 存量修复

### 3.1 根因

- 用户 7-3 晚 19:37 用**旧版合并代码**（contact 改造前）把会员 41127（cell=13501177897）合并进 15506（苍杰），旧代码给 15506 写了 `type=cell` 的 msa 169220 → 按 cell 搜索命中 15506
- 用户拍板原则：**「通过手机号模糊匹配 MSA num 时，忽略 type=contact 的记录」——contact 只是开单/合并那一刻的联系方式快照，不是会员永久常用信息**（否定了我此前把搜索扩成 cell||contact 的做法）

### 3.2 修复三件套

1. **回滚搜索扩展**：[MemberAdminController.cs](../../SnowmeetApi/Controllers/MemberAdminController.cs) `SearchMembersByStaff` cell 过滤恢复只查 `type == "cell"`，注释固化原则
2. **补同类漏洞**：[OrderController.cs:231](../../SnowmeetApi/Controllers/OrderController.cs) 养护订单列表按手机号搜的分支**原本完全没限定 type**（contact/openid 都会命中）→ 补 `msa.type.Trim().Equals("cell")`（与租赁/默认分支既有写法一致）。全系统其余 MSA num 匹配点排查过均已限定 cell
3. **存量数据修复（生产库 UPDATE，已执行）**：msa 169220 `type: cell → contact` + memo 更新。修后模拟搜索验证 13501177897 **零命中**；且线上老后端本就只查 cell，数据修复即时生效不用等部署

## 4. 注册会员页「开卡礼包」（plan 流程，纯前端，后端零改动）

用户拍板：**礼包清单模式**（三个添加按钮，可同类型多条）+ **逐项调用+失败提示**（沿用注册→逐项发放的两步模式）。

- [member_register.js](../../snowmeet_wechat_mini/pages/admin/member/member_register.js)：`grants[]` 清单（coupon: templateId+count / punch: bizType+cardName+total）；券选择弹窗（懒加载 `GetCouponTemplates`，单选+张数 1-50）；次卡弹窗（租赁/养护共用，`GetPunchCardPresets` 按 biz_type 过滤存 `punchPickList`——WXML 不支持方法调用，JS 预派生）；`_runGrants(memberId)` 把储值+礼包组成任务队列**串行**执行、逐项 catch 记录 `{label, ok}`
- wxml：「开卡礼包（选填）」卡片（虚线按钮 + 清单可删）+ 完成页发放结果列表（✓绿/✗红 + 失败提示「可到会员详情页补发」）+ 两个选择弹窗（样式对齐 member_detail 发放弹窗）
- 复用现状确认：`GetPunchCardPresets` 本就是 DB distinct(biz_type, card_name, total)——正合用户「distinct 次卡名称」要求；DB 实况：券模板 18 个有效、卡种 养护 4 + 租赁 2

## 5. 充值储值四字段单弹窗（两处入口 + 后端透传）

用户要求充值时按顺序填：①充值类型（储值送装备/二手回收/零售赠送/预定/其它赠送）②七色米订单号 ③备注 ④金额，四项一个 modal。

- **后端** [MemberAdminController.ChargeMemberDeposit](../../SnowmeetApi/Controllers/MemberAdminController.cs)：`ChargeRequest` 加 `chargeType/mi7Code/memo`，chargeType 空则拒；透传 `DepositCharge(..., mi7OrderId, bizType, memo)`——**底层本就支持**这三个参数，落位：类型→`deposit_balance.biz_type`、七色米号→`biz_id`、备注→`memo`。零库表改动
- **member_detail** 充值弹窗扩四字段（类型 chip 单选 + 两个选填 input + 金额）；**member_register** 初始储值从内联输入框改为「＋ 添加储值」→ 同款四字段 modal → 摘要条（可重开编辑/删除）
- **⚠️ 文案对齐历史数据**：生产 `deposit_balance.biz_type` 历史值是「**其它**赠送」（4 条），前端 chargeTypes 从「其他赠送」改为「其它赠送」（两页），避免同一类型分裂

## 6. 会员列表排除已合并会员

- 用户规则：`member.merge_id` 非 null（已被合并的源会员）不出现在会员列表
- [SearchMembersByStaff](../../SnowmeetApi/Controllers/MemberAdminController.cs) 基查询 `m.valid == 1` → `m.valid == 1 && m.merge_id == null`
- DB 实证：全库 125 个 valid=1 且 merge_id 非空的被合并会员（含 7-3 测试合并的 41127/41128/41135/41136→15506 + 历史批量合并）全部被排除；合并弹层目标搜索走同一接口，一并生效（与 MergeMemberByStaff 的 target 守卫双保险）

## 7. 开单页会员条显示资产 + 查看详情切新版

- **后端新接口** `GetMemberAssetsByStaff(memberId)`（[MemberAdminController.cs](../../SnowmeetApi/Controllers/MemberAdminController.cs)）：返 `{depositTotal, points, punchRemaining}` 三聚合数；鉴权**放宽到 title_level ≥ 100**（开单店员级；该 controller 其余接口都是 200/300）
- **组件** [reception_member_bar](../../snowmeet_wechat_mini/components/reception/reception_member_bar/reception_member_bar.js)：`customer.memberId` 出现/变化（含手机号 lookup 命中）时拉资产，「租赁」标签旁按**有则显示**追加 chip：储值 ¥xxx（绿）/ 次卡 N 次（橙）/ 龙珠 N（粉）；memberId 去重防重复请求 + `loginPromiseNew` 兜登录竞态
- [recept_new.js](../../snowmeet_wechat_mini/pages/admin/reception/recept_new.js) `onMemberDetail`：旧版 `recept_member_info` → `/pages/admin/member/member_detail?id=`（清掉 CLAUDE.md 挂了两个月的 TODO 遗留）
- 测试预期值（DB 实查 15506）：储值 ¥5372.04 / 次卡 58 次 / 龙珠 340
- 注意：新版 member_detail 数据接口是 200 级，100 级店员点进去会提示没权限（与现有权限体系一致，待业务定是否放宽）

## 8. 储值账户管理系统（plan 流程，列表 + 详情两新页）

### 8.1 后端两接口（MemberAdminController，200 级）

- `SearchDepositAccountsByStaff(cell?, pageIndex, pageSize)`：按手机号模糊搜（**只匹配 type=cell，contact 不参与**，同 §3 原则；留空查全部），按会员分组分页（MAX(account.id) 倒序），每账户返 `income/consume/available`（deposit_account 列值直接用，无需聚合 balances）
- `GetDepositAccountDetailByStaff(accountId)`：账户汇总 + 会员信息（姓名/cell）+ 全部流水（valid=1 按 id 倒序）；流水行投影 `{amount, isCharge, bizType, bizId, memo, orderId, orderCode, orderType, createDate}`——消费行经 `b.order` 导航带出订单 code

### 8.2 前端两新页 + 入口

- [deposit_account_list](../../snowmeet_wechat_mini/pages/admin/deposit/deposit_account_list.js)（4 文件）：手机号搜索 + 会员卡片（点头部跳会员详情）内嵌账户行（类型 + 总储值/已消费/可用三列，点行进详情）+ list-pager + onShow 保参重查
- [deposit_account_detail](../../snowmeet_wechat_mini/pages/admin/deposit/deposit_account_detail.js)（4 文件）：顶部账户卡（姓名/可拨打手机号/类型/三格金额）+ 流水列表——充值行绿 `+¥` + 类型 chip + 七色米订单号 + 备注；消费行红 `−¥` + 「订单 WT_ZL_xxx」（无 code 回退 #orderId）；单账户最多 ~73 条一次全拉不分页
- app.json 主包注册两页；admin「储值管理」区块加 `<mp-cell id="deposit_account_list" value="【储值】会员储值账户">` + nav case

### 8.3 数据勘察结论（写进已知遗留）

- `deposit_balance` 485 条（117 充值/368 消费）；充值行 biz_type/biz_id(XSD/JHD 七色米号)/memo 有真实数据；**消费行 366/368 带 order_id+payment_id**（`CreateDepositBalance` 后赋值），biz_* 恒空 → 显示订单号靠 order 导航
- `DepositBalance` 模型字段齐全（含 payment_id/order_id/source + order/payment 导航）；`deposit_account` 88→89 账户
- DB 预演：列表 89 会员、搜「135」命中 5 人、账户 2104 两条充值带完整四字段、账户 1 消费行正确关联 `WT_ZL_260630_00002` 等

## 关键改动文件

| 仓库 | 文件 | 改动 |
|---|---|---|
| SnowmeetApi | `Controllers/MemberAdminController.cs` | ADMIN_LEVEL=300 + Merge 鉴权；搜索 merge_id==null + cell-only；ChargeMemberDeposit 三字段；GetMemberAssetsByStaff(≥100)；SearchDepositAccountsByStaff + GetDepositAccountDetailByStaff |
| SnowmeetApi | `Controllers/MemberController.cs` | MergeMember：源 cell 挂目标改 type=contact + 查重 cell/contact |
| SnowmeetApi | `Controllers/OrderController.cs` | :231 养护订单手机号搜索补 type=cell 限定 |
| mini | `pages/admin/member/member_detail.{js,wxml,wxss}` | isAdmin 合并按钮/守卫；充值四字段弹窗；chargeTypes 其它赠送 |
| mini | `pages/admin/member/member_register.{js,wxml,wxss}` | 开卡礼包清单 + 两选择弹窗 + 储值四字段 modal + done 页结果 |
| mini | `components/reception/reception_member_bar/*` | 资产三 chip + _loadAssets 去重 |
| mini | `pages/admin/reception/recept_new.js` | onMemberDetail 切新版详情页 |
| mini | `utils/data.js` | +4 promise：getMemberAssetsByStaff / searchDepositAccountsByStaff / getDepositAccountDetailByStaff（+充值 body 新字段透传免改） |
| mini | `pages/admin/deposit/deposit_account_{list,detail}.*` | 新建 8 文件 |
| mini | `app.json` / `pages/admin/admin.{js,wxml}` | 两页注册 + 储值管理入口 |
| 生产库 | `member_social_account` id=169220 | UPDATE type cell→contact（已执行并验证） |

**提交状态**：SnowmeetApi `c6af684b merge member` → `11da8150 search only by cell` → `01001da5 set deposit` → `0f93d2a6 goto detail` → `cea1f3d4 deposit list`；snowmeet_wechat_mini `77b0f921` → `104be781 create new member with gift` → `faeb45ca` → `b1cdb8f8 member bar` → `0bd5df79 deposit list`。**两仓均已 push 到 origin/ai**。

## 学到的小知识

1. **title_level 四档语义**：100 店员 / 200 店长（生产只 HR 一人）/ 300 系统管理员（admin.js isAdmin 分界、category_tree >=300 先例）/ 1000 超管。高危操作（会员合并）用 300
2. **contact MSA 原则**：`type=contact` 是开单/合并那一刻的联系方式快照，**不参与任何手机号→会员的匹配**（搜索/反查一律限定 type=cell）；仅作展示。新写手机号匹配查询时必须显式限定 type
3. **`DepositCharge` 底层签名早已支持 mi7OrderId/bizType/memo**，只是 ChargeMemberDeposit 包装层写死——扩展前先看底层签名，常常只需透传
4. **充值类型枚举以生产数据为准**：历史 biz_type 是「其它赠送」不是「其他赠送」，新前端枚举必须对齐否则同类型分裂（写代码前先 `GROUP BY` 看历史值）
5. **deposit_balance 消费行带 order_id/payment_id**（`DepositCosume` 后赋值），biz_* 恒空；流水页显示"消费于订单"走 `b.order.code` 导航投影
6. **旧版代码跑出的存量数据要跟着新规则修**：contact 改造部署前用户已用旧版合并过一次（写了 type=cell），光改代码搜索仍命中——功能语义变更 = 代码 + 存量数据两条腿
7. **本机(Windows) pyodbc 只有 ODBC Driver 17**：连接串用 Driver 17 + `Encrypt=yes`；GBK varchar 中文输出要 `CONVERT(nvarchar, col)` + `sys.stdout.reconfigure(encoding='utf-8')`
8. **本场代码被随手分批 commit+push**（两仓 5+5 个 commit），与以往「工作区堆积待用户提交」不同；end-work 前先 `git status` 核实实际状态再写归档
