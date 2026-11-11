from pulso import news

RSS = b"""<?xml version="1.0"?><rss><channel>
<item><title>Comuneros de Fuerabamba bloquean el corredor minero - RPP Noticias</title>
<link>https://news.google.com/rss/articles/abc</link><pubDate>Mon, 09 Nov 2026 14:00:00 GMT</pubDate>
<description>&lt;a href="x"&gt;Comuneros de Fuerabamba bloquean el corredor minero&lt;/a&gt;</description>
<source url="https://rpp.pe">RPP Noticias</source></item>
<item><title>Selecci&#243;n peruana convoca a nuevos jugadores</title>
<link>https://elcomercio.pe/deporte</link><pubDate>Mon, 09 Nov 2026 10:00:00 GMT</pubDate></item>
<item><title>Sin fecha</title><link>https://larepublica.pe/x</link></item>
</channel></rss>"""


def test_parse_keeps_real_outlet_and_drops_undated_items():
    items = news.parse(RSS, 'Google News', 'feed')
    assert [i['outlet'] for i in items] == ['RPP Noticias', 'Google News']
    assert items[0]['title'] == 'Comuneros de Fuerabamba bloquean el corredor minero'
    assert items[0]['snippet'] == ''  # Google News repeats the headline as description


def test_classify_links_company_case_and_tags():
    first, sports = news.parse(RSS, 'Google News', 'feed')
    companies, cases, tags = news.classify(first)
    assert companies == ['mineria']
    assert cases == ['1132-1218']  # 'corredor minero' alone needs an anchor term
    assert 'Medida de fuerza' in tags
    assert news.classify(sports)[0] == []


def test_homonyms_need_an_anchor_term():
    park = {'title': 'Bosque de 24.000 árboles del parque Sinchi Roca en Comas desapareció', 'snippet': ''}
    huanuco = {'title': 'Disputa territorial entre la Comunidad Nativa Sinchi Roca y posesionarios en Irazola, Huánuco', 'snippet': ''}
    spill = {'title': 'Derrame en Sinchi Roca, Manseriche: comunidades exigen agua', 'snippet': ''}
    assert news.classify(park)[:2] == ([], [])
    assert news.classify(huanuco)[:2] == ([], [])
    assert news.classify(spill)[:2] == (['hidrocarburos'], ['1403-0325'])
