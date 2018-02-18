from django import forms
from django.contrib import admin
from django.conf.urls import patterns, url

from .models import Client, Invoice, InvoiceItem


def custom_titled_filter(title):
    class Wrapper(admin.FieldListFilter):
        def __new__(cls, *args, **kwargs):
            instance = admin.FieldListFilter.create(*args, **kwargs)
            instance.title = title
            return instance
    return Wrapper


def get_urls(self):
    urls = super(InvoiceAdmin, self).get_urls()
    my_urls = patterns(
        "",
        url(r"^upload_xml/$", self.admin_site.admin_view(self.upload_xml_view))
    )
    return my_urls + urls


class InvoiceItemForm(forms.ModelForm):
    class Meta:
        model = InvoiceItem
        fields = '__all__'
        widgets = {
          'additional_info': forms.Textarea(attrs={'rows': 2, 'cols': 30}),
        }


class InvoiceItemInline(admin.TabularInline):
    form = InvoiceItemForm
    model = InvoiceItem
    fields = ('is_hourly', 'description', 'additional_info', 'hours', 'rate', 'amount')
    extra = 1


class ClientAdmin(admin.ModelAdmin):
    fieldsets = [
        (None,  {'fields': [
            'name', 'address', 'country', 'vat_id', 'currency',
            'default_payment_method'
        ]}),
    ]
    list_display = ('name', 'address', 'country')


class InvoiceAdmin(admin.ModelAdmin):
    fields = (
        'seq', 'client', 'created', 'due_date', 'currency', 'exchange_rate',
        'vat_value', 'default_payment_method', 'paid'
    )
    inlines = [InvoiceItemInline]
    list_display = (
        '__unicode__', 'get_client_name', 'created', 'due_date', 'get_subtotal',
        'get_subtotal_hrk', 'get_vat_amount', 'get_vat_hrk', 'get_total',
        'get_total_hrk', 'paid'
    )
    list_filter = [
        ('created', custom_titled_filter('datumu')),
        ('client', custom_titled_filter('klijentu')),
        ('paid', custom_titled_filter('stanju racuna'))
    ]
    change_form_template = "admin/duplicate.html"

    def get_subtotal(self, obj):
        return str(obj.subtotal) + " " + str(obj.currency)
    get_subtotal.short_description = "Osnovica"

    def get_client_name(self, obj):
        return str(obj.client.name)
    get_client_name.short_description = "Klijent"

    def get_subtotal_hrk(self, obj):
        return obj.subtotal_hrk
    get_subtotal_hrk.short_description = "Osnovica(HRK)"

    def get_vat_amount(self, obj):
        return obj.vat_amount
    get_vat_amount.short_description = "PDV"

    def get_vat_hrk(self, obj):
        return obj.vat_hrk
    get_vat_hrk.short_description = "PDV(HRK)"

    def get_total(self, obj):
        return str(obj.total) + " " + str(obj.currency)
    get_total.short_description = "Ukupno"

    def get_total_hrk(self, obj):
        return obj.total_hrk
    get_total_hrk.short_description = "Ukupno(HRK)"

admin.site.register(Client, ClientAdmin)
admin.site.register(Invoice, InvoiceAdmin)
