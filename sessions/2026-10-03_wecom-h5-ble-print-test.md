# 2026-10-03 企业微信 H5 蓝牙打印实验：签名接口 + 养护标签测试页 + 首页临时入口

按时间线整理。Windows 机。先跑 start-work 核对各仓状态，然后按用户要求做企业微信 H5 蓝牙打印实验页，为食材管理最终的企业微信 H5 端探路（09-21 定的方向）。代码落在 SnowmeetApi（`Controllers/Fnb/`、`wwwroot/`），小程序没改。

## 1. start-work 核对

- 文档仓已是最新（`ec3f996`）。各仓分支、HEAD、工作区都核对了；22 端口仍时通时断，reqai、alipay 第一次 fetch 失败。
- **与文档不符 1**：10-02 记录说小程序工作区留着约 118 个旧版横幅生成文件改动。本机小程序工作区是干净的，`legacy/` 文件时间都是 10-02 09:50，112 页里只有 2 页有返回横幅（远端也一样）。改动可能在别的机器，也可能已丢；`tools/legacy/build_legacy.py` 已入库，可重跑生成。
- **与文档不符 2**：小程序远端多 2 个用户提交 `9a3434d1`、`023f7858`（「show legacy」，9 个文件，加回 `legacy/pages/admin/sale/` 下 8 个空 JSON/WXSS）。本机没拉。
- **与文档不符 3**：本机有两份 reqai 检出。`D:\source\snowmeet\ai\snowmeet_reqai` 是最新（`e1c8373`）；`D:\source\snowmeet\snowmeet_reqai` 停在 `6131ea4`。start-work 说明和 `settings.json` 指向的是旧的那份。
- 公众号仓 `OfficialAccountApi.cs` 两行改动仍未提交，与文档一致。

## 2. 需求与方案

用户原话：

> 今天想实验一下企业微信的html应用，通过企业微信的蓝牙组件，链接打印机。……随便找一个养护订单的标签测试打印即可。需要做一个空页面，填写打印的张数，点击打印按钮，直接打印即可。

### 2.1 调研结论

- **企业微信 JS-SDK 蓝牙**：与小程序同名的整套 BLE 接口（`openBluetoothAdapter` … `writeBLECharacteristicValue`）。只在企业微信 App 真机里可用，开发者工具不行；安卓需定位权限；官方建议每次写入不超过 20 字节；页面必须在应用可信域名下，并用 `ww.register` 签名。
- **后端现状**：
  - 企业微信 OAuth 登录（`FnbMaterialController.OAuthLogin`）和发消息已有。
  - **JS-SDK 签名完全没有**：全仓搜不到 `jsapi_ticket`。
  - token 是 `FnbWeComController.GetToken`，每次现取、不缓存。
- **可信域名和 IP**：应用 1000009（餐饮通知）的可信域名是 `mini.snowmeet.top`，用户确认已配；服务器 IP 在企业可信 IP 名单里，本机调企业微信接口报 60020。所以签名接口只能部署后才能测。
- **小程序打印流程**（[`print_care_label.js`](../../snowmeet_wechat_mini/components/care/print_care_label.js) + [`util.js`](../../snowmeet_wechat_mini/utils/util.js)）：
  - 搜索 2 秒，设备名包含 printer 表的名字就算匹配。
  - 逐个服务找可写特征，每包 128 字节，一包写完再写下一包。
  - 标签 75×50mm、间隙 4mm；打印机名含 `Printer_` 用 `TSS24.BF2`，否则用 `TSS32.BF2`。
- **小程序代码里的小问题**（这次没改小程序，只在 H5 里避开）：
  - 取板日期在 `member_pick_date` 为空时引用了未定义的 `pickData`；
  - 找服务的边界判断 `>` 应为 `>=`；
  - `getBLEDeviceCharacteristics` 没有 fail 回调。

### 2.2 用户决策

- 标签数据：「写死一单」。
- 部署：我提出要先跑 `staff_bind_code` SQL，用户答「SQL不是已经执行过了吗？我之前手动执行的」。**只读核实：表 + 2 个索引都在生产库**，文档里「未执行」是过时记录，已更正。
- 可信域名：已配置。
- 计划审批时用户补充：三个打印库文件从 `D:\source\snowmeet\snowmeet_wechat_mini\utils\ble_label_printer` 复制，并看看第三个文件（`tsc.js`）用不用得上。结论：用得上，直接原样使用，不另写 TSPL 构造器。

