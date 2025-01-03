from django.urls import path, re_path, include
from rest_framework.routers import DefaultRouter
from .views import (UserSignupViewSet, UserLoginViewSet, SendOTPViewSet, CheckOTPViewSet,
                    LogoutViewSet, UserProfileViewSet, PasswordChangeRequestViewSet, ForgotPasswordViewSet)
from rest_framework_simplejwt.views import TokenRefreshView

router = DefaultRouter()
# router.register('profile', UserProfileViewSet, basename='userprofile')
# router.register('password-change', PasswordChangeRequestViewSet, basename='passwordchange')
# router.register('forgot-password', ForgotPasswordViewSet, basename='forgot-password')
# router.register('signup', UserSignupViewSet, basename='signup')

urlpatterns = [
    # path('', include(router.urls)),
    path('signup/', UserSignupViewSet.as_view({'post': 'create'}), name='user_signup'),
    path('signup/verify-otp/', UserSignupViewSet.as_view({'post': 'verify_otp'}), name='verify_otp'),
    path('signup/resend-otp/', UserSignupViewSet.as_view({'post': 'resend_otp'}), name='resend_otp'),
    path('login/', UserLoginViewSet.as_view({'post': 'create'}), name='UserLoginViewSet'),
    path('forgot_password/', SendOTPViewSet.as_view({'post': 'create'}), name='forgot-password'),
    path('check_otp/', CheckOTPViewSet.as_view({'post': 'create'}), name='check-otp'),
    path('logout/', LogoutViewSet.as_view({'post': 'logout'}), name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    # forgot password urls
    path('forgot-password/request-forgot-password/', ForgotPasswordViewSet.as_view({'post': 'request_forgot_password'}),
         name='request_forgot_password'),
    path('forgot-password/set-new-password/', ForgotPasswordViewSet.as_view({'post': 'set_new_password'}),
         name='set_new_password'),
    path('forgot-password/verify-otp/', ForgotPasswordViewSet.as_view({'post': 'verify_otp'}), name='verify_otp'),
    path('forgot-password/resend-otp/', ForgotPasswordViewSet.as_view({'post': 'resend_otp'}), name='resend_otp'),
    # Password Change URLs
    path('password-change/request-password-change/',
         PasswordChangeRequestViewSet.as_view({'post': 'request_password_change'}), name='request_password_change'),
    path('password-change/resend-otp/', PasswordChangeRequestViewSet.as_view({'post': 'resend_otp'}),
         name='resend_otp'),
    path('password-change/verify-password-change/',
         PasswordChangeRequestViewSet.as_view({'post': 'verify_password_change'}), name='verify_password_change'),
    # profile
    path('profile/', UserProfileViewSet.as_view({'get': 'retrieve'}), name='user_profile'),
    path('profile/request-email-change/', UserProfileViewSet.as_view({'post': 'request_email_change'}),
         name='request_email_change'),
    path('profile/resend-email-change-otp/', UserProfileViewSet.as_view({'post': 'resend_email_change_otp'}),
         name='resend_email_change_otp'),
    path('profile/verify-email-change/', UserProfileViewSet.as_view({'post': 'verify_email_change'}),
         name='verify_email_change'),
    path('profile/request-name-change/', UserProfileViewSet.as_view({'post': 'request_name_change'}),
         name='request_name_change'),
    path('profile/verify-name-change/', UserProfileViewSet.as_view({'post': 'verify_name_change'}),
         name='verify_name_change'),
]
