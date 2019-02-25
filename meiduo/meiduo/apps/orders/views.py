from django.shortcuts import render
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django_redis import get_redis_connection
from decimal import Decimal
from rest_framework.response import Response
from rest_framework.generics import CreateAPIView, ListAPIView

from goods.models import SKU
from meiduo.utils.paginations import StandardResultsSetPagination
from .models import OrderInfo, OrderGoods
from .serializers import OrderSettlementSerializer, CommitOrderSerializer, Allordersserializer, Orderserializer


class ListAllOrderGoodsView(ListAPIView):
    permission_classes = [IsAuthenticated]  # 给视图指定权限
    serializer_class = Allordersserializer  # 指定序列化器
    pagination_class = StandardResultsSetPagination  # 指定分页类

    def get_queryset(self):
        user = self.request.user
        User_orders = OrderInfo.objects.filter(user_id=user.id).order_by('-create_time')
        return User_orders


class UncommentgoodsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        ordergoods = OrderGoods.objects.filter(order_id=order_id)
        return Response(Orderserializer(ordergoods, many=True).data)


class SavecommentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        ordergood = OrderGoods.objects.get(order_id=request.data['order'], sku_id=request.data['sku'])
        ordergood.score = request.data['score']
        ordergood.is_anonymous = request.data['is_anonymous']
        ordergood.comment = request.data['comment']
        ordergood.is_commented = True
        ordergood.save()
        return Response("提交评论成功", status=status.HTTP_201_CREATED)


# Create your views here.
class CommitOrderView(CreateAPIView):

    # 指定权限
    permission_classes = [IsAuthenticated]

    # 指定序列化器
    serializer_class = CommitOrderSerializer


class OrderSettlementView(APIView):
    """去结算接口"""

    permission_classes = [IsAuthenticated]  # 给视图指定权限

    def get(self, request):
        """获取"""
        user = request.user

        # 从购物车中获取用户勾选要结算的商品信息
        redis_conn = get_redis_connection('cart')
        redis_cart = redis_conn.hgetall('cart_%s' % user.id)
        cart_selected = redis_conn.smembers('selected_%s' % user.id)
        cart = {}
        for sku_id in cart_selected:
            cart[int(sku_id)] = int(redis_cart[sku_id])

        # 查询商品信息
        skus = SKU.objects.filter(id__in=cart.keys())
        for sku in skus:
            sku.count = cart[sku.id]

        # 运费
        freight = Decimal('10.00')
        # 创建序列化器时 给instance参数可以传递(模型/查询集(many=True) /字典)
        serializer = OrderSettlementSerializer({'freight': freight, 'skus': skus})

        return Response(serializer.data)
