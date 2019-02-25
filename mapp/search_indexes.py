#coding:utf8
from haystack import indexes

from .models import SKU


class SKUIndex(indexes.SearchIndex, indexes.Indexable):

    #document=True
    #text 相当于我们新华字段的 汉语拼音查询 根据偏旁部首获取指定页数
    #需要有一个（也是唯一一个）字段 document=True。
    # 这向Haystack和搜索引擎指示哪个字段是在其中搜索的主要字段

    #use_template=True
    # 可以使用模板来定义全文检索的字段
    text = indexes.CharField(document=True, use_template=True)

    #制定字段
    id = indexes.IntegerField(model_attr='id')
    name = indexes.CharField(model_attr='name')
    price = indexes.DecimalField(model_attr='price')
    default_image_url = indexes.CharField(model_attr='default_image_url')
    comments = indexes.IntegerField(model_attr='comments')

    def get_model(self):
        """返回建立索引的模型类"""
        return SKU

    def index_queryset(self, using=None):
        """返回要建立索引的数据查询集"""
        return self.get_model().objects.filter(is_launched=True)