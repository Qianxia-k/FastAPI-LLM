# 新闻相关的缓存方法：新闻分类的读取和写入
# key - value
from typing import List, Dict, Any, Optional

from config.cache_conf import get_json_cache, set_cache

CATEGORIES_KEY = "news:categories"
NEWS_LIST_PREFIX = "news_list:"
NEWS_DETAIL_PREFIX = "news:detail:"
RELATED_NEWS_PREFIX = "news:related:"


# 获取新闻分类缓存
async def get_cached_categories():
    return await get_json_cache(CATEGORIES_KEY)


# 写入新闻分类缓存: 缓存的数据, 过期时间
# 分类、配置 7200；列表： 600； 详情： 1800；验证码：120 -- 数据越稳定，缓存越持久
# 避免所有key同时过期 引起缓存雪崩
async def set_cache_categories(data: List[Dict[str, Any]], expire: int = 7200):
    return await set_cache(CATEGORIES_KEY, data, expire)


# 写入缓存-新闻列表 key = news_list:分类id:页码:每页数量  + 列表数据 + 过期时间
async def set_cache_news_list(category_id: Optional[int], page: int, size: int, news_list: List[Dict[str, Any]], expire: int = 1800):
    # 调用 封装的 Redis 的设置方法，存新闻列表到缓存
    category_part = category_id if category_id is not None else "all"
    key = f"{NEWS_LIST_PREFIX}{category_part}:{page}:{size}"
    return await set_cache(key, news_list, expire)


# 读取缓存-新闻列表
async def get_cache_news_list(category_id: Optional[int], page: int, size: int):
    category_part = category_id if category_id is not None else "all"
    key = f"{NEWS_LIST_PREFIX}{category_part}:{page}:{size}"
    return await get_json_cache(key)


async def get_cached_news_detail(news_id: int) -> Optional[Dict[str, Any]]:
    """
    获取缓存的新闻详情

    Args:
        news_id: 新闻ID

    Returns:
        Optional[Dict[str, Any]]: 新闻数据，不存在则返回None
    """
    key = f"{NEWS_DETAIL_PREFIX}{news_id}"
    return await get_json_cache(key)


async def cache_news_detail(news_id: int, news_data: Dict[str, Any], expire: int = 300) -> bool:
    """
    缓存新闻详情

    Args:
        news_id: 新闻ID
        news_data: 新闻数据字典
        expire: 过期时间（秒），默认5分钟

    Returns:
        bool: 缓存成功返回True
    """
    key = f"{NEWS_DETAIL_PREFIX}{news_id}"
    return await set_cache(key, news_data, expire)


async def cache_related_news(news_id: int, category_id: int, related_list: List[Dict[str, Any]], expire: int = 1800) -> bool:
    """
    缓存相关新闻列表

    Args:
        news_id: 当前新闻ID
        category_id: 新闻分类ID
        related_list: 相关新闻列表数据
        expire: 过期时间（秒）

    Returns:
        bool: 缓存成功返回True
    """
    key = f"{RELATED_NEWS_PREFIX}{news_id}:{category_id}"
    return await set_cache(key, related_list, expire)


async def get_cached_related_news(news_id: int, category_id: int) -> Optional[List[Dict[str, Any]]]:
    """
    获取缓存的相关新闻列表

    Args:
        news_id: 当前新闻ID
        category_id: 新闻分类ID

    Returns:
        Optional[List[Dict[str, Any]]]: 相关新闻列表数据，不存在则返回None
    """
    key = f"{RELATED_NEWS_PREFIX}{news_id}:{category_id}"
    return await get_json_cache(key)