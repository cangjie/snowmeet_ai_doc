# 2026-07-21 mat_expire 小程序移植 + 食材标签打印：把食材过期提醒搬进小程序，并给它加上复用养护标签机制的打印功能

按时间线整理。本场会话接续 7-15/7-19 的「食材过期提醒」（此前只有企微 H5 版本），先把它整套原生移植进微信小程序，再给它加标签打印能力（明确要求尽量复用雪板养护标签打印的机制），中间夹了一次纯问答的佳博打印机标签纸规格调研，收尾前又做了两轮小追加（标签尺寸放大、打印份数可配置）以及顺手调优了养护标签本身的二维码。全部代码改动落在 `SnowmeetApi` + `snowmeet_wechat_mini`，本次会话未提交。

## 1. mat_expire H5 → 小程序移植

### 1.1 背景与决策

- 此前「食材过期提醒」只有企微内 H5 版本（`wwwroot/fnb/mat_expire/`），本次给微信小程序做一套原生实现，**两套并存**，H5 服务企微场景、小程序服务日常员工操作，互不替代
- Plan Mode 下完成研究（plan 文件 `~/.claude/plans/h5-peaceful-duckling.md`），关键决策：
  - OCR 扫描用**实时连续扫描**（`<camera>` 组件持续抓帧），不是拍照后单张识别
  - 功能开放给**全体在职店员**，不做 title_level 分级门槛
- 9 个任务全部完成，`node --check`/WXML 标签平衡/JSON 校验全过

### 1.2 后端改动（唯一改动，最小化）

- [`FnbMaterialController.cs`](../SnowmeetApi/Controllers/Fnb/FnbMaterialController.cs) 的 `_requireStaff` 加一条 fallback 分支：企微 session 查不到时改走 `Util.GetStaffBySessionKey(_db, sessionKey, "wechat_mini_openid")`
- 对企微 H5 老用户零行为变化，同时让全部 8 个业务接口（GetBatches/SaveBatch/DisposeBatch/DeleteBatch/GenBatchNo/UploadPhoto/GetImages/OcrScanName）都能接受小程序会话

### 1.3 前端新增

- `utils/matExpire.js`：`fmtDate`/`addDays`/`daysBetween`/`deriveStatus(batch, today)`，状态口径照抄 H5（已处理>已过期>今日>临期(≤today+warn_days)>正常），**必须用服务端 `today` 字符串**，不能用设备本地日期
- `utils/data.js` 新增 9 个 wrapper（`getMatExpireBatchesPromise`/`saveMatExpireBatchPromise`/`disposeMatExpireBatchPromise`/`deleteMatExpireBatchPromise`/`genMatExpireBatchNoPromise`/`getMatExpireImagesPromise`/`ocrScanMatExpirePromise`/`uploadMatExpirePhotoPromise`/`getAllPrintersPromise`）
- `components/fnb/ocr_scan_layer/`（新组件，4 文件）：`<camera resolution="medium">` + `<cover-view>` 覆盖 UI；`wx.createCameraContext(this)` 组件级作用域；`CAPTURE_INTERVAL_MS=1500` 定时 `takePhoto()` 抓帧调后端 `FnbMaterial/OcrScanName`；与 H5 版用 `getUserMedia`+canvas 抓帧是异构实现，但共用同一套后端 OCR 识别逻辑；`bind:fill`/`bind:confirm`/`bind:close` 三个事件契约
- `pages/admin/fnb/mat_expire_list/`（4 文件）：状态筛选 chip（计数按全量未过滤列表算）+ 搜索 + 卡片列表 + FAB + 底部操作面板
- `pages/admin/fnb/mat_expire_detail/`（4 文件）：创建/编辑/详情复用同一页，全部字段自动计算逻辑照搬 H5，内嵌 `ocr-scan-layer`
- `pages/admin/admin.js`/`admin.wxml`：「餐饮」分组新增导航项「【餐饮】食材过期提醒」
- `app.json`：注册两个新页面

## 2. 食材标签打印（复用养护标签机制）

### 2.1 需求与研究中断

用户原话：「打印的内容是当前批次…附带个二维码，微信扫码后进入该批次的小程序详情页…列表页/详情页增加标签打印按钮…标签尺寸为30\*20…**尽量和雪板标签打印复用**」。研究阶段用户一度喊「暂停下」，正在跑的 Explore 后台 agent 被强制终止，`SendMessage` 尝试恢复收到明确「已被用户停止、不可恢复」提示；用户确认「所有的任务都重新来吧」后，按同一需求重新调研并整体重做。

### 2.2 复用策略

