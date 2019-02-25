from django.conf.urls import url
from . import views

from rest_framework_jwt.views import obtain_jwt_token


from .views import *




urlpatterns = [
    url(r'^usernames/(?P<username>\w{5,20})/count/$',views.RegisterUsernameView.as_view()),
    url(r'^phones/(?P<mobile>1[345789]\d{9})/count/$',views.RegisterMobileView.as_view(), name='phonecount'),
    url(r"zuce/",views.RegisterCreateUserView.as_view(),name='zuce'),
    url(r'^auths/$', obtain_jwt_token),
    url(r'^infos/$',views.UserCenterInfoView.as_view()),
    url(r'^emails/$',views.UserUpdateEmailView.as_view()),
    url(r'^emails/verification/$',views.VerifyEmailView.as_view()),

    url(r'^browerhistories/$', views.UserHistroyView.as_view()),
    url(r'^imagecodes/(?P<image_code_id>.+)/$', views.RegisterImageCodeView.as_view(), name='imagecode'),


    url(r'^smscodes/(?P<mobile>1[345789]\d{9})/$',views. RegisterSMSCodeView.as_view()),
    url(r'^qq/statues/$', views.OauthQQURLView.as_view()),
    url(r'^qq/users/$', views.OauthQQUserView.as_view()),
    url(r'^index/$',views.IndexView.as_view()),


    url(r'^categories/(?P<category_id>\d+)/hotskus/$', views.HotSKUView.as_view()),


    url(r'^categories/(?P<category_id>\d+)/skus/$',views.SKUListAPIView.as_view()),
    url(r'^$',views.CartView.as_view(),name='cart'),
    url(r'^places/$', views.PlaceOrderView.as_view(), name='placeorder'),
    url(r'^$', views.OrderView.as_view()),
    url(r'^orders/(?P<order_id>\d+)/$',views.PaymentView.as_view(),name='pay'),
    url(r'^status/$', views.PaymentStatusView.as_view()),

]

from rest_framework.routers import DefaultRouter
router = DefaultRouter()
router.register(r'addresses',AddressViewSet,base_name='address')
urlpatterns += router.urls

router.register(r'infon',AreaModelViewSet,base_name='area')

urlpatterns += router.urls


router.register('search', views.SKUSearchViewSet, base_name='skus_search')

urlpatterns += router.urls