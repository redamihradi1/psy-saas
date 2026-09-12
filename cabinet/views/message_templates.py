from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404

from ..models import MessageTemplate

DEFAULT_TEMPLATES = [
    {
        'nom': "Rappel veille (J-1)",
        'type_rappel': 'j-1',
        'contenu': (
            "Bonjour {patient}, je vous rappelle votre rendez-vous demain "
            "{date} à {heure} ({lieu}). À demain !"
        ),
    },
    {
        'nom': "Rappel 1h avant (H-1)",
        'type_rappel': 'h-1',
        'contenu': (
            "Bonjour {patient}, petit rappel : notre séance est dans 1h, "
            "à {heure} ({lieu}). À tout à l'heure !"
        ),
    },
]


@login_required
def message_templates_list(request):
    templates = MessageTemplate.objects.all()

    if not templates.exists():
        for data in DEFAULT_TEMPLATES:
            MessageTemplate.objects.create(organization=request.user.organization, **data)
        templates = MessageTemplate.objects.all()

    return render(request, 'cabinet/message_templates_list.html', {'templates': templates})


@login_required
def message_templates_json(request):
    """Liste des modèles au format JSON, pour le modal de rappel WhatsApp"""
    templates = MessageTemplate.objects.all()

    if not templates.exists():
        for data in DEFAULT_TEMPLATES:
            MessageTemplate.objects.create(organization=request.user.organization, **data)
        templates = MessageTemplate.objects.all()

    return JsonResponse({
        'templates': [
            {
                'id': template.id,
                'nom': template.nom,
                'type_rappel': template.type_rappel,
                'type_rappel_display': template.get_type_rappel_display(),
                'contenu': template.contenu,
            }
            for template in templates
        ]
    })


@login_required
def message_template_create(request):
    if request.method == 'POST':
        MessageTemplate.objects.create(
            organization=request.user.organization,
            nom=request.POST.get('nom', ''),
            type_rappel=request.POST.get('type_rappel', 'autre'),
            contenu=request.POST.get('contenu', ''),
        )
        messages.success(request, "Modèle créé avec succès.")
        return redirect('cabinet:message_templates_list')

    return render(request, 'cabinet/message_template_form.html', {
        'title': 'Nouveau modèle',
        'type_choices': MessageTemplate.TYPE_CHOICES,
    })


@login_required
def message_template_edit(request, template_id):
    template = get_object_or_404(MessageTemplate, id=template_id)

    if request.method == 'POST':
        template.nom = request.POST.get('nom', template.nom)
        template.type_rappel = request.POST.get('type_rappel', template.type_rappel)
        template.contenu = request.POST.get('contenu', template.contenu)
        template.save()
        messages.success(request, "Modèle modifié avec succès.")
        return redirect('cabinet:message_templates_list')

    return render(request, 'cabinet/message_template_form.html', {
        'title': f"Modifier « {template.nom} »",
        'template': template,
        'type_choices': MessageTemplate.TYPE_CHOICES,
    })


@login_required
def message_template_delete(request, template_id):
    template = get_object_or_404(MessageTemplate, id=template_id)

    if request.method == 'POST':
        template.delete()
        messages.success(request, "Modèle supprimé.")
        return redirect('cabinet:message_templates_list')

    return render(request, 'cabinet/message_template_delete.html', {'template': template})
