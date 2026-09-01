# 2026-09-01 优惠券分享区重构 + 扫码用券：模板页「分享」折叠卡、分享记录三项改造、券详情页强制授权手机号、开单页扫码用券

接续 2026-08-28 的优惠券海报/领取线。本场四条主线，改动落在 `snowmeet_wechat_mini/`（模板编辑页、券详情页、养护开单组件）与 `SnowmeetApi/`（TicketTemplateAdmin / TicketShareRules）。业务代码用户已自行分次 commit + push。

## 1. 模板编辑页「分享」区重构（纯 UI，三轮迭代）

### 1.1 生成海报按钮移进海报 block

- 用户：「生成海报的按钮，放在海报的这个 block 里」
- 「生成群分享海报」按钮从「分享发券」卡片移到「分享海报」卡片末尾（二维码 X/Y/宽高之后）
- **动态/静态二维码 chip 一并搬走**：`groupQrMode` 只被 `onShareGroupTap` 读，留在原处会指向一个已不在那里的按钮
- 新位置补 `wx:if="{{sharable == 1 && id > 0}}"`——原卡片整张带这个条件，海报卡片则是无条件显示的；不补的话新建模板（id=0）会冒出一颗点了必然失败的按钮
- 条件不满足时改显灰字「模板要先保存、并打开「可分享」，才能生成群分享海报」，原来这种情况用户零反馈

### 1.2 三块合成一个可折叠的「分享」卡片

- 用户：「分享记录和分享发券分开，形成一个独立的 block」+「分享海报、分享小程序卡片、分享记录这三块折叠到一个 block 里，标题就叫分享」
- 一张 card 标题「分享」，内含三个子区，各自点标题开合（`shareOpen: {poster, card, batch}`，**非互斥手风琴**，可同时展开）
- 「分享发券」→ 改名「分享小程序卡片」
- 「分享记录」拆成独立子区，标题右侧带条数徽章；列表为空时补空态（原来列表空则连标题都不渲染）
- 默认三个全收起

### 1.3 整块移到页面底部

- 顺序变为：基础信息 → 业务类型 → 有效期 → 商品优惠 → **分享** → [保存]
- **放在「保存」按钮之上**：海报封面和二维码坐标是要落库的表单字段，排到按钮下面用户拖完坐标会找不到保存入口

## 2. 分享记录三项改造（前后端）

### 2.1 分享方式只分两类

- 用户：「不需要区分分享到群之类，只区分分享小程序卡片和分享海报」
- `TicketShareRules.DescribeShareType`：personal → 「小程序卡片」，group / qrcode → 「海报」
- **顺带修既有 bug**：原判断只 `== ShareGroup`，第三种 `qrcode`（静态二维码批次）落进 else 显示成「分享给好友」——它发出去的其实是海报
- 测试补 `qrcode` 一条 InlineData（原来没测过这个分支，正是它漏判的原因），15 → 16 全过

### 2.2 日期筛选，默认最近一周

- `GetMyShareBatches` 加 `startDate` / `endDate`，按 `create_date` 过滤、两端含当天（`>= start.Date`、`< end.Date.AddDays(1)`），照搬 `TicketAdminController.BuildFilteredQuery` 的既有写法；不传即不限日期
- 前端 `onLoad` 算「今天往前 6 天 ~ 今天」共 7 天，用 `components/date-range-picker` 的 range 模式（符合"日期选择一律走这个组件"的约定）
- **顺带修组件既有 bug**：`activeShortcut` 初值写死 `'today'`，而调用方传进来的初始区间通常不是今天（本页最近一周、coupon_admin 雪季至今）→「今天」按钮被假高亮。attached 时比对，不是今天就不高亮。**影响全部 5 个 range 调用方**（care_order_list / care_unfinished_list / new_rent_list / punchcard_sales / coupon_admin），是修正不是回归

### 2.3 显示分享人 + 列表放开到全店

- 用户要显示分享人，但接口原本 `Where(b => b.staff_id == staff.id)` 只查自己 → 加一列永远是自己。提问后用户拍板：**放开全店，所有能进页面的人都能看，不加二级门槛**
- 接口**改名 `GetMyShareBatches` → `GetShareBatches`**（「My」不再成立），全仓只有小程序一处调用，`data.js` 的包装函数同步改名 `getShareBatchesPromise`
- 每条返回 `staffName` / `staffId` / `isMine`；姓名走 `_db.staff` 批量捞 id+name，口径同优惠券管理页「发券人」，不在循环里逐条查
- **`canRevoke` 收紧为 `b.valid == 1 && b.staff_id == staff.id`**：`RevokeShareBatch` 服务端本就只允许撤自己的，列表放开后不收紧会让别人的行显示必定报错的撤回按钮
- 记录行渲染 `海报  张三  分享中` / `小程序卡片  李四（我）  已领完`

