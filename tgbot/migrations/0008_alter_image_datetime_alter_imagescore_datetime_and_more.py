# Generated by Django 4.2 on 2023-04-24 16:53

from django.db import migrations, models
import tgbot.models


class Migration(migrations.Migration):

    dependencies = [
        ('tgbot', '0007_alter_image_options_profile_last_bot_message_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='image',
            name='datetime',
            field=models.DateTimeField(default=tgbot.models.datetime_now, verbose_name='Дата добавления'),
        ),
        migrations.AlterField(
            model_name='imagescore',
            name='datetime',
            field=models.DateTimeField(default=tgbot.models.datetime_now, verbose_name='Дата взаимодействия'),
        ),
        migrations.AlterField(
            model_name='profile',
            name='last_activity',
            field=models.DateTimeField(default=tgbot.models.datetime_now, verbose_name='Активность пользователя'),
        ),
        migrations.AlterField(
            model_name='profile',
            name='last_bot_message',
            field=models.DateTimeField(default=tgbot.models.datetime_now, verbose_name='Сообщение от бота'),
        ),
    ]