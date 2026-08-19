#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""163 邮箱新邮件检测脚本：通过 IMAP 检测新邮件，通过 PushPlus 推送到微信。

环境变量：
  MAIL_USER       163 邮箱账号（如 xxx@163.com）
  MAIL_PASS       163 邮箱 IMAP 授权码（不是登录密码）
  PUSHPLUS_TOKEN  PushPlus 一对一推送 token
  PUSHPLUS_TOPIC  可选，PushPlus 群组编码，不填则一对一推送
  MAX_NOTIFY      可选，单次最多通知的邮件数，默认 5
"""

import email
import imaplib
import json
import os
import sys
import urllib.parse
import urllib.request
from email.header import decode_header, make_header
from pathlib import Path

MAIL_HOST = os.environ.get("MAIL_HOST", "imap.163.com")
MAIL_PORT = int(os.environ.get("MAIL_PORT", "993"))
MAIL_USER = os.environ["MAIL_USER"]
MAIL_PASS = os.environ["MAIL_PASS"]
PUSHPLUS_TOKEN = os.environ["PUSHPLUS_TOKEN"]
PUSHPLUS_TOPIC = os.environ.get("PUSHPLUS_TOPIC", "")
MAX_NOTIFY = int(os.environ.get("MAX_NOTIFY", "5"))

STATE_FILE = Path(__file__).parent / "state.json"


def decode_header_text(raw: str) -> str:
    """解析 MIME 编码的邮件头（标题、发件人等）。"""
    if not raw:
        return ""
    try:
        return str(make_header(decode_header(raw)))
    except Exception:
        return raw.strip()


def pushplus_send(title: str, content: str) -> None:
    """调用 PushPlus API 推送到微信。"""
    data = urllib.parse.urlencode(
        {
            "token": PUSHPLUS_TOKEN,
            "title": title,
            "content": content,
            "template": "txt",
            "topic": PUSHPLUS_TOPIC,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://www.pushplus.plus/send", data=data, method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    if result.get("code") != 200:
        raise RuntimeError(f"PushPlus 推送失败: {result.get('msg')}")


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text("utf-8"))
        except Exception:
            pass
    return {"uidvalidity": None, "max_uid": 0}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state), "utf-8")


def main() -> int:
    state = load_state()

    mail = imaplib.IMAP4_SSL(MAIL_HOST, MAIL_PORT)
    try:
        mail.login(MAIL_USER, MAIL_PASS)

        # 在 select 之前获取 UIDVALIDITY（status 命令会使连接退回 AUTH 状态，
        # 因此必须在 select 之前调用，否则后续 search/fetch 会失败）
        typ, status = mail.status("INBOX", "(UIDVALIDITY)")
        if typ != "OK":
            raise RuntimeError("获取 UIDVALIDITY 失败")
        # status 返回形如 b'"INBOX" (UIDVALIDITY 1)'，用正则提取
        import re
        uidvalidity_match = re.search(r"UIDVALIDITY (\d+)", status[0].decode())
        uidvalidity = int(uidvalidity_match.group(1)) if uidvalidity_match else 0

        if state["uidvalidity"] != uidvalidity:
            # 邮箱重建，重置状态
            state = {"uidvalidity": uidvalidity, "max_uid": 0}
            print(f"[state] UIDVALIDITY 变化，重置为 {uidvalidity}")

        mail.select("INBOX")
        typ, data = mail.uid("search", None, "ALL")
        if typ != "OK":
            raise RuntimeError("搜索邮件失败")
        if not data or not data[0]:
            print("[info] 收件箱为空")
            return 0

        all_uids = sorted(int(x) for x in data[0].split())
        if state["max_uid"] == 0:
            # 首次运行：记录当前最大 UID，不通知历史邮件
            state["max_uid"] = all_uids[-1]
            save_state(state)
            print(f"[init] 初始化完成，当前最大 UID={state['max_uid']}")
            return 0

        new_uids = [u for u in all_uids if u > state["max_uid"]][-MAX_NOTIFY:]
        if not new_uids:
            print("[info] 无新邮件")
            return 0

        new_mails = []
        for uid in new_uids:
            typ, msg_data = mail.uid("fetch", str(uid), "(BODY.PEEK[HEADER])")
            if typ != "OK" or not msg_data:
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)
            sender = decode_header_text(msg.get("From", ""))
            subject = decode_header_text(msg.get("Subject", "(无主题)"))
            date = decode_header_text(msg.get("Date", ""))
            new_mails.append((uid, sender, subject, date))
            print(f"[new] UID={uid} From={sender} Subject={subject}")

        if not new_mails:
            return 0

        # 组装推送内容
        lines = []
        for uid, sender, subject, date in new_mails:
            lines.append(f"发件人：{sender}\n主题：{subject}\n时间：{date}")
        content = "\n\n".join(lines)

        title = f"163邮箱收到 {len(new_mails)} 封新邮件"
        pushplus_send(title, content)
        print(f"[push] 已推送 {len(new_mails)} 封新邮件")

        # 更新状态
        state["max_uid"] = max(u for u, _, _, _ in new_mails)
        state["uidvalidity"] = uidvalidity
        save_state(state)
        return 0
    finally:
        try:
            mail.logout()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"[error] {e}", file=sys.stderr)
        sys.exit(1)
