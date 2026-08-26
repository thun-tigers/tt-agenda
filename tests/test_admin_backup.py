def test_admin_backup_page_shows_centralized_backup_guidance(client, login_as):
    login_as(username='admin', password='secret', role='admin')

    response = client.get('/admin/backup')

    assert response.status_code == 200


def test_admin_backup_endpoints_redirect_to_central_guidance(client, login_as):
    login_as(username='admin', password='secret', role='admin')

    download_response = client.get('/admin/backup/download', follow_redirects=False)
    restore_response = client.post('/admin/backup/restore', follow_redirects=False)

    assert download_response.status_code == 302
    assert download_response.headers['Location'].endswith('/admin/backup')
    assert restore_response.status_code == 302
    assert restore_response.headers['Location'].endswith('/admin/backup')
