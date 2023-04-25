import datetime
from asgiref.sync import sync_to_async
from django.db import models
from django.utils import timezone
from django.db.models import Max
from django.db.models import Q


class SpamLimitException(Exception):
    pass

def datetime_now():
    return datetime.datetime.now(tz=timezone.utc)

class Profile(models.Model):
    tg_id = models.IntegerField(verbose_name="Идентификатор пользователя", unique=True)
    name = models.TextField(verbose_name="Имя пользователя", default="")
    last_activity = models.DateTimeField(verbose_name="Активность пользователя", default=datetime_now)
    last_bot_message = models.DateTimeField(verbose_name="Сообщение от бота", default=datetime_now)

    @classmethod
    @sync_to_async
    def update_profile(cls, profile_id, name):
        return cls.objects.update_or_create(
            tg_id=profile_id,
            defaults={
                "name": name,
                "last_activity": datetime_now(),
                "last_bot_message": datetime_now(),
            },
        )[0]

    @classmethod
    @sync_to_async
    def list_need_notification(cls):
        return list(cls.objects.exclude(
            last_activity__gte=datetime.datetime.now(tz=timezone.utc) - datetime.timedelta(hours=48)
        ).exclude(
            last_bot_message__gte=datetime.datetime.now(tz=timezone.utc) - datetime.timedelta(hours=48)
        ).values_list('tg_id', flat=True))

    @classmethod
    @sync_to_async
    def update_notification(cls, profile_id):
        profile = cls.objects.get(tg_id=profile_id)
        profile.last_bot_message=datetime_now()
        profile.save()

    class Meta:
        verbose_name = "Профиль пользователя"
        verbose_name_plural = "Профили пользователей"

    def __str__(self) -> str:
        return f"Пользователь: {self.name} - {self.tg_id} ({self.last_activity})"


class Image(models.Model):
    profile = models.ForeignKey(Profile, verbose_name="Профиль владельца", on_delete=models.CASCADE, related_name='image')
    file_id = models.TextField(verbose_name="Идентификатор изображения", default="")
    file_unique_id = models.TextField(verbose_name="Уникальный идентификатор изображения", unique=True)
    phash = models.TextField(verbose_name="Хэш изображения", unique=True)
    datetime = models.DateTimeField(verbose_name="Дата добавления", default=datetime_now)

    @classmethod
    def check_limit(cls, profile_id):
        return cls.objects.filter(
            profile=Profile.objects.get(tg_id=profile_id),
            datetime__gte=datetime.datetime.now(tz=timezone.utc) - datetime.timedelta(minutes=10),
        ).count() >= 25 or cls.objects.filter(
            profile=Profile.objects.get(tg_id=profile_id),
            datetime__gte=datetime.datetime.now(tz=timezone.utc) - datetime.timedelta(hours=24),
        ).count() >= 100

    @classmethod
    @sync_to_async
    def check_daily_limit(cls, profile_id):
        return cls.check_limit(profile_id)

    @classmethod
    @sync_to_async
    def check_unique_id(cls, unique_id):
        return cls.objects.filter(file_unique_id=unique_id).exists()

    @classmethod
    @sync_to_async
    def check_hash(cls, phash):
        return cls.objects.filter(phash=phash).exists()

    @classmethod
    @sync_to_async
    def new_image(cls, profile_id, file_id, file_unique_id, phash):
        if cls.check_limit(profile_id):
            raise SpamLimitException
        profile = Profile.objects.get(tg_id=profile_id)
        image = cls.objects.create(
            profile=profile,
            file_id=file_id,
            file_unique_id=file_unique_id,
            phash=phash,
        )
        ImageScore.objects.create(
            profile=profile,
            image=image,
            score=1,
        )
        return image

    @classmethod
    @sync_to_async
    def advanced_random_image(cls, profile_id):
        profiles = Profile.objects.exclude(tg_id=profile_id).exclude(image__isnull=True).values('tg_id').annotate(
            last_dislike=Max(
                "image__image_score__datetime",
                filter=Q(image__image_score__profile__tg_id=profile_id) & Q(image__image_score__score=-1))
        ).order_by('last_dislike')[:50]
        for profile in profiles:
            if image := Image.objects.filter(profile__tg_id=profile['tg_id']).exclude(image_score__profile__tg_id=profile_id).first():
                return image

    class Meta:
        verbose_name = "Изображение"
        verbose_name_plural = "Изображения"

    def __str__(self) -> str:
        return f"Изображение: {self.file_unique_id} ({self.profile})"


class ImageScore(models.Model):
    profile = models.ForeignKey(Profile, verbose_name="Пользователь", related_name='image_score', on_delete=models.CASCADE)
    image = models.ForeignKey(Image, verbose_name="Изображение", related_name='image_score', on_delete=models.CASCADE)
    score = models.IntegerField(verbose_name="Результат взаимодействия")
    datetime = models.DateTimeField(verbose_name="Дата взаимодействия", default=datetime_now)

    @classmethod
    @sync_to_async
    def new_score(cls, profile_id, file_unique_id, score):
        return cls.objects.create(
            profile=Profile.objects.get(tg_id=profile_id),
            image=Image.objects.get(file_unique_id=file_unique_id),
            score=score,
        )

    class Meta:
        verbose_name = "Оценка изображения"
        verbose_name_plural = "Оценки изображений"
        unique_together = ['profile', 'image']

    def __str__(self) -> str:
        return f"Оценка: {self.profile} - {self.image} ({self.score})"
