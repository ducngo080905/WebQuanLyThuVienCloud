from pathlib import Path

import pytest

import app as app_module


@pytest.mark.parametrize('runtime_flag', ['VERCEL', 'AWS_LAMBDA_FUNCTION_NAME'])
def test_serverless_startup_writes_only_to_temp(monkeypatch, tmp_path, runtime_flag):
    monkeypatch.setenv(runtime_flag, 'test-runtime')
    monkeypatch.setattr(app_module, 'gettempdir', lambda: str(tmp_path))
    original_mkdir = Path.mkdir
    source = Path(app_module.__file__).parent.parent.resolve()

    def reject_source_writes(path, *args, **kwargs):
        assert not path.resolve().is_relative_to(source), 'Serverless startup writes into the source bundle'
        return original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'mkdir', reject_source_writes)
    application = app_module.create_app({'TESTING': True})
    assert Path(application.instance_path) == tmp_path / 'library-instance'
    client = application.test_client()
    assert client.get('/health').status_code == 200
    assert client.get('/').status_code == 200
    assert client.get('/api/mobile/session').status_code == 404
    assert client.get('/download/android').status_code == 404
