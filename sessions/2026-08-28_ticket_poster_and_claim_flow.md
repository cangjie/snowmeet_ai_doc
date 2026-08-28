# 2026-08-28 优惠券动态海报与扫码领取：模板海报、公众号回调和比例修复

本次会话完善店员分享优惠券的领取闭环，并新增模板海报叠加动态二维码的群分享能力。改动横跨 `snowmeet_wechat_mini`、`SnowmeetApi` 与 `SnowmeetOfficialAccount`；业务代码由用户按部署节奏发布。

## 1. 扫码领取闭环

- `ticket_claim` 二维码增加 `show-menu-by-longpress`，支持长按识别。
- 页面检测到关注公众号后自动领取，已关注用户打开页面同样自动触发。
- 公众号新增 `ticket_share_*` 场景事件处理，转发到 `TicketShare/ClaimSharedTicketByOaFollow`。
- 好友批次保持一次性领取；群批次按批次、会员、当天判断重复领取。
- 领取成功通过公众号客服 `miniprogrampage` 卡片跳转「我的优惠券」。
- 领取失败只发送原因文本，不包含任何小程序跳转。

## 2. 模板动态海报

- `ticket_template` 增加 `cover_upload_id`、`poster_width`、`poster_height`、`qr_x`、`qr_y`、`qr_width`、`qr_height`。
- 用户已取得幂等 DDL，生产库须先执行字段迁移才可部署后端。
- 模板编辑页支持上传海报、回显、输入二维码坐标/尺寸和拖拽二维码预览框。
- 上传、回显和后端读取暂统一使用 `https://mini.snowmeet.top`；不改通用上传的默认旧域名。
- 新增 `TicketPosterController.Generate`：按分享批次生成公众号二维码并叠加到模板海报，返回可下载 PNG。
- 群分享入口合并二维码生成：默认动态二维码；模板维护权限为店长及以上，静态二维码可选；生成后下载至相册并调用 `wx.showShareImageMenu`。
- 独立「固定二维码」界面入口已移除。
- 朋友圈启用 `enableShareTimeline`，预生成并缓存海报以适应 `onShareTimeline` 的同步返回限制。

## 3. 比例问题与修复

- 初版后端将源图强制 `Resize(1080, 1440)`，导致 $9:16$ 海报变为 $3:4$，内容被拉胖。
- 后端改为完全保留原图尺寸和比例，只叠加二维码。
- 配置坐标仍以 `1080×1440` 为参考：二维码位置按原图横纵比例分别映射。
- 二维码尺寸必须正方形：宽和高均按原图横向比例缩放，不能分别按横纵比例拉伸。
- 小程序预览读取原图尺寸计算实际预览高度；二维码框宽高同样按预览横向比例计算。
- 拖拽坐标改用设备真实屏宽换算，并限制二维码框不得超出参考画布。
- 用户最后反馈线上下载图仍被拉伸；判断线上 `mini.snowmeet.top` 可能仍运行旧版 API，发布后需重新验证源图与输出图的像素尺寸。

## 关键改动文件

| 文件 | 改动 |
|---|---|
| `snowmeet_wechat_mini/pages/mine/ticket/ticket_claim/ticket_claim.{js,wxml}` | 长按二维码和关注后自动领取 |
| `SnowmeetApi/Controllers/TicketShareController.cs` | 群分享每日领取和公众号自动领取 |
| `SnowmeetOfficialAccount/Controllers/OfficialAccountApi.cs` | `ticket_share_*` 回调及成功卡片/失败文本 |
| `SnowmeetApi/Models/Ticket/TicketTemplate.cs` | 模板海报和布局字段 |
| `SnowmeetApi/Controllers/TicketTemplateAdminController.cs` | 模板字段保存回显和分享海报入口 |
| `SnowmeetApi/Controllers/TicketPosterController.cs` | 动态二维码海报合成 |
| `snowmeet_wechat_mini/pages/admin/ticket/template_edit/*` | 海报上传、布局预览、群分享与朋友圈 |
| `snowmeet_wechat_mini/utils/data.js` | 海报接口和可选上传域名 |

## 验证

1. SnowmeetApi 多次 `dotnet build SnowmeetApi.csproj --no-restore` 成功。
2. SnowmeetOfficialAccount 构建成功，仅有既存警告。
3. `TicketShareRulesTests` 15/15 通过。
4. 小程序 `node --check`、WXML diagnostics 与 `git diff --check` 均通过。

## 待办

1. 先发布 SnowmeetApi 到 `mini.snowmeet.top`，确认运行程序集包含“保留原图比例”的最新 `TicketPosterController`。
2. 发布 SnowmeetOfficialAccount 并重新编译小程序。
3. 真机测试海报上传、相册授权、动态/静态二维码、群分享、朋友圈分享、扫码关注、成功卡片和失败提示。
4. 对同一原始海报比对上传图与生成图的实际像素宽高；如仍变形，记录生成 URL 后直接下载排查。
