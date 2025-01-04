from django.contrib import admin
from .models import NameChangeRequest, EmailChangeRequest, ForgotPasswordRequest, PasswordChangeRequest

admin.site.register(NameChangeRequest)
admin.site.register(EmailChangeRequest)
admin.site.register(ForgotPasswordRequest)
admin.site.register(PasswordChangeRequest)
