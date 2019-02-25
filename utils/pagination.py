#coding:utf8
from rest_framework.pagination import PageNumberPagination

class StandardResultsSetPagination(PageNumberPagination):
    # 默认返回几条数据,如果不传这个参数 默认返回2条
    page_size = 2
    # 我们在前段(url中)输入的key
    page_size_query_param = 'page_size'
    # 返回的最多条数
    max_page_size = 20