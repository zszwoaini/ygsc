import pickle
from collections import OrderedDict

import base64
from QQLoginTool.QQtool import OAuthQQ
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views import View
from drf_haystack.viewsets import HaystackViewSet
from random import randint
from rest_framework.settings import api_settings
from rest_framework_jwt.views import ObtainJSONWebToken
from rest_framework_extensions.cache.mixins import ListCacheResponseMixin,RetrieveCacheResponseMixin,CacheResponseMixin


from libs.captcha import captcha
from mapp import constants
from .utils import *
from .tasks import *

# Create your views here.
from rest_framework import status, filters
from rest_framework.generics import RetrieveAPIView, UpdateAPIView, GenericAPIView, ListAPIView, CreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import mixins
from rest_framework.viewsets import GenericViewSet, ReadOnlyModelViewSet

from .models import *
from .serializers import *

class RegisterUsernameView(APIView):
    #获取参数验证用户名是否存在，查询username的个数
    #count=0不存在
    #count = 1 该用户名已注册
    def get(self,request,username):
        count = User.objects.filter(username=username).count()
        data = {
            'count':count,
            'username':username
        }
        return  JsonResponse(data)
class RegisterMobileView(APIView):
    def get(self,request,mobile):
        count = User.objects.filter(mobile=mobile).count()
        data = {
            'mobile':mobile,
            'count':count
        }
        return JsonResponse(data)
#注册
class RegisterCreateUserView(APIView):
    def post(self,request):
        #接受参数
        data = request.data
        #校检参数
        serializer  = CreateUserSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        # 返回响应
        # 序列化器的操作：将对象转为字典
        # 序列化的操作，是根据序列化器的字段，去获取 模型中的数据，来转换成字典的
        # serializer.data中没有token

        # 在字段中加一个token
        return JsonResponse(serializer.data)
class UserCenterInfoView(RetrieveAPIView):
    serializer_class = UserCenterInfoSerializer
    permission_classes = [IsAuthenticated]
    def get_object(self):
        return self.request.user
# class UserCenterInfoView(APIView):
#     permission_classes = [IsAuthenticated]
#     def get(self,request):
#         user = User.objects.get(id=id)
#         user = request.user
#         serializer = UserCenterInfoSerializer(user)
#         return  Response(serializer.data)

#邮箱激活
# class UserUpdateEmailView(APIView):
#     permission_classes = [IsAuthenticated]
#     def put(self,request):
#         data = request.data
#         user = request.user
#         serializer = EmailSerialzier(instance=user,data=data)
#         serializer.is_valid(raise_exception=True)
#         Serializer.save()
#         return Response(Serializer.data)

class UserUpdateEmailView(UpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = EmailSerialzier
    def get_object(self):
        return self.request.user
#激活邮箱连接
class VerifyEmailView(APIView):
    def get(self,request):
        #获取token
        token = request.query_params.get('token')
        if token is None:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        user = User. check_active_token(token)
        if user is None:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        user.email_avtive = True
        user.save()
        return Response({'msg': 'ok'})
#浏览历史记录
class UserHistroyView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self,request):
        user = request.user
        data = request.data
        serializer = UserHistroySerialzier(data=data)
        serializer.is_valid(raise_exception=True)
        sku_id = serializer.validated_data.get('sku_id')
        redis_conn = get_redis_connection('history')
        redis_conn.lrem('history_%s'% user.id, 0, sku_id)
        redis_conn.lpush('history_%s'%user.id , sku_id)
        redis_conn.ltrim('history_%s'% user.id,0,4)
        return  Response(serializer.data)
    def get(self,request):
        user = request.user
        redis_conn = get_redis_connection('history')
        sku_ids = redis_conn.lrange('history_%s'%user.id,0,5)
        skus=[]
        for sku_id in sku_ids:
            sku = SKU.objects.get(pk=sku_id)
            skus.append(sku)
        serializer = SKUSerialzier(skus,many=True)


        return Response(Serializer.data)
class AreaModelViewSet(CacheResponseMixin,ReadOnlyModelViewSet):
    pagination_class = None
    def get_queryset(self):
        if self.action == 'list':
            return Area.objects.filter(parent=None)
        else:
            return Area.objects.all()
    def get_serializer_class(self):
        if self.action == 'list':
            return  AreaSerializer
        else:
            return SubAreaSerializer

