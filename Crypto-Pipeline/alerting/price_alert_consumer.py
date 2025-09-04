"""
Real-time Crypto Price Alert Consumer
Detects price movements >10% within 5-minute windows
"""

import json
import logging
import os
import smtplib
from collections import defaultdict
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from confluent_kafka import Consumer
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# Configure logging with robust log path resolution
def _resolve_log_path() -> str:
    """Return a writable log file path, handling mapped dir structures.

    Priority:
    1) ALERT_LOG_FILE if provided
    2) ALERT_LOG_DIR/price_alerts.log if dir provided
    3) /logs/price_alerts.log (file) or /logs/price_alerts.log/price_alerts.log if that is a directory
    """
    # Explicit file path takes precedence
    log_file = os.getenv("ALERT_LOG_FILE")
    if log_file:
        parent = os.path.dirname(log_file) or "."
        os.makedirs(parent, exist_ok=True)
        return log_file

    # Directory override
    log_dir = os.getenv("ALERT_LOG_DIR")
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        return os.path.join(log_dir, "price_alerts.log")

    # Default mapping under /logs
    base = "/logs"
    default_candidate = os.path.join(base, "price_alerts.log")
    try:
        # If path exists and is a directory (due to host mapping), write inside it
        if os.path.isdir(default_candidate):
            os.makedirs(default_candidate, exist_ok=True)
            return os.path.join(default_candidate, "price_alerts.log")
        # Otherwise, ensure parent exists and use file path
        os.makedirs(base, exist_ok=True)
        return default_candidate
    except Exception:
        # Final fallback to cwd
        return os.path.join(os.getcwd(), "price_alerts.log")


LOG_PATH = _resolve_log_path()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class PriceAlertConsumer:
    """Consume crypto price events and emit alerts.

    Subscribes to the `crypto_prices` Kafka topic, tracks per-symbol price
    history over a configurable time window, and sends email notifications when
    the percentage change exceeds the configured threshold.
    """

    def __init__(self):
        # Prefer unified env var; fall back to legacy name, then sensible default
        kafka_bootstrap = (
            os.getenv("KAFKA_BOOTSTRAP_SERVERS") or os.getenv("KAFKA_BROKERS") or "redpanda:9092"
        )

        self.consumer = Consumer(
            {
                "bootstrap.servers": kafka_bootstrap,
                "group.id": "price-alert-consumer",
                "auto.offset.reset": "latest",
            }
        )

        # Email configuration
        self.smtp_server = os.getenv("SMTP_SERVER")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        # default recipient if none provided via env
        default_rcpt = "hassan.houta@outlook.com"
        raw_rcpts = os.getenv("ALERT_RECIPIENTS", default_rcpt)
        self.alert_recipients = [r.strip() for r in raw_rcpts.split(",") if r.strip()]

        # Alert configuration
        self.alert_threshold = float(os.getenv("ALERT_THRESHOLD_PERCENT", "10"))
        self.alert_window = int(os.getenv("ALERT_WINDOW_MINUTES", "5"))

        # Track price history per symbol (configurable window)
        self.price_history = defaultdict(list)

    def send_email_alert(self, subject, message):
        """Send email notification for price alerts"""
        if not all(
            [
                self.smtp_server,
                self.smtp_user,
                self.smtp_password,
                self.alert_recipients,
            ]
        ):
            logger.warning("Email alert configuration incomplete. Skipping email notification.")
            return

        try:
            msg = MIMEMultipart()
            msg["From"] = self.smtp_user or ""
            msg["To"] = ", ".join(self.alert_recipients)
            msg["Subject"] = f"[Crypto Alert] {subject}"
            msg.attach(MIMEText(message, "plain"))

            with smtplib.SMTP(self.smtp_server or "localhost", self.smtp_port) as server:
                try:
                    server.starttls()
                except Exception:
                    pass
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.smtp_user or "", self.alert_recipients, msg.as_string())
            logger.info("Email alert sent to %d recipients", len(self.alert_recipients))
        except (smtplib.SMTPException, ConnectionError) as e:
            logger.error("Failed to send email alert: %s", e)

    def track_price_change(self, symbol, price, timestamp):
        """Track price changes and detect anomalies"""
        # Add new price with timestamp
        self.price_history[symbol].append({"price": float(price), "timestamp": timestamp})

        # Remove prices older than configured window
        cutoff = datetime.utcnow() - timedelta(minutes=self.alert_window)
        self.price_history[symbol] = [
            p for p in self.price_history[symbol] if p["timestamp"] >= cutoff
        ]

        # Calculate percentage change if we have historical data
        if len(self.price_history[symbol]) > 1:
            oldest_price = self.price_history[symbol][0]["price"]
            price_change = ((price - oldest_price) / oldest_price) * 100

            if abs(price_change) > self.alert_threshold:
                alert_msg = (
                    f"ALERT: {symbol} price changed by {price_change:.2f}% "
                    f"in last {self.alert_window} minutes ({oldest_price} -> {price})"
                )
                logger.warning(alert_msg)

                # Send email alert
                email_subject = f"{symbol} Price Alert: {price_change:.2f}% Change"
                email_body = f"""
                Cryptocurrency Price Alert
                --------------------------
                Symbol: {symbol}
                Change: {price_change:.2f}%
                Time Period: {self.alert_window} minutes
                Old Price: {oldest_price}
                New Price: {price}
                Timestamp: {datetime.utcnow().isoformat()}
                """
                self.send_email_alert(email_subject, email_body)

    def consume_messages(self):
        """Main consumption loop"""
        self.consumer.subscribe(["crypto_prices"])

        try:
            while True:
                msg = self.consumer.poll(1.0)

                if msg is None:
                    continue
                if msg.error():
                    # Using the numeric value instead of the protected constant
                    if msg.error().code() == -191:  # PARTITION_EOF error code
                        continue
                    else:
                        logger.error("Consumer error: %s", msg.error())
                        break

                try:
                    data = json.loads(msg.value().decode("utf-8"))
                    self.track_price_change(
                        symbol=data["symbol"],
                        price=float(data["price"]),
                        timestamp=datetime.fromisoformat(data["timestamp"]),
                    )
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    logger.error("Error processing message: %s", e)

        except KeyboardInterrupt:
            logger.info("Shutting down consumer...")
        finally:
            self.consumer.close()


if __name__ == "__main__":
    alert_consumer = PriceAlertConsumer()
    logger.info("Starting price alert consumer...")
    alert_consumer.consume_messages()
