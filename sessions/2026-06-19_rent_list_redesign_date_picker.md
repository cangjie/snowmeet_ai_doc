# 2026-06-19（续2）租赁订单列表改版 + date-range-picker 控件：删冗余按钮、标签竖排、等宽标签、自定义日期范围选择器

本会话接续同日因 context 满截断的前一会话。前一会话已完成 `new_rent_list` 基础重写（删 fui-* 组件、新建后端 `GetOrdersByStaffPaged` 分页接口、前端分页），本会话在此基础上迭代 UI 细节并新建 `date-range-picker` 自定义组件。改动落在 `snowmeet_wechat_mini/pages/admin/rent/` 和 `snowmeet_wechat_mini/components/date-range-picker/`。

## 1. 删除「查看详细」按钮

**用户诉求**：截图显示卡片底部有「查看详细」按钮，但点击卡片区域已绑定 `gotoDetail`，按钮冗余。

- 删除 WXML 中的 `<view class="order-footer">` 及其内容
- 删除 WXSS 中的 `.order-footer` 样式
- 把 `id="{{index}}" bindtap="gotoDetail"` 从 `order-rows` 移到 `order-card`（整张卡片可点击）

## 2. 标签从横排改竖排左列

**用户诉求**：「订单列表的样式错了，标签应该放在左边，如图二」（图二为旧页面截图，标签在左侧竖排）

### 2.1 WXML 结构调整

原结构：
```xml
<view class="order-card" id="{{index}}" bindtap="gotoDetail">
  <view class="order-header">...</view>
  <view class="tag-row">  <!-- 横排标签 -->
    <text class="tag ...">测</text>
    ...
  </view>
  <view class="order-rows">...</view>
  <view class="order-footer">...</view>  <!-- 已删 -->
</view>
```

新结构：
```xml
<view class="order-card" id="{{index}}" bindtap="gotoDetail">
  <view class="order-header">...</view>
  <view class="order-body">           <!-- 新增：水平两列容器 -->
    <view class="tag-col">            <!-- 左列：竖排标签 -->
      <text wx:if="{{item.is_test == 1}}" class="tag tag--test">测</text>
      <text wx:if="{{item.haveEntertain}}" class="tag tag--entertain">招</text>
      <text wx:if="{{item.is_package == 0}}" class="tag tag--single">单</text>
      <text wx:if="{{item.haveOnCredit}}" class="tag tag--credit">挂</text>
      <text wx:if="{{item.haveDiscount}}" class="tag tag--discount">减</text>
      <text wx:if="{{item.useCard}}" class="tag tag--card">卡</text>
      <text class="tag tag--member">{{item.memberShip}}</text>
    </view>
    <view class="order-rows">         <!-- 右列：订单详情行 -->
      ...
    </view>
  </view>
</view>
```

### 2.2 WXSS 结构调整

删除 `.tag-row`，新增：
```css
.order-body {
  display: flex;
  flex-direction: row;
  align-items: flex-start;
}
.tag-col {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  width: 48rpx;
  flex-shrink: 0;
  gap: 6rpx;
  padding-top: 2rpx;
  margin-right: 16rpx;
}
```

## 3. 标签等宽修复

**用户诉求**：「这些 icon，需要等宽」（截图显示「单」和「【会】」宽度不同）

**根因**：`.tag-col` 原来 `align-items: center`，标签只取内容宽度，导致「单」和「【会】」（含括号，内容更宽）宽度不一致。

**修复**：
- `.tag-col` 改 `align-items: stretch`（子元素撑满列宽）
- `.tag` 改为 `padding: 2rpx 0`（去掉横向 padding，靠列宽统一宽度）+ `text-align: center`（文字居中）

```css
.tag {
  font-size: 20rpx;
  padding: 2rpx 0;
  border-radius: 4rpx;
  background: #f3f4f6;
  color: #374151;
  text-align: center;
}
```

## 4. 新建 `date-range-picker` 自定义组件

**用户诉求**：「日期选择，做成一个自定义控件...需要通过点击快捷方式来选择起止日期。但是点击日期，弹出日期选择控件 `<van-calendar>`」（图二为聚合支付订单查询页截图，显示日期显示行 + 今天/昨天/本周/上周 快捷按钮）

### 4.1 组件文件（4 文件标准结构）

**`components/date-range-picker/index.json`**：
```json
{
  "component": true,
  "usingComponents": {
    "van-calendar": "@vant/weapp/calendar/index"
  }
}
```

**`components/date-range-picker/index.wxml`**：
- `.dpr-display`：日期显示行，点击触发 `openCalendar`
- `.dpr-shortcuts`：快捷按钮行（今天/昨天/本周/上周），`data-key` 传给 `onShortcut`
- `<van-calendar type="range" allow-same-day>`：挂在页面末尾，`show="{{showCalendar}}"`

**`components/date-range-picker/index.wxss`**：Alpine Operational Minimalist 风格；激活按钮 `.dpr-btn--active` 用 `#006495` 蓝色。

