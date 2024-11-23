from rest_framework_api.views import StandardAPIView
from rest_framework.exceptions import NotFound, APIException
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.core.cache import cache
import redis

from core.permissions import HasValidAPIKey
from .models import Post, Heading, PostAnalytics
from .serializers import PostListSerializer, PostSerializer, HeadingSerializer
from .utils import get_client_ip
from .tasks import increment_post_views_task


redis_client = redis.StrictRedis(host=settings.REDIS_HOST, port=6379, db=0)


class PostListView(StandardAPIView):
    permission_classes = [HasValidAPIKey]

    def get(self, request, *args, **kwargs):
        try:
            # Verificar si los datos están en caché
            cached_posts = cache.get("post_list")
            if cached_posts:
                # Serializar los datos del caché
                serialized_posts = PostListSerializer(cached_posts, many=True).data

                # Incrementar impresiones en Redis para los posts del caché
                for post in cached_posts:
                    redis_client.incr(f"post:impressions:{post.id}")  # Usar `post.id`
                return self.paginate(request, serialized_posts)

            # Obtener posts de la base de datos si no están en caché
            posts = Post.postobjects.all()

            if not posts.exists():
                raise NotFound(detail="No posts found.")

            # Guardar los objetos Post en el caché
            cache.set("post_list", posts, timeout=60 * 5)

            # Serializar los datos para la respuesta
            serialized_posts = PostListSerializer(posts, many=True).data

            # Incrementar impresiones en Redis
            for post in posts:
                redis_client.incr(f"post:impressions:{post.id}")  # Usar `post.id`

        except Exception as e:
            raise APIException(detail=f"An unexpected error occurred: {str(e)}")

        return self.paginate(request, serialized_posts)


class PostDetailView(StandardAPIView):
    permission_classes = [HasValidAPIKey]

    # @method_decorator(cache_page(60 * 1))
    def get(self, request):
        ip_address = get_client_ip(request)
        slug = request.query_params.get("slug")

        if not slug:
            raise NotFound(detail="A valid slug must be provided")

        try:
            # Verificar si los datos están en caché
            cached_post = cache.get(f"post_detail:{slug}")
            if cached_post:
                serialized_post = PostSerializer(cached_post).data
                increment_post_views_task.delay(cached_post.slug, ip_address)
                return self.response(serialized_post)

            # Si no está en caché, obtener el post de la base de datos
            post = Post.postobjects.get(slug=slug)
            serialized_post = PostSerializer(post).data

            # Guardar en el caché
            cache.set(f"post_detail:{slug}", post, timeout=60 * 5)

            increment_post_views_task.delay(post.slug, ip_address)

        except Post.DoesNotExist:
            raise NotFound(detail="The requested post does not exist")
        except Exception as e:
            raise APIException(detail=f"An unexpected error occurred: {str(e)}")

        return self.response(serialized_post)


class PostHeadingsView(StandardAPIView):
    permission_classes = [HasValidAPIKey]

    def get(self,request):
        post_slug = request.query_params.get("slug")
        heading_objects = Heading.objects.filter(post__slug = post_slug)
        serialized_data = HeadingSerializer(heading_objects, many=True).data
        return self.response(serialized_data)
    

class IncrementPostClickView(StandardAPIView):
    permission_classes = [HasValidAPIKey]

    def post(self, request):
        """
        Incrementa el contador de clics de un post basado en su slug.
        """
        data = request.data

        try:
            post = Post.postobjects.get(slug=data['slug'])
        except Post.DoesNotExist:
            raise NotFound(detail="The requested post does not exist")
        
        try:
            post_analytics, created = PostAnalytics.objects.get_or_create(post=post)
            post_analytics.increment_click()
        except Exception as e:
            raise APIException(detail=f"An error ocurred while updating post analytics: {str(e)}")

        return self.response({
            "message": "Click incremented successfully",
            "clicks": post_analytics.clicks
        })
