# -*- coding: utf-8 -*-

import mock
from datetime import datetime, timedelta
from decimal import Decimal
from freezegun import freeze_time

from django.conf import settings
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils.timezone import now, make_aware

from .models import Client, Invoice, InvoiceItem


HNBEX_2016_01_01 = [{
    "median_rate": "7.000907",
    "selling_rate": "7.021910",
    "buying_rate": "6.979904",
    "unit_value": 1,
    "currency_code": "USD"
}]

MOCK_JSON_ATTRS = {"get.return_value.json.return_value": HNBEX_2016_01_01}


class TestClient(TestCase):

    def test_eu_firm_with_vat_number_should_have_reverse_charge(self):
        client = Client.objects.create(country='SE', vat_id='SE999999999901')
        self.assertTrue(client.reverse_charge)

    def test_croatian_firm_should_not_have_reverse_charge(self):
        client = Client.objects.create(country='HR', vat_id='HR2112211221')
        self.assertFalse(client.reverse_charge)

    def test_eu_firm_without_vat_number_should_not_have_reverse_charge(self):
        client = Client.objects.create(country='SE')
        self.assertFalse(client.reverse_charge)

    def test_non_eu_firm_should_not_have_reverse_charge(self):
        client = Client.objects.create(country='US')
        self.assertFalse(client.reverse_charge)


