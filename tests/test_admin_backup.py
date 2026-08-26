import io


def test_admin_backup_page_shows_centralized_backup_guidance(client, login_as):
    login_as(username='admin', password='secret', role='admin')

    response = client.get('/admin/backup')

    assert response.status_code == 200


def test_admin_backup_download_returns_sqlite_file(client, login_as):
    login_as(username='admin', password='secret', role='admin')

    response = client.get('/admin/backup/download', follow_redirects=False)

    assert response.status_code == 200
    assert 'attachment' in response.headers['Content-Disposition']


def test_admin_backup_restore_requires_confirmation_phrase(client, login_as, csrf_token):
    login_as(username='admin', password='secret', role='admin')
    token = csrf_token('/admin/backup')

    restore_response = client.post(
        '/admin/backup/restore',
        data={
            'csrf_token': token,
            'confirm': 'yes-please',
            'backup_file': (io.BytesIO(b'irrelevant'), 'backup.db'),
        },
        content_type='multipart/form-data',
        follow_redirects=False,
    )

    assert restore_response.status_code == 302
    assert restore_response.headers['Location'].endswith('/admin/backup')


def test_admin_backup_restore_rejects_invalid_sqlite_file(client, login_as, csrf_token):
    login_as(username='admin', password='secret', role='admin')
    token = csrf_token('/admin/backup')

    restore_response = client.post(
        '/admin/backup/restore',
        data={
            'csrf_token': token,
            'confirm': 'RESTORE',
            'backup_file': (io.BytesIO(b'not a real sqlite file'), 'backup.db'),
        },
        content_type='multipart/form-data',
        follow_redirects=True,
    )

    assert restore_response.status_code == 200
    assert 'keine g\u00fcltige SQLite-Backup-Datei'.encode() in restore_response.data


def test_admin_backup_restore_replaces_sqlite_file(client, login_as, csrf_token):
    login_as(username='admin', password='secret', role='admin')

    backup_bytes = client.get('/admin/backup/download').data
    assert backup_bytes.startswith(b'SQLite format 3\x00')

    token = csrf_token('/admin/backup')
    restore_response = client.post(
        '/admin/backup/restore',
        data={
            'csrf_token': token,
            'confirm': 'RESTORE',
            'backup_file': (io.BytesIO(backup_bytes), 'backup.db'),
        },
        content_type='multipart/form-data',
        follow_redirects=False,
    )

    assert restore_response.status_code == 302
    assert restore_response.headers['Location'].endswith('/admin/backup')


def test_admin_backup_restore_requires_csrf_token(client, login_as):
    login_as(username='admin', password='secret', role='admin')

    restore_response = client.post(
        '/admin/backup/restore',
        data={
            'confirm': 'RESTORE',
            'backup_file': (io.BytesIO(b'irrelevant'), 'backup.db'),
        },
        content_type='multipart/form-data',
    )

    assert restore_response.status_code == 400
