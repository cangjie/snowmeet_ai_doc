# 2026-09-28 操作指南 PPT 换真实截图（iPhone 镜像）+ 小程序三处文案/样式修正

接 [09-25~27 第三轮打磨](2026-09-24_fnb_prepared_recipe_low_stock_and_guide.md)。

## 1. 用 iPhone 镜像截线上真实界面

- 用户开了 VS Code 的「屏幕录制」和「辅助功能」权限，iPhone 镜像窗口里是线上小程序（已部署新版本，真实数据）。
- 截图：`screencapture -x -o -l <窗口号>`，窗口号用 Swift `CGWindowListCopyWindowInfo` 取（owner 为 iPhone Mirroring、onscreen 的那个，385×844）。
- 操作：`cliclick` 自检说没权限（其实 `AXIsProcessTrusted` 为 true），改用自写 Swift 小工具发 CGEvent。
  - 点击：先 `osascript` 激活 iPhone Mirroring，悬停一下再按下；滚动用 `scrollWheelEvent2`（像素单位），拖动不能滚页面。
  - 打字：`System Events keystroke`；手机是拼音输入法，英文要按回车上屏；没有 confirm 处理的输入框回车才安全。
- 截图裁掉手机外框：`sips --cropOffset 38 8 -c 762 369`。

## 2. PPT 更新

- 链接不变：https://claude.ai/artifact/AkjZNKHQ3xkP2v7Ei4evCf （仅用户可见，可下载 PPTX/PDF）。
- 共 27 张截图，覆盖第 2 页和第 5～18 页；这 15 页改成「左文字、右 1～2 张手机截图」版式，封面、流程、原则、附录未动。
- 第 16 页：「库存不够」弹窗 + 建好的带欠料厨房单；第 17 页：盘点中录实盘（-10 ml）+ 提交/放弃按钮。
- 生成脚本在会话 scratchpad，下次不在；再改要先 Artifact `read` 取回 `project/slides/*.html`。

## 3. 为截图在线上做过的写操作（用户已同意）

- **盘点**：开始盘点，给榛果糖浆录实盘 480 ml，然后「放弃本次盘点」，未过账、库存未变。放弃只清手机本地存的单号，**服务端留下一张 draft 状态的盘点快照**。
- **厨房单**：pizza 2 份（面团欠 1 个），「仍然建单」后约 1 分钟内「删除并退回配料」；已在用量预警页核对面团可用量回到 1 个。「建单并扣料」是用户在手机上亲手点的。

## 4. 小程序三处修正（本地已改，未提交）

| 文件 | 改动 |
|---|---|
| `pages/fnbinv/expiry/expiry.wxml` | 底部提示「临期阈值按二级分类设置」→「临期提醒天数按食材设置，可在『分类』里点食材修改」 |
| `pages/fnbinv/recipe/recipe.wxml` | 菜品配方说明去掉「待核对的厨房单才能出餐」→「发布配方后，才能在『出餐』建厨房单扣料」 |
| `pages/fnbinv/count/count.wxml` / `count.wxss` | 盘点入口卡加 `start-card`：子项 `flex-shrink: 0`、按钮 `margin-top`，修 iOS 上按钮压住说明文字 |

- 小程序测试 167/167；文案和样式测试覆盖不到，真机效果未看。
- 按钮压字是按原因推的：`.card` 有 `overflow: hidden`，iOS 纵向 flex 会把多行说明压扁。

## 5. 待办

- 用户提交并上传小程序后，重截 PPT 第 10 页（临期页）、第 12 页（菜品配方页），换掉旧文案截图。
- PPT 要在 Share 里开放给员工才能看。
- 销毁清单只在有已过期批次时才有入口，今天 0 批，没截。

## 学到的小知识

1. **镜像里点击「丢失」多半是输入框还在焦点**：镜像用 Mac 键盘，手机不弹软键盘，看不出输入框仍在编辑；第一下点击只用来失焦。按 **Esc** 可以退出编辑。
2. **刚切页后的第一下点击也常丢**：点完要截图核对，写操作只点一次、确认后再决定是否重试。
3. **镜像画面有时不刷新**：页面看起来空白不一定是 bug，激活窗口、等几秒或滚一下再截。
4. **盘点「放弃」不是服务端操作**：只清本地单号，草稿快照留在库里。
