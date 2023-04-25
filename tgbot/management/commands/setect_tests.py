from django.core.management.base import BaseCommand
from tgbot.models import Image, ImageScore, Profile
from django.db.models import Sum, Max
from django.db.models import Subquery
from django.db.models import Q


class Command(BaseCommand):
    def handle(self, *args, **options):
        job()


def job():
    profile_id = 994854082
    a = 123
    Image.objects.exclude(image_score__profile__tg_id=profile_id).values("image", "image_score__profile").annotate(profile_score=Sum("image_score__score")).order_by("-profile_score")
    Image.objects.exclude(image_score__profile__tg_id=profile_id)[:5]

    Profile.objects.exclude(tg_id=994854082).values('tg_id').annotate(
        sum_score=Sum("image__image_score__score", filter=Q(image__image_score__profile__tg_id=994854082))).order_by(
        '-sum_score')

    Profile.objects.exclude(tg_id=994854082).values('tg_id').annotate(last_dislike=Max("image__image_score__datetime",
                                                                                       filter=Q(
                                                                                           image__image_score__profile__tg_id=994854082) & Q(
                                                                                           image__image_score__score=-1))).order_by(
        'last_dislike')