### 2.3 测试单

只读查生产库，选了最近一张修刃 + 打蜡的单，标签上大部分行都会打出来：

- 养护单 25693 / 订单 71887，`WF-260715-002` / `WF_YH_260715_00004`
- 万龙服务中心，单板 Burton 170，修刃 89°，热打蜡
- 实付 0.01（用户的测试单）
- 存根格式：姓「苍」，手机 `186****7897`

printer 表里有效的打印机：`Printer_1048/73E7/B644/7371/CA10` 和 `GP-3120TUC_8FA3/B874/8D44/8C48`。

## 3. 实现

### 3.1 签名接口（SnowmeetApi `ai@de6de506`）

- `GET /api/FnbWeCom/GetJsSdkSignature?url=`，不要求登录。返回 `{ corpId, agentId, url, config:{timestamp,nonceStr,signature}, agentConfig:{…} }`。
- `NormalizeJsSdkUrl`：去掉 `#` 之后的部分；只接受 `https://mini.snowmeet.top`（默认端口），其他返回 code=1。
- `GetJsApiTickets`：
  - 企业 ticket 取自 `cgi-bin/get_jsapi_ticket`，应用 ticket 取自 `cgi-bin/ticket/get?type=agent_config`；
  - 存在 static 字段里，`SemaphoreSlim` 防并发，`expires_in - 300s` 过期；
  - 两个都要刷新时只取一次 token，请求沿用 `PerformRequest` 记日志。
- `ComputeJsSdkSignature`：sha1(`jsapi_ticket=..&noncestr=..&timestamp=..&url=..`)，小写十六进制。
- 测试 [`WeComJsSdkSignatureTests.cs`](../../SnowmeetApi/SnowmeetApi.Tests/WeComJsSdkSignatureTests.cs) 12 例：
  - 官方示例向量 `0f9de62f…`；
  - 去掉 hash；
  - 拒绝 http、非默认端口、其他域名、`mini.snowmeet.top.evil…` 这类伪装域名。

### 3.2 实验页 `wwwroot/wecom/ble_print_test/`

| 文件 | 作用 |
|---|---|
| `index.html` | 张数（1–10）+ 打印按钮 + 状态；折叠区：标签预览、高级（每包 20/64/128/180 字节，间隔 0/10/20/50ms，存 localStorage）、日志；内联加载脚本 |
| `ble_print.js` | `ww.register` 和两种签名、读 printer 表、搜索 3 秒、按信号强弱排序、连接、找可写特征、分包写入、断线处理、`pagehide` 时释放 |
| `care_label.js` | 写死的测试单 + `build()`，逐行移植小程序 `getCommand` + `preview()` |
| `encoding-indexes.js` `encoding.js` `tsc.js` | 从用户指定目录原样拷贝，sha1 与源文件一致 |

- **加载顺序**（`index.html` 内联脚本）：
  1. 藏起原生 `TextEncoder/TextDecoder`；
  2. 加载 `encoding-indexes.js`、`encoding.js`；
  3. 收起 GB18030 版（存为 `GbEncoding`），还原原生的；
  4. 临时补 `getApp`、`require`、`module`，加载 `tsc.js`；
  5. 取出 `Tsc`，删掉临时全局。
- **标签与小程序的差别**：修了取板日期的 bug；去掉文本里的 `"`；张数用 `setPrint(n)`（`PRINT n,1`），由打印机自己重复打。
- **找写入通道**：优先选同一服务里还有 notify 的可写特征（打印机串口服务通常如此），否则取第一个可写的；不再要求 read/notify/write 三者齐全。

### 3.3 与计划的两处差异（看了 SDK 源码后调整）

- 去掉「hex 写入格式」选项。`wecom-jssdk-2.4.0.js` 的 `writeBLECharacteristicValue` 会把 `value` 当 ArrayBuffer 转成 base64，传 hex 字符串会变成空数据。
- `ww.register` 的内部逻辑：在企业微信里，只要传了 `getAgentConfigSignature`，之后每次调接口都会先等 agentConfig；它失败，所有接口都失败。所以页面先分别 `ensureCorpConfigReady` / `ensureAgentConfigReady`，结果写进日志；若应用签名失败而企业签名通过，就重新只用企业签名注册。

