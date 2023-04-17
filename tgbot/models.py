from django.db import models


class Profile(models.Model):
    tg_id = models.IntegerField(verbose_name="Идентификатор пользователя", unique=True)
    name = models.TextField(verbose_name="Имя пользователя")
    last_activity = models.DateTimeField(verbose_name="Дата последней активности", auto_now_add=True)

    class Meta:
        verbose_name = "Профиль пользователя"
        verbose_name_plural = "Профили пользователей"

    def __str__(self) -> str:
        return f"Пользователь: {self.name} - {self.tg_id} ({self.last_activity})"


class Image(models.Model):
    profile = models.ForeignKey(Profile, verbose_name="Профиль владельца", on_delete=models.CASCADE)
    image_id = models.TextField(verbose_name="Идентификатор изображения", default="")
    image_unique_id = models.TextField(verbose_name="Уникальный идентификатор изображения", unique=True)
    image_hash = models.TextField(verbose_name="Хэш изображения", unique=True)

    class Meta:
        verbose_name = "Изображение анкеты"
        verbose_name_plural = "Изображения анкет"

    def __str__(self) -> str:
        return f"Изображение: {self.image_unique_id} ({self.profile})"


class ImageScore(models.Model):
    user = models.ForeignKey(Profile, verbose_name="Пользователь", related_name='user', on_delete=models.CASCADE)
    image = models.ForeignKey(Image, verbose_name="Изображение", related_name='image', on_delete=models.CASCADE)
    score = models.IntegerField(verbose_name="Результат взаимодействия")
    datetime = models.DateTimeField(verbose_name="Дата взаимодействия", auto_now_add=True)

    class Meta:
        verbose_name = "Оценка изображения"
        verbose_name_plural = "Оценки изображений"
        unique_together = ['user', 'image']

    def __str__(self) -> str:
        return f"Взаимодействие: {self.user} - {self.image} ({self.score})"