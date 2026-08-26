def test_admin_backup_page_shows_centralized_backup_guidance(client, login_as):
    login_as(username='admin', password='secret', role='admin')

    response = client.get('/admin/backup')

    assert response.status_code == 200


def test_admin_backup_download_returns_sqlite_file(client, login_as):
    login_as(username='admin', password='secret', role='admin')

    response = client.get('/admin/backup/download', follow_redirects=False)

    assert response.status_code == 200
    assert 'attachment' in response.headers['Content-Disposition']


def test_admin_backup_restore_redirects_to_guidance(client, login_as):
    login_as(username='admin', password='secret', role='admin')

    restore_response = client.post('/admin/backup/restore', follow_redirects=False)

    assert restore_response.status_code == 302
    assert restore_response.headers['Location'].endswith('/admin/backup')
