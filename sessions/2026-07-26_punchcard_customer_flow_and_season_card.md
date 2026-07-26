# 2026-07-26 次卡/季卡全链路：顾客自助购买闭环 + 养护季卡语义 + 卡销售管理

接续 7-25 的「次卡/季卡商品维护」。本场把这条线从**后台商品维护**一路打通到**顾客自助购买 → 支付 → 发卡 → 核销 → 管理后台查账**，中途修了 5 个既有 bug（其中 3 个是线上 500）。改动跨 `SnowmeetApi` + `snowmeet_wechat_mini`，用户分批 commit。本场**首次使用 `config.sqlServer` 直连生产库做只读排查**，多次一击定位根因。

---

## 1. 商品维护页：3 个 bug + 使用规则可编辑

### 1.1 `CategoryController.GetProduct` 对次卡商品必 500（线上 bug）

- 现象：进商品编辑页，`Category/GetProduct/716` 抛 `ArgumentNullException (Parameter 'entity')`
- 根因：[CategoryController.cs:433](../SnowmeetApi/Controllers/CategoryController.cs) 直接 `_db.category.Entry(product.category)`，没判空。而**次卡/季卡商品按设计就是 `category_id = null`**（分类关联走稳定的 `category_code`），`product.category` 恒为 null
- 影响面比报错点大：同一 helper 有三个调用方，`ModProduct:320` 也走它 → **保存编辑同样 500**，等于次卡商品的"编辑"整条路都不通
- 修复：`Reference(p => p.category).LoadAsync()` 后加 `if (product.category != null)`，遍历分类属性的循环同样包进判空

### 1.2 「养护次卡添加不了」

- 判断是**筛选条件挡住了**：用户筛选停在「租赁+季卡」却点「+ 养护次卡」，加完返回列表仍被筛选过滤 → 显示「暂无商品」，看着像没加上
- 修复：`onAdd` 点新增时把筛选切到对应组合，加完回来正好看到它

### 1.3 使用规则改为后台可编辑

- SQL：`ALTER TABLE product ADD usage_rules NVARCHAR(MAX) NULL`（[sql/2026-07-25_product_add_usage_rules.sql](../sql/2026-07-25_product_add_usage_rules.sql)），**用户已执行**
- 维护页加第二个 `<editor>` 富文本编辑器，与「简介」共用一个 `format` 工具条 handler，目标由工具条容器上的 `data-target` 区分
- 顾客详情页：编了就整段 `rich-text` 渲染，**留空回退**原来那三条默认规则（存量商品不会空白）

### 1.4 次卡商品删除（软删除）

- 新增 `Rent/DeletePunchCardProduct/{productId}`（staff≥200）：置 `valid=0` + 写 `core_data_mod_log`，只允许删卡类商品（先校验 `category_code` 命中次卡/季卡分类），幂等
- **连带必改**：`GetAllPunchCardProducts` 原本完全不过滤 `valid`，不加 `p.valid == 1` 的话删完还留在列表里，等于没删
- 不物理删行的理由：`retail.product_id` 和顾客自助下单链路还引用它。已发出的卡完全不受影响——卡上的名称/次数是发卡那刻复制过去的

---

## 2. 顾客端商品展示：从数据库读，不再前端硬编码

### 2.1 简介/图片/使用规则一律来自 DB

- 根子在后端：`GetPunchCardProducts` 的投影只吐 5 个字段 `{id, name, sale_price, punch_total, shop}`，**后台编的富文本简介和图片压根没传到顾客端**
- 于是前端只好自己编文案：`punchcard_shop.js` 里硬编码过「双板/单板 + 雪鞋租赁次卡，N 次任选门店核销」，后台改了简介顾客完全看不到
- 新增两个共享 helper：
  - `StripHtmlToPlainText(html, maxLen)` — 富文本剥标签 + 解实体 + 压空白 + 截 60 字
  - `BuildPunchCardProductView(p, bizType, cardType)` — 统一视图，多下发 `content` / `intro` / `usageRules` / `imageUrl` / `bizType` / `cardType` / `isSeason` / `careProjectCount`
- 前端删掉硬编码，首页用 `intro`、详情页用 `content` 富文本

### 2.2 季卡消失（我自己写的 bug）

