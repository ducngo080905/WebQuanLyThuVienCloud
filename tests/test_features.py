from io import BytesIO
from datetime import datetime,timedelta
import hashlib
import re
import pytest
from PIL import Image
from app import create_app,db
from app.models import (User,Member,Book,Issue,SamplePage,RenewalRequest,LibrarySetting,PasswordReset,MailRecord)

@pytest.fixture
def feature_app():
    app=create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':'sqlite:///:memory:',
                    'SECRET_KEY':'test','WTF_CSRF_ENABLED':False})
    with app.app_context():
        yield app
        db.session.remove();db.drop_all()


def account(app,email,role='reader'):
    member=Member(name=role,email=email,member_id=email)
    user=User(member=member,email=email,role=role);user.set_password('password123')
    db.session.add(user);db.session.commit()
    client=app.test_client();client.post('/login',data={'email':email,'password':'password123'})
    return client,user


def png():
    stream=BytesIO();Image.new('RGB',(100,150),'white').save(stream,format='PNG');stream.seek(0);return stream


def test_book_information_samples_edit_and_public_visibility(feature_app):
    from pypdf import PdfWriter
    admin,user=account(feature_app,'admin@example.com','admin')
    book=Book(title='Title',author='Author',isbn='DETAIL',quantity=3,available=2)
    db.session.add(book);db.session.commit()
    document=PdfWriter();document.add_blank_page(width=600,height=800)
    output=BytesIO();document.write(output);pdf=output.getvalue()
    result=admin.post(f'/admin/books/{book.id}/edit',data={'title':'New title','author':'Writer','isbn':'DETAIL',
         'quantity':'5','description':'Description with <script>','publisher':'Publisher','year':'2020','pages':'123',
         'language':'Vietnamese','shelf':'A1','samples':[(BytesIO(pdf),'sample.pdf'),(png(),'page.png')]},follow_redirects=True)
    assert result.status_code==200
    assert book.title=='New title' and book.quantity==5 and book.available==4
    assert SamplePage.query.count()==2
    guest=feature_app.test_client();page=guest.get(f'/book/{book.id}')
    assert b'Description with &lt;script&gt;' in page.data and b'Publisher' in page.data
    assert guest.get(f'/book-samples/{SamplePage.query.first().id}').mimetype=='application/pdf'
    reader,_=account(feature_app,'reader@example.com')
    assert reader.post(f'/admin/books/{book.id}/edit',data={}).status_code==403
    admin.post(f'/admin/books/{book.id}/edit',data={'title':'Title','author':'Author','isbn':'DETAIL','quantity':'0'})
    assert book.quantity==5


def test_invalid_preview_does_not_change_book(feature_app):
    admin,_=account(feature_app,'admin@example.com','admin')
    book=Book(title='Original',author='Author',isbn='INVALID',quantity=1,available=1)
    db.session.add(book);db.session.commit()
    admin.post(f'/admin/books/{book.id}/edit',data={'title':'Changed','author':'A','isbn':'INVALID','quantity':'1','samples':(BytesIO(b'fake pdf'),'fake.pdf')})
    assert book.title=='Original' and SamplePage.query.count()==0


def test_renewal_ownership_and_double_approval(feature_app):
    reader,user=account(feature_app,'reader@example.com')
    admin,_=account(feature_app,'admin@example.com','admin')
    other,_=account(feature_app,'other@example.com')
    book=Book(title='Book',author='Author',isbn='RENEW',quantity=1,available=0)
    issue=Issue(book=book,member_id=user.member_id,due_date=datetime.now()+timedelta(days=3))
    db.session.add(issue);db.session.commit();original=issue.due_date
    assert other.post(f'/my-books/{issue.id}/renew').status_code==403
    for _ in range(2):reader.post(f'/my-books/{issue.id}/renew')
    assert RenewalRequest.query.count()==1
    item=RenewalRequest.query.one()
    for _ in range(2):admin.post(f'/admin/renewals/{item.id}/review',data={'action':'approve'})
    db.session.expire_all();assert issue.due_date==original+timedelta(days=7) and book.available==0
    assert reader.get('/admin/renewals').status_code==403
    assert admin.get('/admin/renewals').status_code==200