**`components/date-range-picker/index.js`** 关键逻辑：
```javascript
function _getMonday(d) {
  var day = d.getDay() || 7   // 周日算 7，周一=1
  var m = new Date(d)
  m.setHours(0, 0, 0, 0)
  m.setDate(d.getDate() - day + 1)
  return m
}
// onShortcut: 4 个 case 分别算 start/end，triggerEvent('change', {startDate, endDate})
// onCalendarConfirm: e.detail = [Date, Date]（van-calendar range 模式）
//   start = _fmt(new Date(dates[0])); end = _fmt(new Date(dates[1]))
```

- `triggerEvent('change', { startDate, endDate })` — 父页面统一通过 `bind:change` 接收
- `activeShortcut` 追踪当前激活的快捷键，手动选日历时清空为 `''`

### 4.2 接入 new_rent_list

- `new_rent_list.json`：注册 `"date-range-picker": "/components/date-range-picker/index"`
- `new_rent_list.wxml`：原双 `<picker mode="date">` 替换为 `<date-range-picker startDate="{{startDate}}" endDate="{{endDate}}" bind:change="onDateRangeChange" />`
- `new_rent_list.js`：`setDate(e)` 改为 `onDateRangeChange(e)` → `setData({ startDate: e.detail.startDate, endDate: e.detail.endDate })`
- `new_rent_list.wxss`：加 `.filter-row--date { align-items: flex-start; padding-top: 14rpx; padding-bottom: 14rpx; }` 避免日期行高度跳动

## 关键改动文件

| 文件 | 改动 |
|---|---|
| [`pages/admin/rent/new_rent_list.wxml`](../snowmeet_wechat_mini/pages/admin/rent/new_rent_list.wxml) | 删 order-footer（查看详细按钮）；tag-row 改为 order-body + tag-col 竖排；接入 date-range-picker 组件 |
| [`pages/admin/rent/new_rent_list.wxss`](../snowmeet_wechat_mini/pages/admin/rent/new_rent_list.wxss) | 删 .order-footer、.tag-row；新增 .order-body、.tag-col；.tag 改等宽；新增 .filter-row--date |
| [`pages/admin/rent/new_rent_list.json`](../snowmeet_wechat_mini/pages/admin/rent/new_rent_list.json) | 注册 date-range-picker 组件 |
| [`pages/admin/rent/new_rent_list.js`](../snowmeet_wechat_mini/pages/admin/rent/new_rent_list.js) | setDate → onDateRangeChange |
| [`components/date-range-picker/index.js`](../snowmeet_wechat_mini/components/date-range-picker/index.js) | 新建：快捷按钮逻辑 + van-calendar 回调 + triggerEvent |
| [`components/date-range-picker/index.wxml`](../snowmeet_wechat_mini/components/date-range-picker/index.wxml) | 新建：日期显示行 + 快捷按钮行 + van-calendar |
| [`components/date-range-picker/index.wxss`](../snowmeet_wechat_mini/components/date-range-picker/index.wxss) | 新建：Alpine 风格样式 |
| [`components/date-range-picker/index.json`](../snowmeet_wechat_mini/components/date-range-picker/index.json) | 新建：component:true + 注册 van-calendar |

注：AliController.CallBack() 日志路径修复属上一段会话（也是 2026-06-19），详见前一 session 归档或 CLAUDE.md 2026-06-19（续1）节。

## 学到的小知识

1. **WXSS 编译器不支持中文字符类名**：`.status-chip--租赁中` 会报 `unexpected '@' at pos X`，原因是编译器把非 ASCII 字符编码为 `@XX` 导致语法错误。解决：JS map 将中文状态字符串转 ASCII class 名（`renting/returned/closed/...`），用 `item.statusClass` in WXML。

2. **flex 列等宽子元素**：`align-items: stretch`（默认）让所有子元素撑满交叉轴（即列宽）。`align-items: center` 只取内容宽，导致不等宽。等宽标签列的正确写法：列容器固定宽度 + `align-items: stretch` + 每个 tag `text-align: center`。

3. **van-calendar `type="range"` confirm 事件**：`e.detail` 是 `[startDate, endDate]`（JS Date 对象数组），不是 `{ start, end }` 对象。用 `e.detail[0]` / `e.detail[1]` 取值，再 `new Date()` 包一层确保类型正确。

4. **`date-range-picker` 的 util 路径**：从 `components/date-range-picker/index.js` 到 utils 需要跨两层目录：`../../utils/util.js`（components 目录 → miniprogram 根 → utils）。

5. **`_getMonday` 周日处理**：`new Date().getDay()` 返回 0（周日）~6（周六）。用 `d.getDay() || 7` 将周日映射为 7，使「距离周一」的计算 `d.getDate() - day + 1` 在周日也正确（减 6 天回到上周一，而不是加 1 天到下周一）。
