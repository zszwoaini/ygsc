import re
from django.contrib.auth.backends import ModelBackend
from rest_framework.mixins import CreateModelMixin

from mapp.models import User
def jwt_response_payload_handler(token,user=None,request=None):
    #token:JWT生成的token
    #user:就是认证之后的user --- 相当于User模型类的对象
    return {
        'token':token,
        'user_id':user.id,
        'username':user.username

    }

def get_user(username):
    try:
        if re.match('1[3-9]\d{9}',username):
            user = User.objects.get(mobile=username)
        else:
            user = User.objects.get(username=username)
    except User.DoesNoExist:
        return None
    else:
        return user

class UsernameMobileModelBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        user = get_user(username)
        if user is not None and user.check_password(password):
            return user
