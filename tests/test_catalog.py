from datetime import datetime, timedelta
from urllib.parse import quote
import pytest
from app import create_app, db
from app.models import Book


@pytest.fixture
def catalog_client():
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI':'sqlite:///:memory:',
                      'SECRET_KEY':'catalog-tests', 'WTF_CSRF_ENABLED':False})
    with app.app_context():
        for index in range(26):
            db.session.add(Book(title=f'Sách {index:02}',author='Nguyễn Đức' if index==0 else 'Tác giả',
                isbn=f'CAT-{index:02}',genre='Lập trình' if index<13 else 'Văn học',
                available=0 if index%2 else 2,quantity=2,created_at=datetime(2026,1,1)+timedelta(days=index)))
        db.session.commit()
        yield app.test_client()
        db.session.remove();db.drop_all()


def test_home_and_discovery_have_distinct_layouts(catalog_client):
    home=catalog_client.get('/').text;page=catalog_client.get('/catalog').text
    assert 'library-hero' in home and 'discoveryFilters' not in home
    assert 'discoveryFilters' in page and 'library-hero' not in page
    assert page.count('data-catalog-book')==12
    assert 'Trang sau' in page and '26 đầu sách' in page
    assert 'aria-current="page">Khám phá sách' in page


def test_catalog_search_folds_accents_and_treats_wildcards_literally(catalog_client):
    page=catalog_client.get('/catalog?q=nguyen+duc&partial=1').text
    assert 'Sách 00' in page and 'Sách 01' not in page
    assert page.count('data-catalog-book')==1
    for query in ('%', '_', '<script>alert(1)</script>'):
        page=catalog_client.get('/catalog?q='+quote(query)+'&partial=1').text
        assert 'data-catalog-book' not in page
        assert '<script>' not in page


def test_filters_sort_and_pagination_work_without_javascript(catalog_client):
    first=catalog_client.get('/catalog?genre='+quote('Lập trình')+'&availability=available&sort=title').text
    assert first.count('data-catalog-book')==7
    assert first.index('Sách 00')<first.index('Sách 02')
    assert 'Sách 13' not in first
    second=catalog_client.get('/catalog?page=2&sort=title').text
    assert 'Sách 12' in second and 'Sách 00' not in second
    assert 'page=3' in second and 'sort=title' in second
    last=catalog_client.get('/catalog?page=999&sort=title').text
    assert last.count('data-catalog-book')==2 and 'Sách 25' in last
    assert catalog_client.get('/catalog?page=bad&sort=bad').status_code==200


def test_partial_response_has_no_shell_and_retains_correct_borrow_permissions(catalog_client):
    response=catalog_client.get('/catalog?partial=1')
    assert response.status_code==200 and response.headers['Cache-Control']=='no-store'
    assert '<html' not in response.text and 'discovery-results-heading' in response.text
    assert 'Đăng nhập để mượn' in response.text and 'action="/borrow/request/' not in response.text
    assert '<script' not in response.text


def test_reader_borrow_forms_remain_independent_and_keep_loan_state(catalog_client):
    from app.models import User, Member, Issue, BorrowRequest
    from app.auth import account_guard
    from html.parser import HTMLParser
    member=Member(name='Reader',email='catalog-reader@example.com',member_id='CAT-READER')
    user=User(email=member.email,password_hash='test-only',role='reader',member=member)
    db.session.add(user);db.session.flush()
    db.session.add(Issue(member_id=member.id,book_id=25,status='issued',due_date=datetime(2026,12,1)))
    db.session.add(BorrowRequest(member_id=member.id,book_id=24,status='pending'))
    db.session.commit()
    with catalog_client.session_transaction() as session:
        session['user_id']=user.id;session['account_guard']=account_guard(user)
    page=catalog_client.get('/catalog').text
    assert 'Bạn đang mượn sách này' in page and 'Đã gửi · Xem yêu cầu' in page
    assert 'action="/borrow/request/' in page
    class Forms(HTMLParser):
        depth=0
        def handle_starttag(self,tag,attrs):
            if tag=='form':
                assert self.depth==0, 'Nested forms break borrowing and search'
                self.depth+=1
        def handle_endtag(self,tag):
            if tag=='form':self.depth-=1
    parser=Forms();parser.feed(page);assert parser.depth==0
