import requests
import random
import datetime
from django.utils import timezone
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from django.contrib.auth.hashers import make_password
from rest_framework.exceptions import AuthenticationFailed
from customuser.models import User
from rest_framework.viewsets import ViewSet
from .serializers import UserSignupSerializer, LoginSerializer, ForgotPasswordSerializer, CheckOTPSerializer, \
    PasswordChangeRequestSerializer, UserProfileSerializer, ForgotPasswordRequestSerializer, \
    VerifyOtpSerializer, ResendOtpSerializer
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from .utils import EmailThread
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.core.mail import send_mail
from rest_framework.permissions import AllowAny, IsAuthenticated
from .security import create_token, decrypt_token
from rest_framework.response import Response
from .models import EmailChangeRequest, PasswordChangeRequest, ForgotPasswordRequest
from django.utils.timezone import now


class ForgotPasswordViewSet(viewsets.ModelViewSet):
    queryset = ForgotPasswordRequest.objects.all()
    serializer_class = ForgotPasswordRequestSerializer

    @action(detail=False, methods=['post'], url_path='request-forgot-password')
    def request_forgot_password(self, request):
        """
        Step 1: Send an email with a URL to reset the password.
        """
        email = request.data.get('email')
        if not email:
            return Response({"error": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(email=email).first()
        if not user:
            return Response({"error": "No user found with this email."}, status=status.HTTP_400_BAD_REQUEST)

        reset_url = f"http://127.0.0.1:8000/auth/forgot-password/set-new-password/?email={email}"
        email_thread = EmailThread(
            subject='Password Reset Request',
            message=f"Click the following link to reset your password: {reset_url}",
            recipient_list=[email],
        )
        email_thread.start()

        return Response({"message": "A password reset link has been sent to your email."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='set-new-password')
    def set_new_password(self, request):
        """
        Step 2: Accept new password and send OTP to email.
        """
        email = request.data.get('email')
        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_password')

        if not email or not new_password or not confirm_password:
            return Response({"error": "Email, new_password, and confirm_password are required."},
                            status=status.HTTP_400_BAD_REQUEST)

        if new_password != confirm_password:
            return Response({"error": "Passwords do not match."}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(email=email).first()
        if not user:
            return Response({"error": "No user found with this email."}, status=status.HTTP_400_BAD_REQUEST)

        ForgotPasswordRequest.objects.filter(user=user).delete()
        otp = random.randint(100000, 999999)

        email_thread = EmailThread(
            subject='Forgot Password OTP',
            message=f"Your OTP for password reset is: {otp}",
            recipient_list=[email],
        )
        email_thread.start()

        ForgotPasswordRequest.objects.create(user=user, otp=otp, new_password=new_password)

        return Response({"message": "An OTP has been sent to your email."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='verify-otp')
    def verify_otp(self, request):
        """
        Step 3: Verify OTP and update password.
        """
        email = request.data.get('email')
        otp = request.data.get('otp')

        if not email or not otp:
            return Response({"error": "Email and OTP are required."}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(email=email).first()
        if not user:
            return Response({"error": "No user found with this email."}, status=status.HTTP_400_BAD_REQUEST)

        forgot_password_request = ForgotPasswordRequest.objects.filter(user=user).first()
        if not forgot_password_request:
            return Response({"error": "No pending forgot password request found."}, status=status.HTTP_400_BAD_REQUEST)

        if str(forgot_password_request.otp) != str(otp):
            return Response({"error": "Incorrect OTP."}, status=status.HTTP_400_BAD_REQUEST)

        otp_age = (timezone.now() - forgot_password_request.created_at).total_seconds()
        if otp_age > 300:
            return Response({"error": "OTP has expired. Please request a new one."}, status=status.HTTP_400_BAD_REQUEST)

        user.password = make_password(forgot_password_request.new_password)
        if not user.is_verified:
            user.is_verified = True
        user.save()

        forgot_password_request.delete()

        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        return Response({
            'message': 'Password reset successful.',
            'access_token': access_token,
            'refresh_token': str(refresh),
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='resend-otp')
    def resend_otp(self, request):
        """
        Step 4: Resend OTP if expired or invalid.
        """
        email = request.data.get('email')

        if not email:
            return Response({"error": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(email=email).first()
        if not user:
            return Response({"error": "No user found with this email."}, status=status.HTTP_400_BAD_REQUEST)

        forgot_password_request = ForgotPasswordRequest.objects.filter(user=user).first()
        if not forgot_password_request:
            return Response({"error": "No pending forgot password request found."}, status=status.HTTP_400_BAD_REQUEST)

        # Generate a new OTP
        otp = random.randint(100000, 999999)
        forgot_password_request.otp = otp
        forgot_password_request.created_at = timezone.now()
        forgot_password_request.save()

        email_thread = EmailThread(
            subject='Forgot Password OTP - Resent',
            message=f"Your new OTP for password reset is: {otp}",
            recipient_list=[email],
        )
        email_thread.start()

        return Response({"message": "A new OTP has been sent to your email."}, status=status.HTTP_200_OK)


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
        email_thread = EmailThread(
            subject='Email Change OTP',
            message=f"Your OTP is: {otp}",
            recipient_list=[new_email],
        )
        email_thread.start()

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

        PasswordChangeRequest.objects.filter(user=user).delete()
        otp = random.randint(100000, 999999)

        email_thread = EmailThread(
            subject='Password Change OTP',
            message=f"Your OTP for password change is: {otp}",
            recipient_list=[user.email],
        )
        email_thread.start()

        PasswordChangeRequest.objects.create(user=user, otp=otp, new_password=new_password)

        return Response({"message": "An OTP has been sent to your email."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='resend-otp')
    def resend_otp(self, request):
        """
        Request a new OTP if the previous one has expired or was invalid.
        """
        user = request.user

        password_change_request = PasswordChangeRequest.objects.filter(user=user).first()

        if not password_change_request:
            return Response({"error": "No pending password change request found."}, status=status.HTTP_400_BAD_REQUEST)

        otp = random.randint(100000, 999999)
        password_change_request.otp = otp
        password_change_request.created_at = timezone.now()
        password_change_request.save()

        email_thread = EmailThread(
            subject='Password Change OTP - Resent',
            message=f"Your new OTP for password change is: {otp}",
            recipient_list=[user.email],
        )
        email_thread.start()

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

        if str(password_change_request.otp) != str(otp):
            return Response({"error": "Incorrect OTP."}, status=status.HTTP_400_BAD_REQUEST)

        otp_age = (timezone.now() - password_change_request.created_at).total_seconds()
        if otp_age > 300:
            return Response({"error": "OTP has expired. Please request a new one."}, status=status.HTTP_400_BAD_REQUEST)

        user.password = make_password(password_change_request.new_password)
        user.save()

        password_change_request.delete()

        refresh_token = request.data.get('refresh_token')
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except Exception as e:
                raise AuthenticationFailed('Refresh token is invalid or expired.')
        return Response({"message": "Password changed successfully. You have been logged out."},
                        status=status.HTTP_200_OK)


class UserSignupViewSet(viewsets.ViewSet):
    """
    Viewset for handling user signup and OTP verification.
    """

    serializer_class = UserSignupSerializer

    def create(self, request, *args, **kwargs):
        """
        Handles user signup.
        """
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Extracting the email and password (the passwords are now validated in the serializer)
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']

        # Check if the user already exists
        user = User.objects.filter(email=email).first()

        if user:
            if not user.is_verified:
                otp = random.randint(100000, 999999)
                user.otp = otp
                user.otp_created_at = now()
                user.save()

                email_thread = EmailThread(
                    subject='Verify your email',
                    message=f'Your OTP is: {otp}',
                    recipient_list=[email],
                )
                email_thread.start()

                return Response({"message": "User already exists but is not verified. OTP resent."}, status=status.HTTP_200_OK)
            else:
                return Response({"error": "User already exists and is verified."}, status=status.HTTP_400_BAD_REQUEST)

        # Create new user
        otp = random.randint(100000, 999999)
        user = User.objects.create(
            first_name=serializer.validated_data['first_name'],
            last_name=serializer.validated_data['last_name'],
            email=email,
            password=make_password(password),  # Using the password validated in the serializer
            otp=otp,
            otp_created_at=now()
        )

        email_thread = EmailThread(
            subject='Verify your email',
            message=f'Your OTP is: {otp}',
            recipient_list=[email],
        )
        email_thread.start()

        return Response({"message": "Signup successful. OTP sent to your email."}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='verify-otp')
    def verify_otp(self, request):
        """
        Verifies the OTP sent to the user's email.
        """
        serializer = VerifyOtpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        otp = serializer.validated_data['otp']

        user = User.objects.filter(email=email).first()
        if not user:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        if user.is_verified:
            return Response({"error": "User is already verified."}, status=status.HTTP_400_BAD_REQUEST)

        if str(user.otp) != otp:
            return Response({"error": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST)

        if now() - user.otp_created_at > datetime.timedelta(minutes=5):
            return Response({"error": "OTP has expired."}, status=status.HTTP_400_BAD_REQUEST)

        user.is_verified = True
        user.otp = None
        user.save()

        return Response({"message": "User verified successfully."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='resend-otp')
    def resend_otp(self, request):
        """
        Resends the OTP to the user's email.
        """
        serializer = ResendOtpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        user = User.objects.filter(email=email).first()
        if not user:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        if user.is_verified:
            return Response({"error": "User is already verified."}, status=status.HTTP_400_BAD_REQUEST)

        otp = random.randint(100000, 999999)
        user.otp = otp
        user.otp_created_at = now()
        user.save()

        email_thread = EmailThread(
            subject='Resend OTP',
            message=f'Your OTP is: {otp}',
            recipient_list=[email],
        )
        email_thread.start()

        return Response({"message": "OTP resent to your email."}, status=status.HTTP_200_OK)


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
