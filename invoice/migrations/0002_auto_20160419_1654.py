# -*- coding: utf-8 -*-
# Generated by Django 1.9.4 on 2016-04-19 14:54
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoice', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='invoiceitem',
            name='additional_info',
            field=models.TextField(blank=True, max_length=300, null=True, verbose_name='Dodatni podaci'),
        ),
    ]
