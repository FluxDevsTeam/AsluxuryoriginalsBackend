from django.urls import path, re_path, include
from rest_framework.routers import DefaultRouter
from .views import (UserSignupViewSet, UserLoginViewSet, SendOTPViewSet, CheckOTPViewSet, CheckSignupOTPViewSet,
                    LogoutViewSet, UserProfileViewSet, PasswordChangeRequestViewSet)
from rest_framework_simplejwt.views import TokenRefreshView

router = DefaultRouter()
router.register('profile', UserProfileViewSet, basename='userprofile')
router.register('password-change', PasswordChangeRequestViewSet, basename='passwordchange')


urlpatterns = [
    path('', include(router.urls)),
    path('signup/', UserSignupViewSet.as_view({'post': 'create'}), name='UserSignupViewSet'),
    path('login/', UserLoginViewSet.as_view({'post': 'create'}), name='UserLoginViewSet'),
    path('forgot_password/', SendOTPViewSet.as_view({'post': 'create'}), name='forgot-password'),
    path('check_otp/', CheckOTPViewSet.as_view({'post': 'create'}), name='check-otp'),
    path('check_signup_otp/', CheckSignupOTPViewSet.as_view({'post': 'create'}), name='check-signup-otp'),
    path('logout/', LogoutViewSet.as_view({'post': 'logout'}), name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