class AddressViewSet(mixins.ListModelMixin,mixins.CreateModelMixin,mixins.UpdateModelMixin,GenericViewSet):
    """
    用户地址新增与修改
    list GET: /users/addresses/
    create POST: /users/addresses/
    destroy DELETE: /users/addresses/
    action PUT: /users/addresses/pk/status/
    action PUT: /users/addresses/pk/title/
    """

    #制定序列化器
    serializer_class = AddressSerializer
    #添加用户权限
    permission_classes = [IsAuthenticated]
    #由于用户的地址有存在删除的状态,所以我们需要对数据进行筛选
    def get_queryset(self):
        return self.request.user.addresses.filter(is_deleted=False)

    def create(self, request, *args, **kwargs):
        """
        保存用户地址数据
        """
        count = request.user.addresses.count()
        if count >= 20:
            return Response({'message':'保存地址数量已经达到上限'},status=status.HTTP_400_BAD_REQUEST)

        return super().create(request,*args,**kwargs)

    def list(self, request, *args, **kwargs):
        """
        获取用户地址列表
        """
        # 获取所有地址
        queryset = self.get_queryset()
        # 创建序列化器
        serializer = self.get_serializer(queryset, many=True)
        user = self.request.user
        # 响应
        return Response({
            'user_id': user.id,
            'default_address_id': user.default_address_id,
            'limit': 20,
            'addresses': serializer.data,
        })

    def destroy(self, request, *args, **kwargs):
        """
        处理删除
        """
        address = self.get_object()

        # 进行逻辑删除
        address.is_deleted = True
        address.save()

        return Response(status=status.HTTP_204_NO_CONTENT)

    from rest_framework.decorators import action

    # addresses/pk/title
    @action(methods=['put'], detail=True)
    def title(self, request, pk=None, address_id=None):
        """
        修改标题
        """
        address = self.get_object()
        serializer = AddressTitleSerializer(instance=address, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(methods=['put'], detail=True)
    def status(self, request, pk=None, address_id=None):
        """
        设置默认地址
        """
        address = self.get_object()
        request.user.default_address = address
        request.user.save()
        return Response({'message': 'OK'}, status=status.HTTP_200_OK)

# class UserAuthorizationView(ObtainJSONWebToken):
#     def post(self, request):
#         response = super().post(request)
#         serializer = self.get_serializer(data=request.data)
#         if serializer.is_valid():
#             user = serializer.validated_data.get('user')
#             response = merge_cookie_to_redis(request,user,response)


# 实现图片验证码
class  RegisterImageCodeView(APIView):
    def get(self,request,image_code_id):
        text , image = captcha.gener_captcha()
        redis_conn = get_redis_connection('code')
        redis_conn.setex('img_%s'%image_code_id,constants.IMAGE_CODE_EXPIRE_TIME,text)
        return HttpResponse(image, content_type='image/jpeg')
#获取短信验证码
class RegisterSMSCodeView(GenericAPIView):
    serializer_class = RegisterSMSCodeSerializer
    def get(self,request,mobile):
        serializer = self.get_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        sms_code = '%06d'%randint(0,999999)
        redis_conn = get_redis_connection('code')
        redis_conn.setex('sms_%s'%mobile,5*60,sms_code)
        send_sms_code.delay(mobile,sms_code)
        return Response({'msg':'ok'})
#第三方登录
class OauthQQURLView(APIView):
    def get(self,request):
        state = '/'
        oauth = OAuthQQ(client_id=settings.QQ_CLIENT_ID,
                        client_secret=settings.QQ_CLIENT_SECRET,
                        redirect_uri=settings.QQ_REDIRECT_URL,
                        # state：用于第三方应用防止CSRF攻击，成功授权后回调时会原样带回
                        state=state)
        # 2.调用对象的方法，获取url
        # 调用OAuthQQ里的方法，用于拼接QQ授权的url
        url = oauth.get_qq_url()
        return Response({'login_url':url})
class OauthQQUserView(APIView):
    def get(self,request):
        code = request.query_params.get('code')
        if code is None:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        oauth = OAuthQQ(client_id=settings.QQ_CLIENT_ID,
                        client_secret=settings.QQ_CLIENT_SECRET,
                        redirect_uri=settings.QQ_REDIRECT_URL,
                        )
        access_token = oauth.get_access_token(code)
        #通过token获取openid
        openid = oauth.get_open_id(access_token)
        # 获取到openid后，我们要查询一下数据库  是否有openid  显示不同页面
        try:
            qquser = OAuthQQUser.objects.get(openid=openid)
        except OAuthQQUser.DoesNotExist:
            # 如果没有 则说明用户没绑定过
            # openid是一个比较敏感的信息，需要加密，最好在设置一个有效期
            access_token = generic_access_token(openid)
            return Response({'access_token': access_token})
        else:
            jwt_payload_handler = api_settings.JWTPAYLOAD_HANDLER
            jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER
            payload = jwt_payload_handler(qquser.user)
            token = jwt_encode_handler(payload)
            return Response({
                'token': token,
                'username': qquser.user.username,
                'user_id': qquser.user.id
            })
    def post(self,request):
        data = request.data
        serializer = OuthQQUserSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        qquser = serializer.save()
        jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
        jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER
        payload = jwt_payload_handler(qquser.user)
        token = jwt_encode_handler(payload)

        return Response({
            "token": token,
            "username": qquser.user.username,
            "user_id": qquser.user.id
        })
#商品首页
class IndexView(View):
    def get(self,request):
        #
        categories = OrderedDict()
        channels = GoodsChannel.objects.order_by('group_id','sequence')
        for channel in channels:
            group_id = channel.group_id
            if group_id not in categories:
                categories[group_id] = {
                    'channels':[],
                    'sub_cats':[]
                }
                one = channel.category
                categories[group_id]['channels'].append({
                    'id':one.id,
                    'name':one.name,
                    'url':channel.url
                })
                for two in one.goodscategory_set.all():
                    two.sub_cats = []
                    for three in two.goodscategory_set.all():
                        two.sub_cats.append(three)

                        # 组织数据
                    categories[group_id]['sub_cats'].append(two)
                    # 广告和首页数据
                contents = {}
                content_categories = ContentCategory.objects.all()
                # content_categories = [{'name':xx , 'key': 'index_new'}, {}, {}]

                # {
                #    'index_new': [] ,
                #    'index_lbt': []
                # }
                for cat in content_categories:
                    contents[cat.key] = cat.content_set.filter(status=True).order_by('sequence')

                # 组织上下文
                context = {
                    'categories': categories,
                    'contents': contents
                }
                # 返回响应
                return render(request, 'index.html', context)
# ######################### 热销商品 ################################

"""
商品页：
热销商品　　用户选择不同的分类时，返回两个热销商品
1.接收商品分类id
2.获取当前分类的商品列表
3.序列化数据
4.返回响应



"""

class HotSKUView(ListAPIView):
    """
    根据分类id获取
    热销商品, 获取之后再将数据转换为JSON
    """
    # 我们设置了默认分页类,这个页面不需要分页,把分页类设置为None
    # 如果不设置会按照分页返回数据,分页的数据 和 不分页的数据结构不一样
    pagination_class = None
    serializer_class = SKUSerialzier
    def get_queryset(self):
        category_id = self.kwargs['category_id']
        return SKU.objects.filter(category_id=category_id, is_launched=True).order_by('-sales')[0:5]
"""
获取商品列表数据

1.获取分类id
2.根据分类获取商品列表，排序，分页
3.序列化数据
4.返回响应



"""
class SKUAPIView(ListAPIView):
    serializer_class = SKUSerialzier
    filter_backends = (filters.OrderingFilter)
    ordering_fields = ('price', 'sales', 'create_time')
    def get_queryset(self):
        category_id = self.kwargs['category_id']
        return SKU.objects.filter(is_launched=True, category_id=category_id)
 ############################# 搜索 #####################################
"""
搜索的步骤   分为两部：
1. elasticsearch 帮助我们实现搜索引擎的功能
    在docker中运行起来

2. haystack  去链接  elasticsearch（需要ip）
    ① 配置haystack
    ② 定义搜索的索引类 让elasticsearch 去分词创建 全文索引
        1.在自应用中创建search_indexes.py文件，编写索引类
        2.创建模板的路径 必须按照文档要求来
            templates/search/indexes/子应用名/模型类名小写_text.txt
        3.执行分词
        python manage.py rebuild_index
    ③ 搜索
"""

class SKUSearchViewSet(HaystackViewSet):
    """
    SKU搜索
    """
    index_models = [SKU]

    serializer_class = SKUIndexSerializer


# #####################################购物车######################

class  CartView(APIView):
    def perform_authentication(self, request):
        pass
    def post(self,request):
        serializer = CartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sku_id = serializer.data.get('sku_id')
        count = serializer.data.get('count')
        selected = serializer.data.get('selected')
        try:
            user = request.user
        except Exception:
            user = None
        if user is not None and user.is_authenticated:
            redis_conn = get_redis_connection('cart')
            redis_conn.hest('cart_%s'%user.id, sku_id)
            if selected:
                redis_conn.sadd('cart_selected_%s' % user.id, sku_id)
            return Response(serializer.data)
        else:
            #未登录：cookie存储
            # 1.读取cookie数据,判断是否存在,在已有数据上进行累加
            cart_str = request.COOKIES.get('cart')
            if cart_str:
                decode = base64.b64decode(cart_str)
                cart = pickle.loads(decode)
            else:
                cart = {}
            if sku_id in cart:
                orginal_count = cart[sku_id]['count']
                count +=orginal_count
            cart[sku_id] = {
                'count':count,
                'selected':selected
            }
            #   对cart进行处理，将字典进行base64编码
            # 将字典转为二进制
            dumps = pickle.dumps(cart)
            # 对二进制进行base64编码

            encode = base64.b64decode(dumps)
            # 将二进制编码转为字符串
            new_cart = encode.decode()
        response = Response(serializer.data)
        response.set_cookie('cart',new_cart,7*24*60*60)
        return response
    def get(self,request):
        try:
            user = request.user

        except Exception:
            user = None
        if user is not None and user.is_authenticated:
            redis_conn = get_redis_connection('cart')
            sku_count = redis_conn.hgetall('cat_%s'%user.id)
            selected_ids = redis_conn.smembers('cart_selected_%s' % user.id)
            cart = {}

            for sku_id,count in sku_count.items():
                if sku_id in selected_ids:
                    selected = True
                else:
                    selectedv= False
                # redis的数据类型是 bytes
                # 转换一下
                cart[int(sku_id)] = {
                    'count':int(count),
                    'selected':selected
                }

        else:
            #未登录用户数据在cookie
            cookie_str = request.COOKIES.get('cart')
            if cookie_str is not None:
                decode = base64.b64decode(cookie_str)
                cart = pickle.loads(decode)
            else:
                cart = {}
        ids = cart.keys()
        skus = SKU.objects.filter(pk__in=ids)
        for sku in skus:
            sku.count = cart[sku.id]['count']
            sku.selected = cart[sku.id]['selected']
        serializer = CartSKUSerializer(skus,many=True)
        return Response(serializer.data)
    def put(self,request):
        serializer = SKUSerialzier(data=request.data)
        serializer.is_valid(raise_exception=True)
        #获取校检字后数据
        sku_id = serializer.data.get('sku_id')
        count = serializer.data.get('count')
        selected = serializer.data.keys('selected')
        try:
            user=request.user
        except Exception:
            user = None
        if user is not None and user.is_authenticated:

            # 4. 登录用户更新redis数据

            redis_conn = get_redis_connection('cart')

            # 直接更新用户提交的数据
            redis_conn.hset('cart_%s'%user.id,sku_id,count)

            if selected:
                redis_conn.sadd('cart_selected_%s'%user.id,sku_id)

            return Response(serializer.data)
        else:
            # 5. 未登录用户更新 cookie数据

            cookie_str = request.COOKIES.get('cart')

            if cookie_str is not None:
                cart = pickle.loads(base64.b64decode(cookie_str))
            else:
                cart = {}

            #更新数据
            #cart = {'id':{'count':5,'selected':1},'id':{'count':5,'selected':1},}
            if sku_id in cart:
                cart[sku_id] = {
                    'count':count,
                    'selected':selected
                }

            #更新cookie数据
            response = Response(serializer.data)

            # dumps
            # encode
            # decode()
            cookie_value = base64.b64encode(pickle.dumps(cart)).decode()

            response.set_cookie('cart',cookie_value,7*24*3600)

            return response
    def delete(self,request):
        serializer = CartDeleteSerializer(data=request.data)
        serializer.is_valid()
        # 2. 获取这个id
        sku_id = serializer.data.get('sku_id')
        # 3. 获取用户的信息
        try:
            user = request.user
        except Exception:
            user = None
        if user is not None and user.is_authenticated:
            # 4. 登录用户操作redis

            redis_conn = get_redis_connection('cart')

            redis_conn.hdel('cart_%s' % user.id, sku_id)

            redis_conn.srem('cart_selected_%s' % user.id, sku_id)

            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            # 5.未登录用户操作cookies

            cookie_str = request.COOKIES.get('cart')

            if cookie_str is not None:
                cart = pickle.loads(base64.b64decode(cookie_str))
            else:
                cart = {}

            # 删除数据
            if sku_id in cart:
                del cart[sku_id]

            # 把新的cookie数据写入到 浏览器中
            response = Response(status=status.HTTP_204_NO_CONTENT)

            cookie_value = base64.b64encode(pickle.dumps(cart)).decode()

            response.set_cookie('cart', cookie_value, 7 * 24 * 3600)

            return response

class PlaceOrderView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self,request):
        user = request.user
        redis_conn = get_redis_connection('cart')
        redis_cart = redis_conn.hegetall('cart_%s'%user.id)
        redis_selected_ids = redis_conn.smembers('cart_selected_%s'%user.id)
        cart = {}
        for sku_id in redis_selected_ids:
            cart[int(sku_id)] = int(redis_cart[sku_id])
        skus = SKU.objects.filter(pk__in=cart.keys())
        for sku in skus:
            sku.count = cart[sku.id]
        freight = Decimal('10.00')
        serializer = OrderSettlementSerializer({'skus': skus, 'freight': freight})
        return Response(serializer.data)

    class OrderView(CreateAPIView):

        """
        # 1.必须是登录用户
        # 2.提交了一些数据(address,pay_method),我们根据(user,order_id)数据生成订单
        # 3.订单商品只能在 有了订单之后 才能入库
        """

        # 1.必须是登录用户
        permission_classes = [IsAuthenticated]

        serializer_class = OrderSerializer


