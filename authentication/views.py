import requests
import random
import datetime
from django.utils import timezone
from django.contrib.auth import logout
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action

from django.contrib.auth.hashers import make_password
from rest_framework.exceptions import AuthenticationFailed

from customuser.models import User
from rest_framework.viewsets import ViewSet
from .serializers import UserSignupSerializer, LoginSerializer, EmailVerificationSerializer, ForgotPasswordSerializer, \
    CheckOTPSerializer, CheckSignupOTPSerializer, PasswordChangeRequestSerializer, UserProfileSerializer
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from .utils import EmailThread
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.core.mail import send_mail
from rest_framework.permissions import AllowAny, IsAuthenticated
from .security import create_token, decrypt_token
from rest_framework.response import Response
from .models import EmailChangeRequest, PasswordChangeRequest


class UserProfileViewSet(viewsets.ModelViewSet):
    serializer_class = UserProfileSerializer
    queryset = User.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return User.objects.filter(id=self.request.user.id)

    @action(detail=False, methods=['post'], url_path='request-email-change')
    def request_email_change(self, request):
        user = request.user
        new_email = request.data.get('new_email')

        if not new_email:
            return Response({"error": "New email is required."}, status=status.HTTP_400_BAD_REQUEST)

        otp = random.randint(100000, 999999)

        # Send OTP email
        send_mail(
            subject="Email Change OTP",
            message=f"Your OTP is: {otp}",
            from_email="no-reply@example.com",
            recipient_list=[new_email],
        )

        EmailChangeRequest.objects.create(user=user, new_email=new_email, otp=otp)

        return Response({"message": "OTP sent to the new email address."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='verify-email-change')
    def verify_email_change(self, request):
        otp = request.data.get('otp')

        if not otp:
            return Response({"error": "OTP is required."}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        email_change_request = EmailChangeRequest.objects.filter(user=user, otp=otp).first()

        if not email_change_request:
            return Response({"error": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST)

        user.email = email_change_request.new_email
        user.save()
        email_change_request.delete()

        return Response({"message": "Email updated successfully."}, status=status.HTTP_200_OK)


class PasswordChangeRequestViewSet(viewsets.ModelViewSet):
    """
    Handles password change requests with OTP verification.
    """
    permission_classes = [IsAuthenticated]
    queryset = PasswordChangeRequest.objects.all()
    serializer_class = PasswordChangeRequestSerializer

    @action(detail=False, methods=['post'], url_path='request-password-change')
    def request_password_change(self, request):
        user = request.user
        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_password')

        if not new_password or not confirm_password:
            return Response({"error": "Both new_password and confirm_password are required."},
                            status=status.HTTP_400_BAD_REQUEST)

        if new_password != confirm_password:
            return Response({"error": "Passwords do not match."}, status=status.HTTP_400_BAD_REQUEST)

        # Create or update the password change request
        PasswordChangeRequest.objects.filter(user=user).delete()
        otp = random.randint(100000, 999999)

        send_mail(
            subject="Password Change OTP",
            message=f"Your OTP for password change is: {otp}",
            from_email="no-reply@example.com",
            recipient_list=[user.email],
        )

        PasswordChangeRequest.objects.create(user=user, otp=otp, new_password=new_password)

        return Response({"message": "An OTP has been sent to your email."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='resend-otp')
    def resend_otp(self, request):
        """
        Request a new OTP if the previous one has expired or was invalid.
        """
        user = request.user

        # Check for an existing request
        password_change_request = PasswordChangeRequest.objects.filter(user=user).first()

        if not password_change_request:
            return Response({"error": "No pending password change request found."}, status=status.HTTP_400_BAD_REQUEST)

        # Generate a new OTP
        otp = random.randint(100000, 999999)
        password_change_request.otp = otp
        password_change_request.created_at = timezone.now()  # Reset timestamp to current timezone-aware time
        password_change_request.save()

        send_mail(
            subject="Password Change OTP - Resent",
            message=f"Your new OTP for password change is: {otp}",
            from_email="no-reply@example.com",
            recipient_list=[user.email],
        )

        return Response({"message": "A new OTP has been sent to your email."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='verify-password-change')
    def verify_password_change(self, request):
        """
        Step 2: Verify OTP and change password.
        """
        otp = request.data.get('otp')

        if not otp:
            return Response({"error": "OTP is required."}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        password_change_request = PasswordChangeRequest.objects.filter(user=user).first()

        if not password_change_request:
            return Response({"error": "No pending password change request found."}, status=status.HTTP_400_BAD_REQUEST)

        # Validate OTP
        if str(password_change_request.otp) != str(otp):
            return Response({"error": "Incorrect OTP."}, status=status.HTTP_400_BAD_REQUEST)

        # Check if OTP has expired
        otp_age = (timezone.now() - password_change_request.created_at).total_seconds()  # Use timezone-aware time
        if otp_age > 300:  # 300 seconds = 5 minutes
            return Response({"error": "OTP has expired. Please request a new one."}, status=status.HTTP_400_BAD_REQUEST)

        # Update user's password
        user.password = make_password(password_change_request.new_password)
        user.save()

        password_change_request.delete()

        # Invalidate refresh token if provided
        refresh_token = request.data.get('refresh_token')
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()  # Blacklist the refresh token
            except Exception as e:
                raise AuthenticationFailed('Refresh token is invalid or expired.')
        return Response({"message": "Password changed successfully. You have been logged out."},
                        status=status.HTTP_200_OK)


class UserSignupViewSet(viewsets.ModelViewSet):
    serializer_class = UserSignupSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):

        if request.method != 'POST':
            return Response({'message': 'Method not allowed'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
        data = request.data
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        email = data['email']
        if not User.objects.filter(email=email).exists():
            User.objects.create(
                first_name=data['first_name'],
                last_name=data['last_name'],
                email=email,
                password=make_password(data['password'])
            )

            user = get_object_or_404(User, email=email)
            otp = str(random.randint(100000, 999999))

            payload = {
                'user_id': user.id,
                'email': user.email,
                'otp': otp,
                'exp': datetime.datetime.now() + datetime.timedelta(minutes=5)
            }
            token = create_token(payload)

            email_thread = EmailThread(
                subject='OTP for signup',
                message=f'Your OTP is {otp}',
                recipient_list=[user.email],
            )
            email_thread.start()

            return Response({
                'token': token
            }, status=status.HTTP_200_OK)

        else:
            return Response({'message': 'User Already Exists'}, status=status.HTTP_400_BAD_REQUEST)


class CheckSignupOTPViewSet(viewsets.ModelViewSet):
    """
    Viewset for OTP validation and token generation.
    """
    serializer_class = CheckSignupOTPSerializer

    # permission_classes = [IsAuthenticated]  # You can adjust permissions as needed

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        otp = serializer.validated_data['otp']
        enc_token = serializer.validated_data['token']
        data = decrypt_token(enc_token)

        if data['status']:
            otp_real = data['payload']['otp']
            if int(otp) == int(otp_real):
                email = data['payload']['email']
                user = User.objects.get(email=email)
                # Generate tokens
                refresh = RefreshToken.for_user(user)
                access_token = str(refresh.access_token)
                if not user.is_verified:
                    user.is_verified = True
                    user.save()

                    return Response({
                        'access_token': access_token,
                        'refresh_token': str(refresh),
                    }, status=status.HTTP_201_CREATED)
                else:
                    return Response({
                        'message': 'cant verify signup more than once...'
                    }, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({
                    'message': 'OTP didn\'t match...',
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({
                'message': 'OTP expired. Try again!',
                'status': False,
            }, status=status.HTTP_400_BAD_REQUEST)


class UserLoginViewSet(viewsets.ModelViewSet):
    serializer_class = LoginSerializer

    def create(self, request, *args, **kwargs):
        if request.method != 'POST':
            return Response({'message': 'Method not allowed'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
        data = request.data
        email = data.get('email')
        password = data.get('password')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'message': 'User Does Not Exist'}, status=status.HTTP_400_BAD_REQUEST)

        if not user.is_verified:
            return Response({'message': 'please verify your email first'}, status=status.HTTP_400_BAD_REQUEST)

        if not user.check_password(password):
            return Response({'message': 'Invalid Password'}, status=status.HTTP_400_BAD_REQUEST)

        # Generate tokens
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        email_thread = EmailThread(
            subject='Login Successful',
            message=f'Your login to ASLuxeryOriginals.com was successful',
            recipient_list=[email],
        )
        email_thread.start()
        return Response({
            'access_token': access_token,
            'refresh_token': str(refresh),
        }, status=status.HTTP_200_OK)


class SendOTPViewSet(viewsets.ModelViewSet):

    serializer_class = ForgotPasswordSerializer

    # permission_classes = [AllowAny]  # Allow any user (even unauthenticated) to access this viewset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        user = get_object_or_404(User, email=email)
        otp = str(random.randint(100000, 999999))

        payload = {
            'user_id': user.id,
            'email': user.email,
            'otp': otp,
            'exp': datetime.datetime.now() + datetime.timedelta(minutes=5)
        }
        token = create_token(payload)

        send_mail(
            'OTP for Forget Password',
            f'Your OTP is {otp}',
            settings.EMAIL_HOST_USER,
            [user.email],
        )

        return Response({
            'token': token
        }, status=status.HTTP_200_OK)


class CheckOTPViewSet(viewsets.ModelViewSet):
    """
    Viewset for OTP validation and token generation.
    """
    serializer_class = CheckOTPSerializer

    # permission_classes = [IsAuthenticated]  # You can adjust permissions as needed

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        otp = serializer.validated_data['otp']
        enc_token = serializer.validated_data['token']

        data = decrypt_token(enc_token)
        if data['status']:
            otp_real = data['payload']['otp']
            if int(otp) == int(otp_real):
                email = data['payload']['email']
                user = User.objects.get(email=email)
                access_token = str(RefreshToken.for_user(user).access_token)

                return Response(
                    {
                        'access_token': access_token,
                        'status': True,
                    }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'message': 'OTP didn\'t match...',
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({
                'message': 'OTP expired. Try again!',
                'status': False,
            }, status=status.HTTP_400_BAD_REQUEST)


class LogoutViewSet(ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def logout(self, request):
        try:
            refresh_token = request.data.get('refresh_token')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()  # Invalidate the refresh token
                return Response({"detail": "Logout successful."}, status=status.HTTP_200_OK)
            else:
                return Response({"detail": "Refresh token is required."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"detail": "Error during logout.", "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
