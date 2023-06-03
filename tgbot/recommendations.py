import random

from django.db.models import Count
import pandas as pd
import numpy as np
import numpy.ma as ma

from tgbot.models import Image, ImageScore


class ColabFilter():
    def __init__(self):
        self.image_ids = None
        self.user_ids = None
        self.raw_data = None
        self.data = None
        self.cosine = None
        self.update_data()
        self.update_cosine()
        self.update_counter = 0
        self.score_count = ImageScore.objects.count()

    def update_data(self):
        scored_images = (
            Image.objects.values("pk")
                .annotate(score_count=Count("image_score", distinct=True))
                .filter(score_count__gte=1).values("pk")
        )
        score_data = ImageScore.objects.filter(image__in=scored_images)
        df = pd.DataFrame(list(score_data.values("profile_id", "image_id", "score")))
        df = df.pivot_table(columns='image_id', index='profile_id', values='score').reset_index()
        data = df.to_numpy(dtype=np.float16)[:, 1:]
        self.image_ids = df.columns.values.tolist()[1:]
        self.user_ids = df.profile_id.tolist()
        self.raw_data = np.nan_to_num(data)

        # нормализовать и заполнить пустые нулями
        np.clip(data, -10, 1, data)
        masked_data = ma.masked_invalid(data, copy=False)
        ma_average = ma.average(masked_data, axis=1)
        masked_data = (masked_data.transpose() - ma_average).transpose()
        self.data = (masked_data.filled(fill_value=0).T + ma_average.filled()).T

    def update_cosine(self):
        # построить матрицу челик-челик
        similarity = np.dot(self.data, self.data.T)

        # squared magnitude of preference vectors (number of occurrences)
        square_mag = np.diag(similarity)

        # inverse squared magnitude
        inv_square_mag = 1 / square_mag

        # if it doesn't occur, set it's inverse magnitude to zero (instead of inf)
        inv_square_mag[np.isinf(inv_square_mag)] = 0

        # inverse of the magnitude
        inv_mag = np.sqrt(inv_square_mag)

        # cosine similarity (elementwise multiply by inverse magnitudes)
        cosine = similarity * inv_mag
        self.cosine = cosine.T * inv_mag

    def check_updates(self):
        self.update_counter += 1
        if self.update_counter > 10:
            self.update_counter = 0
            score_count = ImageScore.objects.count()
            if score_count - self.score_count > 30:
                self.score_count = score_count
                self.update_cosine()

    def predict(self, target_profile_id):
        self.update_data()
        self.check_updates()
        if target_profile_id not in self.user_ids:
            return [{
                "taste_similarity": 0,
                "image_id": random.choice(self.image_ids)
            }]

        profile_index = self.user_ids.index(target_profile_id)
        user_cosine = self.cosine[profile_index]
        items = np.where(self.raw_data[profile_index] == 0)
        if len(items[0]) == 0:
            return []
        prediction_data = self.raw_data[:, items]
        prediction = np.dot(prediction_data.T, user_cosine)[:, 0]
        top_items_pos = prediction.argsort()[-10:]
        predict_image = [
            {
                "taste_similarity": prediction[item_pos],
                "image_id": self.image_ids[items[0][item_pos]],
            } for item_pos in reversed(top_items_pos)
        ]
        print(predict_image)
        return predict_image


# def test_colab_filter():
#     data, image_id, user_id, raw_data = get_data()
#     cosine = get_cosine(data)
#
#     profile_index = 0
#     user_cosine = cosine[profile_index]
#     items = np.where(raw_data[profile_index] != 0)
#     prediction_data = raw_data[1:, items]
#     prediction = np.dot(prediction_data.T, user_cosine[1:])[:, 0]
#     prediction[prediction >= 0] = 1
#     prediction[prediction < 0] = -1
#     diff = raw_data[0, items].clip(-1, 1) - prediction
#     print('correct:', len(diff[diff == 0]))
#     print('false positive:', len(diff[diff == -2]))
#     print("false negative: ", len(diff[diff == 2]))