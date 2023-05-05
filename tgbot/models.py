import datetime
from django.utils import timezone
from django.db import models
from django.db.models import Max, Sum, Q, Count


def datetime_now():
    return datetime.datetime.now(tz=timezone.utc)


class Profile(models.Model):
    tg_id = models.IntegerField(verbose_name="Идентификатор пользователя", unique=True)
    name = models.TextField(verbose_name="Имя пользователя", default="")
    last_activity = models.DateTimeField(verbose_name="Активность пользователя", default=datetime_now)
    last_bot_message = models.DateTimeField(verbose_name="Сообщение от бота", default=datetime_now)

    @classmethod
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
    def block_profile(cls, profile_id):
        profile = cls.objects.get(tg_id=profile_id)
        profile.last_bot_message = datetime.datetime.min
        profile.save()

    @classmethod
    def list_need_notification(cls):
        return list(cls.objects.exclude(
            last_bot_message__lte=datetime.datetime.now(tz=timezone.utc) - datetime.timedelta(days=7)
        ).exclude(
            last_bot_message__gte=datetime.datetime.now(tz=timezone.utc) - datetime.timedelta(hours=48)
        ).values_list('tg_id', flat=True))

    @classmethod
    def update_notification(cls, profile_id):
        profile = cls.objects.get(tg_id=profile_id)
        profile.last_bot_message=datetime_now()
        profile.save()

    @classmethod
    def user_stat(cls, profile_id):
        uploaded_images = cls.objects.get(tg_id=profile_id).image.count()
        likes_from = ImageScore.objects.exclude(image__profile__tg_id=profile_id).filter(profile__tg_id=profile_id, score=1).count()
        likes_to = ImageScore.objects.exclude(profile__tg_id=profile_id).filter(image__profile__tg_id=profile_id, score=1).count()
        return uploaded_images, likes_from, likes_to

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
        ).count() >= 50 or cls.objects.filter(
            profile=Profile.objects.get(tg_id=profile_id),
            datetime__gte=datetime.datetime.now(tz=timezone.utc) - datetime.timedelta(hours=24),
        ).count() >= 250 or cls.objects.filter(
            profile=Profile.objects.get(tg_id=profile_id),
            datetime__gte=datetime.datetime.now(tz=timezone.utc) - datetime.timedelta(days=5),
        ).count() >= 500

    @classmethod
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
            score=2,
        )
        return image

    @classmethod
    def delete_image(cls, profile_id, file_unique_id):
        cls.objects.get(profile__tg_id=profile_id, file_unique_id=file_unique_id).delete()

    @classmethod
    def random_image(cls, profile_id):
        profiles = Profile.objects.exclude(tg_id=profile_id).exclude(image__isnull=True).values('tg_id').annotate(
            last_dislike=Max(
                "image__image_score__datetime",
                filter=Q(image__image_score__profile__tg_id=profile_id) & Q(image__image_score__score__lte=0))
        ).order_by('last_dislike')[:50]
        for profile in profiles:
            if image := Image.objects.filter(profile__tg_id=profile['tg_id']).exclude(image_score__profile__tg_id=profile_id).order_by('?').first():
                return image

    @classmethod
    def colab_filter_image(cls, profile_id):
        if cls.objects.filter(image_score__profile__tg_id=profile_id).count() < 20:
            return
        my_likes = cls.objects.filter(image_score__profile__tg_id=profile_id, image_score__score__gte=1)
        my_dislikes = cls.objects.filter(image_score__profile__tg_id=profile_id, image_score__score__lte=0)
        profiles = Profile.objects.exclude(tg_id=profile_id).values('tg_id') \
            .annotate(
                count=Count(
                    "image_score",
                    filter=Q(image_score__image__in=my_likes) | Q(image_score__image__in=my_dislikes)
                )
            ).annotate(
                taste_sim=100 * (
                        Sum(
                            "image_score__score",
                            filter=Q(image_score__image__in=my_likes)
                        ) + Sum(
                            "image_score__score",
                            filter=Q(image_score__image__in=my_dislikes)
                        )
                ) / Count(
                    "image_score",
                    filter=Q(image_score__image__in=my_likes) | Q(image_score__image__in=my_dislikes)
                )
            ).filter(taste_sim__gte=50, count__gte=10).order_by('-taste_sim')[:50]
        if not profiles:
            return
        disliked_profiles = Profile.objects.filter(
            image__image_score__profile__tg_id=profile_id,
            image__image_score__score__lte=0,
            image__image_score__datetime__gte=datetime_now() - datetime.timedelta(minutes=15)
        )
        if image := cls.objects\
                .exclude(image_score__profile__tg_id=profile_id)\
                .exclude(profile__in=disliked_profiles)\
                .values('file_unique_id')\
                .annotate(
                    taste_similarity=Sum(
                        "image_score__score",
                        filter=Q(image_score__profile__tg_id__in=profiles.values('tg_id'))
                    )
                ).order_by('-taste_similarity').first():
            return cls.objects.get(file_unique_id=image['file_unique_id'])

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