############################################支付宝支付####################################
class PaymentView(APIView):
    def get(self,request,order_id):
        try:
            order = OrderInfo.objects.get(
                order_id=order_id,
                status = OrderInfo.ORDER_STATUS_ENUM['UNPAID'],
                user = request.user
            )
        except OrderInfo.DoesNotExist:
            return  Response(status=status.HTTP_400_BAD_REQUEST)
        alipay = Alipay(
            appid = settings.ALIPAY_APPID,
            app_notify_url = None,
            app_private_key_path = settings.APP_PRIVATE_KEY_PATH,
            alipay_public_key_path=settings.ALIPAY_PUBLIC_KEY_PATH,  # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=True  # 默认False


        )
        # 3. order_string 生成支付的 order_string
        subject = "测试订单"
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_id,  # 订单号 商城生成的
            total_amount=str(order.total_amount),  # 价格 Decimal 转换为string
            subject=subject,
            return_url="http://www.meiduo.site:8080/pay_success.html"
        )
        alipay_url = 'https://openapi.alipaydev.com/gateway.do?' + order_string

        return Response({'alipay_url': alipay_url})
class PaymentStatusView(APIView):
    def put(self,request):
        data = request.query_params.dict()
        signature = data.pop('sign')
        alipay = Alipay(
            appid=settings.ALIPAY_APPID,  # APPID
            app_notify_url=None,  # 默认回调url
            app_private_key_path=settings.APP_PRIVATE_KEY_PATH,
            alipay_public_key_path=settings.ALIPAY_PUBLIC_KEY_PATH,  # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=True  # 默认False
        )
        success = alipay.verify(data, signature)
        if success:
            trade_no = data.get('trade_no')
            out_trade_no = data.get('out_trade_no')

            order = OrderInfo.objects.get(order_id=out_trade_no)
            Payment.objects.create(
                order=order,
                trade_id=trade_no
            )
            # 3. 改变订单的状态
            OrderInfo.objects.filter(order_id=out_trade_no).update(status=OrderInfo.ORDER_STATUS_ENUM['UNSEND'])
        return Response({'trade_no': trade_no})










