from pulso import alerts, portfolio


def test_antamina_portfolio_has_case_actors_and_history():
    p = portfolio.portfolio('antamina')
    case = next(c for c in p['cases'] if c['id'] == '1333-0923')
    assert 'Antamina' in case['actors']['primarios']
    assert len(p['linked_history']) >= 15
    assert any(a['rule'] == 'sin_cierre' for a in p['alerts'])


def test_no_closure_rule_skips_conflicts_still_reported_under_their_code():
    cases = [{'id': '1132-1218', 'name': 'CC Fuerabamba - Minera Las Bambas (Apurímac)', 'events': [], 'commitments': []}]
    history = [{'name': 'CC Fuerabamba (Yavi Yavi) - Minera Las Bambas', 'official_code': '1132-1218', 'last_status': 'Activo', 'last_period': '2025-11'},
               {'name': 'Cotabambas - MMG Las Bambas', 'official_code': '0664-0511', 'last_status': 'Activo', 'last_period': '2025-05'}]
    found = [a for a in alerts.compute(cases, [], [], [], history=history) if a['rule'] == 'sin_cierre']
    assert [a['title'] for a in found] == ['Sin cierre reportado: Cotabambas - MMG Las Bambas']
