from django.http import HttpResponse
from django.shortcuts import render
from django_redis import get_redis_connection
from rest_framework.views import APIView
from QQLoginTool.QQtool import OAuthQQ
from django.conf import settings
from rest_framework.response import Response
from rest_framework import status
import logging
from rest_framework_jwt.settings import api_settings

from .models import QQAuthUser, OAuthSinaUser
from .utils import generate_save_user_token, OAuthWeibo
from .serializers import QQAuthUserSerializer, WeiboOauthSerializer
from carts.utils import merge_cart_cookie_to_redis
from meiduo.utils.captcha.captcha import captcha

logger = logging.getLogger('django')


# Create your views here.
class QQAuthUserView(APIView):
    """扫码成功后回调处理"""

    def get(self, request):
        # 1.获取查询参数中的code参数
        code = request.query_params.get('code')
        if not code:
            return Response({'message': '缺少code'}, status=status.HTTP_400_BAD_REQUEST)
        # 1.1 创建qq登录工具对象
        oauthqq = OAuthQQ(client_id=settings.QQ_CLIENT_ID,
                          client_secret=settings.QQ_CLIENT_SECRET,
                          redirect_uri=settings.QQ_REDIRECT_URI)
        try:
            # 2.通过code向QQ服务器请求获取access_token
            access_token = oauthqq.get_access_token(code)
            # 3.通过access_token向QQ服务器请求获取openid
            openid = oauthqq.get_open_id(access_token)
        except Exception as error:
            logger.info(error)
            return Response({'message': 'QQ服务器异常'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        try:
            # 4.查询openid是否绑定过美多商城中的用户
            qqauth_model = QQAuthUser.objects.get(openid=openid)
        except QQAuthUser.DoesNotExist:
            # 如果openid没有绑定过美多商城中的用户
            # 把openid进行加密安全处理,再响应给浏览器,让它先帮我们保存一会
            openid_sin = generate_save_user_token(openid)
            return Response({'access_token': openid_sin})

        else:
            # 如果openid已经绑定过美多商城中的用户(生成jwt token直接让它登录成功)
            # 手动生成token

            jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER  # 加载生成载荷函数
            jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER  # 加载生成token函数
            # 获取user对象
            user = qqauth_model.user
            payload = jwt_payload_handler(user)  # 生成载荷
            token = jwt_encode_handler(payload)  # 根据载荷生成token

            response = Response({
                'token': token,
                'username': user.username,
                'user_id': user.id
            })
            # 做cookie购物车合并到redis操作
            merge_cart_cookie_to_redis(request, user, response)

            return response

    def post(self, request):

        # 创建序列化器对象,进行反序列化
        serializer = QQAuthUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # 手动生成jwt Token
        jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER  # 加载生成载荷函数
        jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER  # 加载生成token函数
        # 获取user对象

        payload = jwt_payload_handler(user)  # 生成载荷
        token = jwt_encode_handler(payload)  # 根据载荷生成token

        response = Response({
            'token': token,
            'username': user.username,
            'user_id': user.id
        })
        # 做cookie购物车合并到redis操作
        merge_cart_cookie_to_redis(request, user, response)

        return response


class QQAuthURLView(APIView):
    """生成QQ扫码url"""

    def get(self, request):
        # 1.获取next(从那里去到login界面)参数路径
        next = request.query_params.get('next')
        if not next:  # 如果没有指定来源将来登录成功就回到首页
            next = '/'

        # QQ登录参数
        """
        QQ_CLIENT_ID = '101514053'
        QQ_CLIENT_SECRET = '1075e75648566262ea35afa688073012'
        QQ_REDIRECT_URI = 'http://www.meiduo.site:8080/oauth_callback.html'
        oauthqq = OAuthQQ(client_id='101514053', 
                  client_secret='1075e75648566262ea35afa688073012', 
                  redirect_uri='http://www.meiduo.site:8080/oauth_callback.html',
                  state=next)
        """

        # 2.创建QQ登录sdk 的对象
        oauthqq = OAuthQQ(client_id=settings.QQ_CLIENT_ID,
                          client_secret=settings.QQ_CLIENT_SECRET,
                          redirect_uri=settings.QQ_REDIRECT_URI,
                          state=next)
        # 3.调用它里面的get_qq_url方法来拿到拼接好的扫码链接
        login_url = oauthqq.get_qq_url()

        # 4.把扫码url响应给前端
        return Response({'login_url': login_url})

class WeiboAuthUserView(APIView):
    """扫码成功回调处理"""
    def get(self, request):
        """
        微博第三方登录检查
        http://www.meiduo.site:8080/sina_callback.html?state=%2F&
        code=b124cd3260022177d1732a88d8d4010b
        :param request:
        :return:
        """

        # 1.获取查询参数中的code参数
        code = request.query_params.get('code')
        # 检查code参数
        if not code:
            return Response({'message':'缺少code值'},status=status.HTTP_400_BAD_REQUEST)
        next = '/'
        # 1.1创建微博登录工具对象
        weiboauth = OAuthWeibo(
            client_id=settings.WEIBO_CLIENT_ID,
            client_secret=settings.WEIBO_CLIENT_SECRET,
            redirect_uri=settings.WEIBO_REDIRECT_URI,
            state=next
        )
        # 2.通过code向微博服务器请求获取access_token
        try:
            weibotoken = weiboauth.get_access_token(code)
        except Exception as error:
            logger.info(error)
            return Response({'message':'微博服务器异常'},status=status.HTTP_503_SERVICE_UNAVAILABLE)

        # 3.查询access_token是否绑定过美多商城中的用户
        try:
            weibo_model = OAuthSinaUser.objects.get(weibotoken=weibotoken)
        except :
            # 3.1如果access_token没有绑定过美多商城中的用户(创建一个新用户并绑定access_token)
            # serializer = Serializer(settings.SECRET_KEY, 600)
            # # 3.2把access_token进行加密处安全处理,再相应给浏览器,让它先保存
            # weibotoken = serializer.dumps({'weibotoken':weibotoken}).decode()
            # 3.3如果access_token已经绑定美多商城用户(生成jwttoken让它登录成功)
            return Response({'access_token':weibotoken})
        else:
            # 手动生成token

            # 加载生成载荷函数
            jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
            # 加载生成token函数
            jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER
            # 生成载荷
            # 获取user对象,用外键
            user = weibo_model.user
            payload = jwt_payload_handler(user)
            # 根据载荷生成token
            token = jwt_encode_handler(payload)

            return Response({
                'token':token,
                'username':user.username,
                'user_id':user.id
            })

    def post(self, request):
        """微博用户未绑定,绑定微博用户"""
        # 1.获取前端数据
        data = request.data
        # 2.调用序列化器验证数据
        seria = WeiboOauthSerializer(data=data)
        seria.is_valid(raise_exception=True)
        seria.save()
        return Response(seria.data)





class WeiboAuthURLView(APIView):
    """生成weibo扫码URL"""
    def get(self, request):
        # 1.获取next(从哪里去到login界面) 参数路径
        next = request.query_params.get('state')
        if not next:
            next = '/'


    # 微博登录参数配置
    # WEIBO_CLIENT_ID = '3305669385'
    # WEIBO_CLIENT_SECRET = '74c7bea69d5fc64f5c3b80c802325276'
    # WEIBO_REDIRECT_URI = 'http://www.meiduo.site:8080/sina_callback.html'

        # 2.创建微博登录sdk登录对象
        oauth = OAuthWeibo(
            client_id=settings.WEIBO_CLIENT_ID,
            client_secret=settings.WEIBO_CLIENT_SECRET,
            redirect_uri=settings.WEIBO_REDIRECT_URI,
            state=next)

        # 3.调用它里面的get_weibo_url方法拿到拼接好的扫码链接
        login_url = oauth.get_weibo_url()

        # 4.把扫码url相应给前端
        return Response({'login_url':login_url})

#生成图片
def get_image(request, image_code_id):
    """获取验证码图片的后端接口"""
    image_name, real_image_code, image_data = captcha.generate_captcha()
    redis_conn = get_redis_connection("verify_codes")
    redis_conn.setex("CODEID_%s" % image_code_id, 300, real_image_code)
    return HttpResponse(image_data)