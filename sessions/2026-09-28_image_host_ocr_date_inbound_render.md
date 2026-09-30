# 2026-09-28 ~ 09-30 图片域名临时切 mini + OCR 日期优先 yyyy-MM-dd + 入库页首屏 6.6 秒定位修复

在 Windows 机（`D:\source\snowmeet\ai`）上进行。start-work 后用户连续提了三件事：图片先传到 mini、OCR 日期识别规则、入库页显示慢。改动落在 `snowmeet_wechat_mini` 和 `SnowmeetApi`，用户已分批提交推送（小程序 `ai@0c712574`，SnowmeetApi `ai@18e0601a`）。

## 1. start-work 核查

- 文档仓已是最新（`6ec7ea5`）。github 的 22 端口超时，小程序、公众号、支付宝、reqai 四个仓 fetch 失败，ahead/behind 只能看本地缓存。
- reqai 在这台电脑的路径是 `D:\source\snowmeet\snowmeet_reqai`，不是文档里写的 Mac 路径。
- 09-28 Mac 上那三处小程序改动当时这台电脑上没有；后来核对，已在 `b6892624 fix bug` 提交。

## 2. 图片上传域名临时切到 mini.snowmeet.top

### 2.1 现状

- 用户问：图片上传到了哪个域名？
- 食材（新版 fnbinv、旧 mat_expire）、养护、零售的照片都写死传到 `snowmeet.wanlonghuaxue.com`，显示地址也写死同一个域名；接口走 `mini.snowmeet.top`。
- 优惠券海报、次卡商品图（`multi-uploader`）本来就传 mini；南山雪票预约传 `xuexiaotupian.wanlonghuaxue.com`。
- 两个域名是两台服务器，各自读本机 `config.sqlServer`。这台电脑两台都连不上（curl 15 秒超时）。

### 2.2 改动

- 用户原话：「上传图片的域名，临时设置为mini.snowmeet.top，等真正的图片服务器修好了，我们再改回来。」
- 显示必须跟着切：照片落在哪台的磁盘，就只能从那台读。07-08 那次也是上传和显示一起切。
- `data.js` 新增 `IMAGE_HOST`（导出），`uploadFilePromise` 默认值和 `uploadMatExpirePhotoPromise` 都读它。
- 8 处写死的显示地址改为读它：养护开单表单、养护详情、养护列表、未取板列表、未完成列表、零售详情、旧版过期提醒详情、新版食材照片组件和批次详情。
- 没动：雪票详情页的两张固定图片、调试页 `env.wxml`、南山雪票预约。
- 语法检查 10/10，小程序测试 167/167。

## 3. OCR 日期：yyyy-MM-dd 不看前后缀、优先

### 3.1 需求

- 用户原话：「只要有yyyy-MM-dd的字样，无论是否有前后缀，都优先识别日期。」例子要识别成 2025-08-05。
- 用户说附了图，但消息里没有图片，`screenshots` 目录也是空的，所以按规则改。

### 3.2 原因

- `ExtractDates` 的 `2026-07-16` 规则前后都要求「不是数字」：`2025-08-0512:30`（后面紧跟时间）、`12025-08-05`（前面粘数字）都识别不出。
- 结果按行顺序排：上一行的 `250312` 会被当成 6 位喷码日期（2025-03-12），排在真正的日期前面。

### 3.3 改动（先写测试）

- 新增 [`FnbOcrDateTests.cs`](../../SnowmeetApi/SnowmeetApi.Tests/FnbOcrDateTests.cs) 12 例，改之前 5 例失败。
- 新规则 `YMD_PADDED`：`(20\d{2})` + 分隔符 + 两位月 + 分隔符 + 两位日，不加前后边界；分隔符含 `- . /` 和全角横线、斜杠。
- `yyyy-MM-dd` 和 `yyyy年M月d日` 两类明确日期放进优先列表，排在所有宽松格式前面；到期日期候选同样处理。
- 识别过的 `yyyy-MM-dd` 先从文本里抹掉，再跑喷码等规则；保质期识别同样先抹掉。
- 服务端单元 362 过（350 + 新 12）。需 publish SnowmeetApi。
- 没覆盖：OCR 把 `0` 认成字母 `O` 这类识别错字，要看到原图再定。

