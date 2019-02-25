from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django_redis import get_redis_connection
from rest_framework import serializers

from mapp.tasks import send_verify_email
from mapp.models import *
from mapp.utils import *


class CreateUserSerializer(serializers.ModelSerializer):

    password2 = serializers.CharField(label='确认密码', write_only=True, allow_null=False, allow_blank=False)
    sms_code = serializers.CharField(label='短信验证码', max_length=6, min_length=6, allow_null=False, allow_blank=False,
                                     write_only=True)
    allow = serializers.CharField(label='是否同意协议', allow_null=False, allow_blank=False, write_only=True)
    token = serializers.CharField(label='token',read_only=True)
    class Meta:
        model = User
        fields = ['id','username','password','mobile','password2','sms_code','allow','token']

        extra_kwargs = {
            'id':{
                'read_only':True
            },
            'username': {
                'min_length': 5,
                'max_length': 20,
                'error_messages': {
                    'min_length': '仅允许5-20个字符的用户名',
                    'max_length': '仅允许5-20个字符的用户名',
                }
            },
            'password': {
                'write_only': True,
                'min_length': 8,
                'max_length': 20,
                'error_messages': {
                    'min_length': '仅允许8-20个字符的密码',
                    'max_length': '仅允许8-20个字符的密码',
                }
            }
        }

    # 我们需要把 用户名 密码,确认密码,手机号,短信验证码, 是否同意

    # 单个字段校验
    # 手机号,是否同意r

    def validate_mobile(self,value):
        import re
        if not re.match(r'1[3-9]\d{9}',value):
            raise serializers.ValidationError('手机号错误')

        return value

    def validate_allow(self,value):

        if value != 'true':
            raise serializers.ValidationError('您未同一协议')

        return value
    # 多个字段校验
    # 密码  确认密码 短信验证码

    def validate(self, attrs):

        # 1.密码
        password = attrs.get('password')
        password2 = attrs.get('password2')

        if password2 != password:
            raise serializers.ValidationError('密码不一致')

        # 2.短信验证码
        # 获取用户提交的验证码
        code = attrs.get('sms_code')

        # 获取redis的验证码
        redis_conn = get_redis_connection('code')

        # 获取之后进行判断
        redis_code = redis_conn.get('sms_%s'%attrs.get('mobile'))
        if redis_code is None:
            raise serializers.ValidationError('验证码已过期')

        # 校验
        # redis的值  是bytes类型
        if redis_code.decode() != code:
            raise serializers.ValidationError('验证码错误')

        return attrs


        # 重写 create方法


    def create(self, validated_data):
        # 系统在调用此方法时，validated_data多了一些字段，且这些字段不在模型中
        # 创建用户依靠的是fields字段里的信息
        # 所以在创建用户之前，先将validate_data中多余的字段删除


        del validated_data['password2']
        del validated_data['allow']
        del validated_data['sms_code']

        # 重新入库
        user = User.objects.create(**validated_data)

        # 重新设置密码并加密

        user.set_password(validated_data['password'])
        # 保存密码
        user.save()

        # 我们需要在这里  生成一个登陆的token
        from rest_framework_jwt.settings import api_settings

        # 获取这rest_framework_jwt两个方法
        jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
        jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER

        # 用户信息调用给data
        data = jwt_payload_handler(user)
        #编码
        token = jwt_encode_handler(data)

        # 给user添加了字段,序列化
        user.token = token

        return user



class UserCenterInfoSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ['username','mobile','email','email_active']


