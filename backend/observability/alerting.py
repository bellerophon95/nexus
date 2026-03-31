import logging
import os

import requests

logger = logging.getLogger(__name__)

# This would typically be an env var
WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL")


def send_alert(message: str, severity: str = "info"):
    """
    Sends an alert to a configured webhook (Slack/Discord).
    """
    if not WEBHOOK_URL:
        logger.info(f"Alert (no webhook): [{severity.upper()}] {message}")
        return

    payload = {"text": f"🚨 *NEXUS ALERT* [{severity.upper()}]\n{message}"}

    try:
        response = requests.post(WEBHOOK_URL, json=payload, timeout=5)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to send alert: {e}")


def check_drift(metric_name: str, current_value: float, baseline: float, threshold: float = 0.1):
    """
    Checks for metric drift and sends an alert if it exceeds the threshold.
    """
    if current_value < baseline * (1 - threshold):
        msg = f"Quality Regression: `{metric_name}` dropped to `{current_value:.2f}` (Baseline: `{baseline:.2f}`)"
        send_alert(msg, severity="critical")


def check_latency(latency_ms: float, limit_ms: float = 10000):
    """
    Alerts if latency exceeds the limit.
    """
    if latency_ms > limit_ms:
        msg = f"High Latency Detected: `{latency_ms:.0f}ms` (Limit: `{limit_ms}ms`)"
        send_alert(msg, severity="warning")
