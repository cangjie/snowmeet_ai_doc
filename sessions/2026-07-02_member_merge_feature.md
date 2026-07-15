# 2026-07-02 会员合并功能落地：执行 plan，MergeMember 扩展三类资产 + staff 端点 + 详情页合并入口

按时间线整理。会话起始 start-work（doc 仓 already up to date），用户说「执行下刚才的会员合并的计划」——plan 已在前一会话写好（`~/.claude/plans/punch-card-calm-wand.md`），本场纯执行。改动落在 `SnowmeetApi`（2 controller）+ `snowmeet_wechat_mini`（data.js + member_detail 三件套），**无库表变更**。

## 1. Plan 定位

- 用户说「刚才的计划」但本会话刚 start-work，无前文 → 按 mtime 找 `~/.claude/plans/` 最新文件 `punch-card-calm-wand.md`（当天 22:59），文件名叫 punch-card 但内容正是「会员合并（Member Merge）」
- Plan 核心：当前会员的 订单/龙珠/储值/次卡/优惠券 全迁目标会员；当前会员 `merge_id=目标ID + is_merge=1`；MSA 全 `valid=0`；全程 core_data_mod_log
- 现状盘点：`MemberController.MergeMember`（[MemberController.cs:86](../../SnowmeetApi/Controllers/MemberController.cs)）已做 订单+储值 迁移 + MSA 失效 + merge 标记 + 手机号迁移，**缺 龙珠/次卡/优惠券**

## 2. 后端

### 2.1 模型勘察（决定迁移写法）

- `Point`（`user_point_balance`）：`member_id` int，**无 update_date 列** → 只改 member_id
- `PunchCard`（`punch_card`）：`member_id` int + `update_date DateTime?` → 迁移时一并 `update_date=Now`
- `Ticket`（`ticket`）：**主键是字符串 `code`**、`member_id` int? → 差异日志有类型冲突（见 2.2）
- DbSet 名：`_db.point` / `_db.punchCard` / `_db.ticket`（ApplicationDBContext 已有，无需加）

### 2.2 `MergeMember` 扩展（[MemberController.cs](../../SnowmeetApi/Controllers/MemberController.cs)）

- 插入点：deposit 迁移循环之后、`await _db.SaveChangesAsync()` 之前，三段迁移与既有 order/deposit 完全同款：
  - 查 `where member_id == sourceId` → 逐行改 `member_id = targetId` → `Entry().State = EntityState.Modified`（**全局 NoTracking，漏了就静默不存**）→ 每行 AddAsync 一条 CoreDataModLog（`trace_id` 共用方法顶部的 traceId，scene=`用户批量合并`，field_name=member_id，prev/current=source/target）
- 三段差异点：
  - `user_point_balance`：manual_memo=`龙珠迁移`
  - `punch_card`：+`update_date=Now`，manual_memo=`次卡迁移`
  - `ticket`：**`CoreDataModLog.key_value` 是 int、ticket 主键是字符串 code** → `key_value=0`、code 拼进 `manual_memo`（`优惠券迁移 code=XXX`）保留追溯
- 既有 MSA 失效 / merge_id / 手机号迁 target 的逻辑全部不动

### 2.3 `MemberAdminController.MergeMemberByStaff` 新增

- `[HttpGet]`，签名 `(int sourceMemberId, int targetMemberId, string sessionKey, string sessionType)`，鉴权与本 controller 其他端点一致（`GetStaff` + `title_level >= MIN_LEVEL(200)`）
- 校验链：source≠target（`不能合并到自己`）→ 两会员存在（AsNoTracking FirstOrDefault）→ source `is_merge==1` 拒绝（`该会员已被合并过`）→ **target `is_merge==1` 也拒绝**（`目标会员已被合并，不能作为合并目标`，plan 外补的防御——往已失效会员上合并会造成资产黑洞）
- 通过后 `new MemberController(_db, _config).MergeMember(sourceMemberId, targetMemberId)`，返 `{sourceMemberId, targetMemberId}`

## 3. 前端（snowmeet_wechat_mini）

### 3.1 `data.js`

- 加 `mergeMemberByStaffPromise(sourceMemberId, targetMemberId, sessionKey)`（GET，MemberAdmin/MergeMemberByStaff）+ module.exports 导出，紧跟会员管理 promise 组

### 3.2 `member_detail` 三件套

- **wxml**：
  - 资料卡 head-top 的「编辑」右侧加「合并」按钮：`head-edit head-edit--merge`（红边红底浅红 `#ba1a1a`/`#fdecec`，van-icon `exchange`）
  - 文件尾加合并弹层：`mask + sheet`（复用标签弹层样式体系）——标题「合并到其他会员」+ 红色警示条（列明五类资产转移 + 当前会员失效 + 不可撤销）+ 搜索行（`sheet-add/sheet-input/sheet-add-btn` 复用）+ 结果列表（`.opt/.opt-mid/.opt-name/.opt-sub` 复用，显示 姓名（性别）/ ID / 手机号）+ 两个空态（未搜索提示 / 无结果）
