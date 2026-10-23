# 2026-10-22～23 扫码接待 + 扫码取板改小程序码：接待流程改回「店员出码、顾客扫码」，顺带处置 mini 的 1433 暴力破解（Windows 机）

按时间线整理。会话从 start-work 开始，主要在 `SnowmeetApi`（`QrCodeController` 一族接口）和 `snowmeet_wechat_mini`（`pages/admin/reception/`、`pages/order/`、`pages/admin/care/`）两仓，中途三次部署 mini，其中一次撞上生产库被公网暴力破解、磁盘将满。

## 1. 扫码接待（第一版）

### 1.1 用户要求（原意）

- 接待改回类似旧版：顾客扫码识别身份，**直接进小程序、不开公众号**，提示验证手机。
- 验证完提示「请耐心等待店员开单」。
- 店员开单进入微信支付后，顾客手机**自动跳到支付页**；支付宝仍由顾客用支付宝扫码，和以前一样。
- 散客也能做租赁、养护，开单页顶部可填姓名、性别、电话。

### 1.2 用户拍板

- 码是**店员手机上的一次性码**（120 秒换新），不做柜台固定码。
- 会员已有手机号的扫码后**直接等待**，不再验证。
- 散客三项**都选填**（租赁、养护也一样）。
- **非雪季养护仍只接会员**（`PlaceCareOrder` 不改）。
- 两个接待页同时可用：管理员菜单默认进扫码接待，底部链接到原手动录入页 `recept_entry`。

### 1.3 实现（SnowmeetApi `c04e67b7`，小程序 `4f0d2956`）

- 后端沿用 `scan_qrcode` 表，**不加列**：
  - 码 `rc_{10 位随机串}_{id}`，`platform='wechat_mini'`；
  - 二维码文字 `https://mini.snowmeet.top/mapp/recept_checkin?code=…`；
  - 新接口 `QrCode/CreateReceptCheckinByStaff`、`GetReceptCheckinByStaff`、`ScanReceptCheckin`、`VerifyReceptCheckinPhone`、`GetReceptCheckinByCustomer`；
  - 判定放在 [`Helpers/ReceptCheckinRules.cs`](../SnowmeetApi/Helpers/ReceptCheckinRules.cs)，有单测。
- 顾客手机怎么找到要付的单：扫码之后、这位会员名下新出现的「待支付」单。选微信就跳 `payment_entry?paymentId=…&autoPay=1`；选支付宝只提示。
- 「手机号 → 会员」的判定从 `PaymentIdentityController._submitPhone` 抽成 `ResolveMemberByVerifiedPhone`，支付页与接待共用，行为不变。
- 小程序：
  - 顾客报到页 [`pages/order/recept_checkin`](../snowmeet_wechat_mini/pages/order/recept_checkin.js)；
  - `payment_entry` 支持 `autoPay=1`；
  - 共用的手机号工具 `utils/phone.js`。
- 第一次部署：服务器 `git pull` 失败，原因是 10-21 七色米那次用 root 跑过 git，`.git` 里留下 240 个 root 所有的文件。经用户同意，清单存到 `/home/ubuntu/reception-checkin-deploy-20261022/` 后改回 `ubuntu`，再发布。

## 2. 按旧版流程返工

- 用户：「接待页，没做对。参考下老的页面和流程。」要有散客进入按钮；扫码后店员这边跳到直接显示会员信息的页面；新顾客授权手机号后在店员这端弹提示；再选店铺和业务。
  - [`recept_scan`](../snowmeet_wechat_mini/pages/admin/reception/recept_scan.wxml) 只出码，另有「散客进入」；
  - 新增 [`recept_member`](../snowmeet_wechat_mini/pages/admin/reception/recept_member.wxml)（对应旧 `recept_member_info`），在这里选店铺和业务。
  - 提交 `34e2d9d7`。
- 用户：顾客信息页要像旧页面一样**直接显示、就地修改**，不要再弹出编辑页。改的姓名、电话只进本次订单，会员资料不变；点「更新顾客信息」才改会员。
  - 复用 `Member/UpdateMemberInfo`（场景「开单」）：写回姓名、性别，新电话追加为 `contact` 号码，不动绑定手机号；
  - 提交 `ea2091e8`。