### 3.4 首页临时入口（SnowmeetApi `ai@5a79820f`）

- 用户要求在「食材过期管理这个应用首页的最下方」加临时入口。
- 改在 [`wwwroot/fnb/mat_expire/index.html`](../../SnowmeetApi/wwwroot/fnb/mat_expire/index.html)，批次列表下方：虚线按钮「【测试】蓝牙打印养护标签」，跳到 `/wecom/ble_print_test/index.html`。
- 只新增 9 行，前后有 `wecom-ble-test begin/end` 标记；用 `margin-top:-56px; padding-bottom:96px` 避开右下角浮动「+」按钮。
- 用户在线上首页截图问「我看不到呀」：原因是两个提交都只在本机，没 push、没 publish。另外按钮在 15 条批次的最底下，部署后要滑到底才能看到。

## 4. 验证

- `dotnet test`（排除含 DDL 的集成测试）：382 全过，其中新签名测试 12。
- Node（开发者工具自带的 node）比对：
  - 在 vm 里模拟只会 UTF-8 的原生 `TextEncoder`，按 `index.html` 顺序加载；
  - `Printer_1048`（TSS24）和 `GP-3120TUC_8FA3`（TSS32）两种字体，生成的字节都与小程序 `getCommand` **完全一致**（664 字节）；
  - 3 张只把末尾 `PRINT 1,1` 改成 `PRINT 3,1`；
  - 「修刃」编码为 GB18030 的 `D0DE C8D0`；
  - 原生 `TextEncoder` 已还原，没有遗留临时全局。
  - 第一次预览为空，原因是测试脚本把外部的 `Uint8Array` 传进了 vm，不是页面问题；修正脚本后正常。
- 浏览器（本机 `py -m http.server` 静态服务，配置写在 `ai/.claude/launch.json`）：
  - 页面正常加载，官方 CDN 的 SDK 能取到；
  - 非企业微信环境显示提示、按钮置灰、预览正确；
  - 375px 宽无横向滚动；
  - 首页临时按钮显示正常，点击能跳到测试页。
- **没做**：真机打印（要等 publish）；push。（晚上已核实上线，见第 6 节）

## 5. 小程序养护标签打印弹窗（晚，小程序 `b1d6bb02`）

### 5.1 未连接时打印按钮灰掉

用户发来养护订单「打印【标签存根】」弹窗截图，原话：

> 小程序的这个界面，如果没有已连接的打印机，打印按钮应该灰掉。

- 原因：按钮绑定 `disabled="{{ready!=true}}"`，`ready` 只在连接成功时置 true，之后从不复位。手动断开、连接失败、打印完自动断开之后，按钮都还亮着。
- 改法：组件加 `observers.availablePrinters`，算出 `hasConnected`（列表里有一行「已连接」），按钮改为 `disabled="{{!hasConnected}}"`。每次状态变化都会 `setData({ availablePrinters })`，所以这一处就够了，和表格显示的状态一致。
- 项目里没有用内联 WXS 的先例，所以用 JS observer，这在项目里常见。
- 旧版演示用自己那份组件（`legacy/pages/admin/care/order_detail.json` 引用 `/legacy/components/care/print_care_label`）；新版组件只被 `care_order_detail` 用，改动不影响演示。

### 5.2 打完不断开 + 掉线监听

我说明了连带变化（原代码打完自动断开，按钮会随之变灰，补打要先点「连接」）以及中途掉线不会被发现。用户原话：

> 打完不自动断开，再补上掉线监听，然后提交

- `send()` 打完最后一张时，删掉原来的 `closeBLEConnection`；关闭弹窗（`detached`）时照旧断开。
- `ready()` 里注册 `wx.onBLEConnectionStateChange`：`connected=false` 且对应行是「已连接」时改为「未连接」；若是当前连接的那台，`connectingIndex` 清空。`detached()` 里 `wx.offBLEConnectionStateChange`。
- 不弹 toast：手动断开也会触发这个事件，弹「打印机已断开」会误导；表格状态和灰按钮已经能说明问题。
- 全新版只有这一处注册该监听，基础库 3.5.8 支持 `off`，不会和别处冲突。

### 5.3 验证

