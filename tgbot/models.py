import datetime

from django.db.models.functions import Cast
from django.utils import timezone
from django.db import models
from django.db.models import Max, Sum, Q, Count
from django.utils.safestring import mark_safe

from project.settings import bot


def datetime_now():
    return datetime.datetime.now(tz=timezone.utc)


class Profile(models.Model):
    tg_id = models.IntegerField(verbose_name="Идентификатор пользователя", unique=True)
    name = models.TextField(verbose_name="Имя пользователя", default="")
    last_activity = models.DateTimeField(verbose_name="Активность пользователя", default=datetime_now)
    last_bot_message = models.DateTimeField(verbose_name="Сообщение от бота", default=datetime_now)
    language_code = models.TextField(verbose_name="Код языка", default="en")

    @classmethod
    def update_profile(cls, tg_id, name, language_code):
        return cls.objects.update_or_create(
            tg_id=tg_id,
            defaults={
                "name": name,
                "last_activity": datetime_now(),
                "last_bot_message": datetime_now(),
                "language_code": language_code
            },
        )[0]

    @classmethod
    def block_profile(cls, tg_id):
        profile = cls.objects.get(tg_id=tg_id)
        profile.last_bot_message = datetime.datetime.min
        profile.save()

    @classmethod
    def list_need_notification(cls):
        return list(cls.objects.exclude(
            last_bot_message__lte=datetime.datetime.now(tz=timezone.utc) - datetime.timedelta(days=14)
        ).exclude(
            last_bot_message__gte=datetime.datetime.now(tz=timezone.utc) - datetime.timedelta(days=2)
        ).values_list('tg_id', flat=True))

    @classmethod
    def update_notification(cls, tg_id):
        profile = cls.objects.get(tg_id=tg_id)
        profile.last_bot_message=datetime_now()
        profile.save()

    @classmethod
    def user_stat(cls, tg_id):
        profiles_count = cls.objects.count()
        uploaded_images = cls.objects.get(tg_id=tg_id).image.count()
        scores_from = cls.objects.get(tg_id=tg_id).image_score.count()
        uploaded_images_position = (
                Image.objects
                    .exclude(profile__tg_id=tg_id)
                    .values('profile')
                    .annotate(count=Count("profile"))
                    .filter(count__lte=uploaded_images).count()
                + cls.objects.filter(image__isnull=True).count()
           ) * 100 // profiles_count
        score_images_position = (
                ImageScore.objects
                    .exclude(profile__tg_id=tg_id)
                    .values('profile')
                    .annotate(count=Count("profile"))
                    .filter(count__lte=scores_from).count()
                + cls.objects.filter(image_score__isnull=True).count()
            ) * 100 // profiles_count
        if similar_profiles := cls.get_similar_profiles(tg_id):
            similar_profiles_count = similar_profiles.count()
        else:
            similar_profiles_count = 0
        return uploaded_images, uploaded_images_position, scores_from, score_images_position, similar_profiles_count

    @classmethod
    def get_similar_profiles(cls, tg_id):
        if cls.objects.get(tg_id=tg_id).image_score.count() < 20:
            return
        my_likes = Image.get_likes(tg_id)
        my_dislikes = Image.get_dislikes(tg_id)
        profiles = cls.objects.exclude(tg_id=tg_id).values('tg_id') \
            .annotate(
                count=Count(
                    "image_score",
                    filter=Q(image_score__image__in=my_likes) | Q(image_score__image__in=my_dislikes)
                ),
                taste_sim=Cast((
                    Sum(
                        "image_score__score",
                        filter=Q(image_score__image__in=my_likes)
                    ) - Sum(
                        "image_score__score",
                        filter=Q(image_score__image__in=my_dislikes)
                    )
                ), models.FloatField()) / models.F('count'),
            ).filter(taste_sim__gt=0, count__gte=10)
        return profiles

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

    def scheme_image_tag(self):
        return mark_safe('<img src = "{}" width="300">'.format(
            bot.get_file_url(self.file_id)
        ))

    scheme_image_tag.short_description = 'image_view'
    scheme_image_tag.allow_tags = True

    @classmethod
    def check_limit(cls, tg_id):
        ct = datetime_now().replace(second=0, microsecond=0)
        if cls.objects.filter(
                    profile__tg_id=tg_id,
                    datetime__gte=ct - datetime.timedelta(days=ct.weekday(), hours=ct.hour, minutes=ct.minute),
                ).count() >= 500:
            day_limit = 150
        else:
            day_limit = 300

        return cls.objects.filter(
            profile__tg_id=tg_id,
            datetime__gte=ct.replace(minute=ct.minute//10*10),
        ).count() >= 30 or cls.objects.filter(
            profile__tg_id=tg_id,
            datetime__gte=ct.replace(hour=0, minute=0),
        ).count() >= day_limit

    @classmethod
    def new_image(cls, tg_id, file_id, file_unique_id, phash):
        profile = Profile.objects.get(tg_id=tg_id)
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
    def delete_image(cls, tg_id, file_unique_id):
        cls.objects.get(profile__tg_id=tg_id, file_unique_id=file_unique_id).delete()

    @classmethod
    def random_images(cls, tg_id):
        profiles = Profile.objects.exclude(tg_id=tg_id).exclude(image__isnull=True).values('tg_id').annotate(
            image_count=Count(
                "image",
                filter=~Q(image__image_score__profile__tg_id=tg_id),
            ),
            last_dislike=Max(
                "image__image_score__datetime",
                filter=Q(image__image_score__profile__tg_id=tg_id) & Q(image__image_score__score__lte=0)
            )
        ).filter(image_count__gte=1).order_by('last_dislike')[:50]
        for profile in profiles:
            if file_unique_ids := list(
                Image.objects
                    .filter(profile__tg_id=profile['tg_id'])
                    .filter(block__isnull=True)
                    .exclude(image_score__profile__tg_id=tg_id)
                    .values('file_unique_id')
                    .annotate(
                        report_count=Count("report"),
                        score_count=Count("image_score"),
                    )
                    .filter(report_count__lte=2)
                    .order_by('score_count', '?')
                    .values_list('file_unique_id', flat=True)[:15]
            ):
                return [{
                    "file_unique_id": fud,
                    "taste_similarity": 0,
                } for fud in file_unique_ids]

    @classmethod
    def get_likes(cls, tg_id):
        return cls.objects.filter(image_score__profile__tg_id=tg_id, image_score__score__gte=1)

    @classmethod
    def get_dislikes(cls, tg_id):
        return cls.objects.filter(image_score__profile__tg_id=tg_id, image_score__score__lte=0)

    @classmethod
    def colab_filter_images(cls, tg_id):
        profiles = Profile.get_similar_profiles(tg_id)
        if not profiles:
            return
        height_tier_profiles = profiles.filter(taste_sim__gte=0.6)
        mid_tier_profiles = profiles.filter(taste_sim__lt=0.6, taste_sim__gte=0.2)
        low_tier_profiles = profiles.filter(taste_sim__lt=0.2)
        disliked_profiles = Profile.objects.filter(
            image__image_score__profile__tg_id=tg_id,
            image__image_score__score__lte=0,
            image__image_score__datetime__gte=datetime_now() - datetime.timedelta(minutes=15)
        )

        if image_ids := list(
            cls.objects
                .exclude(image_score__profile__tg_id=tg_id)
                .exclude(profile__in=disliked_profiles)
                .filter(block__isnull=True)
                .values('file_unique_id')
                .annotate(
                    taste_similarity=Sum(
                        models.F("image_score__score"),
                        filter=Q(image_score__profile__tg_id__in=height_tier_profiles.values('tg_id'))
                    ) + Sum(
                        models.F("image_score__score"),
                        filter=Q(image_score__profile__tg_id__in=mid_tier_profiles.values('tg_id'))
                    ) * 0.5 + Sum(
                        models.F("image_score__score"),
                        filter=Q(image_score__profile__tg_id__in=low_tier_profiles.values('tg_id'))
                    ) * 0.2,
                    score_count=Count(
                        "image_score",
                        filter=Q(image_score__profile__tg_id__in=profiles.values('tg_id')),
                    ),
                    report_count=Count("report"),
                    taste_similarity_per_score=models.F("taste_similarity") / models.F("score_count")
                ).filter(taste_similarity__gt=0, report_count__lte=2)
                .order_by('-taste_similarity_per_score', '?')[:50]
        ):
            return image_ids

    @classmethod
    def update_image_cache(cls, tg_id, image_ids: list[dict]):
        file_unique_ids = [iid['file_unique_id'] for iid in image_ids]
        disliked_profiles = ImageScore.objects.filter(profile__tg_id=tg_id, score__lte=0, datetime__gte=datetime_now() - datetime.timedelta(minutes=15)).values('image__profile').distinct()
        actual = cls.objects.filter(file_unique_id__in=file_unique_ids).exclude(profile__in=disliked_profiles).values_list('file_unique_id', flat=True)
        return [iid for iid in image_ids if iid['file_unique_id'] in actual]

    @classmethod
    def list_reported_photos(cls, tg_id):
        return cls.objects\
                   .filter(profile__tg_id=tg_id, datetime__gte=datetime_now().replace(month=1, day=1))\
                   .values('file_unique_id')\
                   .filter(report__isnull=False)\
                   .filter(block__isnull=True)\
                   .order_by('-datetime')[:10]

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

    def scheme_image_tag(self):
        return mark_safe('<img src = "{}" width="300">'.format(
            bot.get_file_url(self.image.file_id)
        ))

    scheme_image_tag.short_description = 'image_view'
    scheme_image_tag.allow_tags = True

    @classmethod
    def new_score(cls, tg_id, file_unique_id, score):
        return cls.objects.create(
            profile=Profile.objects.get(tg_id=tg_id),
            image=Image.objects.get(file_unique_id=file_unique_id),
            score=score,
        )

    class Meta:
        verbose_name = "Оценка изображения"
        verbose_name_plural = "Оценки изображений"
        unique_together = ['profile', 'image']

    def __str__(self) -> str:
        return f"Оценка: {self.profile} - {self.image} ({self.score})"


class Report(models.Model):
    profile = models.ForeignKey(Profile, verbose_name="Пользователь", related_name='report', on_delete=models.CASCADE)
    image = models.ForeignKey(Image, verbose_name="Изображение", related_name='report', on_delete=models.CASCADE)
    datetime = models.DateTimeField(verbose_name="Дата взаимодействия", default=datetime_now)

    def scheme_image_tag(self):
        return mark_safe('<img src = "{}" width="300">'.format(
            bot.get_file_url(self.image.file_id)
        ))

    scheme_image_tag.short_description = 'image_view'
    scheme_image_tag.allow_tags = True

    @classmethod
    def check_limit(cls, tg_id):
        ct = datetime_now().replace(second=0, microsecond=0)
        return cls.objects.filter(
            profile__tg_id=tg_id,
            datetime__gte=ct.replace(hour=0, minute=0, second=0, microsecond=0),
        ).count() >= 15

    @classmethod
    def new_report(cls, tg_id, file_unique_id):
        return cls.objects.create(
            profile=Profile.objects.get(tg_id=tg_id),
            image=Image.objects.get(file_unique_id=file_unique_id),
        )

    @classmethod
    def check_reported(cls, tg_id):
        ct = datetime_now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return cls.objects.filter(
            image__block__isnull=True,
            image__profile__tg_id=tg_id,
            image__datetime__gte=ct,
        ).values('image__profile').distinct().count() >= 3 or cls.objects.filter(
            image__block__isnull=True,
            image__profile__tg_id=tg_id,
            image__datetime__gte=ct.replace(month=1),
        ).values('image__profile').distinct().count() >= 10

    class Meta:
        verbose_name = "Жалоба"
        verbose_name_plural = "Жалобы"
        unique_together = ['profile', 'image']


class ImageBlock(models.Model):
    image = models.OneToOneField(
        Image, verbose_name="Изображение", related_name='block', on_delete=models.CASCADE
    )
    datetime = models.DateTimeField(verbose_name="Дата взаимодействия", default=datetime_now)

    def scheme_image_tag(self):
        return mark_safe('<img src = "{}" width="300">'.format(
            bot.get_file_url(self.image.file_id)
        ))

    scheme_image_tag.short_description = 'image_view'
    scheme_image_tag.allow_tags = True

    @classmethod
    def block_image(cls, tg_id, file_unique_id):
        return cls.objects.create(
            image=Image.objects.get(file_unique_id=file_unique_id, profile__tg_id=tg_id),
        )
