from datetime import datetime, timedelta
from io import BytesIO
from urllib.parse import urlsplit, parse_qs
import pytest
from PIL import Image
from app import create_app, db
from app.auth import account_guard
from app.circulation import today, qr_link, signer
from app.models import (User, Member, Book, BookInfo, Issue, BookReservation,
                        LibrarySetting, ReturnReceipt, CirculationConfig, LibraryQRPass)


@pytest.fixture
def flow():
    app = create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':'sqlite:///:memory:',
                      'SECRET_KEY':'qr-tests','WTF_CSRF_ENABLED':False})
    with app.app_context():
        clients, users = {}, {}
        for role in ('reader','other','admin','librarian'):
            member = Member(name=role, email=role+'@example.com', phone='0901234567', member_id=role)
            user = User(member=member,email=member.email,role='reader' if role=='other' else role,password_hash='test')
            db.session.add(user); db.session.flush()
            client = app.test_client()
            with client.session_transaction() as session:
                session['user_id']=user.id; session['account_guard']=account_guard(user)
            clients[role], users[role] = client, user
        book = Book(title='Sách thử QR', author='Tác giả', isbn='QR-BOOK', quantity=1, available=1,
                    genre='Văn học', info=BookInfo(shelf='A-01'))
        db.session.add(book); db.session.commit()
        yield app, clients, users, book
        db.session.remove(); db.drop_all()


def borrow(clients, book, role='reader'):
    response = clients[role].post(f'/borrow/quick/{book.id}')
    assert response.status_code == 303
    db.session.expire_all()
    return Issue.query.order_by(Issue.id.desc()).first()


def test_quick_borrow_stock_duplicate_and_qr_privacy(flow):
    app, clients, users, book = flow
    assert users['reader'].member.library_code.startswith('DG-')
    issue = borrow(clients,book)
    assert issue.member_id==users['reader'].member_id and book.available==0
    assert (issue.due_date.date()-issue.issue_date.date()).days==14
    borrow(clients,book)
    borrow(clients,book,'other')
    assert Issue.query.count()==1 and book.available==0
    page = clients['reader'].get('/my-books')
    assert 'QR tự trả sách' in page.text
    for path in ('/library-card.png', f'/loans/{issue.id}/return-qr.png'):
        response = clients['reader'].get(path)
        assert response.status_code==200 and response.mimetype=='image/png'
        assert response.headers['Cache-Control']=='private, no-store'
        with Image.open(BytesIO(response.data)) as picture:
            assert picture.width>100 and picture.width==picture.height
    assert clients['other'].get(f'/loans/{issue.id}/return').status_code==404
    assert clients['other'].get(f'/loans/{issue.id}/return-qr.png').status_code==404
    assert app.test_client().get('/library-card.png').status_code==302
    assert clients['admin'].post(f'/borrow/quick/{book.id}').status_code==403


def test_scanned_return_requires_staff_confirmation_and_replay_safe(flow):
    app, clients, users, book = flow
    issue=borrow(clients,book)
    with app.test_request_context():
        token=qr_link('return',issue.id)
    assert clients['reader'].get('/circulation/scan',query_string={'code':token}).status_code==403
    response=clients['librarian'].get('/circulation/scan',query_string={'code':token})
    assert response.status_code==302 and response.location.endswith(f'/loans/{issue.id}/return')
    assert issue.status=='issued' and book.available==0
    path=f'/loans/{issue.id}/confirm-return'
    assert clients['reader'].post(path,data={'received':'1','paid':'1'}).status_code==403
    clients['librarian'].post(path)
    db.session.expire_all(); assert issue.status=='issued'
    clients['librarian'].post(path,data={'received':'1'})
    db.session.expire_all(); assert issue.status=='returned' and book.available==1
    assert issue.return_receipt.method=='qr' and issue.return_receipt.confirmed_by==users['librarian'].id
    clients['admin'].post(path,data={'received':'1'})
    clients['admin'].post(f'/issues/return/{issue.id}',data={'return_date':today().isoformat()})
    db.session.expire_all(); assert book.available==1 and ReturnReceipt.query.count()==1
    assert clients['reader'].get(f'/loans/{issue.id}/return-qr.png').status_code==410
    assert 'Đã nhận lại sách' in clients['reader'].get(f'/loans/{issue.id}/return').text