- 用户决定**保留**订单生效后用联系人补会员空姓名、性别的逻辑（`SupplementMemberProfileFromOrder`）。

## 3. 手机号进入 + 店长授权

- 用户：和旧版一样能输手机号进入，普通店员要店长授权。
- 服务器原有 `QueryCell` / `GetTodayAuthCellList` / `GiveAuth` 都还在，但**新版小程序的授权页和菜单入口早删了**（只剩旧版演示，而它连的是另一套 API 和库）。新增 [`recept_auth_list`](../snowmeet_wechat_mini/pages/admin/reception/recept_auth_list.wxml)，后台加「【接待】接待授权」入口，只对店长显示。
- 后端补三处（`2700ed4b`）：
  - 输了手机号的码等授权时不按 2 分钟过期；
  - 这张码顾客不能再扫；
  - 授权列表排除顾客自己扫码的记录和已作废的申请。
- 小程序提交 `20154553`。

## 4. 第二次部署撞上 1433 暴力破解

- 拉取后发现 mini 磁盘只剩 78 MB，每分钟约少 9 MB。
- SQL Server errorlog 里 **29 万多条 `sa` 登录失败**，来自公网 IP（79.110.49.191、45.88.91.242）。攻击直连 mini 公网 1433，不经美国服务器转发；mini 本机没开防火墙，所以问题在 AWS 安全组对 1433 不限来源。
- 用户逐条同意后处理：
  - 用 iptables 只放行 127.0.0.1、172.31.0.0/16、44.207.251.65 访问 1433，其余 DROP，**不持久化**；改前规则存在 `iptables-before.rules`；
  - journal 压到 200 MB，删 8 个旧 `system_health_*.xel`（795 MB），清空 syslog（438 MB）；
  - 磁盘回到 1.9 GB 后才执行 `republish.sh`。
- 待用户：在 AWS 安全组收紧 1433，换 `sa` 密码或停用 `sa`。

## 5. 开单选店、养护门店规则

- 店铺选择组件在开单场景（`scene='recept'`）首项改为「请选择店铺」，**不再默认选基地店**。扫描中显示「正在识别附近店铺…」，信标命中才选中；没命中就停在首项，提示手动选择（`dfa3db9e`）。
- 用户问「为什么选万龙体验中心也能做养护」：
  - 原因是 10-05 提交 `ad4928dd` 沿用旧版规则，把体验中心发起的养护改记到服务中心；
  - 用户决定**去掉**：养护只看门店自己的 `care` 标志，删 `utils/reception_shop.js` 和 `recept_new` 里的改写（`9d78029c`）；
  - 后端 `CarePricingRules.ResolveCareShop` 留作旧版客户端的兜底。

## 6. 扫码取板改小程序码

- 用户：取板不再用公众号码，改小程序码，并做一个页面提示验证结果；规则仍是「当前用户就是下单用户」。
- 后端（`33e1b2de`）：
  - 码 `cp_{随机串}_{careId}_{id}`，二维码 `https://mini.snowmeet.top/mapp/care_pick?code=…`；
  - 新接口 `CreateCarePickByStaff` / `GetCarePickByStaff` / `VerifyCarePick`，判定在 [`Helpers/CarePickRules.cs`](../SnowmeetApi/Helpers/CarePickRules.cs)；
  - 「扫码人是谁」抽成 `PaymentIdentityController.ResolveScannerMemberId`，与储值付租金的身份核验共用。
- 小程序（`f5b5a934`）：
  - [`care_order_detail`](../snowmeet_wechat_mini/pages/admin/care/care_order_detail/care_order_detail.js) 原来是公众号码加 WebSocket，改为小程序码，每 1.5 秒轮询一次；本人扫码就自动完成发板；
  - 码过期不再误报「顾客非本人」；
  - 新增顾客页 [`care_pick_verify`](../snowmeet_wechat_mini/pages/order/care_pick_verify.wxml)。新微信号先授权手机号，再验证。
