from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.views.static import serve as serve_static
from cabinet.views import dashboard_view


def service_worker(request):
    """Sert sw.js à la racine (scope '/') plutôt que sous /static/."""
    response = serve_static(request, 'sw.js', document_root=settings.STATICFILES_DIRS[0])
    response['Service-Worker-Allowed'] = '/'
    response['Cache-Control'] = 'no-cache'
    return response


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', TemplateView.as_view(template_name='home.html'), name='home'),
    path('sw.js', service_worker, name='service_worker'),
    path('accounts/', include('accounts.urls')),
    path('cabinet/', include('cabinet.urls')),
    path('tests/', include('tests_psy.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)