# 七色米进销存抓取工具

Windows / macOS，Python 3.11+。通过账户正常登录读取业务接口，按运行时间生成独立快照；不修改业务单据。支持商品与各仓当前库存、全部时间范围的业务单据、明细、库存流水、相关历史版本、商品图片和附件。

## 在其他电脑同步与安装

已有 `snowmeet_ai_doc` 仓库时先执行 `git pull --ff-only`。尚未下载时：

```text
git clone https://github.com/cangjie/snowmeet_ai_doc.git
```

Windows PowerShell，从仓库根目录执行：

```powershell
cd tools\qisemiyun
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py doctor --network
.\.venv\Scripts\python.exe run.py login
.\.venv\Scripts\python.exe run.py run --scope inventory
```

macOS 终端，从仓库根目录执行：

```bash
cd tools/qisemiyun
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python run.py doctor --network
.venv/bin/python run.py login
.venv/bin/python run.py run --scope inventory
```

`login` 交互输入用户名和密码，不把密码放到命令参数或配置中。每台电脑分别安装依赖、分别登录。

## 命令

以下 `python` 指上面虚拟环境的 Python；Windows 可写 `.\.venv\Scripts\python.exe`，macOS 可写 `.venv/bin/python`。

```text
python run.py doctor --network
python run.py login
python run.py run --scope inventory
python run.py run --scope full
python run.py run --scope full --dry-run
```

- `inventory`：全部商品、仓库、门店、总库存和各仓非零库存，并核对各仓汇总；附原生商品/库存 Excel。
- `full`：配置中列明模块的全部时间范围，含红冲单据、停用档案、单据明细、库存流水、关联历史版本、图片附件和搜索索引。逐商品读取流水、下载原文件，耗时较长。
- `--dry-run`：仅显示步骤和新快照路径，不登录、不联网、不创建快照。

每轮重新请求业务数据，分页缓存只服务于该轮；不会复用前一轮的业务快照。只有全部检查通过才更新成功指针；同时启动的第二个任务会被拒绝。

## 本机数据与登录会话

程序默认把数据放在 Git 仓库之外：

| 系统 | 默认本机目录 |
| --- | --- |
| Windows | `%LOCALAPPDATA%\Snowmeet\qisemiyun` |
| macOS | `~/Library/Application Support/Snowmeet/qisemiyun` |

每次运行保存在 `runs/<年月日-时分秒-微秒>/`，内含 `data/`、`run.json`、`run.log` 和最终 ZIP。`latest-inventory.json`、`latest-full.json` 分别指向最近一次成功结果。历史快照不会自动清理。

可在启动前设置 `QISE_HOME` 指定其他本机磁盘目录；该目录不能位于本 Git 仓库内：

```powershell
$env:QISE_HOME = 'D:\qisemiyun-data'
```

```bash
export QISE_HOME="$HOME/qisemiyun-data"
```

Windows 只保存当前 Windows 用户可解密的 DPAPI 会话文件；macOS 只保存到本机系统钥匙串（服务名 `Snowmeet.QisemiCollector`）。不保存账号密码，不使用明文会话后备文件。`QISE_HOME` 改变后需重新登录。

GitHub 仅同步程序、依赖清单、测试和通用接口配置，不同步抓取结果、登录会话、虚拟环境、平台下载的 JavaScript 或图片。配置中的用户/账套标识在登录后取得，没有写入真实账号或业务 UUID。

## 数据格式

- `*.jsonl`：每行一条接口记录，保留业务 ID 和原始字段。
- `qisemiyun.sqlite3`：数据库；`records` 保存按模块划分的 JSON，`modules` 提供文件名及行数。
- `native/`：平台原生 `.xls/.xlsx`；收付款采用 UTF-8 BOM 的 `.csv`，Excel 可打开，避免依赖 Codex 专用工作簿运行时。CSV 对公式开头文本加转义，原始值仍保留于 JSONL 和 SQLite。
- `media/files/`、`media/图片与附件索引.html`：原图片附件及可搜索的本地索引，仅 full 模式生成。
- `verification.json`、`manifest.json`：库存核对、数量、SQLite 完整性及文件 SHA-256；最终 ZIP 检查 CRC。

## VPN 与网卡

程序不会关闭 VPN 或修改系统路由。Windows 检测物理网卡并绑定其 IPv4；macOS 检测 `en*` 网卡并使用 `IP_BOUND_IF` 绑定出口。自动检测失败时：

```text
python run.py doctor --network --source-ip <本机物理网卡IPv4>
python run.py run --scope inventory --source-ip <本机物理网卡IPv4> --source-interface en0
```

`--source-interface` 主要供 macOS 使用；名称按实际网卡确定。若 VPN 的 DNS/Fake-IP 模式或网络管理策略仍阻断直连，`doctor --network` 会失败，不会跳过 TLS 证书验证。应先让该域名可经物理网络访问，再运行采集。

## 定时调用

Windows 任务计划程序、macOS 用户 LaunchAgent 均可调用相同命令，加 `--non-interactive`：

```text
<虚拟环境Python绝对路径> <run.py绝对路径> run --scope inventory --non-interactive
```

必须使用已经执行 `login` 的同一系统用户。macOS 用户钥匙串需可用且已解锁；首次钥匙串访问按系统提示由用户授权。会话过期或需要网站验证时退出并返回非零状态，需要手动重新登录；不自动保存密码或处理验证码。

此工具不创建定时任务；执行周期由各电脑的任务计划配置决定。全量模式会保留较大的独立快照，需按磁盘空间安排归档。

## 验证

```text
python -m unittest discover -s tests -v
```

测试使用合成数据和临时目录，覆盖新快照隔离、动态会话配置、跨进程锁、库存打包、CSV 和平台存储/网卡适配。GitHub Actions 对 Windows、macOS 执行相同检查。网站真实登录、VPN 网络环境和全量业务采集仍需在目标电脑用 `doctor --network`、`login` 和采集命令验证。

依赖来源：[openpyxl](https://pypi.org/project/openpyxl/)、[xlrd](https://pypi.org/project/xlrd/)、[keyring / macOS Keychain](https://keyring.readthedocs.io/en/latest/)。
