# -*- coding: utf-8 -*-

from __future__ import unicode_literals
from decimal import Decimal
from internationalflavor.vat_number import VATNumberField
from django_countries.fields import CountryField
import datetime
import requests

from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.utils.timezone import now


class Client(models.Model):

    CURRENCY_HRK = u'HRK'
    CURRENCY_EUR = u'EUR'
    CURRENCY_USD = u'USD'
    CURRENCY_AUD = u'AUD'

    CURRENCY_CHOICES = (
        (CURRENCY_HRK, u'Hrvatska Kuna'),
        (CURRENCY_EUR, u'Euro'),
        (CURRENCY_USD, u'Američki dolar'),
        (CURRENCY_AUD, u'Australski dolar')
    )
    CURRENCY_DEFAULT = CURRENCY_HRK

    PAYMENT_METHOD_PAYPAL = 'PayPal'
    PAYMENT_METHOD_WIRETRANSFER = 'Wire-transfer'

    PAYMENT_METHOD_CHOICES = (
        (PAYMENT_METHOD_PAYPAL, u'Paypal'),
        (PAYMENT_METHOD_WIRETRANSFER, u'Wire-transfer')
    )
    PAYMENT_METHOD_DEFAULT = PAYMENT_METHOD_WIRETRANSFER

    class Meta:
        verbose_name = 'Klijent'
        verbose_name_plural = 'Klijenti'

    name = models.CharField(u'Naziv klijenta', max_length=120)
    address = models.TextField(u'Adresa')
    country = CountryField(u'Država', blank_label=u'(Odaberi državu)')
    vat_id = VATNumberField(default="", blank=True, verbose_name=u'VAT ID')
    currency = models.CharField(
        u'Valuta', max_length=30,
        choices=CURRENCY_CHOICES,
        default=CURRENCY_DEFAULT)
    default_payment_method = models.CharField(
        u'Način plaćanja',
        max_length=30,
        choices=PAYMENT_METHOD_CHOICES,
        default=PAYMENT_METHOD_DEFAULT)

    def __unicode__(self):
        return '%s, %s, %s' % (self.id, self.name, self.default_payment_method)

    def __str__(self):
        return '%s, %s, %s' % (self.id, self.name, self.default_payment_method)

    @property
    def reverse_charge(self):
        if self.country not in settings.VAT_DATA or self.country in settings.EXEMPTED_COUNTRIES:
            return False
        if not self.vat_id:
            return False
        return True


def _round2(x):
    return x.quantize(Decimal('0.01'))


def get_latest_invoice():
    val = Invoice.objects.filter(
        created__year=now().year).aggregate(latest=models.Max('seq'))['latest']
    return val + 1 if val is not None else 1


