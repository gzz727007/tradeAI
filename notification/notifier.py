"""
消息推送模块 (Notification Hub)
支持飞书群机器人 (Webhook)、Server酱微信推送以及本地格式化 Markdown 存档。
"""

import json
import requests
from typing import Optional
from config.config import settings

class Notifier:
    @staticmethod
    def send_feishu(markdown_content: str, title: str = "【AI投研】今日可转债调仓与组合内参") -> bool:
        """推送到飞书群机器人"""
        webhook_url = settings.FEISHU_WEBHOOK_URL
        if not webhook_url:
            return False
            
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": "blue"
                },
                "elements": [
                    {
                        "tag": "markdown",
                        "content": markdown_content
                    }
                ]
            }
        }
        try:
            resp = requests.post(webhook_url, json=payload, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            print(f"⚠️ 飞书推送失败: {e}")
            return False

    @staticmethod
    def send_serverchan(markdown_content: str, title: str = "今日可转债投研内参") -> bool:
        """推送到微信 (Server酱)"""
        key = settings.SERVERCHAN_KEY
        if not key:
            return False
            
        url = f"https://sctapi.ftqq.com/{key}.send"
        payload = {
            "title": title,
            "desp": markdown_content
        }
        try:
            resp = requests.post(url, data=payload, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            print(f"⚠️ 微信推送失败: {e}")
            return False

    @staticmethod
    def notify_all(markdown_content: str):
        """统一广播推送"""
        sent_any = False
        if settings.FEISHU_WEBHOOK_URL:
            if Notifier.send_feishu(markdown_content):
                print("📨 成功推送到飞书群机器人！")
                sent_any = True
        if settings.SERVERCHAN_KEY:
            if Notifier.send_serverchan(markdown_content):
                print("📨 成功推送到微信！")
                sent_any = True
        if not sent_any:
            print("ℹ️ 未配置外部 Webhook 推送地址，仅在本地控制台与看板中展示报告。")
