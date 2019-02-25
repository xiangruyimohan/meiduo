from drf_haystack.serializers import HaystackSerializerfrom rest_framework import serializersfrom .models import SKUfrom .search_indexes import SKUIndexfrom orders.models import OrderGoods, OrderInfoclass SKUSerializer(serializers.ModelSerializer):    """商品列表界面"""    class Meta:        model = SKU        fields = ['id', 'name', 'price', 'default_image_url', 'comments']class SKUSearchSerializer(HaystackSerializer):    """    SKU索引结果数据序列化器    """    object = SKUSerializer(read_only=True)    class Meta:        index_classes = [SKUIndex]        fields = ('text', 'object')class SKUOrderSerializer(serializers.ModelSerializer):    """调用SKU序列化器"""    class Meta:        model = SKU        fields = ['id', 'name', 'price', 'default_image_url', 'comments', ]class OrderSerializer(serializers.ModelSerializer):    """商品订单序列化器调用"""    sku = SKUOrderSerializer()    class Meta:        model = OrderGoods        fields = ['id', 'sku', 'count', 'price']class AllOrderSerializer(serializers.ModelSerializer):    """显示全部订单的序列化器"""    skus = OrderSerializer(many=True)    create_time = serializers.DateTimeField(format='%Y-%m-%d  %H:%M:%S')    class Meta:        model = OrderInfo        fields = ['create_time', 'order_id', 'total_amount', 'pay_method', 'freight', 'status', 'skus']