class Invoice(models.Model):

    class Meta:
        verbose_name = 'Račun'
        verbose_name_plural = 'Računi'

    created = models.DateTimeField(
        'Datum izrade računa',
        max_length=120,
        default=now,
        editable=True)
    seq = models.IntegerField(
        'Broj računa',
        default=get_latest_invoice,
        editable=True)
    due_date = models.DateTimeField(
        'Datum dospijeća',
        max_length=120,
        default=now,
        editable=True)
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name=u'invoices',
        verbose_name='Klijent')
    currency = models.CharField(
        'Valuta',
        max_length=120,
        choices=Client.CURRENCY_CHOICES,
        default=Client.CURRENCY_DEFAULT)
    default_payment_method = models.CharField(
        'Način plaćanja',
        max_length=120,
        choices=Client.PAYMENT_METHOD_CHOICES,
        default=Client.PAYMENT_METHOD_DEFAULT)
    exchange_rate = models.DecimalField(
        u'Tečaj',
        max_digits=12,
        decimal_places=6,
        default="1.00",
        null=True)
    vat_value = models.DecimalField(
        u'VAT',
        max_digits=3,
        decimal_places=2,
        blank=True)
    paid = models.BooleanField('Račun je plačen', default=False)

    @property
    def subtotal(self):
        val = self.items.aggregate(subtotal=models.Sum(u'amount'))[u'subtotal']
        return Decimal(val) if val is not None else Decimal(0)

    @property
    def subtotal_hrk(self):
        return _round2(self.subtotal * self.exchange_rate)

    @property
    def vat_amount(self):
        return _round2(self.subtotal * self.vat_value)

    @property
    def vat_hrk(self):
        return _round2(self.subtotal_hrk * self.vat_value)

    @property
    def total(self):
        return _round2(self.subtotal + self.vat_amount)

    @property
    def total_hrk(self):
        return _round2(self.subtotal_hrk + self.vat_hrk)

    @property
    def has_hourly(self):
        return self.items.filter(is_hourly=True).exists()

    def __unicode__(self):
        return str(self.seq) + '/VP1/1'

    def __str__(self):
        return str(self.seq) + '/VP1/1'

    def get_absolute_url(self):
        return reverse('invoice.views.print_invoice', kwargs={"id": self.id})

    def _calc_due_date(self):
        return self.created + datetime.timedelta(days=settings.PAYMENT_POSTPONE_RATE)

    def get_exchange_rate(self, currency, date):
        if currency == Client.CURRENCY_DEFAULT:
            return 1
        else:
            hnbex_url = u'http://hnbex.eu/api/v1/rates/daily/?date=' + date.strftime("%Y-%m-%d")
            currency_data = requests.get(hnbex_url).json()
            for items in range(len(currency_data)):
                if currency_data[items][u'currency_code'] == currency:
                    return Decimal(currency_data[items][u'median_rate'])
            return None

    def duplicate(self):
        new_inv = Invoice.objects.create(client=self.client, currency=self.currency)

        for item in self.items.all():
            new_inv.items.create(
                is_hourly=item.is_hourly,
                description=item.description,
                additional_info=item.additional_info,
                rate=item.rate,
                hours=item.hours,
                amount=item.amount)

        return new_inv

    # overwrite only on first save
    def save(self, *args, **kwargs):
        if self.id is None:
            self.due_date = self._calc_due_date()
        if self.client.reverse_charge:
            self.vat_value = 0
        else:
            self.vat_value = settings.VAT_DATA.get(self.client.country, 0)
        self.exchange_rate = self.get_exchange_rate(self.currency, self.created)
        super(Invoice, self).save(*args, **kwargs)


class InvoiceItem(models.Model):

    class Meta:
        verbose_name = 'Stavka računa'
        verbose_name_plural = 'Stavke računa'

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name=u'items')
    is_hourly = models.BooleanField(
        'Obračun po satu',
        default=True)
    description = models.CharField(
        'Opis stavke',
        max_length=300)
    additional_info = models.TextField(
        'Dodatni podaci',
        max_length=300,
        blank=True,
        null=True)
    amount = models.DecimalField(
        u'Iznos',
        max_digits=7,
        decimal_places=2,
        blank=True,
        null=True)
    rate = models.DecimalField(
        u'Cijena radnog sata',
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True)
    hours = models.DecimalField(
        u'Broj sati',
        max_digits=5,
        decimal_places=1,
        blank=True,
        null=True)

    @property
    def amount_hrk(self):
        return _round2(self.amount * self.invoice.exchange_rate)

    def __unicode__(self):
        return 'Stavka: %s' % (self.id)

    def __str__(self):
        return 'Stavka: %s' % (self.id)

    def clean(self):
        if self.is_hourly:
            if self.rate is None or self.hours is None:
                raise ValidationError("Broj sati i cijena radnog sata moraju biti navedeni")
        else:
            if self.amount is None:
                raise ValidationError("Iznos mora biti naveden")

    def save(self, *args, **kwargs):
        if self.is_hourly:
            self.amount = self.rate * self.hours
        super(InvoiceItem, self).save(*args, **kwargs)
