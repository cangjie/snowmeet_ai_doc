# 2026-07-19 mat_expire 收尾打磨 + 养护列表店铺筛选 bug 修复：staff 闸门、每批次推送、OCR 三期扫描、shop_selector 时序漏洞

上半场接续 7-15 刚落地的食材过期提醒（fnb mat_expire），用户逐字段追加需求做了多轮小步迭代打磨；用户说「食材管理暂告一段落」后切回养护系统，第一件事是排查养护订单列表的店铺筛选 bug。改动落在 `SnowmeetApi`（后端）+ `snowmeet_wechat_mini/components/shop_selector`（前端），全部本地未提交。

## 1. mat_expire：员工关联 + 进入闸门

用户需求原话：「msa里边，增加一个type 为wecom 的记录，num就是企业微信号；增加食材过期记录，需要增加个字段，记录添加人的staff_id；staff_id通过oauth得到的信息关联获取；发送临期或者过期通知的列表，填写的是企业微信号。」

- `MemberSocialAccount.TYPE_WECOM = "wecom"` 常量
- `FnbMaterialBatch` 加 `staff_id`（int?，可空——关联不上不阻断）
- 关联链路复用现成的 `StaffController.GetStaffBySocialNum(wecomUserId, "wecom")`：企微 UserId → `member_social_account(type=wecom)` → `member_id` → `social_account_for_job` → `staff_social_account`（时间窗，取当前日期落在哪个有效绑定段）→ `staff`
- `SaveBatch` 新增批次时用当次鉴权已解析出的 staff 写 `staff_id`（不重复查）

用户随后追加：「进入这个h5，要检查当前用户是否是正常的staff，如果不是，则不能进入系统。」

- **进入闸门**：`OAuthLogin` 换到企微 UserId 后，先用 `_resolveStaffId` 校验能否关联到在职 staff（`staff.valid==1`），关联不到直接返回「仅限在职员工使用，请联系管理员开通」，**不发 session**
- **每请求闸门**：新增 `_requireStaff(sessionKey)` helper（session 有效 + 当前仍关联在职 staff），8 个业务接口（GetBatches/SaveBatch/DisposeBatch/DeleteBatch/GenBatchNo/UploadPhoto/GetImages/PushExpireAlert）鉴权统一升级，离职员工手里的旧 session 立即失效，不用等 30 天过期
- 前端 `mat.js`：登录被拒从 toast 一闪改成整页拒绝提示（`showBlockHint`），避免用户以为是网络问题反复重试

## 2. mat_expire：列表页去重按钮

用户报告顶栏右上角「+」和右下角 FAB 功能完全重复（都跳 `new.html`），删掉顶栏那个，顺手清了 `.hbtn` 死样式。

## 3. mat_expire：生产日期/保质期→到期日联动 bug（本轮耗时最长的排查）

### 3.1 第一轮：`expireManual` 永久锁

用户报告「填写了生产日期和保质期，到期日期应该联动但没有」。

**根因**：旧代码 `expireManual` 布尔开关，到期日期输入框只要被 `change` 事件碰过一次（哪怕 Safari 分段日期编辑器点一下、方向键动一下都会触发）就永久置真，之后 `autoExpire()` 开头直接 `return`，联动**永久禁用且无法恢复**。

**修复**：改成「动源（生产日期/保质期/单位）即重算」的规则——手动改过的到期日只保留到下次再动这些源字段为止。同时给两个日期输入补 `oninput`（不只 `onchange`），分段编辑时立即响应。

单测（node 模拟页面真实 DOM + 内联脚本）覆盖：先保质期后生产日期联动、手改后动源重算覆盖、单位切月联动、生产日期空不覆盖已填到期日 —— 4 场景全过。

### 3.2 第二轮：编辑页同样不联动

用户反馈「编辑界面也是这个样子」。

**根因**：存量批次 `produce_date` 常年为空（旧版页面创建时没有默认值），而 Safari 对 `<input type="date">` 空值会显示成**浅色的今天日期**（视觉上像有值，实际值是空），用户以为已填、改保质期时没有推算基准。

**修复**：
- 新建模式：生产日期默认真实落值为今天（深色真值，消除浅色假象）
- 编辑模式回填：`produce_date` 为空但有保质期时，按 `到期日 − 保质期` 反推出生产日期并真实落值

### 3.3 第三轮：仍不联动 → 确认是部署滞后