## 4. 入库页显示慢

### 4.1 第一次分析（方向错了）

- 数据量：生产库食材 8 条、分类 18 条、单位 5 条、保质期规则 0 条，只有几 KB。
- 每个接口服务端先查 2 次库鉴权，再查业务数据。
- 从这台电脑查库每条约 480 ms，且 API 服务器和数据库按 IP 段看分属 AWS 宁夏和美东，于是推断「跨境查库」是瓶颈。**这个推断后来被实测推翻。**
- 先做的改动：加分步计时（`[入库页耗时]`）、批次号改为与目录数据并发请求、加载中显示「加载中…」、失败给「重试」。

### 4.2 实测

- 用户在开发者工具里跑出：登录 38 ms，4 个接口并发共 110 ms，**首屏渲染 6678 ms，数据渲染 6532 ms**。
- 控制台还有一条：`setData 数据传输长度为 1693 KB，存在有性能问题`。
- 用户问：「数据渲染，用了6秒多，都渲染什么了？」

### 4.3 根因

- `date-range-picker` 里的 `van-calendar` 没有 `wx:if`，只靠 `show` 隐藏在弹层里。
- 月份子组件 `month` 在页面加载时就全部创建；每个的日期、类型、最小/最大日期、当前日期属性变一次就重新生成当月格子并 setData。
- 入库页两个日期框：生产日期 36 个月，到期日期（`allow-future`，往回 3 年到往后 15 年）216 个月，一共 252 个月份组件。

### 4.4 修复

- `date-range-picker` 加 `calendarMounted`，第一次点开才挂载日历，挂载后保留。先以关闭状态挂载，渲染完再打开，弹出动画正常。
- 这个组件有 9 个页面在用，都一起受益。小程序测试 167/167。
- 还没解决：到期日期日历第一次点开要一次渲染 216 个月，预计卡 5 秒左右。建议范围改成今天～往后 3 年，等用户定。

## 关键改动文件

| 文件 | 改动 |
|---|---|
| [`utils/data.js`](../../snowmeet_wechat_mini/utils/data.js) | 新增并导出 `IMAGE_HOST`；两个上传函数读它 |
| 养护/零售/食材 8 个页面和组件 | 写死的 wanlonghuaxue 显示地址改读 `data.IMAGE_HOST` |
| [`FnbMaterialController.cs`](../../SnowmeetApi/Controllers/Fnb/FnbMaterialController.cs) | `YMD_PADDED` + `ExtractDates` 明确日期优先 + 识别后抹掉；保质期识别先抹掉 |
| [`FnbOcrDateTests.cs`](../../SnowmeetApi/SnowmeetApi.Tests/FnbOcrDateTests.cs) | 新建，12 例 |
| [`pages/fnbinv/inbound/inbound.{js,wxml}`](../../snowmeet_wechat_mini/pages/fnbinv/inbound/inbound.js) | 临时计时、批次号并发、加载中/失败状态 |
| [`components/date-range-picker/index.{js,wxml}`](../../snowmeet_wechat_mini/components/date-range-picker/index.js) | 日历用到才挂载 |

## 学到的小知识

1. **弹层里的内容只靠 `show` 隐藏不够**：`van-calendar` 的月份在页面加载时就全部创建了。组件要在用到时才创建，用 `wx:if` 控制。
2. **页面慢先看控制台 setData 警告和分步计时**：这次先凭「本机查库慢 + IP 段」推断是接口慢，实测接口只要 110 ms，真正的问题一眼就在控制台里。
3. **本机到数据库的延迟不能代表 API 服务器到数据库的延迟**：两者网络位置不同。
4. **日期正则用固定位数时可以不要前后边界**：月、日固定两位，后面粘着时间也不会切错，前面粘着数字也能从中间匹配到年份。
5. **这台 Windows 机只有老的 `SQL Server` ODBC 驱动**：连生产库用 `DRIVER={SQL Server}`，不加 `Encrypt`；记忆里原来写的 Driver 17 已更正。
