def test_past_trainings_rejects_unreasonable_week_range(client):
    response = client.get(
        '/api/trainings/past?weeks=53',
        headers={'X-TT-Internal-Secret': 'test-api-secret'},
    )
    assert response.status_code == 400
    assert response.get_json()['error'] == 'weeks must be between 1 and 52'


def test_api_requires_internal_secret(client):
    response = client.get('/api/trainings')
    assert response.status_code == 401
