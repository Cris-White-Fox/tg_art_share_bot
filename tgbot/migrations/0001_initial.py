# Generated by Django 4.2 on 2023-04-17 16:11

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Profile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tg_id', models.IntegerField(unique=True, verbose_name='Идентификатор пользователя')),
                ('name', models.TextField(verbose_name='Имя пользователя')),
                ('last_activity', models.DateTimeField(auto_now_add=True, verbose_name='Дата последней активности')),
            ],
            options={
                'verbose_name': 'Профиль пользователя',
                'verbose_name_plural': 'Профили пользователей',
            },
        ),
        migrations.CreateModel(
            name='Image',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image_id', models.TextField(default='', verbose_name='Идентификатор изображения')),
                ('image_unique_id', models.TextField(unique=True, verbose_name='Уникальный идентификатор изображения')),
                ('image_hash', models.TextField(unique=True, verbose_name='Хэш изображения')),
                ('profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tgbot.profile', verbose_name='Профиль владельца')),
            ],
            options={
                'verbose_name': 'Изображение анкеты',
                'verbose_name_plural': 'Изображения анкет',
            },
        ),
        migrations.CreateModel(
            name='ImageScore',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('score', models.IntegerField(verbose_name='Результат взаимодействия')),
                ('datetime', models.DateTimeField(auto_now_add=True, verbose_name='Дата взаимодействия')),
                ('image', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='image', to='tgbot.image', verbose_name='Изображение')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user', to='tgbot.profile', verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Оценка изображения',
                'verbose_name_plural': 'Оценки изображений',
                'unique_together': {('user', 'image')},
            },
        ),
    ]
