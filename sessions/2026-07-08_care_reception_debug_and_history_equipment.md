# 2026-07-08 养护开单联调修复日：默认店铺 + 保存守卫 + 序列化/跟踪两处后端崩溃 + 上传链路 + 历史装备弹窗

按时间线整理。接 7-4 养护开单迁移，本场是用户在 DevTools/真机实测养护开单暴露的一串问题的联调修复，外加一个新功能（历史装备弹窗）。改动跨 `snowmeet_wechat_mini`（6 文件）+ `SnowmeetApi`（2 文件），**代码仓本地未提交**，用户按部署节奏处理；end-work 仅 push doc 仓。

## 1. 开单页默认店铺（shop_selector）

### 1.1 现象与根因

- 现象：开单页「当前店铺」空着，不选店铺养护按钮灰死；用户要求默认「万龙服务中心」
- 根因：[shop_selector.js](../../snowmeet_wechat_mini/components/shop_selector/shop_selector.js) 只要有任一店配了 beacon 就进蓝牙扫描，扫描期间**不选任何店**；30s 超时按 5-31 设计「不自动选，让用户手动滚 picker」只弹 toast 从不 triggerEvent；`_fallback`（staff 基地店→列表第一家）只在「全店没配 beacon/蓝牙打不开」错误分支触发。扫不到 beacon（办公室/模拟器/beacon 离线）= 永远没店

### 1.2 修复（3 处，均在 shop_selector.js）

- `scene='recept'`（开单入口专用）时**开扫 beacon 前先立即 `_fallback` 落默认店**并 triggerEvent，按钮马上可用；beacon 后续命中会覆盖默认选择
- `_resolveFallbackShop` 兜底链：staff.base_shop_id → **万龙服务中心**（新增 `DEFAULT_SHOP_NAME` 常量）→ 列表第一家
- 影响面收窄：其它 7 个用 shop-selector 的页面（报表/未归还/租赁列表等，scene 非 recept）默认「全部店铺」语义不变；万龙系互换逻辑保留

## 2. 未选装备类型不调 SaveCareRecept

- 需求原话：「养护添加装备的时候，如果没有选单板双板，不要调用 SaveCareRecept 接口。开单中每一件装备，要么是单板要么是双板」
- 实现：[recept_new.js](../../snowmeet_wechat_mini/pages/admin/reception/recept_new.js) `saveCareReceptOrder` 开头加守卫——`(order.cares||[]).some(c => !c.equipment)` 时跳过保存。这是调该接口的唯一入口，覆盖 添加装备/编辑/删除/找回后编辑 全部路径
- 行为：新点「添加装备」在选定类型前连草稿订单都不生成；有一件未选类型时其它装备编辑也暂缓落库（选定后下一次 syncCare 整单保存不丢数据）；去结算不受影响（组件 canCheckout 门控每件「已录入」含类型必选）

## 3. SaveCareRecept 响应序列化 NRE（Order.cs rentalStatus）

### 3.1 根因

- 500 堆栈：`Order.get_rentalStatus() Order.cs:376` NRE。该行写的是 `if (rentals == null && rentals.Count <= 0)` —— **`&&` 应为 `||`**，rentals 为 null 时右侧照样求值 `.Count`
- 触发链：`SaveCareRecept` 为防 TrackGraph 异常显式 `order.rentals = null`（CareController.cs:1007），保存完把同一 order 序列化返回时踩雷。**崩溃在序列化阶段，数据已落库**——前端看 500 但草稿实际已存

### 3.2 修复（2 处，Models/Order/Order.cs）

- `rentalStatus`：`&&` → `||`。附带修正隐藏语义错误：原 rentals 空列表会漏过守卫、`allSettled` 保持 true 返回「已完成」——养护单租赁状态本该 null
- `useCard`：`rentals.Any(...)` / `cares.Any(...)` 补 null 守卫（6-30 新加属性，全文件唯一一处既无 null 检查也无 try/catch 的集合解引用）
- 其余 rentals/cares/guarantys 解引用逐一核过：要么带 `!= null` 守卫要么在 try/catch 里

## 4. 上传图片 400 排查（跨两台服务器）+ uploadFilePromise 假成功修复

### 4.1 排查过程