def test_manual_return_then_qr_does_not_increment_twice(flow):
    _, clients, _, book=flow
    issue=borrow(clients,book)
    clients['admin'].post(f'/issues/return/{issue.id}',data={'return_date':today().isoformat()})
    clients['librarian'].post(f'/loans/{issue.id}/confirm-return',data={'received':'1'})
    db.session.expire_all()
    assert book.available==1 and issue.return_receipt.method=='manual'


def test_overdue_fee_bank_settings_and_staff_payment_verification(flow):
    app, clients, _, book=flow
    issue=borrow(clients,book)
    issue.issue_date=datetime.combine(today()-timedelta(days=20),datetime.min.time())
    issue.due_date=datetime.combine(today()-timedelta(days=3),datetime.min.time())
    db.session.commit()
    path=f'/loans/{issue.id}/return'
    page=clients['reader'].get(path).text
    assert '15,000' in page and 'Chưa cấu hình tài khoản nhận phí' in page
    settings='/admin/circulation-settings'
    assert clients['librarian'].post(settings).status_code==303
    assert clients['reader'].get(settings).status_code==403
    values=dict(bank_bin='970436',bank_account='0123456789',bank_owner='THU VIEN',loan_days='21',fine_per_day='5000')
    assert clients['admin'].post(settings,data=values).status_code==303
    page=clients['reader'].get(path).text
    assert 'img.vietqr.io/image/970436-0123456789-compact2.svg?' in page
    assert 'amount=15000' in page and 'TV PHIEU' in page
    # Presentation of the payment image never marks the fee as paid.
    clients['librarian'].post(f'/loans/{issue.id}/confirm-return',data={'received':'1'})
    db.session.expire_all(); assert issue.return_receipt.amount==15000 and not issue.return_receipt.paid
    pay=f'/loans/{issue.id}/confirm-payment'
    assert clients['reader'].post(pay,data={'verified':'1'}).status_code==403
    clients['librarian'].post(pay)
    db.session.expire_all(); assert not issue.return_receipt.paid
    clients['librarian'].post(pay,data={'verified':'1'})
    db.session.expire_all(); assert issue.return_receipt.paid and book.available==1
    # A future fee-rate edit does not change the settled return receipt.
    values['fine_per_day']='10000'
    clients['admin'].post(settings,data=values)
    assert '15,000' in clients['reader'].get(path).text


def test_queue_fifo_cancel_and_next_reader(flow):
    _, clients, _, book=flow
    issue=borrow(clients,book)
    reserve=f'/books/{book.id}/reserve'
    clients['other'].post(reserve)
    clients['other'].post(reserve)
    assert BookReservation.query.count()==1
    reservation=BookReservation.query.one()
    assert clients['reader'].post(f'/reservations/{reservation.id}/cancel').status_code==404
    clients['admin'].post(f'/loans/{issue.id}/confirm-return',data={'received':'1'})
    borrow(clients,book)  # old borrower cannot jump the waiting reader
    assert Issue.query.count()==1
    borrow(clients,book,'other')
    db.session.expire_all()
    assert Issue.query.count()==2 and book.available==0 and reservation.status=='borrowed'
    clients['reader'].post(reserve)
    reservation=BookReservation.query.filter_by(status='waiting').one()
    clients['reader'].post(f'/reservations/{reservation.id}/cancel')
    db.session.expire_all(); assert reservation.status=='cancelled'


