import random
import datetime
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from rest_framework.viewsets import ViewSet

from customuser import models
from .serializers import UserSignupSerializer, LoginSerializer, EmailVerificationSerializer, ForgotPasswordSerializer, \
    CheckOTPSerializer, CheckSignupOTPSerializer
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
import jwt
from .utils import Util, generate_otp
from django.contrib.sites.shortcuts import get_current_site
from django.urls import reverse
from django.conf import settings
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from django.shortcuts import get_object_or_404
from django.core.mail import send_mail
from rest_framework.permissions import AllowAny, IsAuthenticated
from .security import create_token, decrypt_token
import os
from dotenv import load_dotenv
load_dotenv()


class UserSignupViewSet(viewsets.ModelViewSet):
    serializer_class = UserSignupSerializer

    def create(self, request, *args, **kwargs):
        data = request.data
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)

        email = data['email']

        # Check if the user already exists
        existing_user = models.User.objects.filter(email=email).first()
        if existing_user:
            if not existing_user.is_verified:
                return Response({'message': 'User exists but is not verified. Please verify your email.'},
                                status=status.HTTP_400_BAD_REQUEST)
            return Response({'message': 'User Already Exists'}, status=status.HTTP_400_BAD_REQUEST)

        # Create a new user
        user = models.User.objects.create(
            first_name=data['first_name'],
            last_name=data['last_name'],
            email=email,
            password=make_password(data['password'])
        )

        # Generate OTP
        otp = generate_otp()

        # Generate token
        token = create_token({
            'user_id': user.id,
            'email': user.email,
            'otp': otp,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=5),
        })

        # Send OTP via email
        try:
            send_mail(
                'OTP for Signup',
                f'Your OTP is {otp}',
                settings.EMAIL_HOST_USER,
                [user.email],
            )
        except Exception as e:
            return Response({'message': 'Failed to send OTP email', 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Respond with token
        return Response({'token': token}, status=status.HTTP_201_CREATED)


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
                user = models.User.objects.get(email=email)
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
            user = models.User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'message': 'User Does Not Exist'}, status=status.HTTP_400_BAD_REQUEST)

        if not user.is_verified:
            return Response({'message': 'please verify your email first'}, status=status.HTTP_400_BAD_REQUEST)

        if not user.check_password(password):
            return Response({'message': 'Invalid Password'}, status=status.HTTP_400_BAD_REQUEST)

        # Generate tokens
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        subject = "login"
        message = "your login was successful."
        from_email = os.getenv("EMAIL")
        recipient_list = [data.get('email')]

        send_mail(subject, message, from_email, recipient_list, fail_silently=False)
        return Response({
            'access_token': access_token,
            'refresh_token': str(refresh),
        }, status=status.HTTP_200_OK)


class SendOTPViewSet(viewsets.ModelViewSet):
    """
    Viewset for handling forget password functionality.
    """
    serializer_class = ForgotPasswordSerializer

    # permission_classes = [AllowAny]  # Allow any user (even unauthenticated) to access this viewset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        user = get_object_or_404(models.User, email=email)
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
                user = models.User.objects.get(email=email)
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
            token = RefreshToken(refresh_token)
            token.blacklist()  # Invalidate the refresh token
            return Response({"detail": "Logout successful."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"detail": "Error during logout.", "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)