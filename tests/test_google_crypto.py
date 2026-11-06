import time
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from google.auth import crypt, jwt
from app.google_login import verify_credential

@pytest.fixture
def signed_token(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption())
    public = key.public_key().public_bytes(serialization.Encoding.PEM,
                                           serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    monkeypatch.setattr('google.oauth2.id_token._fetch_certs', lambda *args: {'test-key': public})
    signer = crypt.RSASigner.from_string(private, key_id='test-key')
    def make(**changes):
        now = int(time.time())
        payload = dict(iss='https://accounts.google.com', aud='test-client', sub='test-sub',
                       iat=now, exp=now+3600)
        payload.update(changes)
        return jwt.encode(signer, payload).decode()
    return make


def test_real_signature_and_small_clock_skew(signed_token):
    token = signed_token(iat=int(time.time())+20)
    assert verify_credential(token, 'test-client')['sub'] == 'test-sub'

@pytest.mark.parametrize('changes', [dict(aud='wrong-client'),dict(iat=1,exp=2),
                                     dict(iat=int(time.time())+300),dict(iss='https://attacker.invalid')])
def test_real_verification_rejects_invalid_claims(signed_token,changes):
    from google.auth.exceptions import GoogleAuthError
    with pytest.raises((ValueError, GoogleAuthError)):
        verify_credential(signed_token(**changes), 'test-client')


def test_real_verification_rejects_tampered_signature(signed_token):
    token=signed_token()
    parts=token.split('.')
    parts[2]=('A' if parts[2][0]!='A' else 'B')+parts[2][1:]
    with pytest.raises(ValueError):
        verify_credential('.'.join(parts),'test-client')