- 现象：购买页只显示次卡，「26-27雪季机打蜡季卡」怎么也不出现
- 先猜「商品目录里没建这个商品」——**猜错了**。连生产库一查，商品 717 好好地在那儿：`category_code=0202`、`valid=1`、`on_shelves=1`
- 真因：我让前端传**空串**当「要全部卡类」的哨兵（`?cardType=`），但 **ASP.NET Core 对「参数存在但值为空」的可选参数会回落到默认值**（`cardType` 变回 `"次卡"`），判空分支根本执行不到
- 修复：改用显式哨兵 `all`（非空字符串一定原样传到服务端），前后端同步改，两边都留注释说明为什么不能传空串

### 2.3 图片显示不全

- DevTools 元素面板一看就明白：`<image mode="aspectFill">` 是「填满容器 + 裁掉溢出」，配上我写死的 `height: 180px`，图被切成中间一条
- 改 `mode="widthFix"`（宽度铺满、高度按比例自适应、完整不裁剪），**容器必须同时去掉固定高度**，否则 widthFix 撑出的高度被 `overflow:hidden` 截断，等于又变回裁剪
- 管理列表缩略图改 `aspectFit`（96rpx 方框里整图缩进去，店长一眼核对配了哪张）

### 2.4 `multi-uploader` 上传假成功（既有 bug）

- `wx.uploadFile` 的 `success` 对 **400/401/500 也会触发**，[multi-uploader.js:84](../snowmeet_wechat_mini/components/uploader/multi-uploader.js) 不判 `statusCode`，把**错误响应体**当路径拼进 URL 存库
- 表现：上传界面看着成功、库里存的是垃圾地址、顾客端只能渲染出空白横幅
- 修复：非 2xx 直接 toast 中止；返回值不是以 `/` 开头的站内路径也拒绝入列。共享组件，`rent_product` 等其它调用方一并受益
- 另加 `binderror` 兜底：图片加载失败退回数字热区并在 console 打出坏 URL，不再"空白色块看不出是没配图还是图挂了"

---

## 3. 顾客自助购买闭环（本场最大块）

### 3.1 不再走店员开单的结算页

用户明确：「顾客自行购买次卡，不应该使用店员开单的支付页面」。原来 `onBuyNow` 下单后跳 `/pages/payment/settle`——那是店员收银页（生成二维码给顾客扫，还带现金/挂账/支付宝等店员才用的方式）。

新链路：

```
punchcard_detail「立即购买」
  → Rent/PlaceMyPunchCardOrder（顾客自助专用下单）
  → punchcard_confirm 确认页（新增）
  → Rent/StartMyPunchCardPayment（建待支付单）
  → Order/WechatPayByOrderPayment（换预支付参数，复用顾客扫码支付那条现成的）
  → wx.requestPayment
  → DealSuccessPaidOrder「零售」分支建 punch_card
```

### 3.2 「订单不存在」根因：订单没有归属会员

- `OrderController.PlaceOrder` 开头是 **if/else** 分流：
  ```csharp
  if (staff != null && staff.title_level >= 100)   { order.staff_id = staff.id; }
  else if (member != null && order.member_id == null) { order.member_id = member.id; }
  ```
- 下单人本身是店员时只写 `staff_id`、`member_id` 留空 → 确认页的归属校验 `order.member_id != member.id` 判假
- **不能改成"总是填 member_id"**：店员给散客开单时 member_id 本来就该空，填上会把散客单错记到店员名下
- 解法：顾客自助单独走 `PlaceMyPunchCardOrder`，订单必归属购买人，商品/价格/数量全部服务端现算
- 顺手修了 `PlaceOrder` 里 `staff_id = staff.id` 的 NPE（顾客会话 staff 为 null，方法开头已允许顾客分支、日志这里却没跟上）→ 改 `staff?.id`

### 3.3 手机号验证（服务端强制）

- 两道后端门槛：`PlaceMyPunchCardOrder`（下单）+ `StartMyPunchCardPayment`（发起支付）都校验 `member.cell` 非空
- 前端约束：**微信 `getPhoneNumber` 只能由 `<button open-type="getPhoneNumber">` 直接触发**，JS 调不起来 → 不能"点购买→报错→再弹授权"，必须在点之前就知道该渲染成哪种按钮
- 新增 `Rent/CheckMyPunchCardPurchase` 前置查询；没手机号时「立即购买」原地渲染成授权按钮（文案外观一样，顾客无感），授权成功后**自动接着下单**

### 3.4 `UpdateWechatMemberCell` 对新顾客必 500（既有 bug）

