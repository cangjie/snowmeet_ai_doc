# 2026-06-21（续）开单保存/排序 + 支付宝会员绑定：六个问题，连生产库实证定根因

接 6-21 三修，继续测租赁开单 / 顾客扫码支付。六个问题，前端 + 后端混合；全程连**生产库**核查（用户本会话明确授权"现在可以连数据库"，含一次事务回滚的诊断接口验证，绝不改库）。改动落在 `snowmeet_wechat_mini` + `SnowmeetApi` 工作区**未提交**，需小程序重编 / 后端 publish。

## 1. 订单列表：支付方式不显示储值/次卡 + 含储值加「储」标签

**需求**：`pages/admin/rent/new_rent_list`（租赁订单列表），支付方式行列出当前订单除「储值支付」「次卡支付」外的所有支付方式；若含储值支付，左侧标签列加一个「储」。

**改动**（纯前端）：
- [`new_rent_list.js`](../snowmeet_wechat_mini/pages/admin/rent/new_rent_list.js)：遍历 `availablePayments`，遇「储值支付」置 `haveDeposit=true` 跳过、遇「次卡支付」跳过，其余去重后 `/` 拼接给 `payMethod`。
- [`new_rent_list.wxml`](../snowmeet_wechat_mini/pages/admin/rent/new_rent_list.wxml)：「卡」标签后加 `<text wx:if="{{item.haveDeposit}}" class="tag tag--deposit">储</text>`。
- `new_rent_list.wxss`：`.tag--deposit { background:#ffedd5; color:#c2410c; }`（橙色系）。

## 2. 找回中断单：改租金改不了 + 新增套餐不落库（order 71775 / rental 54404）

**现象**：找回中断单进开单页，改租金无效、加的套餐没存库。

**DB 实查 71775**：只有 1 rental（54404）、`update_date=NULL`；rental 54404 的 `rental_price_preset` **count=0**；54404 是无码物品单品（category 27 雪杖，name='aaaa', noCode）。

