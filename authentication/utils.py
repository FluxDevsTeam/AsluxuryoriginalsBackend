from django.core.mail import EmailMessage
import threading
import jwt
from django.conf import settings
import random


def generate_otp():
    """
    Generate a 6-digit OTP.
    Returns:
        str: A string representation of a 6-digit OTP.
    """
    return str(random.randint(100000, 999999))

class EmailThread(threading.Thread):

    def __init__(self, email):
        self.email = email
        threading.Thread.__init__(self)

    def run(self):
        self.email.send()


class Util:
    @staticmethod
    def send_email(data):
        email = EmailMessage(
            subject=data['email_subject'], body=data['email_body'], to=[data['to_email']])
        EmailThread(email).start()


def create_token(payload):
    """Create a JWT token with the given payload."""
    return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')


def decrypt_token(token):
    """Decrypt a JWT token and return the payload."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        return {'status': True, 'payload': payload}
    except jwt.ExpiredSignatureError:
        return {'status': False, 'message': 'Token has expired'}
    except jwt.InvalidTokenError:
        return {'status': False, 'message': 'Invalid token'}
