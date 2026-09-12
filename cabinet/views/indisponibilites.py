from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from ..models import Indisponibilite

TYPE_COLORS = {
    'formation': '#a78bfa',
    'deplacement': '#fbbf24',
    'conge': '#34d399',
    'autre': '#9ca3af',
}


@login_required
def indisponibilites_api(request):
    """API JSON pour FullCalendar (agenda)"""
    indisponibilites = Indisponibilite.objects.all()

    events = [
        {
            'id': f"indispo-{i.id}",
            'title': f"🚫 {i.titre}",
            'start': i.date_debut.isoformat(),
            'end': i.date_fin.isoformat(),
            'color': TYPE_COLORS.get(i.type_absence, '#9ca3af'),
            'editable': False,
            'extendedProps': {
                'event_type': 'indisponibilite',
                'indisponibilite_id': i.id,
                'type_absence': i.get_type_absence_display(),
                'note': i.note or '',
            }
        }
        for i in indisponibilites
    ]
    return JsonResponse(events, safe=False)


@login_required
@require_http_methods(["POST"])
def indisponibilite_create(request):
    date_debut = request.POST.get('date_debut')
    date_fin = request.POST.get('date_fin')

    try:
        Indisponibilite.objects.create(
            organization=request.user.organization,
            titre=request.POST.get('titre', '').strip() or 'Indisponible',
            type_absence=request.POST.get('type_absence', 'autre'),
            date_debut=date_debut,
            date_fin=date_fin,
            note=request.POST.get('note', ''),
        )
        messages.success(request, "Période bloquée dans l'agenda.")
    except (ValueError, TypeError):
        messages.error(request, "Dates invalides.")

    return redirect('cabinet:agenda')


@login_required
@require_http_methods(["POST"])
def indisponibilite_delete(request, indisponibilite_id):
    indisponibilite = get_object_or_404(Indisponibilite, id=indisponibilite_id)
    indisponibilite.delete()
    messages.success(request, "Blocage supprimé.")
    return redirect('cabinet:agenda')
