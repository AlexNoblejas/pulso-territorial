from pulso import national


def test_parse_location_handles_the_ways_the_defensoria_writes_places():
    assert national.parse_location('Distrito y provincia de San Ignacio', 'Cajamarca') == ('SAN IGNACIO', 'SAN IGNACIO', 'CAJAMARCA')
    assert national.parse_location('Distrito de Cáceres del Perú, provincia del Santa, departamento de Áncash', 'Áncash') == ('CACERES DEL PERU', 'SANTA', 'ANCASH')
    assert national.parse_location('Distrito Trompeteros, provincia de Loreto, departamento de Loreto.', 'Loreto')[:2] == ('TROMPETEROS', 'LORETO')
    assert national.parse_location('Provincia de Espinar, departamento de Cusco.', 'Cusco') == ('', 'ESPINAR', 'CUSCO')
    assert national.parse_location('Nacional.', 'Nacional') == ('', '', '')


def test_national_seed_marks_company_and_territory():
    cases = national.load()['cases']
    assert len(cases) >= 70
    llata = next(c for c in cases if c['code'] == '1333-0923')
    assert 'antamina' in llata['companies'] and 'antamina' in llata['territory']
    assert all(c['coordinate_precision'] for c in cases)
