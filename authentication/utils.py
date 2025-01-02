import threading
import time

from django.core.mail import send_mail
from django.conf import settings


class EmailThread(threading.Thread):
    def __init__(self, subject, message, recipient_list):
        self.subject = subject
        self.message = message
        self.recipient_list = recipient_list
        super().__init__()

    def run(self):
        send_mail(
            self.subject,
            self.message,
            settings.EMAIL_HOST_USER,
            self.recipient_list,
        )


def send_otp_to_email(email):
    otp = random.randint(100000, 999999)
    send_mail(
        subject="Your OTP Code",
        message=f"Use this OTP to verify your email: {otp}",
        from_email="no-reply@example.com",  # Replace with your email address
        recipient_list=[email],
        fail_silently=False,
    )
    return str(otp)  # Ensure OTP is returned as a string
