#!/usr/bin/env python3
"""
Test Email Setup Script
Safely tests email configuration without exposing passwords
"""

import os
import smtplib
import sys
from dotenv import load_dotenv


def test_smtp_connection():
    """Test SMTP connection without sending emails"""

    # Load environment variables
    load_dotenv()

    # Get configuration
    smtp_server = os.getenv("SMTP_SERVER", "smtp-mail.outlook.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "hassan.houta@aucegypt.edu")
    smtp_password = os.getenv("SMTP_PASSWORD")

    print("🔐 Email Configuration Test")
    print("=" * 40)

    # Check configuration
    print(f"SMTP Server: {smtp_server}")
    print(f"SMTP Port: {smtp_port}")
    print(f"SMTP User: {smtp_user}")
    print(f"Password Configured: {'✅ Yes' if smtp_password else '❌ No'}")

    if not smtp_password:
        print("\n⚠️  No password found. Please set SMTP_PASSWORD environment variable.")
        print("   Example: export SMTP_PASSWORD='your_password'")
        return False

    # Test connection
    print("\n🔌 Testing SMTP Connection...")
    try:
        # Create SMTP connection
        server = smtplib.SMTP(smtp_server, smtp_port)
        print("✅ SMTP connection established")

        # Start TLS
        server.starttls()
        print("✅ TLS encryption enabled")

        # Test authentication
        server.login(smtp_user, smtp_password)
        print("✅ Authentication successful")

        # Close connection
        server.quit()
        print("✅ Connection closed properly")

        print("\n🎉 Email configuration is working correctly!")
        return True

    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Authentication failed: {e}")
        print("\n💡 Common solutions:")
        print("   1. Check your password/app password")
        print("   2. Enable 2FA and use App Password")
        print("   3. Verify account settings")
        return False

    except smtplib.SMTPConnectError as e:
        print(f"❌ Connection failed: {e}")
        print("\n💡 Check network connectivity and firewall settings")
        return False

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def test_service_creation():
    """Test if the email service can be created"""
    print("\n🔧 Testing Service Creation...")

    try:
        from periodic_email_service import PeriodicEmailService

        service = PeriodicEmailService()

        if service.smtp_password:
            print("✅ Service created successfully with password")
            return True
        else:
            print("❌ Service created but no password configured")
            return False

    except ImportError as e:
        print(f"❌ Cannot import service: {e}")
        return False
    except Exception as e:
        print(f"❌ Service creation failed: {e}")
        return False


def main():
    """Main test function"""
    print("🧪 Crypto Pipeline Email Service Test")
    print("=" * 50)

    # Test 1: SMTP Connection
    smtp_ok = test_smtp_connection()

    # Test 2: Service Creation
    service_ok = test_service_creation()

    # Summary
    print("\n📊 Test Summary")
    print("=" * 30)
    print(f"SMTP Connection: {'✅ PASS' if smtp_ok else '❌ FAIL'}")
    print(f"Service Creation: {'✅ PASS' if service_ok else '❌ FAIL'}")

    if smtp_ok and service_ok:
        print("\n🎉 All tests passed! Ready to deploy.")
        print("   Run: ./deploy-periodic-email.sh")
    else:
        print("\n⚠️  Some tests failed. Please fix issues before deploying.")
        sys.exit(1)


if __name__ == "__main__":
    main()