- 报错：`ExpressionTreeFuncletizer` + NRE，堆栈指向 [MiniAppUserController.cs:351](../SnowmeetApi/Controllers/User/MiniAppUserController.cs) 的 `.Where(... m.member_id == member.id)`
- 用报错 URL 里的 sessionKey 直接查生产库坐实：
  ```
  session_key = p9IMvLpkwcKwxTulkZh5pQ==
  member_id   = (空)           ← 关键
  wechat_openid  = oHdTn5enw9r05VeyOd5AnR4obmEA
  ```
- 根因：自 2026-05-29 起 `MemberLogin` 不再自动建 stub 会员，没注册过的用户 `mini_session.member_id` 为 null → `GetMemberBySessionKey` 返回 null → EF 求值查询参数时解引用 `member.id` 炸
- **买次卡的新顾客恰恰就是这种人**。雪票预定页用的是同一个接口，一直没炸只是因为走到那步的多半已是老会员
- 修复：`UpdateWechatMemberCell` 加会员兜底 `ResolveOrCreateMemberByCell`，语义**照搬 `PaymentIdentityController._submitPhone`** 已跑通一年的分支——按手机号找会员（找到就把 openid/unionid 链过去，一人多设备共享会员）/ 找不到就建新会员 + 回填 `mini_session.member_id`。共享接口，雪票那几个页面一并受益

---

## 4. 我的次卡 / 会员管理

- **次卡使用明细页**（新建 `pages/mine/punchcard_usage`）：卡片摘要 + 核销记录（订单号 / 业务日期时间 / 该单核销次数）。`punch_card_used` 是「每条 rental / 每件 care 一行」的粒度，同一订单多行，服务端按 `order_id` 汇总
- **会员详情页次卡可点进核销记录**：抽出共享 helper `BuildPunchCardUsageView`，顾客侧 `GetMyPunchCardUsages` 与店员侧 `GetPunchCardUsagesByStaff` 只差「谁有权看这张卡」，展示口径完全一致。店员侧**不下发 refund**——自助退款是顾客入口，店员替顾客退款走店员流程
- 「我的次卡」列表行加高显示开卡日期；`GetMyPunchCards` 去掉 `biz_type == "租赁"` 过滤（顾客能买养护卡，只查租赁会让它凭空消失）+ 加租赁/养护角标

---

## 5. 底部菜单 + 首页

- 底部菜单不是 app.json 原生 `tabBar`，而是 weui `mp-tabbar`，数据源 `app.globalData.userTabBarItem`。在「预定」「我的」之间插入「次卡」
- ⚠️ **各页面 `tabIndex` 是硬编码的**，往数组中间插项会让后面所有页面高亮错位 → 「我的」从 1 改成 2，并在 app.js 数组上方留注释列出所有用 `mp-tabbar` 的页面
- 首页统一跳次卡页：删掉「店员自动进后台」分支——它跳的 `/admin/admin` 路径不存在（注册的是 `pages/admin/admin`），`navigateTo` 必然失败且失败后不走 else，**店员打开小程序其实一直卡在空白首页**。店员进后台走「我的 → 我是管理员」

---

## 6. 养护季卡语义（三条业务规则）

### 6.1 单项 / 双项

- 原来靠**卡名含不含「双项」两个字**判断（`ApplyDefaultServices`），卡名是人工填的，历史上就有「双项10次卡」和「养护双项10次卡」两种写法
- SQL：`product.care_project_count` + `punch_card.care_project_count`（[sql/2026-07-26_care_project_count.sql](../sql/2026-07-26_care_project_count.sql)），**用户已执行**
- 链路：商品维护页定义 → 发卡/售卡时复制到卡 → 核销时**优先读字段**，为 NULL 的历史卡回退老口径（卡名匹配），行为不变、无需回填

### 6.2 季卡「开卡」：首次使用绑定装备

- 发卡/售卡时并不知道顾客拿哪块板来，`equip_*` 三列是空的。第一次真正用它养护时，把这次的装备写进卡，此后只认这块板
- 前端：选中未开卡季卡时**不锁装备**（装备正是要写进去的内容），显示琥珀提示条，文案随录入实时变（装备没填全会写明还缺什么）
- 后端 `EffectCareOrder`：`IsSeasonCardUnbound(card) && HasFullEquipInfo(care)` 才写。**缺一项就不开卡**——写进去一张残缺的绑定，这张季卡以后再也匹配不上任何装备，等于废掉

### 6.3 每天限用一次