用户第三次反馈仍不联动。排查方向：让用户在编辑页看生产日期是深色（新版已生效）还是浅色（仍是旧版）。结论是**这批改动全在本地工作区，从未 publish**，用户测的是服务器上上一版部署。

### 3.4 交互收敛：改动生产日期/保质期一定重算，改到期日绝不反向更新

用户最终拍板固化成正式规则：「任何时候、任何场景，修改了生产日期或保质期，都要自动更新到期日期；但手动修改到期日期不需要更新保质期或生产日期。」

逐场景核对确认现有实现已完全满足（手输/扫描/同名默认值带出/单位切换/编辑回填后再改——全部触发重算；手改到期日/扫描到期日——都不反向更新生产日期或保质期），无需改代码，单测全绿。

## 4. mat_expire：同名食材带默认值

用户需求：「如果输入同名称的食材，从之前的记录除了读取保质期作为默认之外，还需要读取预警提前的天数作为默认。」

- 新建时输入名称，防抖 600ms 后按名称查同名食材的**最近一条批次**（id 最大），带出其保质期（数值+单位）和预警天数
- 规则：只覆盖「空白或此前自动带出」的值——用户手输过的字段，同名匹配不会覆盖；改名称换食材，自动带出的值跟着换成新食材记录
- toast 合并提示「已按上次记录默认：保质期 5 天 · 预警提前 2 天」

## 5. mat_expire：摄像头实时 OCR 扫描（三期迭代）

用户最初需求：「可否通过OCR实时识别食材的名称、生产日期、保质期或者到期日期？」进一步明确：「我不需要拍照上传，仅仅是打开相机后，实时识别。类似于扫二维码一样的，用摄像头对准食材的包装。」

### 5.1 期一：名称扫描

- 前端：`getUserMedia({video:{facingMode:'environment'}})` 全屏取景（暗角遮罩取景框），canvas 每 1.3s 抓一帧（压到 1000px JPEG，质量 0.7），30s 无果自动停帧省费用，帧不落盘不存照片
- 后端新接口 `FnbMaterial/OcrScanName`（wecom staff 鉴权）：复用现成的腾讯云 `GeneralBasicOCR`（凭据同项目里已有的 `OcrController`），`IsNameCandidate` 过滤规则：长度 2-20、排除纯数字/条码/喷码日期、排除净含量/规格、排除含「生产日期/保质期/配料/贮存/执行标准/生产许可/地址/电话/营养成分/…」等说明词的行；候选按字高降序取前 5（包装上名称通常字最大）

用户追加：「识别出来的结果，点击一次填写上即可。识别名称可以识别出多个词组，多选组词回填。」

- 名称候选**多选**：点击 chip 变蓝带序号 ①②③，按点击顺序拼接成名称（不是候选顺序）；再点已选词取消，序号自动重排；底部实时出确认按钮「填入：白玉原香豆浆」；有任何选择即暂停抓帧（候选固定不跳动 + 省 OCR 调用），全取消恢复识别

用真实豆浆包装图验证：「白玉」「原香豆浆」「仅有水和大豆」三候选正确识别，多选拼接单测覆盖顺序拼接与换序取消场景。

### 5.2 期二：生产日期扫描

用户需求：「生产日期也需要可以识别，需要支持中英文的各种日期格式。」

新增 `ExtractDates`（后端静态方法，供单测直接调）从 OCR 文本行提取日期候选、归一化 `yyyy-MM-dd` 去重：

| 格式 | 正则要点 |
|---|---|
| 中文年月日 | `2026年7月16日`，「日」可省 |
| 分隔符 | `2026-07-16` / `2026/7/16` / `2026.07.16` |
| 8 位喷码 | `20260716`（含带班次时间的 `20260703A 16:18` 实拍样式） |
| 6 位喷码 | `260703` → 2026-07-03（首位限定 `2\d` 降低条码误匹配） |
| 日月年 | `03-08-2026` / `17/08/2026`（>12 的一侧判定为日，都 ≤12 时按顺序取前段为日） |
| 英文月份 | `16 JUL 2026` / `JUL 16, 2026` / `16JUL26` |

防误报：年份限 2015-2039、月日合法性校验（`new DateTime(y,mo,d)` try/catch）；用条码、时间 `16:18`、净含量、电话号码验证不误报。

用户加了「生产日期」入口按钮（框旁「扫描」），复用同一扫描层。

### 5.3 期三：到期日期 + 保质期扫描