### 2.1 后端根因（主因）—— 用临时诊断接口（事务回滚）决定性验证
最初猜"member 级联让 SaveChanges 抛异常"，但诊断推翻：
- 写临时 `Rent/DiagReceptUpdate`（JSON 序列化→反序列化往返，模拟前端真实 payload，事务回滚不改库）。
- **真相**：JSON 往返后的 `order.member`（+5 MSA）子图让 **`_db.Update(order)` 在 EF TrackGraph 阶段抛 `Value cannot be null. (Parameter 'key')`**（不是 SaveChanges）。DB 直接加载的 member 不触发，**只有 wx JSON 往返后的 member 才有毒**。
- 该异常被 [`SaveRentRecept` else 分支 try/catch](../SnowmeetApi/Controllers/RentController.cs#L4237) **静默吞掉** → SaveChanges 从不执行 → 不落库；但接口仍 `return Ok(code=0, data=order)`，前端 resolve、UI 显示改成功 → "看着改了，库里没有"。全新订单 member=null 不触发，故只有找回单复现。
- 对照诊断：往返+不置空 member → Update FAILED；往返+置空 member → save OK。

**修复**：[`SaveRentRecept`](../SnowmeetApi/Controllers/RentController.cs#L4150) 开头置空 `order.member` / `order.staff`（与既有 `details=null`/`category=null` 同属防级联清理；`member_id`/`staff_id` 标量列保留，归属不变）。**需 publish**。

### 2.2 前端根因（改租金叠加因）
`createRentalDetail`（[util.js:191](../snowmeet_wechat_mini/utils/util.js#L191)）只在 priceList 能匹配出价时才生成 preset；雪杖类目在该店无价格配置 → pricePresets 始终空（DB count=0 实证不是丢失、是没生成）。前端 [`_applyPkgRate`](../snowmeet_wechat_mini/components/reception/rent_recept_form/rent_recept_form.js#L466) 仅在 `presets.length>0` 时写入 → 空时改租金无效。

**修复**：`_applyPkgRate` 在 pricePresets 为空时新建一条手动 preset（rent_type=日场 / day_type 按起租日周末判断 / scene=门市 / manual=true）。

## 3. 购物车排序：按时间正序 + 按品种

**需求**：「按时间」=按添加时间正序（先添加在上）；「按品种」=套餐在前/单品在后为主排序，组内按添加时间正序。

**根因**：找回单 `GetReceptingOrder` 返回 `OrderByDescending(r => r.id)`（后加在上），组件 `_refreshRentals` 又不排序 → 倒序。`onSortChange` 原来只 `triggerEvent`、父页空 TODO → 排序没生效。

**修复**（纯前端为主，立即生效）[`rent_recept_form.js`](../snowmeet_wechat_mini/components/reception/rent_recept_form/rent_recept_form.js)：
- `byAddedTime`：已保存项按 `id` 升序（自增=创建先后），未保存项（id=0）按 `timeStamp` 升序并排同组最下。
- `byCategoryThenTime`：主排序套餐（`package_id` 非空）在前/单品在后，次排序 `byAddedTime`。
- `_refreshRentals` 按 `this.data.sort`（`time`/`category`）选排序键，覆盖任何后端返回顺序。
- `onSortChange` 切 tab 后用当前数据本地重排（不 `_emitSync`、不触发保存）。
- 后端治本：[`GetReceptingOrder`](../SnowmeetApi/Controllers/RentController.cs#L4580) 改 `OrderBy(r => r.id)`（**需 publish**，前端排序已兜底）。

## 4. 结算按钮点不了 = 另一个 rental 没选分类（order 71776，非招待所致）

**答疑（非 bug）**：用户以为给雪服套装设「招待」导致结算 disable。DB 实查 71776 两 rental：54408（雪服套装，招待）已录入正常；**54407（无码单品 "a a a"）`category_id=NULL` 没选分类** → `evalEntry` 判最高优先级缺项「分类未选」→ 该 rental 未录入 → 结算 `every(_rentalEntered)` 失败被它卡住，与招待无关。54407 正序排上方、折叠态红色「待选分类」、用户没注意。解决：给它选分类即可。建议改进（未做）：结算 disable 时 toast 提示哪个 rental 缺什么 / 自动展开高亮。

## 5. 代付微信支付弹不出窗（paymentId 42639，openid oHdTn5...）

**DB 实查**：op 42639 代付（`is_proxy_pay=True`），付款人 member 41125，**`open_id=''` 空**。member 41125 有**两条** `wechat_mini_openid`：空串（id 169181，排前）+ 真实 `oHdTn5...`（169182）。

**根因**：[`Member.wechatMiniOpenId` getter](../SnowmeetApi/Models/Member/Member.cs#L55) 取 `msaList[0].num` = 空串 → 代付落库时 op.open_id 写空 → 微信 prepay 无付款人 openid → 弹不出窗。[`WechatPayByOrderPayment` 补写分支](../SnowmeetApi/Controllers/OrderController.cs#L1743) 因 `'' != ''` 为 false 而不触发，无法自愈。影响面：全库仅此 1 例脏数据（孤例）。

**修复**：`wechatMiniOpenId` / `wechatUnionId` / `alipayPayerId` 三 getter 改为取**第一个非空** num（新增 `FirstNonEmptyNum`），跳过空占位脏 MSA。**需 publish**；部署后用户重进 payment_entry 点支付，`WechatPayByOrderPayment` 自动补写正确 openid，无需手改数据。

## 6. 支付宝支付没获取手机号 答疑 + 物化重写（paymentId 42641）

### 6.1 答疑（op 42641 本身是预期行为）
DB 实查：op 42641 支付宝**已成功**，buyer_open_id `040P5...`，member_id=15506（本人，`is_proxy_pay=False`）；该支付宝 session（`session_type=alipay_payerid`）`member_id=15506` 且 **`cell=18601197897`（已带手机号）**，buyer_open_id 存在 session 的 `alipay_openid` 列。
→ 手机号其实**获取到了**（登录时 `my.getPhoneNumber`+aes 解密成功，aes_key.txt 已落地、解密链路正常），并据此反查到订单本人；`_resolveStatus` 判 scanner==owner → `direct`（本人直付）→ 前端不弹手机号授权（本人已有、无需重复）。

### 6.2 真实遗漏 → 按用户规则重写物化
**用户规则**：支付宝支付若获取到手机号 —— 手机号匹配到会员且该会员**无 valid=1 支付宝 openid** 则把 openid 绑到该会员；手机号匹配不到会员则用手机号+openid 注册新会员。

**原 `_materializeAlipayMemberOnPaid` 两问题**：① 只在 `payment.member_id == null` 调用（本人/代付单跳过 → openid 永不绑）；② session 反查用 `alipay_payerid` 列，但 buyer_open_id 实存 `alipay_openid` 列 → 拿不到手机号。全库 `alipay_payerid` MSA 只有 member 15506 一条**空串**（同 §5 空 MSA 同源）。

**修复**（[`AliController.cs`](../SnowmeetApi/Controllers/Order/AliController.cs)，**需 publish**）：
- `_materializeAlipayMemberOnPaid` 重写为「以手机号为锚」：取手机号（session 反查兼容 `alipay_openid`/`alipay_payerid` 两列）→ `payment.member_id` 已知则用它不改归属、否则按手机号反查会员（命中即用 / 有号未命中→建新会员(手机号) / 无号→兜底建会员）→ 目标会员若无「valid=1 且非空」的 alipay_payerid 则绑本次 openid，并停用 num 为空的脏占位 MSA（已有有效 openid 则不动，幂等）。
- 调用点去掉 `member_id==null` 限制：本人/代付单也补绑 openid；member_id 已知不覆盖归属、为空才回填。

**诊断验证（事务回滚，不改库）**：
- op 42641（本人单）：返回 member_id=15506（归属不变）、空串 169169→valid=0、新增 `040P5...` valid=1。✓
- `080P5...` 新用户（member_id=null、手机号 13683607473 反查无会员）：session 列名兼容能取到手机号、cell 反查为空 → 会建新会员（手机号+openid）。✓

## 关键改动文件

| 文件 | 改动 | 生效 |
|---|---|---|
| [`new_rent_list.{js,wxml,wxss}`](../snowmeet_wechat_mini/pages/admin/rent/new_rent_list.js) | 支付方式过滤储值/次卡 + 「储」标签 | 重编 |
| [`RentController.cs` SaveRentRecept](../SnowmeetApi/Controllers/RentController.cs#L4150) | 开头置空 `order.member`/`order.staff` 防级联 | **publish** |
| [`RentController.cs` GetReceptingOrder](../SnowmeetApi/Controllers/RentController.cs#L4580) | rentals `OrderBy(id)` 正序 | **publish** |
| [`rent_recept_form.js`](../snowmeet_wechat_mini/components/reception/rent_recept_form/rent_recept_form.js) | preset 空时新建 + byAddedTime/byCategoryThenTime 排序 | 重编 |
| [`Member.cs`](../SnowmeetApi/Models/Member/Member.cs#L55) | 三 getter 取第一个非空 num（`FirstNonEmptyNum`） | **publish** |
| [`AliController.cs`](../SnowmeetApi/Controllers/Order/AliController.cs) | 支付宝物化重写（手机号锚定+补绑 openid）+ 调用点放开 | **publish** |

## 学到的小知识

1. **EF `_db.Update(graph)` 对 JSON 往返后的 member 子图会抛 `Value cannot be null (key)`**：在 `TrackGraph` 阶段炸，不是 SaveChanges。DB 直接加载的实体不触发，只有经 wx JSON 序列化/反序列化往返的导航子图有毒。SaveRentRecept 既有的 `details=null`/`category=null` 正是同类防级联——member/staff 是新暴露的同病，因找回功能首次把 member 子图带回保存。
2. **吞异常的 try/catch 是隐形杀手**：`_db.Update`+`SaveChanges` 包 try/catch 只 `Console.WriteLine`，保存失败却返回 code=0 + 内存对象 → 前端 resolve、UI 显示成功、库里没有。和「非200 不 reject」同类坑。
3. **计算属性 getter 取 `msaList[0]` 遇空占位会返空**：`wechatMiniOpenId`/`wechatUnionId`/`alipayPayerId` 都是此模式。同一会员存在 num='' 的脏 MSA（建会员先占位、后补真实）时直接取首条会拿空串 → 代付/支付 op.open_id 写空、prepay 无 openid。改取第一个非空。
4. **支付宝 buyer_open_id 在 mini_session 存 `alipay_openid` 列、不在 `alipay_payerid` 列**：反查 session 取 cell 要兼容两列。OpenID 模式 notify 也是 `buyer_open_id`。
5. **临时诊断接口 + 事务回滚是连生产库验证 EF 行为的安全姿势**：`BeginTransaction` → 跑真实逻辑（含 SaveChanges）→ 无条件 `Rollback`，能复现/证伪根因且不改库；JSON 往返 helper 能精确复刻前端 payload。验证完即删接口。
6. **本地 `dotnet run` 路由 404 排查**：① 项目多框架残留 bin 但单 target net9.0；② controller route `api/[controller]/[action]` 下方法再写 `[HttpGet("Name")]` 会变成 `.../Name/Name`，应留空 `[HttpGet]`；③ `dotnet run --no-build` 用旧 bin，改完要先 build。
7. **接待中 rental `valid=0` 草稿态** + **`PayWithDeposit` 返回 order 不带 `order.guarantys`**（同 6-21 主条）仍是本轮排查反复用到的前提。
