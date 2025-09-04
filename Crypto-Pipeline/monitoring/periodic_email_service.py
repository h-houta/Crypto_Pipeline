"""
Periodic Email Service for Crypto Pipeline Monitoring
Sends status emails every 5 minutes to specified recipients
"""

import os
import smtplib
import time
import logging
import requests
import getpass
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import threading

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class PeriodicEmailService:
    """Service that sends periodic status emails every 5 minutes"""

    def __init__(self):
        # Email configuration - Using Gmail SMTP (more reliable than Outlook)
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "houtahassan61@gmail.com")

        # Secure password handling - try multiple sources
        self.smtp_password = self._get_smtp_password()

        # Email addresses - use Gmail account for sending
        self.from_email = "houtahassan61@gmail.com"
        self.to_email = "hassan.houta@aucegypt.edu"

        # Service endpoints to check
        self.services = {
            "Airflow": "http://airflow-airflow-webserver-1:8080/health",
            "Prometheus": "http://crypto-pipeline-prometheus-1:9090/-/healthy",
            "Grafana": "http://crypto-pipeline-grafana-1:3000/api/health",
            "Producer": "http://crypto-pipeline-producer-1:8000/",
            "Consumer": "http://crypto-pipeline-consumer-1:8001/",
            "PostgreSQL": "http://crypto-pipeline-postgres-exporter-1:9187/metrics",
            "Redpanda": "http://crypto-pipeline-redpanda-1:9644/metrics",
        }

        # Email interval (5 minutes)
        self.email_interval = 5 * 60  # 5 minutes in seconds

        # Stop flag for graceful shutdown
        self.stop_flag = False

    def _get_smtp_password(self):
        """Get SMTP password from secure sources in order of preference"""

        # 1. Try environment variable first
        password = os.getenv("SMTP_PASSWORD")
        if password:
            logger.info("Using SMTP password from environment variable")
            return password

        # 2. Try Docker secret file
        secret_file = os.getenv("SMTP_PASSWORD_FILE", "/run/secrets/smtp_password")
        if os.path.exists(secret_file):
            try:
                with open(secret_file, "r") as f:
                    password = f.read().strip()
                logger.info("Using SMTP password from Docker secret")
                return password
            except Exception as e:
                logger.warning(f"Failed to read Docker secret: {e}")

        # 3. Try interactive input (only if running in terminal)
        if os.isatty(0):  # Check if running in interactive terminal
            try:
                logger.info(
                    "No password found in environment or secrets. Please enter your Outlook password:"
                )
                password = getpass.getpass("SMTP Password: ")
                if password:
                    logger.info("Using password from interactive input")
                    return password
            except Exception as e:
                logger.warning(f"Interactive password input failed: {e}")

        # 4. Fallback - no password available
        logger.warning("No SMTP password available. Email functionality will be disabled.")
        return None

    def check_service_health(self, service_name, endpoint):
        """Check if a service is healthy"""
        try:
            response = requests.get(endpoint, timeout=5)
            if response.status_code == 200:
                return True, "Healthy"
            else:
                return False, f"HTTP {response.status_code}"
        except requests.exceptions.RequestException as e:
            return False, str(e)

    def get_system_status(self):
        """Get overall system status"""
        status_report = {}
        overall_health = True

        for service_name, endpoint in self.services.items():
            is_healthy, details = self.check_service_health(service_name, endpoint)
            status_report[service_name] = {
                "status": "🟢 Healthy" if is_healthy else "🔴 Down",
                "details": details,
            }
            if not is_healthy:
                overall_health = False

        return status_report, overall_health

    def send_status_email(self, status_report, overall_health):
        """Send status email with system information"""
        if not self.smtp_password:
            logger.warning("SMTP password not configured. Skipping email notification.")
            return

        try:
            # Create email content
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Overall status
            status_emoji = "🟢" if overall_health else "🔴"
            overall_status = "All Systems Operational" if overall_health else "Some Systems Down"

            # Build email body
            email_body = f"""
Crypto Pipeline Status Report
============================

Timestamp: {current_time}
Overall Status: {status_emoji} {overall_status}

Service Status:
"""

            for service_name, info in status_report.items():
                email_body += f"\n{service_name}: {info['status']}"
                if info["details"] != "Healthy":
                    email_body += f" - {info['details']}"

            email_body += f"""

---
This is an automated status report sent every 5 minutes.
Generated by Crypto Pipeline Monitoring System
"""

            # Create email message
            msg = MIMEMultipart()
            msg["From"] = self.from_email
            msg["To"] = self.to_email
            msg["Subject"] = f"[Crypto Pipeline] Status Report - {current_time}"
            msg.attach(MIMEText(email_body, "plain"))

            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.from_email, self.to_email, msg.as_string())

            logger.info(f"Status email sent successfully to {self.to_email}")

        except Exception as e:
            logger.error(f"Failed to send status email: {e}")

    def run_periodic_emails(self):
        """Main loop to send emails every 5 minutes"""
        if not self.smtp_password:
            logger.error("Cannot start email service without SMTP password")
            return

        logger.info("Starting periodic email service - sending emails every 5 minutes")

        while not self.stop_flag:
            try:
                # Get current system status
                status_report, overall_health = self.get_system_status()

                # Send status email
                self.send_status_email(status_report, overall_health)

                # Wait for next email interval
                for _ in range(self.email_interval):
                    if self.stop_flag:
                        break
                    time.sleep(1)

            except Exception as e:
                logger.error(f"Error in periodic email loop: {e}")
                time.sleep(60)  # Wait 1 minute before retrying

    def start(self):
        """Start the periodic email service in a separate thread"""
        if not self.smtp_password:
            logger.error("Email service cannot start without SMTP password")
            return False

        self.email_thread = threading.Thread(target=self.run_periodic_emails, daemon=True)
        self.email_thread.start()
        logger.info("Periodic email service started")
        return True

    def stop(self):
        """Stop the periodic email service"""
        self.stop_flag = True
        if hasattr(self, "email_thread"):
            self.email_thread.join(timeout=5)
        logger.info("Periodic email service stopped")


if __name__ == "__main__":
    # Create and start the service
    email_service = PeriodicEmailService()

    if email_service.smtp_password:
        try:
            email_service.start()

            # Keep the main thread alive
            while True:
                time.sleep(1)

        except KeyboardInterrupt:
            logger.info("Shutting down...")
            email_service.stop()
    else:
        logger.error("Service cannot start without SMTP password. Please configure authentication.")
        logger.info("Options:")
        logger.info("1. Set SMTP_PASSWORD environment variable")
        logger.info("2. Use Docker secrets with SMTP_PASSWORD_FILE")
        logger.info("3. Run interactively to enter password manually")