用户需求（到期日期）：「首先识别日期，如果存在有包括但不限于"保质期 yyyy-mm-dd""请在yyyy-mm-dd前使用""yyyy-dd-mm 到期"则首选这个日期，如果没有，再列出界面上所有识别出来的日期。」

- `ExtractDates` 返回值扩展为 `(all, expire)` 元组：逐行判定是否含到期锚词（`此日期前/前食用/前使用/前饮用/保质期/到期/有效期/赏味/EXP/BEST BEFORE/USE BY/BBE`），命中则该行提取出的日期额外收进 `expire` 集合
- 前端 `expire` 模式：`lastExpireDates` 非空只显示锚词日期，取景提示变「已识别到期标注，点选 📅 日期」；无锚词命中回落显示全部日期

用户需求（保质期）：「识别的文本中出现 xx天 xx个月，就可以认为是保质期。需要可以支持阿拉伯数字和中文。」

- 新增 `ExtractShelfLives`：先用正则把行内日期串替换成空格（防「2026年7月3日」被误判成「7个月」「3天」），再匹配 `(\d{1,3})\s*(个月|月|天|日|年)`（阿拉伯数字）和 `([一二三四五六七八九十百两零]+)\s*(个月|月|天|日|年)`（中文数字，`_cnNumParse` 手写百以内解析，支持「十二」「一百八十」「两年」）
- 归一化：「日」→天，「年」→月×12；数值范围校验（天 1-999、月 1-99）

用户最后收敛交互：「扫描 生产日期 保质期 到期日期 时，和扫描名称应该不一样，识别出来的结果，点击一次填写上即可…但是其他的单选即可。」

- date/expire/shelf 三种模式改为**点 chip 即填即关**（不经确认按钮），只有名称扫描保留多选+确认流程；`toggleDate`/`toggleShelf` 按 `scanMode` 分流，`all` 模式仍走原多选逻辑
- 单测全程用 node 提取内联脚本 + stub DOM/MAT 的方式跑（`test_auto_expire.js`），最终 38 场景全过；日期/保质期正则组另跑独立单测（`test_extract_dates.js`）覆盖 16+11+8 个真实样本

## 6. mat_expire：推送格式 + PushExpireAlert 去 session 校验

用户问「如何发送提醒」后确认走接口直接调，随即要求：「PushExpireAlert 这个接口不需要验证sessionKey」——为将来 crontab 定时直接 curl 铺路。签名改为 `(touser=null, sessionKey=null)` 两个都可选，`sessionKey` 传了仅用于日志记 `send_userid`，滥用兜底靠既有的当天去重（同批次一天只成功推一次）。

用户进一步要求：「发送过期的提示消息，应该是一个批次，发送一个图文的提示消息。图片用这个批次上传的第一张图片即可。如果没有上传图片，就随便写个图片的url即可。」

- 原「一条汇总消息」改成**每批次一条独立图文**：标题 `【状态】食材名`、摘要 `批次号 · 到期日 · 还剩/已逾期N天`、图片取该批次 `image_ids` 第一个 id 对应的 `upload_file.file_path_name`（批量查一次），无照片用站内占位图 `images/logo.png`
- 单批失败不阻断其余批次，`fnb_material_alert_log` 逐批次记自己的 `msgid`/`success`/`err_msg`（比之前共享一个 msgid 追溯性更好）

用户又要求：「点击后，应该跳转到该批次的详情页。」

- `url` 从列表页改为 `new.html?id={批次id}`
- 顺手修了 `mat.js` 的 `gotoOAuth` 重定向丢查询参数的坑：若店长点消息时 session 恰好过期，OAuth 转一圈回来 `?id=5` 会丢、落到空白新建页；改为带上 `location.search` 一起重定向

用户测试反馈「编辑好了 config.fnbAlertReceivers 但是运行接口没有任何反应」——排查后判断大概率是当天去重命中所有候选批次（返回 `count:0`），但没有最终定性，遗留到下次 publish 后带诊断信息重新验证。

## 7. mat_expire：详情页操作区 + 列表卡片可点

用户要求把列表动作面板里「标记用完/标记报废/删除」这三个操作也加到详情页：

- 详情页新增「操作」区块，2×2 网格：标记用完（浅绿）/标记报废（琥珀）/返回列表（中性描边）/删除（浅红），与列表页同接口同确认文案；已处理批次只留返回/删除
- 首版按钮挤成一团（一轮 css 改动忘了 bump 版本号，用户手机加载的是缓存旧样式），加了 `?v=260716x` 系列版本号追随每次 css/js 改动递增

