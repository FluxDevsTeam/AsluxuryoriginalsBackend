from django.db import models
from customuser.models import User


class NameChangeRequest(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="name_change_request")
    new_first_name = models.CharField(max_length=150, null=True, blank=True)
    new_last_name = models.CharField(max_length=150, null=True, blank=True)
    otp = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Name Change Request for {self.user.email} - {self.new_first_name} {self.new_last_name}"


class EmailChangeRequest(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="email_change_request")
    new_email = models.EmailField(unique=True)
    otp = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Email Change Request for {self.user.email} to {self.new_email}"


class ForgotPasswordRequest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    otp = models.IntegerField()
    new_password = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"ForgotPasswordRequest for {self.user.email}"


class PasswordChangeRequest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_change_requests')
    otp = models.CharField(max_length=6)
    new_password = models.CharField(max_length=128)  # To securely store hashed password
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"Password change request for {self.user.username}"
