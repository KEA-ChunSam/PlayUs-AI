import traceback
from datetime import datetime

import requests

from config.config import settings


def send_slack_message(error: Exception):
        now = datetime.now()
        formatted_time = now.isoformat(sep=' ', timespec='milliseconds')

        error_name = type(error).__name__
        error_message = str(error)
        error_stack = traceback.format_exc()

        log_message = f"*🚨[{settings.sentry_environment}]* {formatted_time} ERROR {error_name} - {error_message}\n```{error_stack}```\n<{settings.sentry_repository_uri}|Go-To-Sentry>"

        payload = {"text": log_message}

        try:
            response = requests.post(settings.slack_webhook_url, json=payload)
            response.raise_for_status()
        except Exception as e:
            print(f"Slack 메시지 전송 실패: {e}")
            return e