- **js**：
  - data 加 `mergeShow/mergeKeyword/mergeResults/mergeSearched`
  - `onMergeSearch`：关键字 `/^\d{3,}$/` 判定 → 纯数字按 `{cell}` 搜、否则 `{name}` 搜（复用 `searchMembersByStaffPromise`，取 20 条）；结果 `filter(m.id !== 当前 memberId)` 排除自己
  - `onMergeSelect`：`wx.showModal` 强二次确认（content 列明资产清单 + 目标会员名/ID + 不可撤销；confirmText=`确认合并` 恰好 4 字上限、confirmColor 红）→ confirm 后调 `mergeMemberByStaffPromise` → 成功 toast「合并完成」+ `redirectTo` 目标会员详情（replace 当前页，back 回列表）
  - catch 不再自行 toast（后端 message 如「该会员已被合并过」已由 `performWebRequest` 统一 toast）
- **wxss**：`.head-edit--merge`（margin-left 12rpx 让「编辑」保持 auto 推齐、合并紧随其右）+ `.head-edit-txt--merge` + `.merge-warn`（红警示条）+ `.merge-search` + `.merge-body`（min 320rpx / max 50vh）

### 3.3 搜索返回字段确认

- 看 `member_list.js` 消费方式确认 `searchMembersByStaffPromise` 返 `r.items`（含 `id/name/gender/phone/deposit/points/sys/custom`）+ `r.total`，弹层直接用 id/name/gender/phone 四字段

## 4. 验证

- `dotnet build SnowmeetApi.csproj`：0 error / 12 warning（全历史无关项）
- `node --check`：member_detail.js + data.js 通过
- wxml 标签平衡：view 111/111、scroll-view 6/6、text 53/53、input 6 自闭合，全 OK

## 关键改动文件

| 文件 | 改动 |
|---|---|
| [`SnowmeetApi/Controllers/MemberController.cs`](../../SnowmeetApi/Controllers/MemberController.cs) | `MergeMember` 补 龙珠/次卡/优惠券 三段迁移（Entry Modified + mod log） |
| [`SnowmeetApi/Controllers/MemberAdminController.cs`](../../SnowmeetApi/Controllers/MemberAdminController.cs) | 新增 `MergeMemberByStaff`（鉴权 + 四重校验 + 调 MergeMember） |
| [`snowmeet_wechat_mini/utils/data.js`](../../snowmeet_wechat_mini/utils/data.js) | +`mergeMemberByStaffPromise` |
| [`snowmeet_wechat_mini/pages/admin/member/member_detail.{js,wxml,wxss}`](../../snowmeet_wechat_mini/pages/admin/member/member_detail.js) | 「合并」按钮 + 搜索弹层 + 二次确认 + redirectTo 目标详情 |

## 学到的小知识

1. **字符串主键表的 core_data_mod_log 写法**：`ticket` 主键是 `code`（string）而 `CoreDataModLog.key_value` 是 int → `key_value=0` + 主键拼进 `manual_memo`。以后任何字符串主键表（card 等）做差异日志可复用此模式
2. **合并/迁移类功能要按「资产清单」核对**：`MergeMember` 存在已久却只迁了 订单+储值；`GetWholeMemberById` 的 Include 列表（MSA/deposit/points/tickets）就是现成的资产清单，逐项对照才发现缺三类。次卡是 6-29 才接入 EF 的，说明**资产清单会随功能演进增长，合并逻辑必须跟着补**
3. **弹层/按钮样式全部复用现页 class**（mask/sheet/opt/btn/head-edit），只加 5 个新 class 就完成整套合并 UI——member 系列页面的样式体系已经够成熟，新弹窗优先翻现有 class
4. **`wx.showModal` confirmText 4 字上限**又一次踩线：「确认合并」恰好 4 字，设计文案时先数字数

## 待用户（部署节奏）

- publish SnowmeetApi（MergeMember 扩展 + MergeMemberByStaff，随 6-27/6-30 积压一起上）
- 重编 snowmeet_wechat_mini；真机走：详情页「合并」→ 搜索目标 → 二次确认 → 跳目标详情
- 首单合并后 DB 只读核对：order / user_point_balance / deposit_account / punch_card / ticket 五表 member_id 已迁、source `merge_id/is_merge`、source MSA valid=0、core_data_mod_log scene=`用户批量合并` 行数齐全
- 两代码仓改动**本地未提交**，按部署节奏自行 commit
