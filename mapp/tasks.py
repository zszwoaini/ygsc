from celery import task
from django.conf import settings
from django.core.mail import send_mail

from libs.yuntongxun.sms import CCP
from mapp.utils import generic_verify_url


@task
def send_verify_email(user_id,email):
    content = "易购商城邮箱激活"
    message = ''
    from_email = settings.DEFAULT_FROM_EMAIL
    reciver = [email]
    url = generic_verify_url(user_id,email)
    html_message = '<p>尊敬的用户您好！</p>' \
                   '<p>感谢您使用易购商城。</p>' \
                   '<p>您的邮箱为：%s 。请点击此链接激活您的邮箱：</p>' \
                   '<p><a href="%s">%s<a></p>' % (from_email,url, url)
    send_mail(
        content=content,
        message=message,
        from_email=from_email,
        reciver=reciver,
        html_message=html_message
    )
@task
def send_sms_code(mobile,sms_code):
    ccp = CCP()
    CCP.send_template_sms(mobile,[sms_code,5],1)
