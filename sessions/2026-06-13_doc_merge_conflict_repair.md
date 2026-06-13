# 2026-06-13 文档仓 merge 冲突修复：start-work 解残留冲突 + end-work 二次合并保住 06-05

纯文档/git 维护会话，无业务代码改动。会话从 `start-work` 触发，过程中发现并修复了 `snowmeet_ai_doc` 仓库**两层独立的分叉/冲突**；末尾 `end-work` 又遇到远端中途前进且缺失本机独有的 06-05 归档，靠 merge（非 reset）保住。

## 1. start-work：working tree 残留未解决的 merge 冲突

### 1.1 现象
- start-work SKILL 第 1 步 `git -C snowmeet_ai_doc pull --ff-only` 报 `Pulling is not possible because you have unmerged files`（exit 128）
- `git status`：`main` 与 `origin/main` 分叉（本地 1 / 远端 2）；CLAUDE.md `both modified`；两个 incoming session 文件（06-07/06-08）已 staged；`sessions/2026-06-05_alipay_phone_sign_type_root_cause.md` untracked
- CLAUDE.md 第 2136/2173/2210 行有 `<<<<<<< HEAD` / `=======` / `>>>>>>> 29a3d73...` 三标记

### 1.2 冲突性质 + 解决
- **纯追加冲突**：HEAD 侧 = 06-05 条目（alipay sign_type 闭环）；`29a3d73` 侧 = 06-07（settle 二维码转发）+ 06-08（手机号回填/实时状态）两条目。两侧都只是往 dev log 末尾追加，无语义冲突
- 解决：保留全部，按 **06-05 → 06-07 → 06-08** 时序删三标记（3 次 Edit 各删一行标记）
- `git add CLAUDE.md sessions/2026-06-05_*.md`（06-05 session 文件配对纳入）→ `git commit --no-edit` 完成 merge commit `a3c3025`
- 工作树干净后才向用户展示项目上下文（Current Status / Key Files / Next Steps / Known Issues）

## 2. （忽略）"滤波 API" 提问 = 问错项目

- 用户问「昨天最后做的那个滤波的 api 的用法」
- 排查：4 个仓（SnowmeetApi / snowmeet_wechat_mini / alipay_snowmeet / snowmeet_ai_doc）全文 grep `滤波|卡尔曼|kalman|平滑|smooth|moving average|低通` → **0 命中**
- 查到 06-12 有未归档提交（`snowmeet_wechat_mini`：`2f2ddbc order finish` settle onPaid 弹窗、`34bf843 set domain name` 全版本域名统一 mini.snowmeet.top、`bc1f1da config`，作者 zhx/cangjie）但都与"滤波"无关
- 把 06-12 两处改动如实讲给用户后，用户答「问错项目了」→ 忽略此问

## 3. end-work：origin 中途前进 3 commit，且缺 06-05

### 3.1 二次分叉
- end-work 开始时 doc 仓状态变成 `## main...origin/main [ahead 2, behind 3]`——另一台机器在**本会话进行期间**向 origin/main push 了 3 个 end-work 归档：
  - `45f82b9` end-work 2026-06-10（「切支付宝 order_payment 仍是微信支付」根因=线上后端旧构建）
  - `9102580` end-work 2026-06-12（settle onPaid 弹窗 + 域名统一 + 等待扫码长排查）
  - `c9f2bc3` end-work（收尾）
- 直接 push 会被远端 non-fast-forward 拒绝

### 3.2 关键：origin/main 从未包含 06-05
- `git show origin/main:CLAUDE.md | grep "2026-06-05 — alipay 手机号解密失败闭环"` → **0 命中**
- `git diff HEAD origin/main -- sessions/2026-06-05_*.md` → 显示为 deleted（origin 侧没有该文件）
- 即 origin/main 的 dev log 只有 06-04 / 06-07 / 06-08 / 06-10 / 06-12，**独缺 06-05**。06-05 工作在本机 06-09 commit `22c8e7a`（"claude"）里，本会话之前从未 push；另一台机器的 06-10/06-12 end-work 建立在**不含 06-05** 的线性历史上
- 推论：若 `git reset --hard origin/main` 图省事，会**永久丢失 06-05** 的 CLAUDE.md 条目 + session 文件

### 3.3 干净合并
- 两侧 CLAUDE.md 改的是**不同区段**：我在中部（06-04 之后）插 06-05；origin 在末尾追 06-10/06-12
- `git merge origin/main --no-edit` → **零冲突自动合并**；结果 CLAUDE.md 含全部 06-04 → 06-12（6 条），origin 带来的 06-10/06-12 session 文件 + `_backfill_mi7_col.py` + `_run_*.py/.log` 等也并入
- 合并后 `[ahead 3]`（`22c8e7a` + `a3c3025` + 新 merge commit），behind 0
- 在合并后的干净状态上追加 06-13 dev log 条目 + 写本归档文件 → `git add .` + commit + push

## 关键改动文件

| 文件 | 改动 |
|---|---|
| `snowmeet_ai_doc/CLAUDE.md` | start-work 删 3 个冲突标记保留 06-05/06-07/06-08；end-work merge 并入 06-10/06-12；追加 06-13 dev log 条目 |
| `snowmeet_ai_doc/sessions/2026-06-05_*.md` | 配对纳入 `a3c3025`（origin 缺，本机独有） |
| `snowmeet_ai_doc/sessions/2026-06-13_doc_merge_conflict_repair.md` | 本归档（新建） |

## 学到的小知识

1. **本地领先 commit 不及时 push 会被别机线性历史"绕过"**：`22c8e7a`（06-05）本会话前一直没 push，另一台机器在更早基点继续 end-work，远端历史就完全不含 06-05。再同步只能靠 `merge` 把两条线汇起来——若图快 `reset --hard origin/main` 就永久丢。重申 feedback 记忆里的规矩：**本机做完即 push，别攒**。
2. **同一会话 doc 仓可能两层分叉**：start-work 时一层（working tree 遗留的未解决冲突），end-work 时又一层（远端会话期间前进 3 commit）。**end-work push 前必须 `git fetch` 看 `ahead/behind`**，behind 非 0 先 merge 再 push，绝不盲 push（盲 push 必被拒，或更糟覆盖）。
3. **追加型 dev-log 冲突天然可全留**：多机各自往 CLAUDE.md 末尾加 dated 条目，冲突解决就是"按日期排好、删标记、全保留"，不用做取舍；只要两侧改的是非重叠区段，`git merge` 甚至能自动完成免手动。
4. **判断"远端是否已含本机某段工作"用 `git show origin/main:<file> | grep` 直查内容**，比看 commit message 列表可靠——本次正是靠 grep 0 命中才确认 origin 真缺 06-05，避免了 reset 丢数据。