调研结论：`utils/ble_label_printer/tsc.js`（TSPL 命令生成、二维码由打印机固件原生渲染）+ `utils/util.js` 的通用蓝牙 Promise 是完全通用、零业务耦合的底层库，可以直接原样复用；但 `components/care/print_care_label.js` 这个组件本身（属性定义/`getCommand()` 排版逻辑/自动选打印机业务规则）深度耦合养护订单数据结构，没法直接改造复用。于是新写一个同级组件 `components/fnb/print_food_label/`，只重写两小段业务特有逻辑：

1. **「搜到就连、连上第一台就用」重试循环**——这段逻辑在 `print_care_label.js:178-182` 里其实是**注释掉的死代码**，从未真正启用；这次是把它真正写活（`_tryConnect()` 递归尝试直到成功或候选列表耗尽）
2. **全新的、小得多的标签排版**（`getCommand()`）

`print_care_label.js` 本身保持完全不动，不承担任何回归风险。

### 2.3 后端：`GetAllPrinters`

[`PrinterController.cs`](../SnowmeetApi/Controllers/PrinterController.cs) 新增只读接口，全表查询打印机（不按 shop 过滤——`FnbMaterialBatch` 本身不分店，BLE 扫描的物理距离已经是唯一有效的筛选边界），包 `ApiResult` 信封返回。与已有 `GetPrinters`（未包信封，两个存量调用方靠裸数组返回，不可改）、`GetPrinterByScene`（按店过滤，服务养护流程）三个接口并存但语义不同，明确不合并。

### 2.4 DPI 与二维码尺寸取舍

用 AskUserQuestion 确认用户不掌握真机打印机的实际 DPI 后，拍板按 **200dpi 保守假设**设计（1mm=8dots）。理由：DPI 是打印机硬件固定属性，TSPL 所有坐标（含二维码 `cellWidth`）单位都是「点」，猜错方向的后果不对称——按更低 DPI 假设设计，真机若实际更高只会让内容偏小，不会出边；反过来设计，真机分辨率若比假设低，坐标会被物理放大、二维码可能直接超出标签边缘被裁。`cellWidth` 沿用养护标签当时已在用的密度值 3（同一次论证过程中一度先估了偏保守的 `cellWidth=2`，推算实际尺寸后自我修正为 3，与已验证过的养护标签同密度）。

### 2.5 标签尺寸迭代：30×20mm → 60×40mm

初版 30×20mm 布局实施完成后，用户追加需求：「食材过期提醒的标签尺寸，改为 60\*40，字体，二维码随之放大」。改动是纯粹的等比例 ×2：

- 二维码 `cellWidth` 3→6
- 中文字体 `TSS16.BF2`(16×16dots)→`TSS32.BF2`(32×32dots)，与养护标签默认字体同规格
- 数字英文字体 code `1`(8×12dots)→code `3`(16×24dots)
- 所有坐标 ×2

字符数上限设计不变，只是单字符/单模块的物理尺寸翻倍，更易读、更好扫。

### 2.6 内容与布局

标签仅打印三个字段 + 二维码：

- 名称（截断至 5 字符，用 `TSS32.BF2` 中文字体）
- 批次号（截断至 11 字符，用 ANK 字体 code `3`）
- 到期日期（取前 10 字符 `yyyy-MM-dd`，同上字体）
- 二维码：`https://mini.snowmeet.top/mapp/fnb/mat_detail?id={batchId}`，`setQrcode(218, 36, "L", 6, "M", url)`

### 2.7 打印份数（用户追加需求）

用户要求：「食材过期提醒，打印标签，应该允许选择打印多少份，默认是1，但是可以填写数字来确定打印多少份。注意，填写数字手机上应该使用数字键盘。」（同一句话连发 3 次，判断为客户端问题，按 1 次需求处理）

- `data.copies` 字符串字段，默认 `'1'`（存字符串允许输入中间态，如清空重打）
- WXML `<input class="pf-copies-input" type="number" value="{{copies}}" bindinput="onCopiesInput" />` 触发手机数字键盘
- `_resolveCopies()` 是唯一校验点：非正整数兜底 1，上限 99 防误触多打
- 发现并使用 `tsc.js` 里现成的 `setPrint(n)` 指令（`setPagePrint()` 只是它 n=1 的特例）——份数由打印机固件自己重复出纸，BLE 只需传一遍缓冲区命令，不需要像 `print_care_label.js` 那样为多份打印整份重发数据、自己记账 `looptime`/`currentPrint`

### 2.8 两个入口 + 深链

- 列表页 `mat_expire_list`：⋯ 上下文菜单新增「打印标签」行 + `van-popup` 弹出打印组件
- 详情页 `mat_expire_detail`：独立按钮（受 `opsShow` 门控——未保存批次没有 id，不该能打印），同样弹层
- 详情页 `onLoad` 补 `options.q` 解析（复用 `util.parseQuery`，同养护标签深链范式），支持扫食材标签二维码直接定位打开对应批次

## 3. 佳博打印机标签纸规格调研（纯问答）

