import random
import datetime
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from django.contrib.auth.hashers import make_password
from customuser.models import User
from rest_framework.viewsets import ViewSet
from .serializers import UserSignupSerializer, LoginSerializer, EmailVerificationSerializer, ForgotPasswordSerializer, \
    CheckOTPSerializer, CheckSignupOTPSerializer, UserprofileSerializer
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
import jwt
from .utils import Util
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.core.mail import send_mail
from rest_framework.permissions import AllowAny, IsAuthenticated
from .security import create_token, decrypt_token
import os
from dotenv import load_dotenv

load_dotenv()


class UserProfileViewSet(viewsets.ModelViewSet):
    class UserProfileViewSet(viewsets.ModelViewSet):
        """
        ViewSet for reading and editing the user's profile.
        """
        serializer_class = UserprofileSerializer
        queryset = User.objects.all()
        permission_classes = [IsAuthenticated]

        def get_queryset(self):
            """
            Restrict the queryset to the currently authenticated user.
            """
            return User.objects.filter(id=self.request.user.id)

        def update(self, request, *args, **kwargs):
            """
            Allow authenticated users to update their profile (name and email).
            """
            partial = kwargs.pop('partial', False)
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)

            return Response(serializer.data)


class UserSignupViewSet(viewsets.ModelViewSet):
    serializer_class = UserSignupSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):

        if request.method != 'POST':
            return Response({'message': 'Method not allowed'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
        data = request.data
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        print(serializer)
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

            send_mail(
                'OTP for signup',
                f'Your OTP is {otp}',
                settings.EMAIL_HOST_USER,
                [user.email],
            )

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
            token = RefreshToken(refresh_token)
            token.blacklist()  # Invalidate the refresh token
            return Response({"detail": "Logout successful."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"detail": "Error during logout.", "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
