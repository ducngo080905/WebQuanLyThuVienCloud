import pytest

import botkeep


@pytest.fixture
def hosting(monkeypatch, tmp_path):
    monkeypatch.setattr(botkeep, 'ROOT', tmp_path)
    for key in ('SERVER_PORT', 'BIND', 'SECRET_KEY', 'DATABASE_URL', 'POSTGRES_URL',
                'WEB_CONCURRENCY', 'WEB_THREADS', 'COOKIE_SECURE'):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv('SECRET_KEY', 'test-only-secret')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://test:dummy@db.example.test/library?sslmode=require')
    return monkeypatch, tmp_path


def test_managed_env_loads_assigned_port_without_overriding_runtime(hosting):
    monkeypatch, directory = hosting
    (directory / '.env').write_text('SERVER_PORT=23456\nSECRET_KEY=file-only\n', encoding='utf-8')
    botkeep.configure()
    assert botkeep.os.environ['BIND'] == '0.0.0.0:23456'
    assert botkeep.os.environ['SECRET_KEY'] == 'test-only-secret'
    assert botkeep.os.environ['WEB_CONCURRENCY'] == '1'
    assert botkeep.os.environ['WEB_THREADS'] == '2'
    assert botkeep.os.environ['COOKIE_SECURE'] == '1'


@pytest.mark.parametrize('value', ['', '0', '65536', '5000; echo invalid', 'not-a-port'])
def test_bad_or_missing_port_stops_before_launch(hosting, value):
    monkeypatch, _ = hosting
    monkeypatch.setenv('SERVER_PORT', value)
    with pytest.raises(RuntimeError, match='SERVER_PORT'):
        botkeep.configure()


@pytest.mark.parametrize('missing', ['SECRET_KEY', 'DATABASE_URL'])
def test_missing_persistent_configuration_stops_before_launch(hosting, missing):
    monkeypatch, _ = hosting
    monkeypatch.setenv('SERVER_PORT', '23456')
    monkeypatch.delenv(missing)
    with pytest.raises(RuntimeError, match=missing):
        botkeep.configure()
