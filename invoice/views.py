from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.views.decorators.http import require_http_methods
from django.shortcuts import render, redirect, get_object_or_404

from .models import Invoice


@login_required
def print_invoice(request, id=None):
    instance = get_object_or_404(Invoice, id=id)

    context = {
        "instance": instance,
        "instance_items": instance.items.all(),
        "vat": int(instance.vat_value * 100),
        "colspan": 4 if instance.has_hourly else 2,
    }
    return render(request, "admin/print.html", context)


@require_http_methods(["POST"])
@login_required
def duplicate_invoice(request, id=None):
    current_inv = get_object_or_404(Invoice, id=id)
    new_inv = current_inv.duplicate()
    change_url = reverse(
        'admin:invoice_invoice_change',
        args=(new_inv.id,),
        current_app='invoice')
    return redirect(change_url)
