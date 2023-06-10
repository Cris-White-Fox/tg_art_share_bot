from contextlib import suppress

from django.test import TestCase
from django.db.utils import IntegrityError

from tgbot.models import ImageScore, ImageBlock, Image, Profile
from tgbot.recommendations import ColabFilter


class RecommendationTestCase(TestCase):
    def setUp(self):
        for i in range(5):
            Profile.update_profile(i, str(i), 'ru')
        for i in range(15):
            Image.new_image(i // 3, i, i, i)
        # матрица оценок:
        #    0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14
        # 0  2,  2,  2,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0
        # 1  0,  0,  0,  2,  2,  2,  0,  0,  0,  0,  0,  0,  0,  0,  0
        # 2  0,  0,  0,  0,  0,  0,  2,  2,  2,  0,  0,  0,  0,  0,  0
        # 3  0,  0,  0,  0,  0,  0,  0,  0,  0,  2,  2,  2,  0,  0,  0
        # 4  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  2,  2,  2

    def test_dislike(self):
        for i in range(15):
            score = 1 if i < 10 else -1
            ImageScore.objects.get_or_create(
                profile=Profile.objects.get(tg_id=0),
                image=Image.objects.get(file_unique_id=i),
                defaults={"score": score},
            )
            ImageScore.objects.get_or_create(
                profile=Profile.objects.get(tg_id=2),
                image=Image.objects.get(file_unique_id=i),
                defaults={"score": score},
            )
        for i in range(10, 15):
            ImageScore.objects.get_or_create(
                profile=Profile.objects.get(tg_id=1),
                image=Image.objects.get(file_unique_id=i),
                defaults={"score": -1},
            )
        ImageScore.objects.get_or_create(
            profile=Profile.objects.get(tg_id=1),
            image=Image.objects.get(file_unique_id=7),
            defaults={"score": -1},
        )

        # матрица оценок:
        #    0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14
        # 0  2,  2,  2,  1,  1,  1,  1,  1,  1,  1, -1, -1, -1, -1, -1
        # 1  0,  0,  0,  2,  2,  2,  0, -1,  0,  0, -1, -1, -1, -1, -1
        # 2  1,  1,  1,  1,  1,  1,  2,  2,  2,  1, -1, -1, -1, -1, -1
        # 3  0,  0,  0,  0,  0,  0,  0,  0,  0,  2,  2,  2,  0,  0,  0
        # 4  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  2,  2,  2

        cf = ColabFilter()
        prediction = cf.predict(Profile.objects.get(tg_id=1).id)
        a = 1
        # self.assert