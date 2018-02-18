"""project URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.9/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""

from django.conf.urls import url
from django.contrib import admin

from invoice.views import print_invoice, duplicate_invoice

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^invoice/(?P<id>\d+)/$', print_invoice),
    url(r'^invoice/(?P<id>\d+)/duplicate/$', duplicate_invoice, name="duplicate_invoice"),
]

homepage_title = 'Dobar kod - Simple invoicer'
admin.site.site_header = homepage_title
admin.site.site_url = None
