from django.db import models
from customuser.models import User


class ForgotPasswordRequest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    otp = models.IntegerField()
    new_password = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"ForgotPasswordRequest for {self.user.email}"


class EmailChangeRequest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='email_change_requests')
    new_email = models.EmailField()
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"Email change request for {self.user.username} to {self.new_email}"


class PasswordChangeRequest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_change_requests')
    otp = models.CharField(max_length=6)
    new_password = models.CharField(max_length=128)  # To securely store hashed password
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"Password change request for {self.user.username}"