def test_reports_fees_excel_and_print(feature_app):
    from openpyxl import load_workbook
    admin,_=account(feature_app,'admin@example.com','admin')
    reader,user=account(feature_app,'reader@example.com')
    book=Book(title='=evil()',author='A',isbn='REPORT',quantity=1,available=0)
    issue=Issue(book=book,member_id=user.member_id,issue_date=datetime.now(),due_date=datetime.now()-timedelta(days=2))
    db.session.add(issue);db.session.commit()
    assert reader.get('/admin/reports').status_code==403
    admin.post('/admin/reports',data={'fine_per_day':'1000'})
    from app.features import fine_amount
    assert fine_amount(issue)==2000
    response=admin.get('/admin/reports?format=xlsx')
    sheet=load_workbook(BytesIO(response.data)).active
    assert sheet['B2'].data_type=='s' and sheet['B2'].value.startswith("'")
    assert sheet['H2'].value==2000
    assert b'window.print' in admin.get('/admin/reports?format=print').data


def recovery_form(email):
    return dict(email=email,name='Reader',phone='0900000000',member_code='MEM1',
                contact='Gặp trực tiếp ở thư viện',evidence='Thông tin các sách đã mượn để admin đối chiếu')


def test_admin_recovery_manual_verification_and_forced_password_change(feature_app):
    from app.models import AccountRecovery,PasswordChangeRequired
    reader,user=account(feature_app,'reader@example.com')
    admin,_=account(feature_app,'admin@example.com','admin')
    guest=feature_app.test_client()
    assert guest.post('/forgot-password',data=recovery_form(user.email)).status_code==302
    item=AccountRecovery.query.one()
    assert item.status=='pending' and user.check_password('password123')
    assert reader.get('/admin/account-recovery').status_code==403
    assert admin.get('/admin/account-recovery').status_code==200
    admin.post(f'/admin/account-recovery/{item.id}/review',data={'action':'approve'})
    assert user.check_password('password123')
    response=admin.post(f'/admin/account-recovery/{item.id}/review',data={'action':'approve','verified':'1'})
    temporary=re.search(r'id="temporary"[^>]*value="([^"]+)"',response.text).group(1)
    assert user.check_password(temporary) and db.session.get(PasswordChangeRequired,user.id)
    assert temporary not in str(db.session.get(AccountRecovery,item.id).__dict__)
    assert reader.get('/my-books').status_code==302
    guest.post('/login',data={'email':user.email,'password':temporary})
    assert guest.get('/my-books').headers['Location'].endswith('/profile')
    guest.post('/profile',data={'name':user.member.name,'phone':'','current_password':temporary,
                       'password':temporary,'confirm_password':temporary})
    assert db.session.get(PasswordChangeRequired,user.id)
    guest.post('/profile',data={'name':user.member.name,'phone':'','current_password':temporary,
                       'password':'mynewpassword123','confirm_password':'mynewpassword123'})
    assert not db.session.get(PasswordChangeRequired,user.id)
    assert guest.get('/my-books').status_code==200
    assert admin.post(f'/admin/account-recovery/{item.id}/review',data={'action':'approve','verified':'1'}).status_code==302
    assert user.check_password('mynewpassword123')


def test_web_due_notifications_no_email_endpoints(feature_app):
    reader,user=account(feature_app,'reader@example.com')
    admin,_=account(feature_app,'admin@example.com','admin')
    book=Book(title='Overdue Book',author='A',isbn='WEB-NOTICE',quantity=2,available=0)
    db.session.add(book);db.session.flush()
    db.session.add_all([Issue(book_id=book.id,member_id=user.member_id,due_date=datetime.now()-timedelta(days=1)),
                        Issue(book_id=book.id,member_id=user.member_id,due_date=datetime.now()+timedelta(days=2))]);db.session.commit()
    page=reader.get('/notifications')
    assert page.status_code==200 and 'Quá hạn'.encode() in page.data and 'Còn 2 ngày'.encode() in page.data
    assert b'Overdue Book' not in admin.get('/notifications').data
    assert b'send-reminders' not in admin.get('/admin/reports').data
    assert admin.post('/admin/send-reminders').status_code==404
    assert 'send-reminders' not in feature_app.cli.commands


def test_recovery_unknown_email_rate_limit_and_changed_account(feature_app):
    from app.models import AccountRecovery
    guest=feature_app.test_client()
    for _ in range(5):guest.post('/forgot-password',data=recovery_form('unknown@example.com'))
    assert AccountRecovery.query.count()==3
    admin,_=account(feature_app,'admin@example.com','admin')
    unknown=AccountRecovery.query.first()
    admin.post(f'/admin/account-recovery/{unknown.id}/review',data={'action':'approve','verified':'1'})
    assert unknown.status=='pending'
    reader,user=account(feature_app,'reader@example.com')
    guest.post('/forgot-password',data=recovery_form(user.email))
    item=AccountRecovery.query.filter_by(user_id=user.id).one()
    user.set_password('alreadychanged123');db.session.commit()
    admin.post(f'/admin/account-recovery/{item.id}/review',data={'action':'approve','verified':'1'})
    assert item.status=='pending' and user.check_password('alreadychanged123')
    assert guest.get('/reset-password/old-email-token').headers['Location'].endswith('/forgot-password')


