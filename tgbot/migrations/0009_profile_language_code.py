# Generated by Django 4.2 on 2023-05-05 10:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tgbot', '0008_alter_image_datetime_alter_imagescore_datetime_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='language_code',
            field=models.TextField(default='en', verbose_name='Код языка'),
        ),
    ]