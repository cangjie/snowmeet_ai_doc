# 2026-07-09 打蜡券不可见根因修复 + 券/卡双 tab 选择弹层：Ticket 默认 valid=0 定位、四张测试券修数、养护开单弹层重做

按时间线整理。接 7-8 养护开单联调线，本场三条主线：上传域名回切、优惠券不可见排查修复、优惠券选择弹层重做成券/卡双 tab。改动跨 `snowmeet_wechat_mini`（7 文件，含新组件 4 文件）+ `SnowmeetApi`（2 文件）+ 生产库一次数据修复；**两代码仓本地未提交**，end-work 仅 push doc 仓。

## 0. start-work 基线

- doc 仓 pull already up to date；核实两代码仓状态：**7-8 批次已被用户 commit+push**（SnowmeetApi `c84a55b7` "care equip brand modal" / mini `721c3bf6` "care"），双仓工作区干净——CLAUDE.md 里「7-8 本地未提交」已过时，本场已更正
- 本机新发现：微信开发者工具自带 node（`C:\Program Files (x86)\Tencent\微信web开发者工具\node.exe`），可做 `node --check`；python 需重装 pyodbc（5.3.0）

## 1. 上传/显示域名回切 wanlonghuaxue

用户原话：「小程序客户端，所有上传图片的域名，改回之前的 snowmeet.wanlonghuaxue.com」。

- 7-8 暂切 mini.snowmeet.top 的恰好 3 处全部改回：[`utils/data.js`](../../snowmeet_wechat_mini/utils/data.js) `uploadFilePromise`、`care_recept_form.js` `UPLOAD_HOST`、`care_order_detail.js` `IMG_HOST`；「2026-07-08 暂时」注释清理
- 其余 `mini.snowmeet.top`（requestPrefix / 二维码链接）按 6-12 约定不动
- 提醒用户两个前提/后果：① wanlonghuaxue 那台部署未对齐前上传会再次 400（7-8 根因未收口）② 过渡期经 mini 上传的照片落在 mini 磁盘，回切后 404（联调测试数据可不管）

## 2. 「选择我的优惠券，不显示」根因定位 + 修复

用户问题原话：「养护开单，会员id 15506，名下有四张免费的打蜡券，code 分别是 999357148 188326793 1935961230 103730884 为什么选择我的优惠券，不显示？」

### 2.1 过滤链定位

- 新旧养护开单同用 `ticket_selector/ticket_list` → `Ticket/GetMemberTicketsByStaff`
- 基查询 [`GetMemberTickets`](../../SnowmeetApi/Controllers/TicketController.cs)：`member_id == memberId && valid == 1 && is_active == 1`；canUse=true 再过滤 start/expire 日期窗 + `used==0`；bizType 过滤 `biz_type=='养护' || template_id==12`

### 2.2 生产库实查（只读）

- 三张券（999357148/188326793/103730884）：member_id=15506、template 12、biz_type=养护、is_active=1、used=0、expire 2026-10-01——**唯独 `valid=0`**，第一道过滤就被挡掉
- 第四张 `1935961230` 在 ticket 表 0 行；LIKE 模糊找回真身 **`193596120`**（用户抄多一位），同样 valid=0
- 四张全部 `channel='daidai'`、create_memo=''、2025-09-18~21 写入；**全库 daidai 通道恰好就这 4 张**；当前代码 + git 全历史搜不到 daidai → 外部通道直插的数据

### 2.3 根因链（系统性，不止这 4 张）

- **`Ticket` 模型 C# 默认 `valid = 0`**（Ticket.cs:36）
- 在用发券路径 [`GenerateTicketByAction`](../../SnowmeetApi/Controllers/TicketController.cs)（买雪票增券 / 扫码领取 / 非雪季养护 17/18）**漏设 valid 和 member_id** → 从该路径发的券天生不可见；非雪季 17/18 靠 `CareController` 545/549 事后补 `valid=1` 侥幸能用
- 全库 template 12 有 **84 张 valid=0**：45 张「买雪票增券」+ 30 余张 create_memo=雪票id + 4 张 daidai + 3 张杂项；「非雪季养护」存量 334 张中 8 张 member_id 为空且恰是 valid=0 的 8 张（member_id 漏设的实证）
- **接口口径不一致**：旧 `/core/Ticket/GetTicketsByUser`（admin ticket_unuse_list、旧 ticket_selector）只按 openid+used 过滤**不看 valid** → 「admin 券列表看得到、开单选不出」的错觉来源
- 顺带发现新版 `api/Ticket/GetMyTickets` 对未使用券的过期过滤 `expire_date <= 今天` 疑似方向写反（只显示已过期券）→ **spawn 后台任务**，用户已在独立会话启动核查

### 2.4 修复（用户拍板「测试数据，valid 更新成 1，bug 也修」）

- **DB**：`UPDATE ticket SET valid=1 WHERE code IN (四张) AND member_id=15506 AND valid=0`——影响行数恰 4 才 commit（否则回滚），修后核查全部 valid=1。立即生效，无需部署
- **代码**：`GenerateTicketByAction` 初始化器补 `valid = 1` + `member_id = memberId`；build 0 错误
- 未动：其余 ~80 张存量 valid=0 券，待业务确认是否批量修

## 3. 养护开单优惠券弹层重做：券/卡双 tab（两轮）

### 3.1 第一轮：双 tab + 卡展示

