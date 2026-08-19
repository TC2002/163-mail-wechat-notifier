# 163 邮箱新邮件 → 微信通知

完全免费、无需自己服务器的方案：

- **GitHub Actions**（免费托管运行器）每 5 分钟检测一次 163 邮箱
- 通过 **IMAP** 协议读取新邮件（只检测，不修改邮件状态）
- 发现新邮件通过 **Server酱** 推送到微信

## 架构

```
GitHub Actions 定时任务（每5分钟，免费）
    ↓ IMAP 连接 imap.163.com:993
检测到新邮件
    ↓ Server酱 API
个人微信收到通知
```

## 使用前提

1. **163 邮箱开通 IMAP**：登录网页版邮箱 → 设置 → POP3/SMTP/IMAP → 开启 IMAP 服务，获取**授权码**（不是登录密码）
2. **注册 Server酱**（https://sct.ftqq.com）：微信扫码登录并关注公众号，获取 SendKey（以 `SCT` 开头）

## 配置 Secrets

在仓库 `Settings → Secrets and variables → Actions → New repository secret` 添加：

| Secret | 值 |
|---|---|
| `MAIL_USER` | 你的 163 邮箱账号，如 `xxx@163.com` |
| `MAIL_PASS` | 163 邮箱 IMAP 授权码 |
| `SEND_KEY` | Server酱 SendKey（以 `SCT` 开头） |

## 说明

- 首次运行只记录当前最新邮件 UID，**不会**推送历史邮件
- 状态保存在 `state.json`（自动提交回仓库），重启/重建后不重复通知
- 单次最多推送 5 封新邮件（可用 `MAX_NOTIFY` 环境变量调整）
- 手动触发：仓库 `Actions → 163 邮箱新邮件检测 → Run workflow`

## 免费额度

- GitHub Actions：公共仓库免费无限时长
- Server酱：免费每天 5 条推送
