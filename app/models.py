from app import db
from datetime import datetime

class Book(db.Model):
    __tablename__ = 'books'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    isbn = db.Column(db.String(20), unique=True, nullable=False)
    genre = db.Column(db.String(50))
    quantity = db.Column(db.Integer, default=1)
    available = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    issues = db.relationship('Issue', backref='book', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'author': self.author,
            'isbn': self.isbn,
            'genre': self.genre,
            'quantity': self.quantity,
            'available': self.available
        }


class Member(db.Model):
    __tablename__ = 'members'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    member_id = db.Column(db.String(20), unique=True, nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    issues = db.relationship('Issue', backref='member', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'member_id': self.member_id
        }


class Issue(db.Model):
    __tablename__ = 'issues'
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    issue_date = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime, nullable=False)
    return_date = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='issued')  # issued / returned

    def to_dict(self):
        return {
            'id': self.id,
            'book': self.book.title if self.book else None,
            'member': self.member.name if self.member else None,
            'issue_date': self.issue_date.strftime('%Y-%m-%d'),
            'due_date': self.due_date.strftime('%Y-%m-%d'),
            'return_date': self.return_date.strftime('%Y-%m-%d') if self.return_date else None,
            'status': self.status
        }


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='reader')
    active = db.Column(db.Boolean, nullable=False, default=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), unique=True)
    member = db.relationship('Member', backref=db.backref('account', uselist=False))

    def set_password(self, password):
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        from werkzeug.security import check_password_hash
        return bool(self.password_hash) and check_password_hash(self.password_hash, password)


class BorrowRequest(db.Model):
    __tablename__ = 'borrow_requests'
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)
    issue_id = db.Column(db.Integer, db.ForeignKey('issues.id'))
    book = db.relationship('Book', backref=db.backref('borrow_requests', cascade='all, delete-orphan'))
    member = db.relationship('Member', backref=db.backref('borrow_requests', cascade='all, delete-orphan'))
    issue = db.relationship('Issue', backref=db.backref('borrow_request', uselist=False))
    __table_args__ = (db.Index('uq_pending_borrow_request', 'book_id', 'member_id', unique=True,
                              sqlite_where=db.text("status = 'pending'"),
                              postgresql_where=db.text("status = 'pending'")),)


class MobileConnection(db.Model):
    __tablename__ = 'mobile_connections'
    id = db.Column(db.String(64), primary_key=True)
    proof_hash = db.Column(db.String(64), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    user_id = db.Column(db.Integer)
    account_guard = db.Column(db.String(64))


class GoogleIdentity(db.Model):
    __tablename__ = 'google_identities'
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(255), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    user = db.relationship('User', backref=db.backref('google_identity', uselist=False,
                                                   cascade='all, delete-orphan'))


class ActivityPresence(db.Model):
    __tablename__ = 'activity_presence'
    id = db.Column(db.String(64), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    last_seen = db.Column(db.DateTime, nullable=False, index=True)
    last_page = db.Column(db.String(100), nullable=False, default='Thư viện')
    last_view_at = db.Column(db.DateTime)
    ended_at = db.Column(db.DateTime)
    user = db.relationship('User', backref=db.backref('presences', cascade='all, delete-orphan'))


class ActivityEvent(db.Model):
    __tablename__ = 'activity_events'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    action = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    user = db.relationship('User', backref=db.backref('activity_events', cascade='all, delete-orphan'))


class LivePresence(db.Model):
    __tablename__ = 'live_presence'
    id = db.Column(db.String(64), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    session_key = db.Column(db.String(64), nullable=False, index=True)
    last_seen = db.Column(db.DateTime, nullable=False, index=True)
    visible = db.Column(db.Boolean, nullable=False, default=True)
    closed = db.Column(db.Boolean, nullable=False, default=False)
    device = db.Column(db.String(100), nullable=False)
    ip = db.Column(db.String(45), nullable=False)
    user = db.relationship('User', backref=db.backref('live_presences', cascade='all, delete-orphan'))


class RegistrationBlock(db.Model):
    __tablename__ = 'registration_blocks'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False, unique=True)
    google_subject = db.Column(db.String(255), unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class DeletedAccountId(db.Model):
    __tablename__ = 'deleted_account_ids'
    user_id = db.Column(db.Integer, primary_key=True)


class BookCover(db.Model):
    __tablename__ = 'book_covers'
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), primary_key=True)
    data = db.deferred(db.Column(db.LargeBinary, nullable=False))
    version = db.Column(db.String(32), nullable=False)
    book = db.relationship('Book', backref=db.backref('cover', uselist=False, cascade='all, delete-orphan'))


class BookInfo(db.Model):
    __tablename__ = 'book_info'
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), primary_key=True)
    description = db.Column(db.Text, default='')
    publisher = db.Column(db.String(150), default='')
    year = db.Column(db.Integer)
    pages = db.Column(db.Integer)
    language = db.Column(db.String(50), default='Tiếng Việt')
    shelf = db.Column(db.String(60), default='')
    book = db.relationship('Book', backref=db.backref('info', uselist=False, cascade='all, delete-orphan'))