def test_card_scan_invalid_qr_csrf_and_settings_validation(flow):
    app, clients, users, book=flow
    with app.test_request_context():
        card=qr_link('card',users['reader'].member_id)
        forged='LIBQR:'+signer().dumps({'kind':'card','id':users['reader'].member_id,'guard':'wrong'})
    assert users['reader'].member.library_code in clients['admin'].get('/circulation/scan',query_string={'code':card}).text
    for code in ('https://evil.example/path','LIBQR:garbage',forged,'x'*2001):
        response=clients['admin'].get('/circulation/scan',query_string={'code':code})
        assert response.status_code==200 and 'QR không hợp lệ' in response.text
    assert clients['admin'].post('/admin/circulation-settings',data={'bank_bin':'evil','loan_days':'0'}).status_code==200
    assert db.session.get(CirculationConfig,'bank_bin') is None
    app.config['WTF_CSRF_ENABLED']=True
    clients['reader'].post(f'/borrow/quick/{book.id}')
    assert Issue.query.count()==0
    clients['reader'].get('/catalog')
    with clients['reader'].session_transaction() as session: token=session['csrf_token']
    clients['reader'].post(f'/borrow/quick/{book.id}',data={'csrf_token':token})
    assert Issue.query.count()==1


def test_shelves_removed_but_book_suggestions_retained(flow):
    _,clients,_,book=flow
    other=Book(title='Cùng thể loại',author='Người viết',isbn='SIMILAR-2',genre='Văn học',quantity=2,available=2)
    db.session.add(other);db.session.commit()
    for role in clients:
        assert clients[role].get('/shelves').status_code==404
        assert clients[role].post('/admin/shelves/suggest').status_code==404
    detail=clients['reader'].get(f'/book/{book.id}').text
    assert 'Cùng thể loại' in detail and 'Vị trí kệ' not in detail
    assert 'Sơ đồ kệ' not in clients['reader'].get('/').text


def test_staff_portal_login_access_and_embedded_configuration(flow):
    app,clients,users,_=flow
    guest=app.test_client()
    assert guest.get('/circulation/scan').location.endswith('/circulation/login')
    assert guest.get('/admin/circulation-settings').location.endswith('/circulation/login')
    for role in ('reader','other'):
        assert clients[role].get('/circulation/scan').status_code==403
        assert clients[role].get('/circulation/login').status_code==403
        assert clients[role].post('/circulation/scan',data={'loan_days':'1'}).status_code==403
    for role in ('admin','librarian'):
        users[role].set_password('staff-password')
    users['reader'].set_password('reader-password');db.session.commit()
    assert guest.post('/circulation/login',data={'email':users['reader'].email,'password':'reader-password'}).status_code==200
    with guest.session_transaction() as session:
        assert not session.get('user_id')
    for role in ('admin','librarian'):
        client=app.test_client()
        response=client.post('/circulation/login',data={'email':users[role].email,'password':'staff-password'})
        assert response.status_code==303 and response.location.endswith('/circulation/scan')
        page=client.get('/circulation/scan').text
        assert 'qr-portal-body' in page and 'staffSidebar' not in page
        assert 'id="settings"' in page and 'bank_account' in page and 'zone_A' not in page
        response=client.post('/circulation/scan',data={'loan_days':'18','fine_per_day':'3000'})
        assert response.status_code==303 and response.location.endswith('/circulation/scan#settings')
        assert db.session.get(CirculationConfig,'loan_days').value=='18'
        assert client.get('/admin/circulation-settings').location.endswith('/circulation/scan#settings')
        if role=='admin':
            assert 'Mở trạm QR' in client.get('/admin').text
        client.post('/logout',data={'qr_portal':'1'})
        with client.session_transaction() as session:
            assert not session.get('user_id')


def test_portal_login_csrf_and_disabled_staff(flow):
    app,clients,users,_=flow
    user=users['librarian'];user.set_password('staff-password');user.active=False;db.session.commit()
    guest=app.test_client()
    guest.post('/circulation/login',data={'email':user.email,'password':'staff-password'})
    with guest.session_transaction() as session:
        assert not session.get('user_id')
    user.active=True;db.session.commit()
    app.config['WTF_CSRF_ENABLED']=True
    assert guest.post('/circulation/login',data={'email':user.email,'password':'staff-password'}).status_code==303
    guest.get('/circulation/login')
    with guest.session_transaction() as session: token=session['csrf_token']
    assert guest.post('/circulation/login',data={'email':user.email,'password':'staff-password','csrf_token':token}).location.endswith('/circulation/scan')
    guest.post('/circulation/scan',data={'loan_days':'99','fine_per_day':'10'})
    assert db.session.get(CirculationConfig,'loan_days') is None