用户需求：弹出 modal 两个 tag——「选择优惠券」列 code/名称/到期日/**create_memo**；另一 tag 显示会员名下次卡/季卡等各类卡，次卡显示名称/已用/剩余，季卡显示上次使用时间。

- 探索结论：`punch_card` 现库 6 种卡名全是「N次卡」（15506 名下 4 张），**季卡实体尚不存在** → 按 `card_name` 含「季卡」自适应识别，后发季卡不用改码；上次使用时间 = `punch_card_used`（valid 行）max(create_date)
- 后端新接口 [`MemberAdmin/GetMemberCardsByStaff`](../../SnowmeetApi/Controllers/MemberAdminController.cs)（staff≥100，与开单页会员条同级）：返回 id/biz_type/card_name/total/punches/remaining/lastUsedDate
- 前端新组件 [`components/reception/ticket_card_selector/`](../../snowmeet_wechat_mini/components/reception/ticket_card_selector/ticket_card_selector.js)（自带 van-popup，Alpine 风格对齐 search_product_fuzzy；`show` observer + `wx.nextTick` 等同批 props 落定再加载）；`data.js` 加 `getMemberCardsPromise`
- 事件契约沿旧 ticket_list（`Event`={action, selectedTicket}），care_recept_form.js 第一轮零改动；旧 `ticket_selector/ticket_list` 不动（旧版养护不受影响）

### 3.2 第二轮：卡可选 + 全局互斥单选（用户拍板）

用户原话：「第一，会员卡应该可以选择；第二，优惠券和优惠券，会员卡和会员卡，优惠券和会员卡，只能单选。」

- 组件：卡行加单选圆点/高亮；`pickedCode / pickedCardId / pickedNone` 三态互斥；两 tab 各有「不使用优惠券/会员卡」行；确认事件扩展 `{action:'confirm', selectedTicket, selectedCard}`（最多一个非空，都空=清除）；重开弹层已选卡时直接落卡 tab 并预选
- 表单侧落点调研：`Care.use_card` 是后端既有 bool（订单列表【卡】筛选/标签认它）但**任何现有流程都没写过它**；Care 无 card_id 列
- 接线（care_recept_form）：选卡 → `use_card=true` + `card_id/card_name` 前端标量；选券清卡侧、选卡清券侧（ticket/ticket_code/free_wax/discount）、「不使用」双清；blankCare 补三字段；chips 券/卡互斥；行 label 改「优惠券/卡」显示「(卡)卡名」
- [`recept_new.js`](../../snowmeet_wechat_mini/pages/admin/reception/recept_new.js) 保存回填：`card_id/card_name` 后端无列不回传，从本地 care 带回（同 ticket 对象合并模式）；POST 里多出的两标量后端 System.Text.Json 静默忽略，无害
- **明确边界（已告知用户）**：① 中断找回只知 use_card=true，显示「已选会员卡」不带卡名（要精确需 care 表加列）② 选卡不改价、不扣次数——真正核销（扣 punches + 写 punch_card_used，类似租赁 UseRentalPunchCard）在结算/支付链路，养护版待做

## 关键改动文件

| 文件 | 改动 |
|---|---|
| `snowmeet_wechat_mini/utils/data.js` | 上传域名回切 + `getMemberCardsPromise` |
| `snowmeet_wechat_mini/components/reception/care_recept_form/*` | UPLOAD_HOST 回切；弹层换新组件；选卡 use_card/互斥/显示 |
| `snowmeet_wechat_mini/pages/admin/care/care_order_detail/care_order_detail.js` | IMG_HOST 回切 |
| `snowmeet_wechat_mini/components/reception/ticket_card_selector/*`（新建 4 文件） | 券/卡双 tab 全局互斥单选弹层 |
| `snowmeet_wechat_mini/pages/admin/reception/recept_new.js` | 保存回填带回 card_id/card_name |
| `SnowmeetApi/Controllers/TicketController.cs` | GenerateTicketByAction 补 valid=1 + member_id |
| `SnowmeetApi/Controllers/MemberAdminController.cs` | 新接口 GetMemberCardsByStaff |
| 生产库 `ticket` 表 | 4 行 valid 0→1（15506 测试券） |

## 学到的小知识

1. **模型默认值是隐形业务规则**：`Ticket.valid` C# 默认 0，发券代码不显式置 1 就静默不可见——与「全局 NoTracking 静默不存」同族：不报错的失效最耗排查时间。新发券/新实体创建必须核对每个门控字段的默认值
2. **同一数据三个接口三种可见性**：查「看得到选不了」类问题，先 DB 直查实体门控字段（valid/is_active/used/expire），再对比各查询路径的过滤差异，不要从 UI 往下猜
3. **channel 字段可定位数据来源**：`channel='daidai'` 代码史无此字 → 判定外部直插；`GROUP BY channel, create_memo` 能快速给存量券分堆归因
4. **本机微信开发者工具自带 node.exe**（`C:\Program Files (x86)\Tencent\微信web开发者工具\node.exe`），小程序 JS 可 `node --check`（本机 PATH 无 node）
5. **前端专有标量随保存往返的模式**：后端模型无对应列的展示字段（ticket 对象、card_id/card_name），POST 时后端静默忽略、响应不回传，须在保存回填处从本地对象带回——这是 recept_new 的既定模式，新字段照抄即可
6. **写生产库脚本的护栏**：UPDATE 限定到最窄（code+member_id+旧值），核对 rowcount 与预期不符即 rollback，改后立刻 SELECT 回验