- 现象：养护开单传照片，`UploadFileWithThumb` 全部 400（打 `snowmeet.wanlonghuaxue.com`）；手机旧版能传（用户据此判断服务器端可用）
- 本地 [UploadFileController.cs](../../SnowmeetApi/Controllers/UploadFileController.cs) 逐行核过：对合法 staff 会话唯一 400 出口是 `staff == null || title_level < 100`；`GetStaffBySessionKey` 内部自己 UrlDecode，编码链没问题
- 矛盾事实：**同一 sessionKey** 打 `mini.snowmeet.top` 的 `GetMemberAssetsByStaff`（同样 staff≥100 gated）成功，打 wanlonghuaxue 的上传 400。DNS 确认两域名是**两台服务器**（161.189.64.210 vs 60.8.110.78）
- 用户澄清：两域名跑同一个本地项目、部署在不同服务器 → 结论：两台**状态不一致**。两个具体嫌疑：① wanlonghuaxue 部署早于 6-14（`bb210a9` 给 `GetStaffBySessionKey` 加的 openid 兜底——7 月初会员合并测试后本账号 session 可能正依赖它）② 各自的 config.sqlServer（gitignored 服务器本地文件）指向不同库
- 手机旧版能传的解释：6-12 域名统一前的旧正式包登录域名就是 wanlonghuaxue，session 落在那台可查的库/可解析的链路上
- 直连生产库验证被 auto-mode classifier 拦（合理）；线上探测被用户打断（用户指示只看本地代码）

### 4.2 前端确定 bug：uploadFilePromise 把 HTTP 400 当成功

- `wx.uploadFile` 的 success 对**任何 HTTP 状态码**都触发，原代码 `resolve(JSON.parse(res.data))` 把 400 的 ProblemDetails 错误体当 UploadFile resolve → `uploaded.id` = undefined → 第二跳缩略图请求 URL 只剩 sessionKey（截图圈出的请求形态）→ 再 400 → 表单出现 `https://...undefined` 假图片框 → `image_id: undefined` 垃圾 careImage 混进 SaveCareRecept payload
- 修复（[data.js](../../snowmeet_wechat_mini/utils/data.js) uploadFilePromise）：success 里非 2xx reject；`fail` 回调原 `resolve(JSON.parse(res))`（对对象 JSON.parse 必抛）改 reject。修完 care_recept_form 既有 catch 正确弹「照片上传失败」并清占位

### 4.3 上传域名暂切 mini.snowmeet.top（用户拍板）

- 3 处（都标「2026-07-08 暂时」注释）：[data.js](../../snowmeet_wechat_mini/utils/data.js) uploadFilePromise 上传 URL（全局唯一上传出口）、[care_recept_form.js](../../snowmeet_wechat_mini/components/reception/care_recept_form/care_recept_form.js) `UPLOAD_HOST`、[care_order_detail.js](../../snowmeet_wechat_mini/pages/admin/care/care_order_detail/care_order_detail.js) `IMG_HOST`（上传落谁磁盘就从谁显示）
- 注意：真机需在公众平台把 mini.snowmeet.top 加进 **uploadFile 合法域名**；旧页面（care_recept/retail_recept/旧 order_detail）显示前缀没动，过渡期从旧页面新传的照片在旧页面预览不出

## 5. SaveCareRecept 500：EF 跟踪撞键（Remove 沿导航图遍历）

### 5.1 根因（用户贴的完整堆栈钉死）

- `InvalidOperationException: The instance of entity type 'Care' cannot be tracked...` at `_db.careImage.Remove(oriImage)`（CareController.cs:1095）
- 连锁链：前端保存回填用本地 careImages 整体覆盖（id 恒 0）→ 每次保存 `_db.Update(order)` 把 id=0 careImage 当新行再插一遍 + 跟踪 posted Care 25631 → 删旧行逻辑 `Remove(oriImage)` **沿导航图遍历**：oriImage.care 经 Include fixup 指向 AsNoTracking 加载的 Care 25631 实例 → 附加时与已跟踪的同 id posted Care 撞键

### 5.2 修复（前后端各一）

- 后端 [CareController.cs](../../SnowmeetApi/Controllers/CareController.cs)：删 care/careImage 的三处 `Remove()` 全改 `_db.Entry(x).State = EntityState.Deleted`（只附加单实体、不遍历导航图）
- 前端 [recept_new.js](../../snowmeet_wechat_mini/pages/admin/reception/recept_new.js) `saveCareReceptOrder` 响应回填：保留本地 url/thumb 展示字段、按 `image_id` 匹配回填服务端生成的 `careImage.id`/`care_id` → 下次保存发真实 id，走更新不再"插新删旧"
- 不用手工清库：测试期积累的重复 care_image 行会在部署后第一次成功保存时被删旧行逻辑自动清掉

## 6. 装备卡片展开态：录入中永不自动折叠（两轮迭代）

### 6.1 第一轮：选完类型被折叠

- 根因：卡片展开态按 key 记忆，key 规则 `id>0 ? 'c'+id : 't'+timeStamp`。选完类型触发第一次真正落库（§2 守卫放行），回填后 care.id 从 0 变真实 id → key 变 → 展开记录丢失 → 默认规则 `care.id===0 && !ev.ok` 判折叠
- 修：默认规则改「未录入完整就展开」（不看 id）

### 6.2 第二轮（用户拍板终态）：不论选什么填什么都不自动折叠

