# 2026-10-03 美国服务器端口转发：SSH 与 SQL Server 公网转发已启用

本场先执行 start-work，随后按用户要求在美国服务器配置两个 TCP 映射。业务代码和数据库均未修改。

## 1. 启动核查

- 文档 main `63536d5`，pull 成功。
- SnowmeetApi ai `5a79820f`，干净且与刷新后的 origin/ai 一致；蓝牙实验的两个提交已推送，部署未核实。
- 小程序 ai `c4216875`，干净，落后 origin/ai 两个提交：`9a3434d1`、`023f7858`（show legacy）。
- 公众号 ai `4c9c0a6`，`Controllers/OfficialAccountApi.cs` 未提交。
- 当前 workspace reqai main `fefa3a4`，干净；旧副本 `D:/source/snowmeet/snowmeet_reqai` 停在 `6131ea4`。
- 公众号和 reqai fetch 因 GitHub SSH 22 超时，启动核查时远端引用未刷新。

## 2. 用户要求与授权

用户要求美国服务器的 2222 端口映射到 `161.189.64.210:22`，1433 映射到 `161.189.64.210:1433`。初次误以为是告知已有配置，用户明确要求执行配置后开始操作。

自动审批首次拒绝 root 创建持久公网监听，理由是尚未明确授权广泛网络开放和开机启动。向用户说明后，用户确认：“对，已经对公网开放，你执行吧。”随后配置获准执行。

## 3. 配置与验证

美国服务器为 `ubuntu@44.207.251.65`，主机名 `ip-172-31-30-54`。SSH 实际可用；历史文档里的 ari.pem 本机不存在，指定时仅出现警告，SSH 通过已有默认认证成功；未读取或输出私钥。

配置前确认 2222/1433 均无监听，UFW inactive，NAT 表未配置规则；从美国服务器访问目标 22、1433 均成功。无需安装额外软件，使用 `/usr/lib/systemd/systemd-socket-proxyd`。

创建四个文件：

- `/etc/systemd/system/snowmeet-forward-2222.socket`
- `/etc/systemd/system/snowmeet-forward-2222.service`
- `/etc/systemd/system/snowmeet-forward-1433.socket`
- `/etc/systemd/system/snowmeet-forward-1433.service`

socket 分别监听 `0.0.0.0:2222`、`0.0.0.0:1433`，启用 NoDelay；对应 service 的 ExecStart 分别转发至目标 22、1433。服务使用 DynamicUser、NoNewPrivileges、PrivateTmp、ProtectSystem=strict、ProtectHome 和 Restart=on-failure。

运行 systemd-analyze verify、daemon-reload 和 enable --now。verify 仅报告系统既有 xfs CPUAccounting 选项警告。最终复核四个 unit 全部 active，两个 socket 全部 enabled；未重启服务器，开机恢复由 enabled 状态确认。

公网验证：

- `44.207.251.65:2222` TCP 连通，返回 `SSH-2.0-OpenSSH_8.9p1 Ubuntu-3ubuntu0.17`。
- `44.207.251.65:1433` TCP 连通，SQL Server TDS prelogin 返回 43 字节、类型 4。
- 未执行目标 SSH 登录或数据库身份验证，也未修改云安全组。

检查和回滚：

```bash
systemctl status snowmeet-forward-2222.socket snowmeet-forward-2222.service snowmeet-forward-1433.socket snowmeet-forward-1433.service
sudo systemctl disable --now snowmeet-forward-2222.socket snowmeet-forward-1433.socket
sudo systemctl stop snowmeet-forward-2222.service snowmeet-forward-1433.service
```

## 4. SSH 使用与认证失败解释

用户执行 `ssh ubuntu@44.207.251.65 -p 2222` 后接受新地址主机密钥，提示该密钥也见于 `161.189.64.210`，随后 `Permission denied (publickey)`。

映射正常，失败发生在目标服务器账号认证。`-p` 是小写端口选项，`-i` 指定目标服务器私钥：

```powershell
ssh -p 2222 -i "C:\路径\目标服务器密钥.pem" ubuntu@44.207.251.65
```

用户名也必须属于目标服务器；仍失败时加 `-v` 检查实际提供的密钥。用户成功登录尚未确认。

## 5. 收尾

更新 CLAUDE.md 的当前状态、端口映射和开发日志。本轮不自动提交业务仓。end-work 首次 GitHub SSH 22 被拒，改用 SSH 443（Hostname=ssh.github.com、HostKeyAlias=github.com）pull 成功。

## 关键改动文件

| 文件 | 改动 |
|---|---|
| [CLAUDE.md](../CLAUDE.md) | 转发入口、验证结果、Git 状态纠正 |
| 本会话记录 | 配置、验证、授权与登录排障 |
| 美国服务器四个 systemd unit | 持久 TCP 转发 |

## 下一步

使用目标服务器私钥确认 SSH 登录；需要数据库访问时通过 `44.207.251.65,1433` 使用目标 SQL Server 凭据。蓝牙实验 publish/真机测试、小程序旧版验收和公众号链接发布仍待完成。
