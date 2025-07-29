from django.urls import path, include
from .views import (
    VideoListView, 
    VideoBookmarkToggleView, 
    BookmarkedVideoListView, 
    ScriptCacheView, 
    VideoDeleteView,
    VideoEventStreamView
)


urlpatterns = [
    # SSE events stream
    path('events/<str:channel_id>/', VideoEventStreamView.as_view(), name='video_event_stream'),
    # Video list and creation

    path('', VideoListView.as_view(), name='list_videos'),

    # Bookmark operations
    path('bookmarks/<int:videoId>', VideoBookmarkToggleView.as_view(), name='toggle_bookmark'),
    path('bookmarks/bookmarked', BookmarkedVideoListView.as_view(), name='list_bookmarked_videos'),

    # Video deletion
    path('<int:videoId>/', VideoDeleteView.as_view(), name='delete_video'),

    # Script caching
    path('cache-script/', ScriptCacheView.as_view(), name='cache_script'),
]