- `node --check` 通过；diff 只有预期的几行。
- Node 模拟整个组件（mock `wx`、`data`、`util`，`setData` 触发 observer），12 项全过：
  - 初始按钮灰；自动连上后可点；
  - 打完不断开、按钮仍可点；补打直接写、不重连；
  - 别的设备掉线不影响；本机打印机掉线后状态改「未连接」、按钮灰、`connectingIndex` 清空；
  - 手动重连可点、手动断开变灰；关闭弹窗后监听注销。
- 小程序测试 194/194。真机未试。

## 6. 上线核实（end-work 时）

- 文档仓这期间多了其他会话的提交（S3 迁移、reqai-digest、端口转发）；end-work SKILL.md 新增「Git 长期授权」和 22 端口改走 443 的规则。
- SnowmeetApi：`534aad0c`（S3 迁移，14:33 已发布）就在我的 `de6de506`、`5a79820f` 之上，与 origin 一致，所以蓝牙实验页**已随那次发布上线**。上午说的「没 push、没 publish」已过时。
- 本机连不上 `mini.snowmeet.top`，经美国服务器 curl 核实：
  - `/wecom/ble_print_test/index.html` 返回 200；
  - 首页 HTML 里有 `wecom-ble-test` 标记（2 处，begin/end）；
  - `GetJsSdkSignature?url=https://evil.example.com/` 返回 code=1「只能为 https://mini.snowmeet.top 下的页面签名」；
  - 对测试页 URL 返回 code=0，corpId/agentId 和两种签名都有，说明两种 jsapi_ticket 都取到了。
- 小程序：`b1d6bb02` 16:57 已 push。22 端口超时，用 443 `ls-remote` 确认远端就是 `b1d6bb02`。

## 关键改动文件

| 文件 | 改动 |
|---|---|
| `SnowmeetApi/Controllers/Fnb/FnbWeComController.cs` | `GetJsSdkSignature`、`NormalizeJsSdkUrl`、`ComputeJsSdkSignature`、`GetJsApiTickets`（缓存） |
| `SnowmeetApi/SnowmeetApi.Tests/WeComJsSdkSignatureTests.cs` | 新增 12 例 |
| `SnowmeetApi/wwwroot/wecom/ble_print_test/*` | 实验页 3 个文件 + 打印库 3 个原样拷贝 |
| `SnowmeetApi/wwwroot/fnb/mat_expire/index.html` | 首页最底部临时入口（`wecom-ble-test` 标记） |
| `ai/.claude/launch.json` | 本机静态预览配置（不在任何仓库里） |
| `snowmeet_wechat_mini/components/care/print_care_label.js` | `hasConnected` observer；打完不断开；掉线监听及注销 |
| `snowmeet_wechat_mini/components/care/print_care_label.wxml` | 打印按钮 `disabled="{{!hasConnected}}"` |

## 学到的小知识

1. **企业微信 SDK 的 BLE 写入**：传 ArrayBuffer，SDK 内部转 base64；不是 hex，也不用自己编码。
2. **agentConfig 失败会拖垮全部接口**：注册时传了应用签名函数，SDK 就会在每次调接口前先等 agentConfig。
3. **官方 CDN 版本**：只有 `wwcdn.weixin.qq.com/node/wework/wwopen/js/wecom-jssdk-2.4.0.js` 能访问；npm 上最新是 2.4.4，但 CDN 上 2.4.4 等版本返回 404。
4. **`encoding.js` 在浏览器里**：发现已有原生 `TextEncoder` 就不会挂自己的 GB18030 版，中文会静默变成 UTF-8 乱码；要先藏起原生的再加载。
5. **vm 测试跨 realm**：把外部的 `Uint8Array` 注入 vm，`encoding.js` 的 `instanceof ArrayBuffer` 判断会失败，解码返回空串。
6. **本机连不上 `mini.snowmeet.top`**：curl 超时；线上状态只能靠用户在手机上看。
7. **组件状态别靠一次性标记**：`ready` 只置不复位，按钮状态和实际连接就会脱节；从显示用的列表推导（observer）才不会漏掉某条分支。
8. **`onBLEConnectionStateChange` 对主动断开也会触发**：处理掉线时只认「已连接」→ 断开这一种变化，也别弹提示，否则手动断开会被当成掉线。
9. **「已发布」要看构建所在的提交**：别的会话在你的提交之上发布，你的改动也就一起上线了；看 `git log` 的先后，别只信早先的「未部署」记录。
