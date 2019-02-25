from django.conf.urls import url

from . import views


urlpatterns = [
    # 图片验证码
    url(r'^image_codes/(?P<image_code_id>[\w-]+)/$', views.ImageView.as_view()),
    url(r'^accounts/(?P<username>\w{5,20})/sms/token/$', views.FindUser.as_view()),
    url(r'^sms_codes/$', views.SMSCodeView.as_view()),
    url(r'^accounts/(?P<username>\w{5,20})/password/token/$', views.CheackSmsCode.as_view()),
    url(r'^users/(?P<user_id>[\w-]+)/password/$', views.ChangePassword.as_view()),
]