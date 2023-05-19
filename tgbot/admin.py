from django.contrib import admin
from django.db import models
from django.db.models import Q
from .models import Profile, Image, ImageScore, Report, ImageBlock


class ActivityFilter(admin.SimpleListFilter):
    title = 'Активность пользователей'
    parameter_name = 'activity'

    def lookups(self, request, model_admin):
        return (
            ('img_1', '1+ изображение'),
            ('img_100', '100+ изображений'),
            ('img_1000', '1000+ изображений'),
            ('scr_1', '1+ оценка'),
            ('scr_100', '100+ оценок'),
            ('scr_1000', '1000+ оценок'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'img_1':
            return queryset.annotate(
                image_count=models.Count('image', distinct=True)
            ).filter(image_count__gte=1).order_by('-image_count')
        elif self.value() == 'img_100':
            return queryset.annotate(
                image_count=models.Count('image', distinct=True)
            ).filter(image_count__gte=100).order_by('-image_count')
        elif self.value() == 'img_1000':
            return queryset.annotate(
                image_count=models.Count('image', distinct=True)
            ).filter(image_count__gte=1000).order_by('-image_count')
        elif self.value() == 'scr_1':
            return queryset.annotate(
                image_score_count=models.Count('image_score', distinct=True)
            ).filter(image_score_count__gte=1).order_by('-image_score_count')
        elif self.value() == 'scr_100':
            return queryset.annotate(
                image_score_count=models.Count('image_score', distinct=True)
            ).filter(image_score_count__gte=100).order_by('-image_score_count')
        elif self.value() == 'scr_1000':
            return queryset.annotate(
                image_score_count=models.Count('image_score', distinct=True)
            ).filter(image_score_count__gte=1000).order_by('-image_score_count')


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        'tg_id',
        'name',
        'images_uploaded',
        'scores_from',
        'last_activity',
        'last_bot_message'
    )
    list_filter = (ActivityFilter,)
    search_fields = ('tg_id', 'name')
    list_per_page = 25

    @admin.display(description='Загружено изображений')
    def images_uploaded(self, obj):
        return obj.image.count()

    @admin.display(description='Выставлено оценок')
    def scores_from(self, obj):
        return obj.image_score.count()


@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    list_display = (
        'profile',
        'likes_count',
        'dislikes_count',
        'scheme_image_tag',
        'file_unique_id',
        'datetime',
        'file_id',
        'phash',
    )
    readonly_fields = ('scheme_image_tag',)
    search_fields = ('profile__name', 'profile__tg_id', 'file_unique_id', 'phash')
    list_per_page = 25

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
    list_display = ('profile', 'score', 'scheme_image_tag', 'image', 'datetime', )
    list_filter = ('score', )
    readonly_fields = ('scheme_image_tag',)
    search_fields = ('profile__name', 'profile__tg_id', 'image__file_unique_id', 'image__phash')
    list_per_page = 25


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('profile', 'image', 'scheme_image_tag', 'datetime',)
    search_fields = ('profile__name', 'profile__tg_id', 'image__file_unique_id', 'image__phash')
    readonly_fields = ('scheme_image_tag',)
    list_per_page = 25


@admin.register(ImageBlock)
class ImageBlockAdmin(admin.ModelAdmin):
    list_display = ('image', 'datetime', 'scheme_image_tag')
    readonly_fields = ('scheme_image_tag',)
    list_per_page = 25

