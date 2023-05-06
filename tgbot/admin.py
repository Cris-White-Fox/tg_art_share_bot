from django.contrib import admin
from django.db import models
from django.db.models import Q

from .models import Profile, Image, ImageScore


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        'tg_id',
        'name',
        'images_uploaded',
        'likes_count',
        'dislikes_count',
        'outerlikes_count',
        'outerdislikes_count',
        'last_activity',
        'last_bot_message'
    )
    search_fields = ('tg_id', 'name')

    def get_queryset(self, request):
        qs = super(ProfileAdmin, self)\
            .get_queryset(request)\
            .annotate()\
            .annotate(
                image__count=models.Count('image', distinct=True),
                likes__count=models.Count(
                    'image_score',
                    distinct=True,
                    filter=Q(image_score__score__gte=1)
                ) - models.Count('image', distinct=True),
                dislikes__count=models.Count(
                    'image_score',
                    distinct=True,
                    filter=Q(image_score__score__lte=0)
                ),
                outerlikes__count=models.Count(
                    'image__image_score',
                    distinct=True,
                    filter=Q(image__image_score__score__gte=1)
                ) - models.Count('image', distinct=True),
                outerdislikes__count=models.Count(
                    'image__image_score',
                    distinct=True,
                    filter=Q(image__image_score__score__lte=0)
                ),
            )
        return qs

    @admin.display(ordering="image__count", description='Загружено изображений')
    def images_uploaded(self, obj):
        return obj.image__count

    @admin.display(ordering="likes__count", description='Лайки от')
    def likes_count(self, obj):
        return obj.likes__count

    @admin.display(ordering="dislikes__count", description='Дизлайки от')
    def dislikes_count(self, obj):
        return obj.dislikes__count

    @admin.display(ordering="outerlikes__count", description='Лайки для')
    def outerlikes_count(self, obj):
        return obj.outerlikes__count

    @admin.display(ordering="outerdislikes__count", description='Дизлайки для')
    def outerdislikes_count(self, obj):
        return obj.outerdislikes__count


@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    list_display = (
        'profile',
        'file_unique_id',
        'datetime',
        'likes_count',
        'dislikes_count',
        'file_id',
        'phash',
    )
    search_fields = ('profile__name', 'profile__tg_id', 'file_unique_id', 'phash')

    def get_queryset(self, request):
        qs = super(ImageAdmin, self)\
            .get_queryset(request)\
            .annotate(likes__count=models.Count('image_score', distinct=True, filter=Q(image_score__score__gte=1)))\
            .annotate(dislikes__count=models.Count('image_score', distinct=True, filter=Q(image_score__score__lte=0)))
        return qs

    @admin.display(ordering="likes__count", description='likes')
    def likes_count(self, obj):
        return obj.likes__count

    @admin.display(ordering="dislikes__count", description='dislikes')
    def dislikes_count(self, obj):
        return obj.dislikes__count


@admin.register(ImageScore)
class ImageScoreAdmin(admin.ModelAdmin):
    list_display = ('profile', 'image', 'score', 'datetime')
    list_filter = ('score', )
    search_fields = ('profile__name', 'profile__tg_id', 'image__file_unique_id', 'image__phash')
