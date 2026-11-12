"""Searchable, paginated book discovery; the home page keeps its own layout."""
import math
import unicodedata
from flask import g, render_template, request
from sqlalchemy import event, func
from sqlalchemy import String
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import GenericFunction
from sqlalchemy.orm import joinedload
from app import db
from app.models import Book, BorrowRequest, Issue


def fold(value):
    text = unicodedata.normalize('NFD', (value or '').casefold().replace('đ', 'd'))
    return ''.join(char for char in text if not unicodedata.combining(char))


class library_fold(GenericFunction):
    type = String()
    inherit_cache = True


@compiles(library_fold, 'postgresql')
def postgres_fold(element, compiler, **kwargs):
    # Match the SQLite function for Vietnamese precomposed and combining accents.
    accented = 'àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ'
    plain = ''.join(fold(char) for char in accented)
    argument = compiler.process(list(element.clauses)[0], **kwargs)
    source = compiler.render_literal_value(accented, String())
    target = compiler.render_literal_value(plain, String())
    combining = compiler.render_literal_value('[\u0300-\u036f]', String())
    return f"regexp_replace(translate(lower({argument}), {source}, {target}), {combining}, '', 'g')"


def install_catalog_search(app):
    with app.app_context():
        if db.engine.dialect.name == 'sqlite':
            @event.listens_for(db.engine, 'connect')
            def connect(connection, record):
                connection.create_function('library_fold', 1, fold, deterministic=True)


def catalog_page():
    keyword = request.args.get('q', '').strip()[:160]
    genre = request.args.get('genre', '').strip()[:50]
    availability = request.args.get('availability', '')
    if availability not in ('available', 'unavailable'):
        availability = ''
    sort = request.args.get('sort', 'newest')
    if sort not in ('newest', 'title', 'author', 'available'):
        sort = 'newest'
    query = Book.query
    if keyword:
        query = query.filter(func.library_fold(Book.title + ' ' + Book.author + ' ' + Book.isbn).contains(fold(keyword), autoescape=True))
    if genre:
        query = query.filter(func.trim(Book.genre) == genre)
    if availability:
        query = query.filter(Book.available > 0 if availability == 'available' else Book.available <= 0)
    count = query.count()
    pages = max(1, math.ceil(count / 12))
    page = max(1, min(request.args.get('page', 1, type=int) or 1, pages))
    orders = {'newest': (Book.created_at.desc(), Book.id.desc()),
              'title': (func.library_fold(Book.title), Book.id),
              'author': (func.library_fold(Book.author), func.library_fold(Book.title), Book.id),
              'available': (Book.available.desc(), Book.id.desc())}
    books = query.options(joinedload(Book.cover)).order_by(*orders[sort]).offset((page - 1) * 12).limit(12).all()
    pending, active = set(), set()
    if g.user and g.user.role == 'reader' and books:
        ids = [book.id for book in books]
        pending = {row[0] for row in db.session.query(BorrowRequest.book_id).filter(BorrowRequest.member_id == g.user.member_id, BorrowRequest.status == 'pending', BorrowRequest.book_id.in_(ids))}
        active = {row[0] for row in db.session.query(Issue.book_id).filter(Issue.member_id == g.user.member_id, Issue.status == 'issued', Issue.book_id.in_(ids))}
    context = dict(books=books, pending_books=pending, active_books=active,
                   keyword=keyword, genre=genre, availability=availability, sort=sort,
                   count=count, page=page, pages=pages, start=(page-1)*12+1 if count else 0,
                   end=min(page*12, count))
    if request.args.get('partial') == '1':
        return render_template('_catalog_results.html', **context)
    context['genres'] = db.session.query(func.trim(Book.genre), func.count(Book.id)).filter(func.trim(Book.genre) != '').group_by(func.trim(Book.genre)).order_by(func.library_fold(func.trim(Book.genre))).all()
    context['total_books'] = Book.query.count()
    context['available_books'] = Book.query.filter(Book.available > 0).count()
    return render_template('catalog.html', **context)
