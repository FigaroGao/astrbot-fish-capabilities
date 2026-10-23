# 恢复器部署与验证

[English — 完整翻译](recovery.en.md)

## 边界

参考 NapCat 4.18.38。先让 NapCat 内部处理 Worker 与会话恢复；外部管理器只调用已有登录 API，不杀 QQ、不重启 Worker。它轮询登录状态，不声称每次都自动验收完整 OneBot → AstrBot → 模型链路。升级 NapCat 后需要核对接口与响应字段。

状态包括在线、等待内置恢复、快速登录请求、密码登录请求、需要人工验证、没有密码等待扫码、次数耗尽及 WebUI 不可达。一次检查约每 30 秒；重试预算持久化、单实例文件锁防重入。错误只记阶段和类型，不落地原始响应或密码。状态文件本身也属于私有运行数据。

## 安装

在原生 Termux 运行 `pkg install python termux-services`。修改 `recovery/napcat_recovery.py` 顶部 `WEB` 路径，使其指向真正的 NapCat `config/webui.json`；默认是 proot-distro 的 `napcat` 容器与 `/root/Napcat/opt/QQ/`。不要复制原机器的 webui.json。

执行 `python recovery/install.py`，本地输入 QQ 号。安装器拒绝覆盖现有服务或恢复器文件；已有安装应先备份并逐项比较，不能反复安装。安装器是新整理的分享工具，离线语法检查不等于已在每台平板安装测试。

服务目录为 `$PREFIX/var/service/fish-recovery`，运行脚本为 `~/.napcat-recovery/manager.py`，设置为同目录 `settings.json`。可选密码通过 `set-password` 本地输入；摘要可用于登录，必须和密码一样保护。`remove-password` 取消回退。安装器不会重启或退出 QQ。

## 恢复流程

1. 确认 QQ 完整在线后清掉本轮离线与重试状态。
2. 掉线先等 120 秒；正在初始化、重连或已扫码等待处理时不竞争登录流程。
3. 最多两次快速登录，至少间隔 300 秒。请求前保存次数，未知结果也计数。
4. 没有配置密码就等待扫码；配置了最多尝试一次密码登录。
5. 腾讯验证码、身份 / 安全 / 新设备验证、冻结、错误密码等转人工处理。不会循环输入密码或绕过验证。
6. 手机完成官方验证后，执行 `python ~/.napcat-recovery/manager.py resume` 允许新一轮有限尝试；并不保证手机验证后原会话必然复用。仍需扫码时在本地 NapCat 流程处理。

查看 `python ~/.napcat-recovery/manager.py status`。状态 `webui_unreachable` 说明 API 无法确认状态，不能据此认定 QQ 掉线并强杀进程。

## 看守、暂停与停止

runit 对恢复器单独退出提供重启；`finish` 等 5 秒，日志由 `svlogd` 轮转。`service-exits.log` 记录恢复器退出码及信号；它不会自动捕获另一个已经在终端运行的 QQ 实例的输出。

可选加载 `astrbot_plugin_fish_host_guard`，每 60 秒执行原生 `ensure_services.py`。检查恢复器锁、状态更新时间和官方 runsvdir 进程；缺失时启动官方 service-daemon 并只拉起 fish-recovery，持锁但 180 秒不更新才仅重启恢复器。每小时 3 次、间隔 180 秒，先保存修复预算。

```bash
# 维护前暂停看守，再停止恢复器；不会退出 QQ
touch ~/.napcat-recovery/host-guard.pause
sv down "$PREFIX/var/service/fish-recovery"
# 维护后恢复
rm ~/.napcat-recovery/host-guard.pause
sv up "$PREFIX/var/service/fish-recovery"
```

整个 Termux 或 AstrBot 被停止后，此方案不会自行在 Android 外部复活。没有承诺开机自启动，也没有部署公网恢复入口或手机推送。浏览器保持后台不是服务管理器的替代。

## 验证边界

合成状态与隔离看守测试覆盖预算、冷却、验证停止、API 失败与缺失服务修复。原设备验证过只结束恢复器后由 runit 拉起、以及原本缺失服务的恢复，QQ 进程与 ready 状态保持。原先退出的确切原因未被证实，不能拿旧系统清理记录代替本次根因。

没有主动制造 QQ 服务端掉线、实测密码登录、触发风控验证或整机重启。恢复后仍需确认 QQ 在线、OneBot WebSocket 连上、AstrBot 收到一条正常消息并成功回复；只看到登录成功不能宣布全链路恢复。