class EmailSerialzier(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = [ 'email']
        extra_kwargs = {
            'email': {
                'required': True
            }
        }

    def update(self, instance, validated_data):

        # 更新数据

        email = validated_data.get('email')

        instance.email = email
        instance.save()
        send_verify_email.delay(instance.id,email)

        return instance


class AddressSerializer(serializers.ModelSerializer):

    province = serializers.StringRelatedField(read_only=True)
    city = serializers.StringRelatedField(read_only=True)
    district = serializers.StringRelatedField(read_only=True)
    province_id = serializers.IntegerField(label='省ID', required=True)
    city_id = serializers.IntegerField(label='市ID', required=True)
    district_id = serializers.IntegerField(label='区ID', required=True)
    mobile = serializers.RegexField(label='手机号', regex=r'^1[3-9]\d{9}$')

    class Meta:
        model = Address
        exclude = ('user', 'is_deleted', 'create_time', 'update_time')


    def create(self, validated_data):
        # 因为没有让前端传递user_id，所以执行
        # Address.objects.create(**validated_data)的时候,缺少了user
        # 会报错
        #Address模型类中有user属性,将user对象添加到模型类的创建参数中
        validated_data['user'] = self.context['request'].user
        # super() 会调用 ModelSerialzier 的create方法
        return super().create(validated_data)

class AddressTitleSerializer(serializers.ModelSerializer):
        """
        地址标题
        """

        class Meta:
            model = Address
            fields = ('title',)



class UserHistroySerialzier(serializers.Serializer):

    sku_id = serializers.CharField(label='id',write_only=True)


    def validate(self, attrs):

        sku_id = attrs.get('sku_id')
        # 判断商品是否存在
        try:
            sku = SKU.objects.get(pk=sku_id)

        except SKU.DoesNotExist:

            raise serializers.ValidationError('商品不存在')



        return attrs

class SKUSerialzier(serializers.ModelSerializer):

    class Meta:
        model = SKU
        fields = ('id','name','price','default_image_url','comments')


class AreaSerializer(serializers.ModelSerializer):
    """
       序列化器

       [{'id:1,'name':'xxxx'},{'id:1,'name':'xxxx'}{'id:1,'name':'xxxx'}]
       """

    class Meta:
        model = Area
        fields = ['id','name']

class SubAreaSerializer(serializers.ModelSerializer):

    # related_name='subs'
    # 因为我设置了 修改 关联模型 的名字
    # area_set = AreaSerializer(many=True,read_only=True)
    subs = AreaSerializer(many=True, read_only=True)

    class Meta:
        model = Area
        fields = ('id', 'name', 'subs')
#验证码
class RegisterSMSCodeSerializer(serializers.Serializer):
    text = serializers.CharField(label='图片验证码',max_length=4,min_length=4,required=True)
    image_code_id = serializers.UUIDField(label='uuid')
    def validate(self, attrs):
        text = attrs.get('text')
        image_code_id = attrs.get('image_code_id')
        redis_conn = get_redis_connection('code')
        redis_text = redis_conn.get('img_%s'%image_code_id)
        if redis_text is None:
            raise  serializers.ValidationError("验证码过期")
        redis_conn.delete('img_%s'%image_code_id)
        print(redis_text)
        if redis_text.decode().lower() != text.lower:
            raise serializers.ValidationError('输入验证码不一致')
        return attrs
class OuthQQUserSerializer(serializers.Serializer):
    access_token = serializers.CharField(label='凭证')
    mobile = serializers.RegexField(label='手机号', regex=r'^1[3-9]\d{9}$')
    password = serializers.CharField(label='密码', max_length=20, min_length=8)
    sms_code = serializers.CharField(label='短信验证码')
    def validate(self, attrs):
        sms_code = attrs.get('sms_code')
        mobile = attrs.get('mobile')
        redis_conn = get_redis_connection('code')
        redis_code = redis_conn.get('sms_%s'%mobile)
        if redis_code is None:
            raise serializers.ValidationError('短信验证码过期')
        if redis_code.decode() != sms_code:
            raise serializers.ValidationError('验证码不一致')
        access_token = attrs.get('access_token')
        openid = check_access_token(access_token)
        if openid is None:
            raise  serializers.ValidationError('不正确')
        attrs['openid'] = openid
        try:
            user = User.objects.get(mobile=mobile)
        except User.DoesNotExist:
            pass
        else:
            if not user.check_password(attrs['password']):
                raise serializers.ValidationError('密码正确')
            attrs['user'] = user
        raise  attrs
    def create(self,validaed_data):
        user = validaed_data.get('user')
        if user is None:
            user = User.objects.create(
                username = validaed_data.get('username'),
                mobile = validaed_data.get('mobile'),
                password = validaed_data.gt('password')

            )
            user.set_password(validaed_data.get('password')
                              )
            user.save()
            #给绑定用户模型数据入库
            OAuthQQUser.objects.create(
                openid = validaed_data.get('openid'),
                user = user

            )
            return user

class SKUSerializer(serializers.ModelSerializer):

    class Meta:
        model = SKU
        fields = ('id', 'name', 'price', 'default_image_url', 'comments')


from .search_indexes import SKUIndex
from drf_haystack.serializers import HaystackSerializer

class SKUIndexSerializer(HaystackSerializer):
    """
    SKU索引结果数据序列化器
    """
    class Meta:
        index_classes = [SKUIndex]
        fields = ('text', 'id', 'name', 'price', 'default_image_url', 'comments')
class CartSerializer(serializers.Serializer):
    sku_id = serializers.IntegerField(label='sku_id', required=True, min_value=1)
    count = serializers.IntegerField(label='数量', required=True, min_value=1)
    selected = serializers.BooleanField(label='是否勾选', required=False, default=True)
    def validate(self, attrs):
        try:
            sku = SKU.objects.get(pk = attrs.get('sku_id'))
        except SKU.DoesNoExist:
            raise serializers.ValidationError('商品不存在')
        if sku.stock < attrs.get('count'):
            raise serializers.ValidationError('库存不足')
        return attrs
class CartSKUSerializer(serializers.ModelSerializer):

    count = serializers.IntegerField(label='数量')
    selected = serializers.BooleanField(label='是否勾选')

    class Meta:
        model = SKU
        fields = ('id','count', 'name', 'default_image_url', 'price', 'selected')


class CartDeleteSerializer(serializers.Serializer):

    sku_id = serializers.IntegerField(label='商品id',min_value=1)

    def validate(self, attrs):

        #判断商品是否存在
        try:
            sku = SKU.objects.get(pk=attrs['sku_id'])
        except SKU.DoesNotExist:
            raise serializers.ValidationError('商品不存在')

        return attrs
class CartGoodSerializer(serializers.ModelSerializer):
    """
    购物车商品数据序列化器
    """
    count = serializers.IntegerField(label='数量')

    class Meta:
        model = SKU
        fields = ('id', 'name', 'default_image_url', 'price', 'count')
class OrderSettlementSerializer(serializers.Serializer):
    """
    订单结算数据序列化器
    """
    freight = serializers.DecimalField(label='运费', max_digits=10, decimal_places=2)
    skus = CartGoodSerializer(many=True)
class OrderSerializer(serializers.ModelSerializer):
    pass

    class Meta:
        model = OrderInfo
        fields = ('order_id', 'address', 'pay_method')
        read_only_fields = ('order_id',)
        extra_kwargs = {
            'address': {
                'write_only': True,
                'required': True,
            },
            'pay_method': {
                'write_only': True,
                'required': True
            }
        }

    def create(self,validated_data):
        user = self.context['request'].user
        order_id = timezone.now().strftime('%Y%m%d%H%M%S%f') + ('%09d'%user.id)
        address = validated_data.get('address')

        # 2.4 初始化数量 价格和运费
        total_count = 0
        total_amount = 0
        freight = Decimal('10.00')

        #2.5 pay_method
        pay_method = validated_data.get('pay_method')
        if pay_method == 1:
            status = OrderInfo.ORDER_STATUS_ENUM['USERND']
        else:
            status = OrderInfo.ORDER_STATUS_ENUM['UNPAID']
        with transaction.atomic():

            # 创建事务的保存点
            save_id = transaction.savepoint()
            try:
                order = OrderInfo.objects.create(
                    user = user,
                    order_id= order_id,
                    address=address,
                    total_count=total_count,
                    total_amount=total_amount,
                    freight=freight,
                    pay_method=pay_method,
                    status=status
                )
                # 3.1 连接redis
                reids_conn = get_redis_connection('cart')

                # 3.2 获取数据
                redis_cart = reids_conn.hgetall('cart_%s' % user.id)

                # 选中的
                # [1,2,3]
                redis_selected_ids = reids_conn.smembers('cart_selected_%s' % user.id)
                cart = {}
                for sku_id in redis_selected_ids:
                    cart[int(sku_id)] = int(redis_cart[sku_id])
                for sku_id, count in cart.items():
                    # 3.5 根据sku_id获取sku信息
                    sku = SKU.objects.get(pk=sku_id)

                    # 3.6 判断库存
                    if sku.stock < count:
                        transaction.savepoint_rollback(save_id)
                        raise serializers.ValidationError('库存不足')
                        # 模拟并发
                    import time
                    time.sleep(10)

                    # 乐观锁实现

                    # 先记录库存(销量)
                    orginal_stock = sku.stock
                    orginal_sales = sku.sales

                    # 生成新的记录
                    new_stock = sku.stock - count
                    new_sales = sku.sales + count
                    result = SKU.objects.filter(pk=sku_id, stock=orginal_stock).update(stock=new_stock, sales=new_sales)


                    if result == 0:
                         continue
                    OrderGoods.objects.create(
                        order=order,
                        sku=sku,
                        count=count,
                        price=sku.price
                    )
                    # 统计 商品个数和商品价格
                    order.total_count += count
                    order.total_amount += (sku.price * count)

                    break

                order.save()
            except Exception as e :
                transaction.savepoint_rollback(save_id)
                raise Exception('下单失败')
            transaction.savepoint_commit(save_id)

            # 清除redis数据
            # redis_selected_ids [1,2,3]
            # *redis_selected_ids
            reids_conn.hdel('cart_%s' % user.id, *redis_selected_ids)

            reids_conn.srem('cart_selected_%s' % user.id, *redis_selected_ids)

            return order





