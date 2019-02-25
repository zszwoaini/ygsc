from django.conf import settings
from itsdangerous import TimedJSONWebSignatureSerializer as Serizlizer, BadSignature


def generic_verify_url(req,user_id,email):
    serializer = Serizlizer(settings.SECRET_KEY)
    data = {
        'user_id':user_id,
        'email':email
    }
    #加密
    token = serializer.dumps(data)
    return 'http://www.mmrx.site:8080/success_verify_email.html?token=' + token.decode()
def check_active_token(token):
    serializer = Serizlizer(settings.SCRET_KEY)
    try :
        result = serializer.loads(token)
    except BadSignature:
        return None
    return result.get('user_id')

#QQ登录
def generic_access_token(openid):
    serializer = Serizlizer(settings.SECRET_KEY,3600)
    token = serializer.dumps({'openid':openid})
    return token.decode()
def check_access_token(token):
    serializer = Serizlizer(settings.SECRET_KEY,3600)
    try:
        result = serializer.loads((token))
    except BadSignature:
        return None
    return result.get('openid')

