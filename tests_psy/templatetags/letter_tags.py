from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.simple_tag
def render_letter(letter, top_strokes=0, bottom_strokes=0, is_target=False):
    """Rendu d'une lettre avec ses traits"""
    
    # Générer les traits du haut
    traits_haut_html = ""
    if top_strokes > 0:
        traits = ''.join(['<div class="w-0.5 h-2 bg-black"></div>'] * top_strokes)
        traits_haut_html = f'<div class="absolute -top-2 left-1/2 transform -translate-x-1/2 flex gap-0.5">{traits}</div>'
    
    # Générer les traits du bas
    traits_bas_html = ""
    if bottom_strokes > 0:
        traits = ''.join(['<div class="w-0.5 h-2 bg-black"></div>'] * bottom_strokes)
        traits_bas_html = f'<div class="absolute -bottom-2 left-1/2 transform -translate-x-1/2 flex gap-0.5">{traits}</div>'
    
    is_target_str = 'true' if is_target else 'false'
    
    html = f'''
    <label class="relative select-none cursor-pointer symbol-container inline-block" data-is-target="{is_target_str}">
      <input type="checkbox" class="hidden symbol-checkbox" onchange="handleSymbolClick(this)" />
      <span class="text-2xl font-normal">{letter}</span>
      {traits_haut_html}
      {traits_bas_html}
      <div class="absolute inset-0 hidden cross-marker flex items-center justify-center text-red-600 font-bold text-3xl">×</div>
    </label>
    '''
    
    return mark_safe(html)