@mock.patch('invoice.models.requests', **MOCK_JSON_ATTRS)
class TestInvoice(TestCase):

    def setUp(self):
        self.client = Client.objects.create()

    def test_usd_exchange_rate_retrieved_correctly(self, requests):
        invoice = Invoice.objects.create(
            client=self.client,
            currency='USD', created=make_aware(datetime(2016, 1, 1)))
        self.assertEqual(requests.get.return_value.json.call_count, 1)
        self.assertEqual(invoice.exchange_rate, Decimal('7.000907'))

    def test_hrk_exchange_rate_retrieved_correctly(self, requests):
        invoice = Invoice.objects.create(client=self.client, currency='HRK')
        self.assertEqual(requests.get.return_value.json.call_count, 0)
        self.assertEqual(invoice.exchange_rate, Decimal('1'))

    def test_invalid_exchange_rate_retrieves_none(self, requests):
        invoice = Invoice.objects.create(client=self.client, currency='DJANGO')
        self.assertEqual(requests.get.return_value.json.call_count, 1)
        self.assertEqual(invoice.exchange_rate, None)

    def test_subtotal_calc_for_two_items(self, requests):
        invoice = Invoice.objects.create(client=self.client)
        invoice.items.create(is_hourly=False, amount=10)
        invoice.items.create(is_hourly=False, amount=5)
        self.assertEqual(requests.get.return_value.json.call_count, 0)
        self.assertEqual(invoice.subtotal, 15)

    def test_hourly_and_rate_subtotal_calc_for_two_items(self, requests):
        invoice = Invoice.objects.create(client=self.client)
        invoice.items.create(rate=5, hours=2)
        invoice.items.create(rate=10, hours=2)
        self.assertEqual(requests.get.return_value.json.call_count, 0)
        self.assertEqual(invoice.subtotal, 30)

    def test_subtotal_calc_for_no_items_returns_zero(self, requests):
        invoice = Invoice.objects.create(client=self.client)
        self.assertEqual(requests.get.return_value.json.call_count, 0)
        self.assertEqual(invoice.subtotal, Decimal('0'))

    def test_calc_subtotal_hrk_for_fixed_usd_currency(self, requests):
        invoice = Invoice.objects.create(
            client=self.client,
            currency='USD', created=make_aware(datetime(2016, 1, 1)))
        invoice.items.create(is_hourly=False, amount=10)
        self.assertEqual(requests.get.return_value.json.call_count, 1)
        self.assertEqual(invoice.subtotal_hrk, Decimal('70.01'))

    def test_vat_amount_for_croatia_returns_correct_amount(self, requests):
        invoice = Invoice.objects.create(client=self.client)
        invoice.client.country = 'HR'
        invoice.items.create(is_hourly=False, amount=100)
        invoice.save()
        self.assertEqual(requests.get.return_value.json.call_count, 0)
        self.assertEqual(invoice.vat_amount, settings.VAT_DATA['HR'] * 100)

    def test_vat_amount_for_eu_returns_zero(self, requests):
        invoice = Invoice.objects.create(client=self.client)
        invoice.client.country = 'UK'
        invoice.items.create(is_hourly=False, amount=100)
        invoice.save()
        self.assertEqual(requests.get.return_value.json.call_count, 0)
        self.assertEqual(invoice.vat_amount, 0)

    def test_subtotal_plus_vat_amount_returns_correct_total(self, requests):
        invoice = Invoice.objects.create(client=self.client)
        invoice.client.country = 'HR'
        invoice.save()
        self.assertEqual(requests.get.return_value.json.call_count, 0)
        self.assertEqual(invoice.total, invoice.subtotal + invoice.vat_amount)

    def test_total_hrk_converts_total_correctly(self, requests):
        invoice = Invoice.objects.create(
            client=self.client,
            currency='USD', created=make_aware(datetime(2016, 1, 1)))
        invoice.items.create(is_hourly=False, amount=100)
        self.assertEqual(requests.get.return_value.json.call_count, 1)
        self.assertEqual(invoice.total_hrk, Decimal('700.09'))

    def test_first_invoice_always_has_seq_1(self, requests):
        invoice = self.client.invoices.create()
        self.assertEqual(requests.get.return_value.json.call_count, 0)
        self.assertEqual(invoice.seq, 1)

    def test_second_invoice_always_has_seq_1_plus_1(self, requests):
        self.client.invoices.create()
        second_invoice = self.client.invoices.create()
        self.assertEqual(requests.get.return_value.json.call_count, 0)
        self.assertEqual(second_invoice.seq, 2)

    def test_invoice_seq_is_always_increased_for_current_year(self, requests):
        self.client.invoices.create()
        second_invoice = self.client.invoices.create()
        self.assertEqual(requests.get.return_value.json.call_count, 0)
        self.assertEqual(second_invoice.seq, 2)

    def test_invoice_seq_is_always_increased_for_current_year_with_gaps(self, requests):
        self.client.invoices.create()
        self.client.invoices.create()
        third_invoice = self.client.invoices.create()
        self.assertEqual(requests.get.return_value.json.call_count, 0)
        self.assertEqual(third_invoice.seq, 3)

    def test_invoice_seq_ignores_other_years(self, requests):
        self.client.invoices.create(
            created=now().replace(day=1, month=1, year=2015))
        second_invoice = self.client.invoices.create(
            created=now().replace(day=1, month=1, year=2016))
        self.assertEqual(requests.get.return_value.json.call_count, 0)
        self.assertEqual(second_invoice.seq, 1)

    @override_settings(PAYMENT_POSTPONE_RATE=0)
    @freeze_time('2016-01-01')
    def test_invoice_due_date_with_PPR_of_0(self, requests):
        invoice = self.client.invoices.create()
        self.assertEqual(requests.get.return_value.json.call_count, 0)
        self.assertEqual(invoice.due_date, invoice.created)

    @override_settings(PAYMENT_POSTPONE_RATE=100)
    @freeze_time('2016-01-01')
    def test_invoice_due_date_with_PPR_of_100(self, requests):
        invoice = self.client.invoices.create()
        self.assertEqual(requests.get.return_value.json.call_count, 0)
        self.assertEqual(invoice.due_date - invoice.created, timedelta(days=100))

    @override_settings(PAYMENT_POSTPONE_RATE=1000)
    @freeze_time('2016-01-01')
    def test_invoice_due_date_with_PPR_of_1000(self, requests):
        invoice = self.client.invoices.create()
        self.assertEqual(requests.get.return_value.json.call_count, 0)
        self.assertEqual(invoice.due_date - invoice.created, timedelta(days=1000))

    @override_settings(PAYMENT_POSTPONE_RATE=-5)
    @freeze_time('2016-01-01')
    def test_invoice_due_date_with_PPR_of_negative_value(self, requests):
        invoice = self.client.invoices.create()
        self.assertEqual(requests.get.return_value.json.call_count, 0)
        self.assertEqual(invoice.due_date - invoice.created, timedelta(days=-5))

    def test_invoice_client_has_reverse_charge_with_value_of_zero(self, requests):
        self.client = Client.objects.create(country='SE', vat_id='SE999999999901')
        invoice = self.client.invoices.create()
        self.assertEqual(requests.get.return_value.json.call_count, 0)
        self.assertEqual(invoice.vat_value, 0)

    def test_invoice_has_hourly(self, requests):
        invoice = self.client.invoices.create()
        invoice.items.create(is_hourly=False)
        self.assertFalse(invoice.has_hourly)
        invoice.items.create(is_hourly=True, hours=10, rate=15)
        self.assertTrue(invoice.has_hourly)
        invoice.items.create(is_hourly=False)
        self.assertTrue(invoice.has_hourly)