def test_scan_dialog_and_confirm_return_stay_on_station(flow):
    app,clients,users,book=flow
    issue=borrow(clients,book)
    with app.test_request_context():
        code=qr_link('return',issue.id)
        card=qr_link('card',users['reader'].member_id)
    headers={'X-QR-Dialog':'1'}
    for token in (code,card):
        response=clients['librarian'].get('/circulation/scan',query_string={'code':token},headers=headers)
        assert response.status_code==200 and response.is_json
        assert 'html' in response.json and 'title' in response.json
        assert '<html' not in response.json['html']
    page=clients['librarian'].get(f'/loans/{issue.id}/return')
    assert page.location.endswith(f'/circulation/scan?loan={issue.id}')
    assert clients['reader'].get(f'/loans/{issue.id}/return',headers=headers).status_code==403
    response=clients['librarian'].post(f'/loans/{issue.id}/confirm-return',data={'received':'1'},headers=headers)
    assert response.status_code==200 and response.json['ok']
    assert 'Sẵn sàng quét' in response.json['message']
    assert 'Location' not in response.headers
    db.session.expire_all();assert book.available==1
    clients['librarian'].post(f'/loans/{issue.id}/confirm-return',data={'received':'1'},headers=headers)
    db.session.expire_all();assert book.available==1
    invalid=clients['librarian'].get('/circulation/scan',query_string={'code':'LIBQR:invalid'},headers=headers)
    assert invalid.status_code==400 and invalid.json['error']


def test_reader_qr_updates_after_staff_returns_without_page_reload(flow):
    _,clients,_,book=flow
    issue=borrow(clients,book)
    endpoint=f'/loans/{issue.id}/live-status'
    initial=clients['reader'].get(endpoint,query_string={'state':'issued:none'})
    assert initial.status_code==200 and not initial.json['changed']
    assert 'html' not in initial.json
    assert 'no-store' in initial.headers['Cache-Control']
    assert clients['other'].get(endpoint).status_code==404
    page=clients['reader'].get(f'/loans/{issue.id}/return').text
    assert 'reader_loan_live.js' in page and 'QR trả sách phiếu' in page
    clients['librarian'].post(f'/loans/{issue.id}/confirm-return',data={'received':'1'})
    updated=clients['reader'].get(endpoint,query_string={'state':'issued:none'}).json
    assert updated['changed'] and updated['status']=='returned' and updated['complete']
    assert 'QR trả sách phiếu' not in updated['html']
    assert 'đã nhận sách' in updated['html']
    assert not clients['reader'].get(endpoint,query_string={'state':updated['state']}).json['changed']


@pytest.mark.parametrize('same_reader',[False,True])
def test_simultaneous_quick_loans_do_not_oversell_or_duplicate(tmp_path,same_reader):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    app=create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':'sqlite:///'+str(tmp_path/'concurrent.db'),
                    'SECRET_KEY':'concurrency','WTF_CSRF_ENABLED':False})
    with app.app_context():
        accounts=[]
        for i in range(2):
            member=Member(name=f'Reader {i}',email=f'{i}@example.com',phone='0901234567',member_id=f'T{i}')
            user=User(member=member,email=member.email,role='reader',password_hash='test')
            db.session.add(user);db.session.flush();accounts.append((user.id,account_guard(user)))
        copies=2 if same_reader else 1
        book=Book(title='Last copy',author='Author',isbn='LAST',quantity=copies,available=copies)
        db.session.add(book);db.session.commit();book_id=book.id
    barrier=Barrier(2)
    def submit(account):
        client=app.test_client()
        with client.session_transaction() as session:
            session['user_id'],session['account_guard']=account
        barrier.wait(timeout=10)
        return client.post(f'/borrow/quick/{book_id}').status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses=list(executor.map(submit,[accounts[0],accounts[0] if same_reader else accounts[1]]))
    assert responses==[303,303]
    with app.app_context():
        assert Issue.query.count()==1
        assert db.session.get(Book,book_id).available==copies-1
        db.session.remove();db.drop_all()
