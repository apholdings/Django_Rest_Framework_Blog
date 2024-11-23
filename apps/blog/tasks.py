from celery import shared_task

import logging

import redis
from django.conf import settings

from .models import PostAnalytics, Post

logger = logging.getLogger(__name__)

redis_client = redis.StrictRedis(host=settings.REDIS_HOST, port=6379, db=0)

@shared_task
def increment_post_impressions(post_id):
    """
    Incrementa las impresiones del post asociado
    """
    try:
        analytics, created = PostAnalytics.objects.get_or_create(post__id=post_id)
        analytics.increment_impression()
    except Exception as e:
        logger.info(f"Error incrementing impressions for Post ID {post_id}: {str(e)}")


@shared_task
def increment_post_views_task(slug, ip_address):
    """
    Incrementa las vistas de un post.
    """
    try:
        post = Post.objects.get(slug=slug)
        post_analytics, _ = PostAnalytics.objects.get_or_create(post=post)
        post_analytics.increment_view(ip_address)
    except Exception as e:
        logger.info(f"Error incrementing views for Post slug {slug}: {str(e)}")


@shared_task
def sync_impressions_to_db():
    """
    Sincronizar las impresiones almacenadas en redis con la base de datos
    """
    keys = redis_client.keys("post:impressions:*")
    for key in keys:
        try:
            post_id = key.decode("utf-8").split(":")[-1]
            impressions = int(redis_client.get(key))

            analytics, _ = PostAnalytics.objects.get_or_create(post__id=post_id)
            analytics.impressions += impressions
            analytics.save()

            analytics._update_click_through_rate()

            redis_client.delete(key)
        except Exception as e:
            print(f"Error syncing impressions for {key}: {str(e)}")