- 第三次部署前确认 iptables 规则还在、没有新的登录失败，正常发布。

## 7. 排查与列表状态

- `WF_YH_261022_00006` 没有养护任务：只读查库确认，¥0.01 付款单停在「待支付」，微信下单成功（顾客已看到付款弹窗）但没付。养护任务和任务码只在订单生效时由 `CareController.EffectCareOrder` 生成，所以这不是漏建。
- 养护订单列表原来对有装备的单一律显示「正常订单」。和旧系统其它订单列表（`fire_care_list`、`fd_order_list`）及新版零售列表看齐，改为显示后端 `Order.orderStatus`：
  - 状态有待生成、待支付、部分支付、支付成功、已下单、订单关闭、退款、挂账；
  - 没有装备的仍显示「临时订单」；
  - 没付成功的整张卡片置灰；
  - 提交 `5de080ba`。

## 关键改动文件

| 文件 | 改动 |
|---|---|
| `SnowmeetApi/Controllers/QrCodeController.cs` | 扫码接待 5 个接口、扫码取板 3 个接口；授权列表过滤 |
| `SnowmeetApi/Helpers/ReceptCheckinRules.cs` / `CarePickRules.cs` | 码格式与阶段判定（含单测） |
| `SnowmeetApi/Controllers/Order/PaymentIdentityController.cs` | 抽出 `ResolveMemberByVerifiedPhone`、`ResolveScannerMemberId`、`LoadSessionContext` |
| `snowmeet_wechat_mini/pages/admin/reception/recept_scan.*` | 出码、散客进入、手机号进入、等授权 |
| `snowmeet_wechat_mini/pages/admin/reception/recept_member.*` | 顾客信息页：就地改称呼电话、更新顾客信息、选店铺业务 |
| `snowmeet_wechat_mini/pages/admin/reception/recept_auth_list.*` | 店长接待授权页 |
| `snowmeet_wechat_mini/pages/order/recept_checkin.*` / `care_pick_verify.*` | 顾客扫码落地页 |
| `snowmeet_wechat_mini/pages/order/payment_entry.js` | `autoPay=1` |
| `snowmeet_wechat_mini/components/shop_selector/shop_selector.js` | 开单场景「请选择店铺」 |
| `snowmeet_wechat_mini/components/reception/reception_member_bar/*` | 开单页顶部顾客条可编辑、静默匹配会员 |
| `snowmeet_wechat_mini/pages/admin/care/care_order_detail/*` | 扫码取板改小程序码 + 轮询 |
| `snowmeet_wechat_mini/pages/admin/care/care_order_list.*` | 显示 `orderStatus`，未支付置灰 |

## 学到的小知识

1. **「扫普通链接二维码打开小程序」的体验版测试**：要求扫码人是管理员、开发者或体验者，而且扫的码要和「测试链接」匹配。测试链接最多 5 条，文档要求带参数时完整填写。我们的码每张都不一样，前缀能不能匹配上要实测；规则也只能在小程序发版后发布。
2. **mini 上不要用 root 跑 git**：`republish.sh` 是以 `ubuntu` 身份 `git pull` 的，root 留下的对象目录和 refs 会让拉取失败。
3. **部署前先看磁盘**：公网暴力破解会把 SQL Server errorlog、system_health xel、syslog、journal 一起灌满。`republish.sh` 会先停服、删运行配置文件再构建，构建到一半磁盘写满，服务就起不来了。
4. **养护任务只在订单生效时生成**：生效包括支付成功、0 元确认、储值、核销。没付款的单没有任务，也没有任务码。
5. **两套订单状态**：`careProperties.orderStatus` 只有临时、正常两态，看有没有装备；`Order.orderStatus` 才反映付款进度。
6. **本机 `config.sqlServer` 里的 `100.28.143.19` 连不上**：端口能开，但 SQL 握手失败，测试期间 mini 那边也没有拦截记录，所以和 iptables 无关。只读查询改走美国服务器转发 `44.207.251.65`。
