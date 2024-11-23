from django.urls import path

from .views import (
    PostListView, 
    PostDetailView, 
    PostHeadingsView, 
    IncrementPostClickView
)

urlpatterns = [
    path('posts/', PostListView.as_view(), name='post-list'),
    path('post/', PostDetailView.as_view(), name='post-detail'),
    path('post/headings/', PostHeadingsView.as_view(), name='post-headings'),
    path('post/increment_click/', IncrementPostClickView.as_view(), name='increment-post-click'),
]