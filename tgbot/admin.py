from django.contrib import admin
from .models import Profile, Image, ImageScore


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('tg_id', 'name', 'last_activity')
    search_fields = ('tg_id', 'name')


@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    list_display = (
        'profile',
        'file_id',
        'file_unique_id',
        'phash',
        'datetime',
    )
    search_fields = ('profile', 'file_unique_id', 'phash')


@admin.register(ImageScore)
class ImageScoreAdmin(admin.ModelAdmin):
    list_display = ('profile', 'image', 'score', 'datetime')
    list_filter = ('score', )
    search_fields = ('profile__name', 'profile__tg_id', 'image__profile', 'image__file_unique_id', 'image__phash')