- 季卡不限总次数，没有这道闸就等于无限次免费养护
- 选卡列表：`usedToday` 置灰 + 「今日已用」角标 + 点击 toast（只置灰不给反馈，店员会以为点击没生效、反复戳）
- 服务端 `PlaceCareOrder` 兜底拦两种冲突：① 今天已在别的单上核销过 ② **同一张卡在本单多件装备上重复选**（下单这刻本单还没落 `punch_card_used`，查库看不出来，用 `seasonCardUsedInThisOrder` 集合在循环里累加）

---

## 7. 门店语义修正（用户澄清后返工）

用户：「这个门店属性，仅仅是购买收款到哪个门店的账户下，并不意味着限制使用的门店。」

我按「限制使用门店」实现的地方全错了，三处返工：

- **后端目录不再按门店过滤** —— 卡全店通用，任何门店的目录都该列出全部卡种
- **顾客端不再展示门店** —— 详情页/确认页的「适用门店」整块删掉。这是内部记账属性，展示给顾客只会造成"只能在这家用"的误解
- **后台改成「收款门店」并设为必填** —— `product.shop → order.shop → GetMchId 选微信商户号 + GenerateOrderCode 取订单号前缀`，没有它服务端不知道钱进谁的账

另外把手输文本框换成**门店选择器**：顾客端过滤原本是精确字符串匹配，而真实店名里「南山」「总部」「渔阳」「怀北」都不带「店」字，手输极易写错。存量脏值在编辑时会自动清空逼重选。

---

## 8. 接待页 / 会员条

- **接待页会员匹配提示**：原来匹配到会员但档案没姓名/性别时**界面毫无反应**（只 console.warn），店员会以为没匹配上、按散客处理，开单就挂不到这个会员名下。改成常驻提示条（不用 toast——缺资料是要店员动手补的信息，必须一直看得见），缺哪项说哪项，补齐后自动从琥珀警示收敛成绿色
- **会员条资产 chip 扩展**：原来只有储值/次卡/龙珠，只有季卡或只有券的会员一片空白。`GetMemberAssetsByStaff` 加 `ticketCount` + 按业务线拆分的次卡/季卡计数。chip 改由 JS 派生并带 icon，**卡按当前业务线过滤**——否则养护开单看到「次卡 20 次」（其实是租赁次卡）会让店员以为这单能用卡

---

## 9. 卡类产品销售列表（管理后台新页面）

- 新增 `Rent/GetPunchCardSalesByStaff`（分页倒序）+ 新页面 `pages/admin/rent/punchcard_sales/`
- **销售方式按「卡是怎么来的」判定**：`source_retail_id` 为空 → 赠送；关联零售行挂在**租赁订单**上 → 随订单购买；其余 → 顾客自助购买
- 明细页**复用 `punchcard_usage` 的店员模式**而不是新建第三个页面（核销记录列表和卡片摘要完全一样），店员模式多出顾客信息卡 + 季卡绑定装备编辑
- 新增 `Rent/UpdatePunchCardEquipByStaff`：**只开放品牌和长度**，装备类型换了等于换一块板，那是"换卡"不是"改信息"

---

## 关键改动文件

