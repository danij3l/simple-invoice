# -*- coding: utf-8 -*-
# Generated by Django 1.9.4 on 2016-04-28 16:24
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoice', '0004_auto_20160426_1333'),
    ]

    operations = [
        migrations.AlterField(
            model_name='invoice',
            name='exchange_rate',
            field=models.DecimalField(blank=True, decimal_places=6, default='1.00', max_digits=12, verbose_name='Te\u010daj'),
        ),
    ]