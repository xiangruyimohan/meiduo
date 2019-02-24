from django.shortcuts import render
from drf_haystack.viewsets import HaystackViewSet
from rest_framework.generics import ListAPIView
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated

from .models import SKU
from .serializers import SKUSerializer, SKUSearchSerializer, AllOrderSerializer
from utils.paginations import StandardResultsSetPagination
from orders.models import OrderInfo


# Create your views here.
# /categories/(?P<category_id>\d+)/skus?page=xxx&page_size=xxx&ordering=xxx

class SKUListView(ListAPIView):
    """商品列表界面"""

    # 指定序列化器
    serializer_class = SKUSerializer
    # 指定过滤后端为排序
    filter_backends = [OrderingFilter]
    # 指定排序字段
    ordering_fields = ['create_time', 'price', 'sales']

    # 指定查询集
    # queryset = SKU.objects.filter(is_launched=True, category_id=category_id)

    def get_queryset(self):
        category_id = self.kwargs.get('category_id')  # 获取url路径中的正则组别名提取出来的参数
        return SKU.objects.filter(is_launched=True, category_id=category_id)


class SKUSearchViewSet(HaystackViewSet):
    """
    SKU搜索
    """
    index_models = [SKU]

    serializer_class = SKUSearchSerializer


class SKUListOrderView(ListAPIView):

    # 指定权限
    permission_classes = [IsAuthenticated]

    # 指定序列化器
    serializer_class = AllOrderSerializer

    # 指定分页
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        user = self.request.user
        user_orders = OrderInfo.objects.filter(user_id=1)

        return user_orders

