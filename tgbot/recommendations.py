import random
import time

import pandas as pd
import numpy as np
import numpy.ma as ma

from tgbot.models import ImageScore, ImageBlock, Image
from tgbot.helpers import timeit


class ColabFilter():
    def __init__(self):
        self.image_ids = None
        self.user_ids = None
        self.raw_data = None
        self.data = None
        self.cosine = None
        if self.update_data_from_db():
            self.update_cosine()
        self.update_timer = time.time()
        self.image_count = Image.objects.count()

    @timeit
    def update_data_from_db(self):
        score_data = ImageScore.objects.exclude(image__in=ImageBlock.objects.values("image"))
        if not score_data:
            return
        df = pd.DataFrame(list(score_data.values("profile_id", "image_id", "score")))
        df = df.pivot_table(columns='image_id', index='profile_id', values='score').reset_index()
        data = df.to_numpy(dtype=np.float16)[:, 1:]
        self.image_ids = df.columns.values.tolist()[1:]
        self.user_ids = df.profile_id.tolist()
        self.raw_data = np.nan_to_num(data)

        # нормализовать и заполнить пустые нулями
        masked_data = ma.masked_invalid(data, copy=False)
        ma_average = ma.average(masked_data, axis=1)
        masked_data = (masked_data.transpose() - ma_average).transpose()
        self.data = masked_data.filled(fill_value=0)
        return True

    @timeit
    def update_score(self, profile_id, image_id, score):
        if profile_id not in self.user_ids or image_id not in self.image_ids:
            return
        profile_index = self.user_ids.index(profile_id)
        image_index = self.image_ids.index(image_id)

        self.raw_data[profile_index, image_index] = score
        return True

    @timeit
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
        image_count = Image.objects.count()
        if image_count - self.image_count > 25 and time.time() - self.update_timer > 15 * 60:
            self.image_count = image_count
            if self.update_data_from_db():
                self.update_cosine()
            self.update_timer = time.time()

    @timeit
    def predict(self, target_profile_id):
        self.check_updates()
        if target_profile_id not in self.user_ids:
            return [{
                "taste_similarity": 0,
                "image_id": random.choice(self.image_ids)
            }]

        profile_index = self.user_ids.index(target_profile_id)
        last_dislikes = ImageScore.last_dislikes(target_profile_id)
        users = np.setdiff1d(
            np.where(self.cosine[profile_index] > 0),
            np.array([self.user_ids.index(profile_id) for profile_id in last_dislikes])
        )
        items = np.where(self.raw_data[profile_index] == 0)
        if len(items[0]) == 0:
            return []
        user_cosine_data = self.cosine[profile_index, users]

        prediction_data = self.raw_data[users, :][:, items[0]]
        prediction = np.dot(prediction_data.T, user_cosine_data) / np.sqrt(np.count_nonzero(prediction_data, axis=0) + 1)
        top_items_pos = prediction.argsort()[-50:]
        predict_image = [
            {
                "taste_similarity": prediction[item_pos],
                "image_id": self.image_ids[items[0][item_pos]],
            } for item_pos in reversed(top_items_pos)
        ]
        return predict_image

    def test_colab_filter(self):
        for profile_index, target_profile_id in enumerate(self.user_ids):
            users = np.where(self.cosine[profile_index] > 0)
            items = np.where(self.raw_data[profile_index] != 0)
            if len(items[0]) == 0:
                continue
            user_cosine_data = self.cosine[profile_index, users][0]
            prediction_data = self.raw_data[users, :][0, :, :][:, items][:, 0, :]
            raw_prediction = np.dot(prediction_data.T, user_cosine_data)
            scores_count = np.count_nonzero(prediction_data, axis=0) + 1
            prediction = raw_prediction / scores_count

            prediction[prediction >= 0] = 1
            prediction[prediction < 0] = -1
            rd = self.raw_data[0, items]
            rd[rd >= 0] = 1
            rd[rd < 0] = -1
            diff = rd - prediction
            print('correct:', len(diff[diff == 0]), '| false positive:', len(diff[diff == -2]), "| false negative: ", len(diff[diff == 2]), "| result: ", len(diff[diff == 0]) / len(diff[0]))
