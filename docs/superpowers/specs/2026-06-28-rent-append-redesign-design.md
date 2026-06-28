# 租赁订单追加商品 — 界面重组设计（2026-06-28）

## 背景
订单详情页 `rent_order_detail` 当前在页面**底部常驻**「+添加套餐 / +添加单品 / ✓确认追加」栏。追加是低频操作，不该常驻底部。后端追加 + 生效骨架已存在：`Rental.appending`(bool?) / `append_commit_time` + `AppendRental` / `SaveAppendings` / `RemoveAppendingRental` / `EffectAppendingRentals` / `EffectRentOrder`。

## 目标（用户确认）
1. 入口从底部常驻栏 → 详情页内**一块独立卡片区**（入口按钮 + 已追加项简要信息）。
2. 点入口进**独立追加页**，录入"和开单一样的规则"（内嵌 `rent_recept_form`）。
3. 生效分流：**应付>0 → 支付成功后才生效**；**应付=0 → 二次确认后生效**。支付/确认前都是草稿。
4. 未确认草稿可**随时删除 = 放弃**，不影响原订单。

## 界面流程
```
订单详情页 rent_order_detail（移除底部常驻栏）
  └─【追加租赁商品】独立卡片区（订单未关闭时显示）
       ├─ 「+ 追加租赁商品」入口按钮 → rent_append?orderId=
       ├─ 草稿区(appending=true)：名称·起租日·押金/租金，标「未确认」
       │     每条「删除」(放弃) ·「继续编辑」(进追加页)；可选「放弃全部」
       └─ 待支付区(appending=false 未生效)：名称·应付，标「待支付」，「去支付」→ onGoPay
                    │ 点入口
                    ▼
独立追加页 rent_append（新建，内嵌 rent_recept_form）
  ├─ onLoad(orderId)：加载订单上下文(shop/member/已有草稿)，购物车只装本次追加项
  ├─ 添加套餐/单品/无码 → 复用 recept_package / search_product_fuzzy；变更走 AppendRental
  ├─ 编辑沿用组件：押金租金 modal、起租日历、编码搜索、完整性 chip
  ├─ 左划删 = RemoveAppendingRental（放弃该条）
  └─ 底部「确认追加」→ SaveAppendings → 后端算应付
        ├─ paying_amount>0 → 跳结算页 settle → 支付成功 → EffectAppendingRentals 生效
        └─ paying_amount==0 → 二次确认 modal → 确认 → 立即 EffectRental 生效
                    │ 完成 / 中途退出草稿留库
                    ▼
        返回详情页 getData 刷新（生效项并入正式 rentals）
```

## 生效状态机
```
appending=true,  commit_time=null                         → 草稿（未确认，可删=放弃）
  ── 确认追加 SaveAppendings ──┐
  ├─ 免押: appending=false, commit_time=now, EffectRental  → 已生效
  └─ 有押: appending=false, commit_time=null, paying>0
                ── 支付成功 EffectRentOrder→EffectAppendingRentals ── → 已生效
```
详情页三态归类：草稿区(`appending=true`) / 待支付区(`appending=false` 未生效) / 正式 rentals(已生效)。

## 复用 vs 新建
- **复用**：后端全部接口；`recept_package` / `search_product_fuzzy` / 无码入口；`rent_recept_form` 组件。
- **新建**：`pages/admin/rent/rent_append`（4 文件，内嵌组件 + 加载/草稿/提交/确认 modal）+ 详情页追加卡片区。
- `rent_recept_form` 可能需小改支持"追加模式"（购物车只装追加项、提交端走追加接口而非 PlaceRentOrder）。

## ⚠️ 待核实点（实现时必查）
1. `EffectAppendingRentals` (RentController.cs:4786) `guaranties[i]` 疑似应为 `guaranties[j]`（误用外层索引）—— 潜在 bug，确认是否顺手修。
2. 需支付追加项 `SaveAppendings` 后 `append_commit_time` 设置点 + 支付回调是否确实走 `EffectRentOrder`/`EffectAppendingRentals`（决定"待支付区"显示口径）。
3. `rent_recept_form` 复用为"追加模式"的改造面（加载现有订单、购物车隔离、提交分流）实际多大。

## 验收
- 详情页底部不再常驻追加栏；追加卡片区在无草稿时只占一个入口按钮。
- 追加录入体验与开单一致（套餐/单品/无码、押金租金/起租/编码、完整性校验）。
- 应付>0 走结算页支付后生效；应付=0 二次确认后生效；草稿可删=放弃。