| 文件 | 改动 |
|---|---|
| [`Controllers/CategoryController.cs`](../SnowmeetApi/Controllers/CategoryController.cs) | `GetProduct` 加 `product.category` 判空（修三个调用方共有的 500） |
| [`Controllers/RentController.cs`](../SnowmeetApi/Controllers/RentController.cs) | `StripHtmlToPlainText` / `BuildPunchCardUsageView` / `BuildPunchCardProductView` 三个共享 helper；新增 `GetPunchCardProduct` / `PlaceMyPunchCardOrder` / `GetMyPunchCardOrder` / `StartMyPunchCardPayment` / `CheckMyPunchCardPurchase` / `GetMyPunchCardUsages` / `GetPunchCardUsagesByStaff` / `GetPunchCardSalesByStaff` / `UpdatePunchCardEquipByStaff` / `DeletePunchCardProduct`；`cardType=all` 哨兵；目录去掉门店过滤 |
| [`Controllers/OrderController.cs`](../SnowmeetApi/Controllers/OrderController.cs) | `PlaceOrder` 的 `staff?.id` NPE 修复；发卡按 category 反解 `biz_type`（原写死"租赁"）+ 季卡 `total=null` + 复制 `care_project_count`；`PlaceCareOrder` 季卡每日限一次闸门 |
| [`Controllers/CareController.cs`](../SnowmeetApi/Controllers/CareController.cs) | `IsSeasonCardUnbound` / `HasFullEquipInfo`；`EffectCareOrder` 季卡开卡绑定装备；`ApplyDefaultServices` 优先读 `care_project_count` |
| [`Controllers/MemberAdminController.cs`](../SnowmeetApi/Controllers/MemberAdminController.cs) | 发卡预设改读商品目录 + `GrantPunchCard` 只收 productId；`GetMemberAssetsByStaff` 加券/季卡；`GetMemberCardsByStaff` 加 `usedToday` |
| [`Controllers/User/MiniAppUserController.cs`](../SnowmeetApi/Controllers/User/MiniAppUserController.cs) | `UpdateWechatMemberCell` 加 `ResolveOrCreateMemberByCell` 会员兜底（修新顾客 500） |
| `Models/Product.cs` / `Models/Rent/PunchCard.cs` | `usage_rules` / `care_project_count` |
| `components/uploader/multi-uploader.js` | 上传假成功修复（判 statusCode + 校验返回路径形状） |
| `components/reception/reception_member_bar/` | 资产 chip 改 JS 派生 + icon + 按业务线过滤 |
| `components/reception/ticket_card_selector/` | 季卡今日已用禁选 |
| `components/reception/care_recept_form/` | 季卡开卡提示条 |
| `pages/punchcard/{punchcard_shop, punchcard_detail, punchcard_confirm}` | 顾客自助购买全链路（confirm 页新建） |
| `pages/mine/{my_punchcards, punchcard_usage}` | 开卡日期 + 使用明细页（新建，双模式） |
| `pages/admin/rent/punchcard_sales/` | 卡类产品销售列表（新建） |
| `pages/admin/reception/recept_entry.*` | 会员匹配常驻提示条 |
| `app.js` / `pages/index/index.js` | 底部菜单加「次卡」+ 首页统一跳次卡页 |

---

## 学到的小知识

1. **ASP.NET Core 对「查询参数存在但值为空」的可选参数会回落到默认值**：`?cardType=` 不会传 `""` 或 `null` 进来，而是变回默认的 `"次卡"`。想表达「全部」必须用**显式非空哨兵**（如 `all`），不能靠空串
2. **`wx.uploadFile` 的 `success` 对任何 HTTP 状态码都触发**：不判 `statusCode` 就会把错误响应体当上传结果。这已经是本项目第二次踩（`uploadFilePromise` 是第一次），任何 `wx.uploadFile` 封装都必须判状态码 + 校验返回值形状
3. **`mode="aspectFill"` 是裁剪、`widthFix` 才是完整显示**；用 `widthFix` 时**容器必须去掉固定高度**，否则被 `overflow:hidden` 截断等于又变回裁剪
4. **`GetMemberBySessionKey` 在 session 存在但 `member_id` 为 null 时返回 null**：自 2026-05-29 不建 stub 会员后，所有"新顾客第一次做某事"的接口都要考虑这个分支。EF 里 `member.id` 出现在 LINQ 表达式中时，NRE 会以 `ExpressionTreeFuncletizer` 的形式抛出，堆栈看着像 EF 内部错误，实则是自己的空引用
5. **`PlaceOrder` 是 if/else 分流的**：staff 会话只写 `staff_id`，member 会话只写 `member_id`。顾客自助场景不能复用它（下单人恰好是店员时订单就没有归属会员），要么单开接口、要么显式传
6. **`punch_card_used` 是「每条 rental / 每件 care 一行」的粒度**：按订单展示核销记录必须 `GroupBy(order_id)` 汇总，否则一单会重复出现好几行
7. **同一批次内的重复占用查库查不出来**：季卡每日限一次时，同一订单多件装备选同一张卡，下单这刻都还没落 `punch_card_used`，必须在循环里用集合累加才能拦住
8. **weui `mp-tabbar` 的 `tabIndex` 硬编码在各页面 data 里**：往菜单数组中间插项会让后面所有页面高亮错位，增删项必须同步核对所有使用页面
9. **只置灰不给点击反馈会让人反复戳**：禁用项被点击时要 toast 说明原因
10. **直连生产库只读排查比反复猜快一个数量级**：本场三次靠一条 SQL 一击定位（季卡商品其实存在、session 的 member_id 为空、会员只有一张季卡），前两次都推翻了我自己的错误假设