用户问「佳博打印机的标签纸，除了70\*50之外，还有什么规格？」，做了一次网络搜索回答常见 Gprinter/Gainscha 标签纸规格，未涉及代码改动。

## 4. 养护标签二维码调优（顺手改的生产文件）

用户看到食材标签放大后的效果，先问「养护订单详情页打印小票的二维码尺寸是多少」——答疑：`print_care_label.js` 当时用的是 `cellWidth=3`（41 模块见方 ≈15.4mm），标签存根和顾客小票共用同一 `getCommand(labelType)` 函数、同一段二维码代码。

随即用户明确要求：「cellwidth 调整到4，为了防止打印不下，二维码往左适当移动。」

改动 [`print_care_label.js`](../snowmeet_wechat_mini/components/care/print_care_label.js) 单行 `setQrcode`：`cellWidth` 3→4（放大），x 坐标 400→360（左移防止放大后在 75mm 标签宽度上出边被裁）。⚠️ 未经真机验证：x=300 处的「其他：」/「注：」两个可选文本字段与二维码共享同一竖向区间（y≈150-190），若这两字段实际内容较长，理论上可能与放大后的二维码左边缘重叠，需下次真机打印留意。

## 5. 答疑：mat_expire 菜单位置

用户问「小程序的这特临期查询，添加到了菜单的什么地方？」——直接从记忆回答（admin 页面「餐饮」分组，`admin.js`/`admin.wxml` 的 `mat_expire` 项），未做代码改动。

## 关键改动文件

| 文件 | 改动 |
|---|---|
| [`Controllers/Fnb/FnbMaterialController.cs`](../SnowmeetApi/Controllers/Fnb/FnbMaterialController.cs) | `_requireStaff` 加小程序 session fallback 分支 |
| [`Controllers/PrinterController.cs`](../SnowmeetApi/Controllers/PrinterController.cs) | 新增 `GetAllPrinters`（全表、包 `ApiResult`） |
| `snowmeet_wechat_mini/utils/matExpire.js` | 新建：状态派生 `deriveStatus` 等日期/状态工具 |
| `snowmeet_wechat_mini/utils/data.js` | 新增 9 个 wrapper（mat_expire 8 个 + `getAllPrintersPromise`） |
| `snowmeet_wechat_mini/components/fnb/ocr_scan_layer/` | 新建：连续摄像头 OCR 扫描组件（4 文件） |
| `snowmeet_wechat_mini/pages/admin/fnb/mat_expire_list/` | 新建：列表页（4 文件，含打印入口） |
| `snowmeet_wechat_mini/pages/admin/fnb/mat_expire_detail/` | 新建：详情/编辑页（4 文件，含打印入口 + `options.q` 深链） |
| `snowmeet_wechat_mini/pages/admin/admin.{js,wxml}` | 「餐饮」组新增 mat_expire 导航入口 |
| `snowmeet_wechat_mini/app.json` | 注册两个新页面 |
| `snowmeet_wechat_mini/components/fnb/print_food_label/` | 新建：食材标签打印组件（4 文件，60×40mm + 打印份数） |
| [`components/care/print_care_label.js`](../snowmeet_wechat_mini/components/care/print_care_label.js) | `setQrcode` cellWidth 3→4、x 400→360 |

## 学到的小知识

1. **DPI 是硬件固定属性，TSPL 坐标单位是「点」不是「毫米」**：不确定真机分辨率时，按更保守（更低）的 DPI 假设设计是唯一安全方向——错误后果不对称，偏低估只会让内容变小，偏高估会导致真机裁切出边
2. **`tsc.js` 里 `setPrint(n)` 与 `setPagePrint()` 的关系**：后者只是前者 n=1 的特例，多份打印应优先用 `setPrint(n)` 交给打印机固件处理，不必模仿 `print_care_label.js` 更复杂的应用层多份重发逻辑
3. **公共 TSPL/BLE 基础设施（`tsc.js`+`util.js`）与业务组件（`print_care_label.js`）复用粒度不同**：前者零耦合可以直接复用，后者深度耦合业务数据结构复用性差，正确的复用策略是「共享底层库、新写业务组件」而不是改造既有业务组件塞新参数
4. **后台 agent 被用户中断后不可恢复，需重新调度**：`SendMessage` 到被「暂停」打断的 Explore agent 会返回明确的「已停止不可恢复」提示，此时应直接重新 spawn 而非反复尝试恢复
5. **QR 码字节模式容量决定标签最小可用尺寸**：以小写字母为主的 URL 必须走字节模式（不能用字母数字模式），ECC-L 下 Version 4（33×33 模块）容量 78 字节、Version 5（37×37）106 字节，内容长度→QR 版本→模块数→（配合 `cellWidth` 和 DPI）→物理尺寸，是设计标签布局前必须先算清楚的一条链路
