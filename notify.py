#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
报告推送模块 notify.py
=====================
报告生成后，自动把内容推送到你指定的渠道。支持多渠道，按环境变量开关，
没配置的渠道自动跳过，不会报错。

手机端（微信）：Server酱（最简单，扫码即用）
邮箱端：SMTP（QQ/163/Gmail 等，需授权码）
办公协作：企业微信机器人 / 钉钉机器人 / 飞书机器人
国际：Telegram Bot

所有配置都来自环境变量（GitHub 里填 Secrets 即可）。
"""

import os
import sys
import smtplib
import email.utils
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

import requests

TIMEOUT = 20


def _ok(msg):
    print(f"[notify] {msg}")


def _warn(msg):
    print(f"[notify][WARN] {msg}", file=sys.stderr)


# ------------------------- 微信推送：Server酱 -------------------------
def send_serverchan(sendkey, title, content):
    """Server酱（sctapi.ftqq.com）把消息推到微信。desp 支持 Markdown。"""
    url = f"https://sctapi.ftqq.com/{sendkey}.send"
    resp = requests.post(url, data={"title": title, "desp": content}, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Server酱返回错误: {data}")
    _ok("Server酱推送成功")


# ------------------------- 企业微信机器人 -------------------------
def send_wecom(webhook, title, content):
    """企业微信群机器人，markdown 消息（正文上限约 4096 字符）。"""
    body = content[:4000]
    resp = requests.post(webhook, json={
        "msgtype": "markdown",
        "markdown": {"content": f"## {title}\n{body}"}
    }, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    if data.get("errcode") != 0:
        raise RuntimeError(f"企业微信返回错误: {data}")
    _ok("企业微信推送成功")


# ------------------------- 钉钉机器人 -------------------------
def send_dingtalk(webhook, title, content):
    """钉钉自定义机器人，markdown 消息。"""
    body = content[:4000]
    resp = requests.post(webhook, json={
        "msgtype": "markdown",
        "markdown": {"title": title, "text": f"{body}"}
    }, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    if data.get("errcode") != 0:
        raise RuntimeError(f"钉钉返回错误: {data}")
    _ok("钉钉推送成功")


# ------------------------- 飞书机器人 -------------------------
def send_feishu(webhook, title, content):
    """飞书自定义机器人，markdown 消息（富文本）。"""
    body = content[:4000]
    resp = requests.post(webhook, json={
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {"title": {"tag": "plain_text", "content": title[:50]}},
            "elements": [{"tag": "markdown", "content": body}]
        }
    }, timeout=TIMEOUT)
    resp.raise_for_status()
    _ok("飞书推送成功")


# ------------------------- Telegram Bot -------------------------
def send_telegram(bot_token, chat_id, title, content):
    """Telegram Bot：sendMessage，支持 MarkdownV2/HTML。这里用明文以免转义出错。"""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    text = f"*{title}*\n\n{content[:3800]}"
    resp = requests.post(url, data={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }, timeout=TIMEOUT)
    resp.raise_for_status()
    _ok("Telegram 推送成功")


# ------------------------- 邮箱 SMTP -------------------------
def send_email(smtp_host, smtp_port, user, password, to_addrs, subject,
               body_text, attachment_path=None, use_ssl=True):
    """通过 SMTP 发送邮件，可带附件（日报 .md）。支持 QQ/163/Gmail 等。"""
    msg = MIMEMultipart()
    msg["From"] = user
    msg["To"] = ", ".join(to_addrs) if isinstance(to_addrs, list) else to_addrs
    msg["Subject"] = subject
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg.attach(MIMEText(body_text, "markdown", "utf-8"))

    if attachment_path and os.path.exists(attachment_path):
        with open(attachment_path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        fname = os.path.basename(attachment_path)
        part.add_header("Content-Disposition", "attachment", filename=fname)
        msg.attach(part)

    if use_ssl:
        with smtplib.SMTP_SSL(smtp_host, int(smtp_port), timeout=TIMEOUT) as s:
            s.login(user, password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(smtp_host, int(smtp_port), timeout=TIMEOUT) as s:
            s.starttls()
            s.login(user, password)
            s.send_message(msg)
    _ok("邮件发送成功")


# ------------------------- 统一入口 -------------------------
def send_report(report_path, title, summary, full_markdown):
    """
    根据环境变量决定推送到哪些渠道。
    - 未配置任何渠道：打印提示并跳过。
    - 任一渠道失败：打印警告，不影响其他渠道与主流程。
    """
    sent = False

    # 1) 微信（Server酱）
    if os.environ.get("SERVERCHAN_SENDKEY"):
        try:
            send_serverchan(os.environ["SERVERCHAN_SENDKEY"], title, full_markdown)
            sent = True
        except Exception as e:
            _warn(f"Server酱推送失败: {e}")

    # 2) 企业微信机器人
    if os.environ.get("WECOM_WEBHOOK"):
        try:
            send_wecom(os.environ["WECOM_WEBHOOK"], title, full_markdown)
            sent = True
        except Exception as e:
            _warn(f"企业微信推送失败: {e}")

    # 3) 钉钉机器人
    if os.environ.get("DINGTALK_WEBHOOK"):
        try:
            send_dingtalk(os.environ["DINGTALK_WEBHOOK"], title, full_markdown)
            sent = True
        except Exception as e:
            _warn(f"钉钉推送失败: {e}")

    # 4) 飞书机器人
    if os.environ.get("FEISHU_WEBHOOK"):
        try:
            send_feishu(os.environ["FEISHU_WEBHOOK"], title, full_markdown)
            sent = True
        except Exception as e:
            _warn(f"飞书推送失败: {e}")

    # 5) Telegram
    if os.environ.get("TG_BOT_TOKEN") and os.environ.get("TG_CHAT_ID"):
        try:
            send_telegram(os.environ["TG_BOT_TOKEN"], os.environ["TG_CHAT_ID"],
                          title, full_markdown)
            sent = True
        except Exception as e:
            _warn(f"Telegram 推送失败: {e}")

    # 6) 邮箱
    if os.environ.get("EMAIL_USER") and os.environ.get("EMAIL_PASSWORD"):
        try:
            to = os.environ.get("EMAIL_TO", os.environ["EMAIL_USER"])
            to_list = [x.strip() for x in to.split(",") if x.strip()]
            send_email(
                smtp_host=os.environ.get("EMAIL_SMTP_HOST", "smtp.qq.com"),
                smtp_port=os.environ.get("EMAIL_SMTP_PORT", "465"),
                user=os.environ["EMAIL_USER"],
                password=os.environ["EMAIL_PASSWORD"],
                to_addrs=to_list,
                subject=title,
                body_text=full_markdown,
                attachment_path=report_path,
                use_ssl=str(os.environ.get("EMAIL_USE_SSL", "true")).lower() == "true",
            )
            sent = True
        except Exception as e:
            _warn(f"邮件推送失败: {e}")

    if not sent:
        _ok("未配置任何推送渠道，仅生成本地报告（如需推送，请在 Secrets 中配置）。")
    return sent