def test_additive_schema_upgrade_preserves_existing_preview(tmp_path):
    import sqlite3
    path=tmp_path/'legacy.db'
    with sqlite3.connect(path) as connection:
        connection.execute('CREATE TABLE sample_pages (id INTEGER PRIMARY KEY, book_id INTEGER NOT NULL, position INTEGER NOT NULL, data BLOB NOT NULL)')
        connection.execute("INSERT INTO sample_pages VALUES (1,999,1,?)",(b'legacy-image',))
        connection.execute('CREATE TABLE mail_records (id INTEGER PRIMARY KEY, kind VARCHAR(30) NOT NULL, recipient VARCHAR(120) NOT NULL, issue_id INTEGER, sent_at DATETIME NOT NULL)')
        connection.execute('CREATE TABLE password_resets (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, digest VARCHAR(64) NOT NULL, expires_at DATETIME NOT NULL, used BOOLEAN NOT NULL, created_at DATETIME NOT NULL)')
    app=create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':'sqlite:///'+path.as_posix(),'SECRET_KEY':'test'})
    with app.app_context():
        row=db.session.get(SamplePage,1)
        assert row.data==b'legacy-image' and row.mimetype=='image/jpeg' and row.page_count==1
        from app.schema import upgrade_schema
        upgrade_schema(app)
        db.session.remove()
    assert len(list(tmp_path.glob('schema-backup-*.db')))==1

def test_recovery_password_visible_to_admin_encrypted_and_hidden_after_change(feature_app):
    from app.models import AccountRecovery,RecoveryCredential
    admin,_=account(feature_app,'admin@example.com','admin')
    reader,user=account(feature_app,'reader@example.com')
    guest=feature_app.test_client();guest.post('/forgot-password',data=recovery_form(user.email))
    item=AccountRecovery.query.one()
    result=admin.post(f'/admin/account-recovery/{item.id}/review',data={'action':'approve','verified':'1'})
    temporary=re.search(r'id="temporary"[^>]*value="([^"]+)"',result.text).group(1)
    stored=db.session.get(RecoveryCredential,item.id)
    assert temporary.encode() not in stored.ciphertext
    assert temporary in admin.get('/admin/account-recovery').text
    assert reader.get('/admin/account-recovery').status_code==302
    assert guest.get('/admin/account-recovery').status_code==302
    new=feature_app.test_client();new.post('/login',data={'email':user.email,'password':temporary})
    assert new.get('/admin/account-recovery').status_code==302
    new.post('/profile',data={'name':user.member.name,'phone':'','current_password':temporary,
                            'password':'changed-password123','confirm_password':'changed-password123'})
    assert temporary not in admin.get('/admin/account-recovery').text
    assert admin.post(f'/admin/account-recovery/{item.id}/reissue',data={'verified':'1'}).status_code==302
    assert user.check_password('changed-password123')


def test_reissue_legacy_password_and_24_hour_visibility(feature_app):
    from app.models import AccountRecovery,PasswordChangeRequired,RecoveryCredential
    admin,_=account(feature_app,'admin@example.com','admin')
    reader,user=account(feature_app,'reader@example.com')
    item=AccountRecovery(user_id=user.id,email=user.email,name='Reader',phone='123',member_code='',
          contact='Direct verification',evidence='Checked',status='approved',resolved_at=datetime.utcnow())
    db.session.add_all([item,PasswordChangeRequired(user_id=user.id)]);db.session.commit()
    admin.post(f'/admin/account-recovery/{item.id}/reissue',data={})
    assert db.session.get(RecoveryCredential,item.id) is None
    response=admin.post(f'/admin/account-recovery/{item.id}/reissue',data={'verified':'1'},follow_redirects=True)
    assert response.status_code==200
    temporary=re.search(r'id="temporary-\d+"[^>]*value="([^"]+)"',response.text).group(1)
    assert user.check_password(temporary)
    row=db.session.get(RecoveryCredential,item.id);row.expires_at=datetime.utcnow()-timedelta(seconds=1);db.session.commit()
    assert temporary not in admin.get('/admin/account-recovery').text