class TestInvoiceDuplicate(TestCase):

    def setUp(self):
        self.client = Client.objects.create()

    def test_duplicated_invoice_has_the_same_client(self):
        current_invoice = self.client.invoices.create()
        new_invoice = current_invoice.duplicate()
        self.assertEqual(new_invoice.client.id, current_invoice.client.id)

    @mock.patch('invoice.models.requests', **MOCK_JSON_ATTRS)
    def test_duplicated_invoice_has_same_currency(self, requests):
        current_invoice = self.client.invoices.create(currency='USD')
        new_invoice = current_invoice.duplicate()
        self.assertEqual(requests.get.return_value.json.call_count, 2)
        self.assertEqual(new_invoice.currency, current_invoice.currency)

    def test_duplicated_invoice_items_have_same_attributes(self):
        current_invoice = self.client.invoices.create()
        current_invoice.items.create(is_hourly=False, amount=1024)
        new_invoice = current_invoice.duplicate()
        self.assertEqual(
            list(current_invoice.items.all().values_list('amount')),
            list(new_invoice.items.all().values_list('amount')))
        self.assertEqual(
            list(current_invoice.items.all().values_list('rate')),
            list(new_invoice.items.all().values_list('rate')))
        self.assertEqual(
            list(current_invoice.items.all().values_list('hours')),
            list(new_invoice.items.all().values_list('hours')))
        self.assertEqual(
            list(current_invoice.items.all().values_list('additional_info')),
            list(new_invoice.items.all().values_list('additional_info')))
        self.assertEqual(
            list(current_invoice.items.all().values_list('description')),
            list(new_invoice.items.all().values_list('description')))
        self.assertEqual(
            list(current_invoice.items.all().values_list('is_hourly')),
            list(new_invoice.items.all().values_list('is_hourly')))

    @freeze_time('2016-01-01')
    def test_duplicated_invoice_items_do_not_duplicate_created_time(self):
        current_invoice = self.client.invoices.create()
        self.assertEqual(current_invoice.created, make_aware(datetime(2016, 1, 1)))
        with freeze_time('2016-01-02'):
            new_invoice = current_invoice.duplicate()
        self.assertEqual(new_invoice.created, make_aware(datetime(2016, 1, 2)))
        self.assertNotEqual(current_invoice.created, new_invoice.created)

    @freeze_time('2016-01-01')
    def test_duplicated_invoice_items_have_different_due_date(self):
        current_invoice = self.client.invoices.create()
        self.assertEqual(current_invoice.due_date, make_aware(datetime(2016, 1, 15)))
        with freeze_time('2016-01-02'):
            new_invoice = current_invoice.duplicate()
        self.assertEqual(new_invoice.due_date, make_aware(datetime(2016, 1, 16)))
        self.assertNotEqual(current_invoice.due_date, new_invoice.due_date)


class TestInvoiceItem(TestCase):

    def setUp(self):
        self.client = Client.objects.create()
        self.invoice = Invoice.objects.create(client=self.client)

    def test_calculated_amount_for_no_hourly(self):
        item = InvoiceItem.objects.create(invoice=self.invoice, is_hourly=False, amount=1024)
        self.assertEqual(item.amount, 1024)

    def test_calculated_amount_for_rate_and_hours(self):
        item = InvoiceItem.objects.create(invoice=self.invoice, is_hourly=True, rate=10, hours=5)
        self.assertEqual(item.amount, 50)

    def test_hourly_item_should_have_rate_and_hours(self):
        item = InvoiceItem(invoice=self.invoice, is_hourly=True, hours=None)
        self.assertRaises(ValidationError, item.clean)

    def test_hourly_item_should_have_rate(self):
        item = InvoiceItem(invoice=self.invoice, is_hourly=True, hours=100)
        self.assertRaises(ValidationError, item.clean)

    def test_fixed_item_should_have_amount(self):
        item = InvoiceItem.objects.create(invoice=self.invoice, is_hourly=False)
        self.assertRaises(ValidationError, item.clean)

    @mock.patch('invoice.models.requests', **MOCK_JSON_ATTRS)
    def test_amount_hrk_is_properly_rounded(self, requests):
        self.invoice = Invoice.objects.create(
            client=self.client,
            currency='USD',
            created=make_aware(datetime(2016, 1, 1))
            )
        item = InvoiceItem(invoice=self.invoice, amount=1024)
        self.assertEqual(requests.get.return_value.json.call_count, 1)
        # amount_hrk = _round2(self.amount * self.invoice.exchange_rate (median_rate))
        self.assertEqual(item.amount_hrk, Decimal('7168.93'))


class TestsViews(TestCase):

    def setUp(self):
        self.invoice = Invoice.objects.create(client=Client.objects.create(), seq=50)
        self.user = User.objects.create_user(
            username='test_user',
            email='test_user@dobarkod.hr', password='test_password')
        self.client.login(username='test_user', password='test_password')

    def test_non_logged_in_user_should_be_redirected(self):
        self.client.logout()
        response = self.client.get('/invoice/1/')
        self.assertEqual(response.status_code, 302)

    def test_logged_in_user_has_access(self):
        response = self.client.get('/invoice/1/')
        self.assertEqual(response.status_code, 200)

    def test_querying_non_existing_invoice_returns_404(self):
        response = self.client.get('/invoice/707/')
        self.assertEqual(response.status_code, 404)

    def test_view_uses_correct_context(self):
        response = self.client.get('/invoice/1/')
        self.assertIsInstance(response.context['instance'], Invoice)

    def test_view_uses_correct_template(self):
        response = self.client.get('/invoice/1/')
        self.assertTemplateUsed(response, 'admin/print.html')

    def test_duplicate_invoice_view_redirects_if_method_is_post(self):
        reverse_url = reverse('duplicate_invoice', args=[self.invoice.id])
        response = self.client.post(reverse_url)
        self.assertEqual(response.status_code, 302)

    def test_duplicate_invoice_view_returns_405_if_method_is_get(self):
        reverse_url = reverse('duplicate_invoice', args=[self.invoice.id])
        response = self.client.get(reverse_url)
        self.assertEqual(response.status_code, 405)
