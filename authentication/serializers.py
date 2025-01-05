from customuser.models import User
from rest_framework import serializers


class ForgotPasswordRequestSerializer(serializers.Serializer):
    otp = serializers.CharField(max_length=6, required=True)
    email = serializers.EmailField(required=True)
    new_password = serializers.CharField(write_only=True, required=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, required=True, min_length=8)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return attrs


class UserProfileSerializer(serializers.Serializer):
    otp = serializers.CharField(max_length=6, required=True)
    new_email = serializers.CharField(write_only=True, required=True, min_length=8)
    new_first_name = serializers.CharField(write_only=True, required=True, min_length=8)
    new_last_name = serializers.CharField(write_only=True, required=True, min_length=8)


class ViewUserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email', 'phone_number']


class PasswordChangeRequestSerializer(serializers.Serializer):
    otp = serializers.CharField(max_length=6, required=True)
    new_password = serializers.CharField(write_only=True, required=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, required=True, min_length=8)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return attrs


class UserSignupSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=100, required=False)
    last_name = serializers.CharField(max_length=100, required=False)
    phone_number = serializers.CharField(max_length=15, required=False)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    verify_password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, data):

        if data['password'] != data['verify_password']:
            raise serializers.ValidationError("Passwords do not match.")
        return data


class UserSignupSerializerOTP(serializers.Serializer):
    otp = serializers.CharField(max_length=6)
    email = serializers.EmailField()


class UserSignupSerializerResendOTP(serializers.Serializer):
    email = serializers.EmailField()


class EmailVerificationSerializer(serializers.ModelSerializer):
    token = serializers.CharField(max_length=555)

    class Meta:
        model = User
        fields = ['token']


class LoginSerializer(serializers.ModelSerializer):
    password = serializers.CharField(max_length=50, min_length=6, write_only=True)
    email = serializers.EmailField(max_length=50, min_length=2)

    class Meta:
        model = User
        fields = ['email', 'password']


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'first_name', 'last_name', 'email')
        read_only_fields = ['email', ]


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.CharField(max_length=100)


class CheckOTPSerializer(serializers.Serializer):
    otp = serializers.CharField(max_length=6)
    token = serializers.CharField()


class CheckSignupOTPSerializer(serializers.Serializer):
    otp = serializers.CharField(max_length=6)
    token = serializers.CharField()