用户又要求「列表中，点击各个条目，应该可以直接进入到详情页」——卡片改整卡 `bindtap` 跳详情，三点按钮 `stopPropagation` 防止误触跳页仍可开动作面板。

## 8. mat_expire：`valid` 列 int→bit 迁移

用户告知已把生产库 `fnb_material_batch.valid` 从 int 改成 bit。同步 `Models/Fnb/FnbMaterialBatch.cs` 的 `int valid` → `bool valid`，控制器里 7 处 `b.valid == 1` / `= 1` / `= 0` 判断改成布尔用法（`b.valid` / `= true` / `= false`），编译通过。

## 9. 养护订单列表店铺筛选 bug：`shop_selector` 自动定位覆盖手动选择

用户报告：「养护订单查询页，店铺选择必须选全部店铺才能查到"万龙服务中心"的订单，直接选择"万龙服务中心"则目前是查询不到任何订单的。」

### 9.1 排查过程

1. 先怀疑前端把空字符串当 `shop` 传给后端，导致过滤条件 `o.shop.Trim().Equals("")` 恒假——但推演后发现这个假设会让「全部店铺」也返回 0（矛盾），排除
2. 直接连生产库核实：`order.shop` 对养护订单的存量分布——`万龙服务中心`13079 / `万龙`（孤儿值，无对应 `shop_list` 记录）1323 / `怀北`424 / `南山`315 / `渔阳`169 / `崇礼旗舰店`58 / `万龙体验中心`34。确认 DB 数据本身干净，没有脏空格等问题
3. 查 `shop_list` 表（`[Table("shop_list")]`，不是 `shop`）：`万龙服务中心`(id=1, `care=1`) / `万龙体验中心`(id=10, **`care=0`**，这家店不开展养护业务)
4. 对生产库**直接模拟后端 `GetCommonOrders` 的确切过滤 SQL**，用同一日期区间（2026-07-01~07-19）分别跑「无 shop 过滤」vs「`shop='万龙服务中心'`」——**两者都返回 18 单，完全一致**，证明后端 LINQ 过滤逻辑和数据库层面完全正常，问题不在这一层
5. 转向 `shop_selector.js` 组件：发现它在**任何页面**`ready()` 时都会自动起蓝牙 beacon 扫描（不判断 `scene` 是否为 `'recept'`），扫描最长持续 30 秒；用户手动从下拉框选店触发的 `selectChanged` 不会停止这个后台扫描

### 9.2 根因

时序漏洞：
1. 用户手动选「万龙服务中心」→ `this.data.shop` 短暂正确
2. 后台仍在跑的 beacon 扫描随后异步命中 → `_finalizeIfHit()` → `_applySelectedShop(picked, -1)`，**静默覆盖**刚才的手动选择
3. `_applySelectedShop` 里有条「万龙互换逻辑」（沿用旧版设计，本意是让物理定位模糊时按店员自己配置的店落地）：只要扫描命中的店名含「万龙」，且**当前登录店员自己的 `staff.shop.name` 也含「万龙」**，就强制把结果换成**店员自己的基地店**，而非扫描实际命中的那家
4. 若这个查询页面的登录账号（店长/管理员）的 `base_shop_id` 恰好挂在「万龙体验中心」（`care=0`，不做养护业务），选择就被覆盖成一个永远查不到养护订单的店
5. 点「查询」时实际发出的过滤条件变成 `shop=万龙体验中心`，自然返回空

### 9.3 修复

[`components/shop_selector/shop_selector.js`](../snowmeet_wechat_mini/components/shop_selector/shop_selector.js) 的 `selectChanged`（用户手动选择的唯一入口）顶部加 `that._stopScan()`：

```js
selectChanged: function (e) {
  var that = this
  that._stopScan()  // 用户手动选择必须优先，停掉可能仍在跑的自动定位扫描
  that.setData({ currentSelectedIndex: e.detail.value })
  ...
```

`_stopScan()` 本身写得很防御（handler/timer 判空 + try/catch 包 wx API 调用），扫描还没开始或已结束时调用也安全；`_finalizeIfHit`/`_onDeviceFound`/`_onBeaconUpdate` 各自开头都有 `if (!this._scanActive) return` 守卫，就算异步回调在 `_stopScan()` 之后才触发也会被拦下，不会再次覆盖。

### 9.4 影响范围

