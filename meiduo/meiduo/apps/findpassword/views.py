from django.shortcuts import render
from django.contrib.auth.hashers import check_password
from django.http import HttpResponse
from django_redis import get_redis_connection
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status


from meiduo.utils.captcha.captcha import captcha
from . import constants
import random
from users.models import User
from celery_tasks.sms import tasks as sms_tasks
from oauth.utils import generate_save_user_token, check_save_user_token


# Create your views here.

class FindUser(APIView):
    """
    用户名数量
    """
    def get(self, request, username):
        """
        获取指定用户是否存在,查看用户名在数据库数量,大于0说明有
        """
        # 核对验证码
        text = request.query_params.get('text')
        image_code_id = request.query_params.get('image_code_id')
        # 查询redis验证码
        redis_conn = get_redis_connection('image')
        redis_text = redis_conn.get('ImageCode_' + image_code_id).decode()

        if redis_text != text:
            return Response({"message": "验证码错误"}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.get(username=username)
        if not user:
            return Response(status=status.HTTP_404_NOT_FOUND)

        # 补充生成记录登录状态的token
        mobile = user.mobile
        token = generate_save_user_token(mobile)
        mobile = mobile.replace(mobile[3:7], '****')
        data = {
            "access_token": token,
            "mobile": mobile
        }
        response = Response(data=data)

        return response


class ImageView(APIView):
    """获取验证码图片"""
    def get(self, request, image_code_id):
        code_id = image_code_id
        # 生成图片
        name, text, image = captcha.generate_captcha()
        print(text)
        redis_conn = get_redis_connection('image')
        # 管道存储
        pl = redis_conn.pipeline()
        pl.setex('ImageCode_' + code_id, constants.IMAGE_CODE_REDIS_EXPIRES, text)
        # 执行
        pl.execute()

        return HttpResponse(image)

class SMSCodeView(APIView):
    """发送短信验证码"""

    def get(self, request):
        # 通过token获取手机号
        access_token = request.query_params.get('access_token')
        mobile = check_save_user_token(access_token)
        # 发短信
        redis_conn = get_redis_connection('verify_codes')
        # 获取此手机是否有发送的标记
        flag = redis_conn.get('send_flag_%s' % mobile)
        if flag:
            return Response({"message": "发送短信过于频繁"}, status=status.HTTP_400_BAD_REQUEST)
        # 生成短信验证码
        sms_code = '%06d' % random.randint(0, 999999)
        print(sms_code)
        # celery
        sms_tasks.send_sms_code.delay(mobile, sms_code)
        # 管道存储
        pl = redis_conn.pipeline()
        pl.setex('sms_%s' % mobile, constants.SMS_CODE_REDIS_EXPIRES, sms_code)
        pl.setex('send_flag_%s' % mobile, constants.SEND_SMS_CODE_INTERVAL, 1)
        # 执行
        pl.execute()

        return Response(status=status.HTTP_200_OK)

class CheackSmsCode(APIView):
    def get(self, request, username):
        username = username
        sms_code = request.query_params.get('sms_code')
        # 通过username获取手机号
        user = User.objects.get(username=username)
        mobile = user.mobile

        redis_conn = get_redis_connection('verify_codes')
        real_sms_code = redis_conn.get('sms_%s' % mobile)
        # 验证短信验证码
        if real_sms_code is None:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        if sms_code != real_sms_code.decode():
            return Response(status=status.HTTP_400_BAD_REQUEST)
        user_id = user.id
        token = generate_save_user_token(mobile)
        data = {
            "user_id": user_id,
            "access_token": token
        }

        return Response(data=data, status=status.HTTP_200_OK)


class ChangePassword(APIView):
    """修改密码"""
    def post(self, request, user_id):
        # 获取前端表格数据
        user_id = user_id
        new_password = request.data.get("password")
        password2 = request.data.get("password2")
        if new_password != password2:
            return Response({"message": "两次输入密码不对"}, status=status.HTTP_400_BAD_REQUEST)
        # 解析token
        access_token = request.data.get("access_token")
        mobile = check_save_user_token(access_token)
        user = User.objects.get(mobile=mobile)
        if not user:
            return Response(status=status.HTTP_404_NOT_FOUND)
        id = user.id
        if int(user_id) != int(id):
            return Response({"message": "信息错误"}, status=status.HTTP_400_BAD_REQUEST)
        old_password = user.password
        pwd_bool = check_password(new_password, old_password)
        if pwd_bool:
            return Response({"message": "请勿输入旧密码"}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()
        return Response(status=status.HTTP_200_OK)

    
