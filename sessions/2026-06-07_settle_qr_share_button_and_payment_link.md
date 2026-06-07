# 2026-06-07 — settle 页二维码「转发给微信好友」按钮 + 微信支付链接路径改 order_payment

## 背景

前台开单走到第五步（支付结算页 `pages/payment/settle/`）生成支付二维码后，希望能把二维码直接转发给顾客微信，省去「退出小程序 → 分享 → 重进小程序 → 找回订单」的来回操作。

## 一、可行性讨论（方案选型）

两条路：
- **方案 A（采用）：转发二维码图片** —— `wx.downloadFile` 把后端 `MediaHelper/GetQRCode` 返回的 PNG 下到临时文件，再 `wx.showShareImageMenu` 拉起微信原生「发送给朋友」面板。改动小、不动后端。
- **方案 B（弃用）：转发小程序卡片** —— `<button open-type="share">` + 页面 `onShareAppMessage`，体验顺但分享的是卡片不是二维码；且二维码不一定是微信码，**也可能是支付宝 `alipays://platformapi/startapp` scheme 码**，卡片方案对支付宝无意义。

用户拍板走方案 A（明确理由：二维码未必是微信的，也有支付宝二维码）。

## 二、代码改动（用户已 commit）

主要文件：`snowmeet_wechat_mini/components/order-payment/{index.js,index.wxml,index.wxss}`

### 1. 「转发二维码给微信好友」按钮（commit `share`）
- **wxml**：二维码卡片 `.qr-card` 内、`.qr-meta` 下方加
  ```
  <button wx:if="{{qrCodeUrl}}" class="qr-share-btn" bindtap="onShareQrCode">
    <van-icon name="share-o" .../><text>转发二维码给微信好友</text>
  </button>
  ```
  `wx:if="{{qrCodeUrl}}"` 控制显隐（二维码生成后才出现）。`van-icon` 该组件 json 已注册。
- **wxss**：加 `.qr-share-btn`（浅蓝底 + `#4aa9e9` 字 + flex 居中 + `::after { border:none }`）。
- **js `onShareQrCode`**：`wx.downloadFile(qrCodeUrl)` → `success` 里判 `statusCode===200`：
  - `typeof wx.showShareImageMenu === 'function'` → `wx.showShareImageMenu({ path: tempFilePath, fail })`
  - `fail` 分支：`console.warn` + 若 `errMsg` 含 `cancel`（用户主动取消）直接 return；否则 toast「当前环境不支持直接分享，已打开预览，可长按图片转发」+ `wx.previewImage` 兜底
  - 旧基础库（无 `showShareImageMenu`）直接 `wx.previewImage`

### 2. 微信支付二维码链接路径改 `/mapp/order_payment`（commit `payment id`）
- `order-payment/index.js:116` qrText：
  - 旧：`https://mini.snowmeet.top/mapp/order/payment_entry?paymentId=...`
  - 新：`https://mini.snowmeet.top/mapp/order_payment?paymentId=...`
- 旧版 recept 流程的 `components/payment/payment.js:160` 仍是旧路径 `/mapp/order/payment_entry`，**本次未动**（用户只要求改新版 settle 页）。待确认是否统一新旧。

## 三、踩坑 / 经验

- 📌 **`wx.showShareImageMenu` 是真机专属能力，DevTools 模拟器调用必 `fail`**：模拟器里点按钮只会落到 `previewImage` 兜底 —— 这正是用户反馈「只显示图片、不弹分享菜单」的根因，不是代码 bug。要测真正的原生「发送给朋友」面板必须**真机预览/调试**。基础库 3.5.8 远高于该 API 的 2.14.3 门槛，排除版本因素。
- 📌 **DevTools 改动不生效先清缓存**：按钮加完用户初次看不到，清缓存 + 编译后才出现（符合既有记忆规则）。
- 📌 **`wx.downloadFile` 正式校验需配域名**：二维码 PNG 来自 `requestPrefix` 域（`snowmeet.wanlonghuaxue.com`/线上域名），正式版要把它加入公众平台「downloadFile 合法域名」，否则真机下载失败；真机临时测可在手机微信开「不校验合法域名」。

## 四、答疑（无代码）—— 普通链接二维码「扫码打开小程序」

用户问：体验版要不要填「测试链接」才生效？结论：
- **体验版 / 开发版**：规则未发布也行，但**必须填「测试链接」**，用体验版/开发版扫码才会跳进小程序。
- **正式版**：靠点「发布」规则生效，不依赖测试链接。
- 配置位置：公众平台 → 开发管理 → 接口设置 →「扫普通链接二维码打开小程序」；需先**验证域名归属**（下载校验文件放域名根目录）。
- 两个坑：① 通过普通链接二维码跳进来时，原始 URL 被整体塞进小程序启动参数 `q` 字段（URL-encoded），入口页要 `decodeURIComponent(options.q)` 再解析 `paymentId`；② 若只是想让二维码在微信里打开 H5 网页，则**完全不需要**这套规则，也无「版本」概念。

## 状态

- ✅ 分享按钮 + 链接路径改动落地并由用户 commit（`share` / `payment id`），`snowmeet_wechat_mini` 分支 `ai` 已与 origin 同步
- 🚧 待真机验证：`showShareImageMenu` 在真机弹原生分享面板 + downloadFile 域名配置
- ⏳ 待确认：旧版 `components/payment/payment.js:160` 是否一并改成 `/mapp/order_payment`