class SamplePage(db.Model):
    __tablename__ = 'sample_pages'
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False, index=True)
    position = db.Column(db.Integer, nullable=False)
    data = db.deferred(db.Column(db.LargeBinary, nullable=False))
    mimetype = db.Column(db.String(30), nullable=False, default='image/jpeg')
    page_count = db.Column(db.Integer, nullable=False, default=1)
    book = db.relationship('Book', backref=db.backref('sample_pages', order_by='SamplePage.position', cascade='all, delete-orphan'))


class RenewalRequest(db.Model):
    __tablename__ = 'renewal_requests'
    id = db.Column(db.Integer, primary_key=True)
    issue_id = db.Column(db.Integer, db.ForeignKey('issues.id'), nullable=False)
    original_due = db.Column(db.DateTime, nullable=False)
    requested_days = db.Column(db.Integer, nullable=False, default=7, server_default='7')
    approved_days = db.Column(db.Integer)
    status = db.Column(db.String(20), nullable=False, default='pending')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    issue = db.relationship('Issue', backref=db.backref('renewals', cascade='all, delete-orphan'))
    __table_args__ = (db.Index('uq_pending_renewal', 'issue_id', unique=True,
                               sqlite_where=db.text("status = 'pending'"), postgresql_where=db.text("status = 'pending'")),)


class LibrarySetting(db.Model):
    __tablename__ = 'library_settings'
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.Integer, nullable=False)


class MailRecord(db.Model):
    __tablename__ = 'mail_records'
    id = db.Column(db.Integer, primary_key=True)
    dispatch_key = db.Column(db.String(100), unique=True)
    kind = db.Column(db.String(30), nullable=False)
    recipient = db.Column(db.String(120), nullable=False)
    issue_id = db.Column(db.Integer)
    sent_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class PasswordReset(db.Model):
    __tablename__ = 'password_resets'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    digest = db.Column(db.String(64), nullable=False, unique=True)
    account_guard = db.Column(db.String(64), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('password_resets', cascade='all, delete-orphan'))


class AccountRecovery(db.Model):
    __tablename__ = 'account_recoveries'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    email = db.Column(db.String(120), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    member_code = db.Column(db.String(40), nullable=False)
    contact = db.Column(db.String(200), nullable=False)
    evidence = db.Column(db.Text, nullable=False)
    account_guard = db.Column(db.String(64))
    status = db.Column(db.String(20), nullable=False, default='pending')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)
    user = db.relationship('User', backref=db.backref('recovery_requests'))


class PasswordChangeRequired(db.Model):
    __tablename__ = 'password_change_required'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    user = db.relationship('User', backref=db.backref('password_change_required',uselist=False,cascade='all, delete-orphan'))


