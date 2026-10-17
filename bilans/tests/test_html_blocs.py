from django.test import SimpleTestCase

from bilans import html_blocs as hb


class NettoyageTests(SimpleTestCase):

    def test_supprime_scripts_attributs_et_liens(self):
        sale = ('<p onclick="x()">Bonjour <script>alert(1)</script><a href="javascript:x">lien</a>'
                '<img src=x onerror=alert(1)><span style="color:red">rouge</span></p>')
        propre = hb.nettoyer(sale)
        self.assertEqual(propre, '<p>Bonjour lienrouge</p>')

    def test_conserve_mise_en_forme_listes_et_tableaux(self):
        html = ('<h2 data-section="motif" data-type="ia">Motif</h2><p><b>Gras</b> et <em>italique</em> '
                'et <u>souligné</u></p><ul><li>un</li><li><p>deux</p></li></ul>'
                '<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>')
        self.assertEqual(hb.nettoyer(html), '\n'.join([
            '<h2 data-section="motif" data-type="ia">Motif</h2>',
            '<p><strong>Gras</strong> et <em>italique</em> et <u>souligné</u></p>',
            '<ul><li>un</li><li>deux</li></ul>',
            '<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>',
        ]))

    def test_attribut_section_invalide_ignore(self):
        propre = hb.nettoyer('<h2 data-section="x&quot; onload=&quot;y" data-type="pirate">Titre</h2>')
        self.assertEqual(propre, '<h2>Titre</h2>')
        propre = hb.nettoyer('<h2 data-section="ok" data-type="pirate">Titre</h2>')
        self.assertEqual(propre, '<h2 data-section="ok" data-type="libre">Titre</h2>')

    def test_echappe_le_texte(self):
        self.assertEqual(hb.nettoyer('<p>&lt;script&gt; 3 &lt; 5</p>'), '<p>&lt;script&gt; 3 &lt; 5</p>')

    def test_div_de_contenteditable_devient_paragraphe(self):
        self.assertEqual(hb.nettoyer('<div>ligne 1</div><div>ligne 2<br></div>texte libre'),
                         '<p>ligne 1</p>\n<p>ligne 2</p>\n<p>texte libre</p>')

    def test_idempotent(self):
        html = hb.nettoyer('<h1>T</h1><p>a<br>b</p><ol><li>x</li></ol>')
        self.assertEqual(hb.nettoyer(html), html)


class SectionsEtTexteTests(SimpleTestCase):

    def test_decouper_et_reassembler(self):
        blocs = hb.lire('<h1>Bilan</h1><h2 data-section="a" data-type="ia">A</h2><p>x</p>'
                        '<h2>Sous-partie libre</h2><p>y</p><h2 data-section="b" data-type="auto">B</h2>')
        preambule, sections = hb.decouper_sections(blocs)
        self.assertEqual(len(preambule), 1)
        self.assertEqual([s[0]['section'] for s in sections], ['a', 'b'])
        self.assertEqual(len(sections[0][1]), 3)  # le h2 sans section reste dans "a"
        self.assertEqual(hb.assembler_sections(preambule, sections), blocs)

    def test_blocs_depuis_texte_ia(self):
        blocs = hb.blocs_depuis_texte("Premier **important** paragraphe.\n\n- un\n- deux\n\nFin\nsuite")
        self.assertEqual([b['type'] for b in blocs], ['p', 'ul', 'p'])
        self.assertEqual(blocs[0]['runs'][1], {'t': 'important', 'b': True, 'i': False, 'u': False})
        self.assertEqual(len(blocs[1]['items']), 2)
        self.assertIn({'br': True}, blocs[2]['runs'])

    def test_markdown_ia_titres_et_listes_sans_ligne_vide(self):
        texte = ("## Éléments d'anamnèse :\n- Scolarité : [à compléter]\n- Santé : RAS\nPhrase finale.\n"
                 "### Vineland\nCommentaire")
        blocs = hb.blocs_depuis_texte(texte, titre_a_ignorer="Éléments d'anamnèse")
        self.assertEqual([b['type'] for b in blocs], ['ul', 'p', 'h3', 'p'])
        self.assertEqual(len(blocs[0]['items']), 2)
        self.assertEqual(hb.texte_runs(blocs[2]['runs']), 'Vineland')

    def test_en_texte(self):
        texte = hb.en_texte(hb.lire('<h2 data-section="r" data-type="auto">Résultats</h2>'
                                    '<table><tr><th>Échelle</th><th>T</th></tr><tr><td>Inhibition</td><td>70</td></tr></table>'))
        self.assertIn('## Résultats', texte)
        self.assertIn('| Inhibition | 70 |', texte)
