import pytest
from app import db
from app.auth import create_account
from app.models import User, Member, GoogleIdentity
from tests.test_auth import auth_app
from tests.test_google_crypto import signed_token


def registration(client, app, token_factory, email='reader@gmail.com', subject='registration-sub', **claims):
    app.config['GOOGLE_CLIENT_ID']='test-client'
    client.get('/register')
    with client.session_transaction() as session:
        nonce=session['google_nonce']; csrf=session['csrf_token']
    payload=dict(email=email,email_verified=True,nonce=nonce,sub=subject,name='Google Reader')
    payload.update(claims)
    token=token_factory(**payload)
    data={'google_credential':token,'csrf_token':csrf,'name':'Reader','email':email,'password':'secret123','confirm_password':'secret123','role':'admin'}
    return data


def test_registration_requires_google_and_creates_link_atomically(auth_app,signed_token):
    client=auth_app.test_client()
    page=client.get('/register').text
    assert 'registrationGoogleCredential' in page and 'registrationSubmit' in page and 'Bước 1' in page
    response=client.post('/register',data={'name':'Reader','email':'reader@gmail.com','password':'secret123','confirm_password':'secret123','google_subject':'invented-sub'})
    assert response.status_code==400 and User.query.count()==0
    data=registration(client,auth_app,signed_token)
    auth_app.config['WTF_CSRF_ENABLED']=True
    assert client.post('/register',data=data).status_code==302
    account=User.query.one()
    assert account.role=='reader' and account.check_password('secret123')
    assert account.google_identity.subject=='registration-sub'
    live=client.get('/live-updates')
    assert live.json['google_link_required'] is False and live.json['phone_required'] is True
    assert live.headers['Cache-Control']=='no-store'
    client.post('/logout',data={'csrf_token':client.get('/profile').text.split('name="csrf_token" value="')[1].split('"')[0]})
    # The same credential cannot be reused with a new session/nonce.
    client.get('/register')
    with client.session_transaction() as session: data['csrf_token']=session['csrf_token']
    assert client.post('/register',data=data).status_code==400
    assert User.query.count()==1


@pytest.mark.parametrize('bad_claims',[{'nonce':'different-session'},{'email_verified':False},{'sub':''},{'exp':1}, {'hd':'','email':'reader@example.com'}])
def test_registration_rejects_unverified_or_stale_google(auth_app,signed_token,bad_claims):
    client=auth_app.test_client()
    data=registration(client,auth_app,signed_token,**bad_claims)
    assert client.post('/register',data=data).status_code==400
    assert User.query.count()==0 and GoogleIdentity.query.count()==0


def test_registration_rejects_email_swap_and_tampering(auth_app,signed_token):
    client=auth_app.test_client();data=registration(client,auth_app,signed_token)
    data['email']='other@gmail.com'
    assert client.post('/register',data=data).status_code==200
    assert User.query.count()==0
    data=registration(client,auth_app,signed_token)
    parts=data['google_credential'].split('.')
    parts[2]=('A' if parts[2][0]!='A' else 'B')+parts[2][1:]
    data['google_credential']='.'.join(parts)
    assert client.post('/register',data=data).status_code==400
    assert User.query.count()==0


def test_identity_conflict_rolls_back_entire_registration(auth_app,signed_token):
    create_account('Existing','old@gmail.com','secret123',google_subject='already-linked')
    client=auth_app.test_client();data=registration(client,auth_app,signed_token,email='new@gmail.com',subject='already-linked')
    assert client.post('/register',data=data).status_code==200
    assert User.query.count()==1 and Member.query.count()==1 and GoogleIdentity.query.count()==1
    assert User.query.filter_by(email='new@gmail.com').first() is None


def test_legacy_accounts_are_not_auto_linked_and_notice_updates_live(auth_app,signed_token):
    account=create_account('Legacy','legacy@gmail.com','secret123','0901234567')
    client=auth_app.test_client();data=registration(client,auth_app,signed_token,email=account.email)
    client.post('/register',data=data)
    assert GoogleIdentity.query.count()==0 and User.query.count()==1
    client.post('/login',data={'email':account.email,'password':'secret123'})
    assert client.get('/live-updates').json['google_link_required']
    page=client.get('/profile').text
    assert 'hidden' not in page.split('id="googleLinkNotice"',1)[1].split('>',1)[0]
    identity=GoogleIdentity(subject='legacy-linked',user_id=account.id);db.session.add(identity);db.session.commit()
    assert not client.get('/live-updates').json['google_link_required']
    assert 'hidden' in client.get('/profile').text.split('id="googleLinkNotice"',1)[1].split('>',1)[0]
    db.session.delete(identity);db.session.commit()
    assert client.get('/live-updates').json['google_link_required']
    account.role='admin';db.session.commit()
    assert client.get('/live-updates').json['google_link_required']
    assert 'google-account-warning' in client.get(f'/accounts/{account.id}/edit').text


def test_google_configuration_and_csrf_cannot_be_bypassed(auth_app,signed_token):
    client=auth_app.test_client();data=registration(client,auth_app,signed_token)
    auth_app.config['WTF_CSRF_ENABLED']=True
    assert client.post('/register',data={**data,'csrf_token':'wrong'}).status_code==303
    assert User.query.count()==0
    auth_app.config['WTF_CSRF_ENABLED']=False;auth_app.config['GOOGLE_CLIENT_ID']=''
    assert client.post('/register',data=data).status_code==400
    assert User.query.count()==0



def test_registration_uses_verified_email_without_step_two_email_field(auth_app,signed_token):
    client=auth_app.test_client()
    page=client.get('/register').text
    assert 'name="email"' not in page and 'Email được lấy từ Google ở bước 1' not in page
    data=registration(client,auth_app,signed_token,email='verified@gmail.com')
    del data['email']
    assert client.post('/register',data=data).status_code==302
    user=User.query.one()
    assert user.email=='verified@gmail.com' and user.google_identity.subject=='registration-sub'
    client.post('/logout')
    assert 'name="email"' in client.get('/login').text