### 2.4 顺带发现的口径出入（未处理）

- CLAUDE.md 记「静态码仅模板维护权限（店长及以上）可选」，但模板编辑页准入门槛本身就是 `title_level ≥ 200`，**实际没有第二道门槛**——能进来的人都能选静态码
- 用户口述也是「≥200 的可以生成静态永久二维码」。若本意是更高一档（如 ≥300），这条尚未落地

## 3. 顾客券详情页强制授权手机号（走 brainstorming，bounded）

- 用户：「点击进入优惠券详情页，如果当前顾客未授权手机号，则强制授权，并按之前的会员手机号规则入库」
- 摸清三条既有链路后选定：**判断用 `globalData.member.cell`**（不新增接口，2026-05-29 起 MemberLogin 不再建 stub 会员，没验证过的顾客 member 直接是 null）
- **入库走 `MiniAppUser/UpdateWechatMemberCell`**（次卡购买页 2026-07 刚验证过的那条），内部 `ResolveOrCreateMemberByCell`：按 cell 查到会员就归并并把当前 openid/unionid 链上去，查不到才建新会员（`source = "小程序手机号验证"`），最后回填 `mini_session.member_id`
- 拦截形态：全屏遮罩 `z-index: 200`（压过转赠弹层的 100），`catchtap` + `catchtouchmove` 吃掉穿透，遮罩点不掉；卡片里一颗 `open-type="getPhoneNumber"` 按钮 + 「返回」出口（微信不接受完全堵死的页面），返回走 `navigateBack`，深链无上一页时兜底 `redirectTo` 到「我的优惠券」
- **授权成功后重跑 `_checkCell()` 而不是直接 `needAuth: false`**：后端可能返回不带 cell 的 member（会话归属没回填上），那时不能放行
- 页面里那行注释掉的 `<auth wx:if="{{needAuth}}" validType="cell">` 是当年想做没落地的，`needAuth` 字段正好接上
- **局限**：`bindWechatCellPromise` 直连 `/core` 旧路由、返回裸 Member 非 `ApiResult` 信封，reject 只拿得到 statusCode，失败时只能给通用 toast，没法告诉顾客具体原因
- 只拦详情页，列表页和店员侧 coupon_detail 不动；服务端不加校验（`GetTicket` 不带会话，加校验要改签名）

## 4. 扫码用券（走 brainstorming，bounded）

### 4.1 阻塞发现：公众号二维码扫不出券码

- 用户要在养护开单页优惠券行加扫一扫，扫券详情页二维码识别 code
- **券详情页那个「核销二维码」是公众号带参二维码**（`QR_STR_SCENE`，scene=`oper_ticket_code_{code}`，图片来自 `mp.weixin.qq.com/cgi-bin/showqrcode?ticket=`）。里面编码的是 weixin.qq.com 短链，**券码不在二维码内容里**，`wx.scanCode` 还原不出来
- 它不是死码：走 `case "oper"` → `ScanTicket`，店员用**微信扫一扫**扫它 → 公众号回一条消息带 `{ticket.miniapp_recept_path}?ticketCode={code}` 的跳小程序链接 → 点进去就是开单页。**需求要的效果本来就有一条等价路径**，只是绕公众号
- 给了 4 个方案，用户选：**直接把二维码换成券码码**，接受公众号 ScanTicket 那条路失效

### 4.2 落地

- `ticket_detail.js`：`qrCodeUrl` 改为 `MediaHelper/GetQRCode?qrCodeText={code}`（后端现成，QRCoder 生成普通码，order-payment 在用）
- `care_recept_form`：优惠券行右侧加扫码图标（`van-icon scan`），**不受「散客无可用优惠券」限制**——扫码恰恰是给散客定人的手段
- 流程：`wx.scanCode` → `_parseTicketCode`（容错 URL 取券码）→ `TicketAdmin/GetTicketDetailByStaff` 查持有者 → 三分支：
  - 无持有者（memberId=0）→ 弹窗「该券尚未绑定会员」中止
  - 持有者 == 当前开单会员 → 直接选券
  - 持有者是别人 → `wx.showModal` 二次确认（带姓名+手机号）→ 切人 + 选券
