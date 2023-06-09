# Generated by Django 4.2 on 2023-05-07 05:45

from django.db import migrations, models
import django.db.models.deletion
import tgbot.models


class Migration(migrations.Migration):

    dependencies = [
        ('tgbot', '0011_report_image_file'),
    ]

    operations = [
        migrations.CreateModel(
            name='ImageBlock',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('datetime', models.DateTimeField(default=tgbot.models.datetime_now, verbose_name='Дата взаимодействия')),
                ('image', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='block', to='tgbot.image', verbose_name='Изображение')),
            ],
        ),
    ]