class RecoveryCredential(db.Model):
    __tablename__ = 'recovery_credentials'
    recovery_id = db.Column(db.Integer, db.ForeignKey('account_recoveries.id'), primary_key=True)
    ciphertext = db.Column(db.LargeBinary, nullable=False)
    account_guard = db.Column(db.String(64), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    recovery = db.relationship('AccountRecovery', backref=db.backref('credential', uselist=False, cascade='all, delete-orphan'))


class Announcement(db.Model):
    __tablename__ = 'announcements'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    body = db.Column(db.Text, nullable=False)
    color = db.Column(db.String(7), nullable=False, default='#1b3885', server_default='#1b3885')
    expires_at = db.Column(db.DateTime)
    audience = db.Column(db.String(20), nullable=False)
    target_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    sender = db.relationship('User', foreign_keys=[sender_id])


class AnnouncementReceipt(db.Model):
    __tablename__ = 'announcement_receipts'
    announcement_id = db.Column(db.Integer, db.ForeignKey('announcements.id'), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    read_at = db.Column(db.DateTime)
    announcement = db.relationship('Announcement', backref=db.backref('receipts',cascade='all, delete-orphan'))
    user = db.relationship('User',backref=db.backref('announcement_receipts',cascade='all, delete-orphan'))


class DueReminder(db.Model):
    __tablename__ = 'due_reminders'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    issue_id = db.Column(db.Integer, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    book_title = db.Column(db.String(200), nullable=False)
    removed = db.Column(db.Boolean, nullable=False, default=False)
    user = db.relationship('User', backref=db.backref('due_reminders', cascade='all, delete-orphan'))
    __table_args__ = (db.UniqueConstraint('user_id', 'issue_id', 'due_date'),)


class ChatThread(db.Model):
    __tablename__ = 'chat_threads'
    id = db.Column(db.Integer, primary_key=True)
    low_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    high_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    low_read = db.Column(db.Integer, nullable=False, default=0)
    high_read = db.Column(db.Integer, nullable=False, default=0)
    low_typing = db.Column(db.DateTime)
    high_typing = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    low_user = db.relationship('User', foreign_keys=[low_id], backref=db.backref('chats_low', cascade='all, delete-orphan'))
    high_user = db.relationship('User', foreign_keys=[high_id], backref=db.backref('chats_high', cascade='all, delete-orphan'))
    __table_args__ = (db.UniqueConstraint('low_id', 'high_id'), db.CheckConstraint('low_id < high_id'))


class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'
    id = db.Column(db.Integer, primary_key=True)
    thread_id = db.Column(db.Integer, db.ForeignKey('chat_threads.id'), nullable=False, index=True)
    sender_id = db.Column(db.Integer, nullable=False, index=True)
    body = db.Column(db.Text, nullable=False)
    reply_id = db.Column(db.Integer, db.ForeignKey('chat_messages.id', ondelete='SET NULL'))
    edited_at = db.Column(db.DateTime)
    deleted_at = db.Column(db.DateTime)
    client_id = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    thread = db.relationship('ChatThread', backref=db.backref('messages', cascade='all, delete-orphan'))
    __table_args__ = (db.UniqueConstraint('sender_id', 'client_id'), db.Index('ix_chat_thread_message', 'thread_id', 'id'))


class ChatAttachment(db.Model):
    __tablename__ = 'chat_attachments'
    message_id = db.Column(db.Integer, db.ForeignKey('chat_messages.id'), primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    mimetype = db.Column(db.String(100), nullable=False)
    data = db.deferred(db.Column(db.LargeBinary, nullable=False))
    size = db.Column(db.Integer, nullable=False)
    message = db.relationship('ChatMessage', backref=db.backref('attachment', uselist=False, cascade='all, delete-orphan'))


class ChatReaction(db.Model):
    __tablename__ = 'chat_reactions'
    message_id = db.Column(db.Integer, db.ForeignKey('chat_messages.id'), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    emoji = db.Column(db.String(10), nullable=False)
    message = db.relationship('ChatMessage', backref=db.backref('reactions', cascade='all, delete-orphan'))
    user = db.relationship('User', backref=db.backref('chat_reactions', cascade='all, delete-orphan'))


class ChatChange(db.Model):
    __tablename__ = 'chat_changes'
    id = db.Column(db.Integer, primary_key=True)
    thread_id = db.Column(db.Integer, db.ForeignKey('chat_threads.id'), nullable=False, index=True)
    message_id = db.Column(db.Integer, nullable=False)
    thread = db.relationship('ChatThread', backref=db.backref('changes', cascade='all, delete-orphan'))


class ChatContact(db.Model):
    __tablename__ = 'chat_contacts'
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    peer_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    owner = db.relationship('User', foreign_keys=[owner_id], backref=db.backref('chat_contacts_owned', cascade='all, delete-orphan'))
    peer = db.relationship('User', foreign_keys=[peer_id], backref=db.backref('chat_contacts_received', cascade='all, delete-orphan'))


class ChatBlock(db.Model):
    __tablename__ = 'chat_blocks'
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    peer_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    owner = db.relationship('User', foreign_keys=[owner_id], backref=db.backref('chat_blocks_owned', cascade='all, delete-orphan'))
    peer = db.relationship('User', foreign_keys=[peer_id], backref=db.backref('chat_blocks_received', cascade='all, delete-orphan'))


class ChatState(db.Model):
    __tablename__ = 'chat_states'
    thread_id = db.Column(db.Integer, db.ForeignKey('chat_threads.id'), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    cleared_through = db.Column(db.Integer, nullable=False, default=0)
    hidden = db.Column(db.Boolean, nullable=False, default=False)
    thread = db.relationship('ChatThread', backref=db.backref('states', cascade='all, delete-orphan'))
    user = db.relationship('User', backref=db.backref('chat_states', cascade='all, delete-orphan'))


class UserAvatar(db.Model):
    __tablename__ = 'user_avatars'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    data = db.deferred(db.Column(db.LargeBinary, nullable=False))
    version = db.Column(db.String(32), nullable=False)
    user = db.relationship('User', backref=db.backref('avatar', uselist=False, cascade='all, delete-orphan'))


class ChatGroup(db.Model):
    __tablename__ = 'chat_groups'
    thread_id = db.Column(db.Integer, db.ForeignKey('chat_threads.id'), primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    thread = db.relationship('ChatThread', backref=db.backref('group', uselist=False, cascade='all, delete-orphan'))


class ChatGroupMember(db.Model):
    __tablename__ = 'chat_group_members'
    thread_id = db.Column(db.Integer, db.ForeignKey('chat_threads.id'), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    owner = db.Column(db.Boolean, nullable=False, default=False)
    joined_after = db.Column(db.Integer, nullable=False, default=0)
    last_read = db.Column(db.Integer, nullable=False, default=0)
    typing_at = db.Column(db.DateTime)
    thread = db.relationship('ChatThread', backref=db.backref('group_members', cascade='all, delete-orphan'))
    user = db.relationship('User', backref=db.backref('chat_group_memberships', cascade='all, delete-orphan'))

# Group history survives account deletion, so a recycled SQLite user ID must never
# claim old messages or change their displayed author.
from sqlalchemy import event


@event.listens_for(User, 'before_delete')
def retire_chat_sender(mapper, connection, target):
    connection.execute(ChatMessage.__table__.update().where(
        ChatMessage.sender_id == target.id).values(sender_id=-ChatMessage.id))
