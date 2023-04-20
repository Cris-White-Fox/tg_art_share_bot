import datetime
from asgiref.sync import sync_to_async
from django.db import models
from django.utils import timezone


class Profile(models.Model):
    tg_id = models.IntegerField(verbose_name="Идентификатор пользователя", unique=True)
    name = models.TextField(verbose_name="Имя пользователя", default="")
    last_activity = models.DateTimeField(verbose_name="Дата последней активности", auto_now_add=True)

    @classmethod
    @sync_to_async
    def update_profile(cls, profile_id, name):
        return cls.objects.update_or_create(
            tg_id=profile_id,
            defaults={
                "name": name,
                "last_activity": datetime.datetime.now(tz=timezone.utc),
            },
        )[0]

    class Meta:
        verbose_name = "Профиль пользователя"
        verbose_name_plural = "Профили пользователей"

    def __str__(self) -> str:
        return f"Пользователь: {self.name} - {self.tg_id} ({self.last_activity})"


class Image(models.Model):
    profile = models.ForeignKey(Profile, verbose_name="Профиль владельца", on_delete=models.CASCADE)
    file_id = models.TextField(verbose_name="Идентификатор изображения", default="")
    file_unique_id = models.TextField(verbose_name="Уникальный идентификатор изображения", unique=True)
    phash = models.TextField(verbose_name="Хэш изображения", unique=True)
    datetime = models.DateTimeField(verbose_name="Дата добавления", auto_now_add=True)

    @classmethod
    @sync_to_async
    def check_daily_limit(cls, profile_id):
        return cls.objects.filter(
            profile=Profile.objects.get(tg_id=profile_id),
            datetime__gte=datetime.datetime.now(tz=timezone.utc) - datetime.timedelta(hours=6),
        ).count() > 20

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
    def random_image(cls, profile_id):
        return cls.objects.exclude(
            id__in=ImageScore.objects.filter(
                profile=Profile.objects.get(tg_id=profile_id)
            ).values('image')
        ).order_by('?').first()

    @classmethod
    @sync_to_async
    def advanced_random_image(cls, profile_id):
        scored_images = ImageScore.objects.filter(
            profile=Profile.objects.get(tg_id=profile_id)
        ).values('image')
        disliked_profiles = ImageScore.objects.filter(
            profile=Profile.objects.get(tg_id=profile_id),
            datetime__gte=datetime.datetime.now(tz=timezone.utc) - datetime.timedelta(hours=6),
            score=-1,
        ).values('image__profile')
        return cls.objects.exclude(
            id__in=scored_images,
        ).exclude(
            profile__in=disliked_profiles,
        ).order_by('?').first()

    class Meta:
        verbose_name = "Изображение анкеты"
        verbose_name_plural = "Изображения анкет"

    def __str__(self) -> str:
        return f"Изображение: {self.file_unique_id} ({self.profile})"


class ImageScore(models.Model):
    profile = models.ForeignKey(Profile, verbose_name="Пользователь", related_name='user', on_delete=models.CASCADE)
    image = models.ForeignKey(Image, verbose_name="Изображение", related_name='image', on_delete=models.CASCADE)
    score = models.IntegerField(verbose_name="Результат взаимодействия")
    datetime = models.DateTimeField(verbose_name="Дата взаимодействия", auto_now_add=True)

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
        return f"Взаимодействие: {self.profile} - {self.image} ({self.score})"