`shop_selector` 是共享组件，被 10+ 个页面引用（`grep '<shop-selector'` 结果）：养护/零售/租赁订单列表、未归还列表、打印任务、租赁商品/套餐设置、雪票报表、接待流程（`scene='recept'`）等。一次修复同时覆盖所有引用页面，不用逐页改；纯前端，无需后端配合。

## 关键改动文件

| 文件 | 改动 |
|---|---|
| [`Models/Member/MemberSocialAccount.cs`](../SnowmeetApi/Models/Member/MemberSocialAccount.cs) | 加 `TYPE_WECOM` 常量 |
| [`Models/Fnb/FnbMaterialBatch.cs`](../SnowmeetApi/Models/Fnb/FnbMaterialBatch.cs) | 加 `staff_id`；`valid` int→bool |
| [`Controllers/Fnb/FnbMaterialController.cs`](../SnowmeetApi/Controllers/Fnb/FnbMaterialController.cs) | `_resolveStaffId`/`_requireStaff` 闸门；新接口 `OcrScanName` + `ExtractDates`/`ExtractShelfLives`/`IsNameCandidate`/`_hasExpireHint`/`_cnNumParse`；每批次独立推送；`PushExpireAlert` 签名去 session 强制校验；valid 布尔化 7 处 |
| [`wwwroot/fnb/mat_expire/new.html`](../SnowmeetApi/wwwroot/fnb/mat_expire/new.html) | 联动 bug 三轮修复；同名默认值；扫描层三模式（all/date/expire/shelf）+ 多选/单选点击即填；详情页操作区 |
| [`wwwroot/fnb/mat_expire/index.html`](../SnowmeetApi/wwwroot/fnb/mat_expire/index.html) | 删重复按钮；卡片整卡可点跳详情 |
| [`wwwroot/fnb/mat_expire/mat.js`](../SnowmeetApi/wwwroot/fnb/mat_expire/mat.js) | 登录拒绝整页提示；OAuth 重定向带查询参数 |
| [`wwwroot/fnb/mat_expire/mat.css`](../SnowmeetApi/wwwroot/fnb/mat_expire/mat.css) | 扫描层遮罩/候选 chip/操作区网格样式 |
| [`components/shop_selector/shop_selector.js`](../snowmeet_wechat_mini/components/shop_selector/shop_selector.js) | `selectChanged` 加 `_stopScan()` |
| [`sql/2026-07-16_fnb_material_batch_add_staff_id.sql`](sql/2026-07-16_fnb_material_batch_add_staff_id.sql) | 新建：staff_id DDL 备忘 + wecom MSA 录入模板 |

## 学到的小知识

1. **date input 空值在 Safari 显示成浅色假象**：用户以为「明明有值」，实际值是空字符串，任何依赖该值的联动/校验逻辑读不到东西。排查这类「看着有值实际没有」的 bug，先让用户区分输入框文字是深色（真值）还是浅色（占位）
2. **共享 UI 组件的隐藏副作用会跨页面复现同一个 bug**：`shop_selector` 被 10+ 个页面引用，这类组件改动前先 grep 全部引用点评估影响面；反过来，改好一次也同时修复了所有引用页面，不用逐个 review
3. **排查"代码/数据看着都对但结果不对"，优先在数据库层面复现后端的精确过滤条件**：用「有筛选 vs 无筛选」两个查询对比行数，比逐行读 C# LINQ 或猜前端传参更快定位问题到底在哪一层（本例证明后端和 DB 完全无辜，省下了大量误查后端的时间）
4. **异步操作没有互斥保护会产生"后来者覆盖"的隐蔽 bug**：beacon 扫描是异步的且耗时可达 30 秒，用户手动操作后如果不显式停止后台任务，稍后异步结果可能覆盖用户的显式意图。这类组件设计要明确「用户主动操作」和「自动检测」谁该赢，并在代码里落实（本例：手动选择必须停掉自动扫描）
5. **给 chip/候选类交互设计要按"字段是否单值"决定确认流程**：单值字段（日期、保质期）点一次就该直接生效关闭；只有可能多值拼接的字段（名称）才需要多选+确认按钮的两段式交互，混用会让单值字段的操作多余一步
6. **正则提取类需求要主动加「反例」防误报测试**：日期/保质期提取如果只测正例，很容易被"生产日期：2026年7月3日"这类行误判出多个假保质期（7个月、3天），提取前先把已识别出的日期串从原文里挖掉再匹配保质期是关键防线