- 用户原话：「填写装备信息，不论选择任何选项，填写任何信息，当前装备信息，均不应该自动折叠」
- 实现（[care_recept_form.js](../../snowmeet_wechat_mini/components/reception/care_recept_form/care_recept_form.js) `_refreshCares`）：无手动记录时「未录入完整」默认展开**并把展开态写入 expandedMap**——录入过程任何字段变化（含补完最后一个缺项、ev.ok 翻真）都读到记住的展开态，唯一收起方式是手动点卡片头部；找回中断单时已完整装备默认收起、未完整默认展开
- 顺手加固 expandedMap 兜底分支引用回写

## 7. 历史装备弹窗（新功能，前后端）

需求：选双板/单板后，若顾客是会员且之前养护过同类型装备 → 弹 modal 列出（按下单时间倒序）供店员直接选择；列表里没有的可在 modal 里直接填品牌和长度；没有记录则不弹、页面直填。

### 7.1 后端

- 新接口 [CareController.GetMemberCaredEquipments](../../SnowmeetApi/Controllers/CareController.cs)（GET，staff≥100）：`care.valid=1 + equipment 匹配 + care.order.member_id = memberId + brand 非空`，按 create_date 倒序，**brand+scale 去重**（同板多次养护只出一条，取最近时间），返 brand/scale/boot_length/serials/year/with_pole/last_care_date

### 7.2 前端

- [data.js](../../snowmeet_wechat_mini/utils/data.js) 加 `getMemberCaredEquipmentsPromise`
- [care_recept_form](../../snowmeet_wechat_mini/components/reception/care_recept_form/care_recept_form.js)：`onEquipTap` 重构（重复点同类型早退不弹不保存）→ `_maybeShowHistory`（散客不查；异步返回校验类型没被中途切换；查询失败静默降级页面填写；空列表不弹）→ 底部 van-popup：列表行「品牌+长度+上次养护日期」点选带入 brand/scale；下半区「不在列表里？直接填写新装备」品牌 picker（同类型品牌字典）+ 长度输入 + 确认（两项必填）；「跳过」回页面照常填
- wxml 弹层 + wxss `history-*` 样式（复用 amount-modal 按钮/kv-cell 既有类）

## 关键改动文件

| 仓库 | 文件 | 改动 |
|---|---|---|
| mini | `components/shop_selector/shop_selector.js` | recept 场景开扫前落默认店；fallback 链加万龙服务中心 |
| mini | `pages/admin/reception/recept_new.js` | 未选类型跳过 SaveCareRecept；careImage 按 image_id 回填服务端 id |
| mini | `utils/data.js` | uploadFilePromise 非 2xx/fail reject + 上传域名暂切 mini；新增 getMemberCaredEquipmentsPromise |
| mini | `components/reception/care_recept_form/{js,wxml,wxss}` | UPLOAD_HOST 切 mini；展开态永不自动折叠；历史装备弹窗（数据/handler/弹层/样式） |
| mini | `pages/admin/care/care_order_detail/care_order_detail.js` | IMG_HOST 暂切 mini |
| api | `Models/Order/Order.cs` | rentalStatus `&&`→`||` NRE 修复；useCard null 守卫 |
| api | `Controllers/CareController.cs` | 删行改 Entry().State=Deleted（防导航图撞键）；新增 GetMemberCaredEquipments |

## 学到的小知识

1. **EF `Remove()`/`Add()` 沿导航图遍历附加实体**：AsNoTracking + Include fixup 的实体带着反向导航，Remove 会把导航指向的实体一并附加进跟踪器，与 `_db.Update(order)` 已跟踪的同 id 实体撞键。删除单实体用 `_db.Entry(x).State = EntityState.Deleted`（不遍历导航）
2. **`wx.uploadFile` 的 success 对任何 HTTP 状态码都触发**：不判 `res.statusCode` 就 resolve 会把错误体当成功结果，下游拿 undefined 字段继续"假成功"；fail 回调里 `JSON.parse(res)`（res 是对象）必抛
3. **保存回填"整体用本地对象覆盖服务端返回"会让子行 id 永远为 0**：后端每次保存插新行删旧行（数据抖动），还引爆撞键。正确做法：保留本地展示字段、按业务键（image_id）回填服务端生成的主键
4. **`if (a == null && a.Count <= 0)` 是典型手滑**：`&&` 让 null 时右侧照样求值。这类守卫必须 `||`
5. **两域名两台服务器**：mini.snowmeet.top=161.189.64.210 / snowmeet.wanlonghuaxue.com=60.8.110.78，同一项目各自部署、config.sqlServer 各自本地——"同一份代码"不等于"同一状态"，同 sessionKey 两台鉴权结果可以不同
6. **组件 UI 状态按 key 记忆时警惕 key 漂移**：id 0→真实 id 的落库瞬间 key 变化会丢状态；要么稳定 key，要么把"默认态"落成显式记录（本场选后者）
7. **微信小程序上传域名要单独在公众平台登记 uploadFile 合法域名**（与 request 域名分开）