- **抽出 `_applyTicketSelection(cidx, ticket, card)`**：从 `onTicketSelectorEvent` 的 confirm 分支抽出，手选弹层和扫码共用同一段代码——「效果跟手选一样」靠的是同一段代码，不是两段写成一样
- **券可用性校验用「在不在该会员的可用券列表里」**（`getMemberTicketsPromise(memberId, '养护', true)`）：过期 / 已用 / 作废 / 非养护线统统表现为"不在列表里"，不在前端把服务端的券状态机重写一遍
- 切人连带处理：清掉其他 care 上挂着的旧顾客券（否则结算时拿别人的券抵扣）+ 姓名/手机号/性别一起换（顶部会员条按 `customer.cell` 反查，只换 memberId 会让条上还挂着原顾客）
- 同单重复用券也拦一道，与手选弹层的 `disabledCodes` 同口径
- 三个接口门槛都是 `title_level >= 100`（店员即可），开单店员能调

### 4.3 修掉一个竞态

- 切人后紧接着 `_applyTicketSelection` → `_fetchPrice`，此时组件的 `memberId` **property 还没被父页 setData 回传**，会拿旧会员 id 去 `CalcCareCharge` → 算错价
- 修法：`_switchMemberTo` 里组件内先 `setData({ memberId })` 顶上；父页随后传回同一个值，observer 幂等（`_loadDeposit` 自带 `_lastDepositMemberId` 去重）

### 4.4 发布顺序风险

- 本次生效需要**小程序和顾客侧一起发**：老版本小程序里券详情页还是公众号码，新版开单页扫它会「无法识别」；反过来顾客更新了、店员没更新，微信扫一扫那条已断而新扫码按钮还没有——中间有空窗

## 关键改动文件

| 文件 | 改动 |
|---|---|
| `SnowmeetApi/Helpers/TicketShareRules.cs` | `DescribeShareType` 改为只分「小程序卡片 / 海报」两类，qrcode 归海报 |
| `SnowmeetApi/Controllers/TicketTemplateAdminController.cs` | `GetMyShareBatches` → `GetShareBatches`：去掉只看自己的过滤、加日期筛选、返回 staffName/staffId/isMine、canRevoke 收紧 |
| `SnowmeetApi/SnowmeetApi.Tests/TicketShareRulesTests.cs` | 分享方式文案口径跟改 + 补 qrcode 用例（16 全过） |
| `snowmeet_wechat_mini/pages/admin/ticket/template_edit/*` | 三块合成可折叠「分享」卡片、移到页面底部、记录加日期筛选与分享人 |
| `snowmeet_wechat_mini/components/date-range-picker/index.js` | 修 activeShortcut 假高亮（影响全部 5 个 range 调用方） |
| `snowmeet_wechat_mini/utils/data.js` | `getMyShareBatchesPromise` → `getShareBatchesPromise` + 日期参数 |
| `snowmeet_wechat_mini/pages/mine/ticket/ticket_detail.*` | 未验证手机号全屏遮罩强制授权；二维码换成券码普通码 |
| `snowmeet_wechat_mini/components/reception/care_recept_form/*` | 优惠券行加扫码按钮；抽 `_applyTicketSelection`；扫码用券 + 切会员 + 清旧券 |
| `snowmeet_wechat_mini/pages/admin/reception/recept_new.*` | 新增 `onMemberSwitchByTicket`，整体切换 customer 并落盘 |

## 学到的小知识

1. **微信公众号带参二维码不能被第三方扫码还原 scene**：`QR_STR_SCENE` 生成的码里是 weixin.qq.com 短链，只有微信客户端扫码才会解析 scene 触发公众号事件。要让小程序扫得出内容，必须用普通二维码。做"扫码识别"需求前先确认目标二维码的类型
2. **组件 property 在父页 setData 回传前不可靠**：子组件触发父页改 property，紧接着的逻辑仍读到旧值。跨组件切状态时组件内先 `setData` 顶上，父页回传同值幂等
3. **用「可用列表」当校验，别在前端复刻服务端状态机**：券过期/已用/作废/业务线不符统统表现为"不在可用列表里"，一句提示就够。自己解释一遍状态迟早和服务端对不上
4. **接口语义变了就改名**：`GetMyShareBatches` 去掉"只看自己"后名字就在说谎，改成 `GetShareBatches`。全仓只有一个调用方时改名成本几乎为零
5. **放开列表范围必须同步收紧行级操作权限**：列表从"只看自己"放开到全店，`canRevoke` 若不跟着加 `staff_id == staff.id`，别人的行会显示一颗必定报错的撤回按钮。服务端有校验不等于前端可以不管
6. **"DB 有列/代码有分支但没人测"的地方藏 bug**：`DescribeShareType` 只判了 group，第三种 qrcode 静默落进 else 显示错文案，测试里恰好也没这条用例
7. **控件的默认高亮要和调用方传入的初值对账**：`activeShortcut` 写死 'today' 而调用方传"最近一周"，UI 说的和查的不是一回事，5 个页面一起错了很久
