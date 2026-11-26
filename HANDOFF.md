# Bàn giao dự án Thư viện

Cập nhật: 16/11/2026.

## Trạng thái hiện tại

- Chỉ duy trì website; dự án Android, API riêng cho app và nút tải APK đã được gỡ theo yêu cầu. Bản nén dự phòng nằm trong `instance/archives/`, không được đưa lên Git hoặc hosting.
- Local chạy SQLite ở cổng 5000. Vercel dùng Neon PostgreSQL qua `DATABASE_URL`; dữ liệu hai môi trường không tự đồng bộ nếu local chưa cấu hình cùng database.
- Thanh điều hướng dùng SVG để tránh font icon làm vỡ bố cục khi chuyển trang. Không bật lại hiệu ứng chụp khung hình cả trang; chuyển động nhẹ chỉ áp dụng menu, chat và hộp thoại.
- Các mục bên dưới có phần lịch sử; xác minh với code và test trước khi áp dụng.

## Bắt đầu cho chat/tài khoản mới

Đọc file này, README.md và mã nguồn hiện tại trước khi sửa. Không dựa vào lịch sử chat cũ.
Repo: https://github.com/ducngo080905/WebQuanLyThuVienCloud
Dự án Flask + SQLAlchemy + SQLite, Jinja2, CSS/JS thuần. Chạy local cổng 5000.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
.\.venv\Scripts\python.exe -m pytest -q
```

Trên máy hiện tại, thư mục dự án: `E:\Đám mây\College-Library-Management-System-main`.
Không tạo thêm nhiều tiến trình run.py trên cùng cổng; sửa Python/template cần khởi động lại vì debug tắt.

## Chức năng và lựa chọn đã thống nhất

- Khách xem trang chủ `/`, kho `/catalog`, chi tiết `/book/<id>`, ảnh bìa và đọc thử.
- Độc giả đăng ký email/mật khẩu hoặc Google; tài khoản mới luôn là reader. Đăng nhập reader về trang thư viện.
- Admin/librarian về `/admin`; kiểm tra quyền phía server, không chỉ ẩn nút giao diện.
- `/my-books`: thống kê, sách đang mượn theo hạn gần nhất, yêu cầu chờ, lịch sử thu gọn.
- Mượn theo yêu cầu: độc giả gửi, thủ thư/admin duyệt và lập phiếu; kho chỉ giảm khi duyệt.
- Gia hạn +7 ngày/lần, tối đa 2 lần; cần thủ thư duyệt; chưa quá hạn và chưa trả.
- Sách: thêm/xóa/chỉnh sửa thông tin xuất bản, mô tả, kệ; ảnh JPG/PNG/WebP tối đa 5 MB.
- Đọc thử: admin tải PDF/ảnh có sẵn, tổng tối đa 10 trang; PDF 10 MB, tổng request 32 MB.
- PDF dùng pypdf Python thuần, hiển thị bằng trình đọc PDF trình duyệt; PyMuPDF từng bị Windows chặn DLL, đã bỏ.
- Báo cáo theo tháng, xuất Excel, in/lưu PDF qua trình duyệt. Phí trễ hạn chỉ tạm tính, mặc định 0, chưa có sổ thu tiền.
- Không dùng email/SMTP cho nhắc hạn hoặc khôi phục. Thông báo hạn trả ngay trên web `/notifications`.
- Quên mật khẩu: gửi thông tin nhận dạng tại `/forgot-password`, chỉ admin xem `/admin/account-recovery`.
- Admin xác minh trực tiếp rồi cấp mật khẩu tạm; buộc người dùng đổi sau đăng nhập; phiên cũ mất hiệu lực.
- Danh sách khôi phục gọn thành bảng, mở Chi tiết để đối chiếu. Mật khẩu tạm lưu mã hóa Fernet,
  admin có thể xem/chép trong 24 giờ trước khi người dùng đổi mật khẩu; có cấp lại sau khi xác minh.
- Gộp giao diện Thành viên vào `/accounts`, bỏ menu riêng. Giữ bảng Member cho phiếu mượn cũ.
- `/accounts` chỉ admin: tách nhóm quản trị và người dùng; sửa tên/email/điện thoại/mã/ngày đăng ký/quyền/trạng thái/mật khẩu/Google.
- Xóa tài khoản: chỉ xóa thì được đăng ký lại với hồ sơ mới; xóa+chặn thì chặn email/Google, có bỏ chặn.
- Không xóa admin trực tiếp, cần chuyển quyền sang tài khoản khác trước. Phiếu mượn cũ giữ nguyên.
- Trạng thái online ngay trong accounts: polling 5 giây, heartbeat 15 giây, hết hạn 45 giây; có thiết bị, IP.
- Không có nhật ký hoạt động riêng nữa. Các bảng nhật ký cũ được giữ nhưng không ghi mới.
- Tổng quan đếm User (tài khoản), không đếm Member (có thể có hồ sơ lưu trữ sau xóa).

## Dữ liệu, xác thực và cấu hình

`instance/` chứa database, khóa phiên và token khởi tạo; bị Git bỏ qua, không đưa lên GitHub.
Dùng cùng máy/thư mục thì dữ liệu vẫn còn. Clone trên máy mới không có dữ liệu người dùng, ảnh hoặc bản đọc thử cũ
(vì ảnh/PDF lưu trong DB). Muốn chuyển cần sao lưu SQLite riêng bằng phương thức phù hợp, giữ riêng tư.
Không thay khóa SECRET_KEY của hệ thống đang dùng nếu muốn giữ phiên và khả năng giải mã mật khẩu tạm.
Google Client ID là định danh công khai; SECRET_KEY, mật khẩu và token khởi tạo là bí mật.
Admin đầu tiên được tạo bằng `/setup?token=...`, đọc token local trong `instance/setup-token`, không công khai.
Đăng nhập Google đã được người dùng thử thành công. Local origins cần khớp Google Console.

Các model bổ sung dùng bảng riêng để tránh phá schema cũ. `app/schema.py` xử lý nâng cấp SQLite thêm cột,
backup trước khi đổi; không xóa DB để sửa lỗi schema.

## Bản đồ mã nguồn

- app/__init__.py: app factory, cấu hình, đăng ký blueprint, create_all và nâng cấp schema.
- app/models.py: toàn bộ model, bao gồm các bảng cũ giữ tương thích.
- app/auth.py: login/register/profile/accounts, chặn đăng ký, chuyển quyền, xóa/sửa tài khoản.
- app/google_login.py: Google token verification, nonce, liên kết danh tính, guard phiên.
- app/routes.py: dashboard, sách/ảnh bìa, thành viên cũ, phiếu mượn/trả, API.
- app/features.py: thông tin sách/đọc thử, gia hạn, báo cáo/phí, thông báo web, admin recovery.
- app/activity.py: trạng thái online/IP/device (không còn nhật ký).
- app/static và app/templates: giao diện; giữ phong cách sáng xanh, tiếng Việt, responsive.
- tests/: integration tests, crypto token tests, dữ liệu giả. Lần chạy đầy đủ gần nhất: 75 test đạt;
  sau đó sửa thống kê User và kiểm tra 3 test dashboard đều đạt.

## Quy trình tiếp tục

Kiểm tra `git status`, đọc thay đổi hiện tại, sửa đúng yêu cầu; chạy test phù hợp rồi restart đúng server.
Không reset mật khẩu, xóa dữ liệu hoặc tạo tài khoản thật chỉ để thử UI. Dùng DB test trong bộ kiểm thử.
README có một số phần lịch sử; nếu khác code thì xác minh code/test thay vì tin tuyệt đối tài liệu.
Chưa triển khai hosting online; push GitHub chỉ đưa code lên, không tự chạy Flask bằng GitHub Pages.

## Câu nhắn dùng cho chat mới

> Đây là dự án quản lý thư viện của tôi. Đọc HANDOFF.md và README.md, kiểm tra mã nguồn và git status,
> rồi tiếp tục từ trạng thái hiện tại. Giữ dữ liệu instance/ và các quyết định trong HANDOFF.md.
> Yêu cầu tiếp theo của tôi là: ...

## Bổ sung 06/11/2026: thông báo trực tiếp

- `app/messages.py`, `live_updates.js`, `live_overlays.html`: bắt buộc bổ sung điện thoại, polling 5 giây.
- `Announcement`, `AnnouncementReceipt`: admin soạn cho tất cả/nhóm/từng người tại `/admin/announcements`.
- Hộp thư người dùng `/inbox`, trạng thái đã đọc theo tài khoản. Người chưa mở web nhận khi quay lại.
- Có modal điện thoại cho Google mới và tài khoản cũ chưa có số; chưa xác minh OTP.
- Kiểm thử mới `tests/test_messages.py`; xem kết quả chạy test hiện tại thay vì suy đoán từ mốc cũ.


## Messenger trên web
- Thêm `app/chat.py`, models `ChatThread`/`ChatMessage`, trang `/messenger`, menu cho staff/reader và badge tin chưa đọc trên mọi trang đăng nhập.
- API `/chat/api/…` kiểm tra thành viên cho mọi thao tác, CSRF theo app hiện tại, nonce chống gửi trùng, cursor đọc tăng dần, lịch sử phân trang, trạng thái nhập và online từ LivePresence. Poll chat 2,5 giây, badge 10 giây.
- UI riêng `messenger.css/js`, responsive 2 cột/1 màn hình trên điện thoại, dùng textContent cho tin nhắn, không render HTML người dùng.
- Chat văn bản/emoji/ảnh/PDF/TXT, trả lời, cảm xúc, chỉnh sửa 15 phút, thu hồi, tìm kiếm. Chưa có gọi/chat nhóm. Xóa User sẽ cascade xóa cuộc trò chuyện liên quan. Các bảng mới được `db.create_all()` thêm khi khởi động, không thay bảng cũ.

- Mở rộng chat: `ChatAttachment` blob deferred, `ChatReaction` một cảm xúc/người/tin, `ChatChange` cursor đồng bộ sửa/thu hồi/cảm xúc. `ChatMessage.reply_id/edited_at/deleted_at` nâng cấp thêm bằng schema.py có backup, không thay bảng cũ. Ảnh dùng read_cover để chuẩn hóa; PDF/TXT tải xuống, kiểm tra thành viên ở mọi lượt tải, no-store/nosniff.
- Frontend v2: toolbar trên tin, composer context trả lời/chỉnh sửa, chọn 1 tệp/lượt, preview ảnh, search panel phân trang/context jump. Thu hồi có hộp xác nhận; nội dung/tệp bị xóa, trích dẫn cập nhật, không thể thu hồi bản đã được người nhận tải xuống ngoài web.


## Chat privacy / contacts / avatar
- Added ChatContact (directed rows, created/deleted reciprocally), ChatBlock (one-way blocking, enforced in both directions), ChatState (per-user clear cursor + hidden), UserAvatar. New tables only, startup create_all.
- Non-admin overview returns friends only; POST /chat/api/contacts/add exact full email (no suggestions) adds both sides. Non-admin start/send require friend; admin directory remains global and admin start/send establishes reciprocal contact for replies. No automatic migration of old threads into friends.
- Block endpoints prevent send/edit/react/typing, including admin, mask online/typing. Recall/read/history still allowed. Remove-contact deletes friendship both sides, hides/clears only caller history via cursor; all reads/search/attachment/quotes/updates enforce clear cursor. Other participant keeps history, User not deleted.
- /profile/avatar POST normalizes through read_cover then square256; /chat/api/avatars/<id> access scoped to own/admin/friend/existing conversation. Avatar used on profile, header, chat contacts/thread/peer.
- UI v3: tools beside bubble, red unread badge, exact-email add form for non-admin, header menu block/delete, blocked manager.

## Hồ sơ cá nhân và sửa avatar tràn
- Trang profile dùng profile.css/profile.js riêng: thẻ danh tính/ảnh bên trái, thông tin cá nhân, mục bảo mật đóng/mở và liên kết Google bên phải; responsive một cột. Giữ nguyên các trường và quy tắc POST /profile, forced temporary password, Google linking.
- Header avatar có kích thước HTML/inline 36×36 dự phòng và account_ui.css riêng, tránh ảnh nguyên kích thước khi CSS chính còn cache. library.css v7. Profile avatar 112 px, xem trước ảnh trước lưu, kiểm tra 5 MB/20 MP phía client bổ sung cho kiểm tra server.
- Đã kiểm tra trực tiếp IAB: ảnh header/profile đúng kích thước, các cột không tràn, bảo mật mở/đóng được. 25 kiểm thử auth/avatar qua. Ảnh kiểm tra tại instance/profile-redesign.png (ignored).

## Chụp ảnh trong chat
- Nút camera trong ô soạn mở hộp chụp ảnh: xem camera, đổi trước/sau nếu thiết bị hỗ trợ, chụp lại, dùng ảnh hoặc chọn ảnh từ thiết bị. Ảnh chỉ được đưa vào bản nháp; người dùng bấm Gửi để gửi.
- Camera xin quyền khi người dùng bấm nút; không bật microphone. Cần HTTPS hoặc localhost. Đóng hộp thoại, chụp xong, rời tab/trang sẽ dừng camera; kết quả cấp quyền đến muộn cũng được giải phóng.
- Ảnh chụp JPEG cạnh dài tối đa 1600 px và giới hạn 5 MB, đi qua cùng API ảnh riêng tư hiện có. Nút tắt khi sửa tin/không có quyền gửi. Không lưu nếu cuộc trò chuyện đã đổi.
- `node --test tests/chat_camera.test.cjs` kiểm tra quyền đến muộn, đóng khi chụp, tắt camera, chụp lại, đổi camera và giới hạn ảnh.

## Chat nổi dành cho người dùng
- User và thủ thư dùng nút chat nổi góc dưới phải; admin giữ menu/trang chat đầy đủ. Khung 420 px bo24, chuyển động mở/đóng, badge đỏ, nút mở trang đầy đủ; responsive và prefers-reduced-motion.
- Widget chỉ tạo iframe /messenger?embed=1 khi mở lần đầu. Embed không có nav/overlays/presence/badge lặp, không đọc flash của trang cha. Dùng cùng giao diện/API/quyền chat hiện có.
- PostMessage kiểm tra origin + source. Khi thu nhỏ, frame dừng poll/đánh dấu đã đọc và đóng camera; giữ bản nháp. Nhớ trạng thái mở/cuộc chat trong sessionStorage theo user.
- 90 pytest qua; đã kiểm tra nút nổi và mở/thu nhỏ bằng IAB với dữ liệu mẫu. Phiên cookie riêng của preview không duy trì trong các request động ở IAB; HTTP integration cùng cookie riêng xác nhận overview/embed 200. Không xác nhận trực quan toàn bộ chat embedded bằng IAB. Xem thử dùng SQLite memory, không dùng dữ liệu thật; screenshot instance/chat-widget-corner.png.
- Lưu ý khi mở preview tương lai: luôn dùng tên cookie riêng ngay từ đầu hoặc hostname riêng; không dùng library_session chung host với web chính dù khác port.

## Chat nhóm
- ChatThread low_id/high_id nullable cho nhóm; ChatGroup metadata + ChatGroupMember (owner/active/joined_after/last_read/typing). ChatMessage/attachment/reaction/change dùng chung. Nhóm 2–50 người, user mời contacts/admin toàn bộ, check block mọi cặp thành viên.
- schema.upgrade_chat_threads rebuild nguyên tử bảng chat_threads với backup schema-backup-groups, giữ ID, message/file refs/indexes và unique pair direct; chưa bao giờ tạo user giả. Đã kiểm tra upgrade thật: các số lượng account/thread/message/attachment cũ không đổi.
- chat_groups.py đăng ký trên blueprint chat; membership authorization áp dụng mọi message/search/file/edit/react route, active owner-only management, join/rejoin history cutoff, transfer/leave và owner recovery sau account delete. API group_reads để cập nhật số người đã xem; quote/sender names dùng tên người gửi trong nhóm.
- User before_delete retires sender_id của tin còn tồn tại thành -message.id để tránh SQLite tái dùng user ID gán tin cũ cho người mới; direct threads vẫn cascade xóa theo cơ chế cũ.
- UI v6 tạo nhóm, picker theo contacts, group avatar/name/sender labels, quản lý/transfer/remove confirm 2 click và leave confirm. Dùng được cả embed/widget. Kiểm tra trực tiếp hộp tạo nhóm bằng IAB, chỉ chọn trong form, không tạo nhóm thật hoặc gửi tin. Screenshot instance/create-chat-group.png.
- 94 pytest toàn app qua trước test sender-ID reuse bổ sung; 5 group tests + direct deletion pass sau sửa sender retirement. Camera 5 Node tests qua. Tên cookie preview luôn giữ riêng theo lưu ý trước.

## Registration requires verified Google / legacy link reminder
- Public POST /register now requires google_credential proof validated with the real Google verifier (signature/audience/issuer/expiry + nonce/email_verified/Google Gmail or Workspace). Typed email must equal verified email. create_account accepts optional google_subject and atomically flushes User + GoogleIdentity then commits; setup/admin-created password accounts stay possible and get reminders.
- Registration GSI callback only decodes signed payload for UX autofill (name/email), puts original token in hidden input associated via form=registrationForm, enables submit. Backend never trusts decoded client fields. Registration still supports a separate website password, clearly labelled; existing login Google auto-register path remains linked and passwordless.
- googleLinkNotice SSR banner for every unlinked current user, excluded from chat embed, updated by live_updates v3 /live-updates google_link_required bool (including admin). Profile #google-account target; admin account list/editor clearly identify unlinked email vs linked Google. No automatic legacy linking/merging; existing profile link still requires current password and matching verified email.
- google_account.css separate from library CSS v8 to avoid stale cache. UI verified on localhost:5001/register preview, SQLite memory, random secret, SESSION_COOKIE_NAME library_registration_preview (no real session changed); no Google account consent or linking performed by agent. Screenshot instance/google-linked-registration.png.
- 105 pytest passed incl 10 new Google registration tests with real locally signed RSA tokens and mocked cert transport, checking plain-signup rejection, nonce/expiry/email/sig/CSRF rejection, rollback on subject conflict, legacy reminder live add/remove, admin warnings. Existing auth tests now explicitly seed pre-Google accounts with legacy_account helper to retain migration/password behavior coverage.

## Checkpoint trước UI smooth (2026-11-06)
- Đã bỏ hẳn trường Email ở bước 2 /register. Callback Google chỉ hiển thị email ở trạng thái bước 1; server lấy email từ registration_google_claims, không phụ thuộc trường email do client gửi. Nếu client cố gửi email khác proof vẫn bị từ chối.
- Yêu cầu người dùng: cập nhật repo origin/main hiện có sau thay đổi signup, rồi mới làm smooth. Staging chỉ app/, tests/, README.md, HANDOFF.md; không thêm file untracked ad hoặc instance/secret/database. Các hiệu ứng smooth phải để local khi chờ người dùng xem, checkpoint GitHub vẫn là bản trước smooth.


## UI motion removed at user request
- User requested removing all opening effects and cleaning their code. Deleted local ui_motion.css, page_navigation.css/js and their tests/includes. Removed chat widget opening/closing/icon transitions and toast entry keyframes directly from source CSS; bumped stylesheet versions.
- Pages, dialogs, floating chat and announcements now open immediately; retained original layouts, functionality and ordinary control hover feedback. No navigation interception, animation timers or motion override stylesheet remains.
- Checkpoint 68654fa remains on GitHub; current cleanup is local only. Untracked user file ad remains untouched.

## Whole-site performance work (2026-11-06, local only)
- User clarified perceived sluggishness affects the entire site and authorized full optimization, while keeping all opening/page/modal effects removed. No SPA/history interception or artificial delay added.
- app/performance.py: content-hash rev URLs for static assets, immutable caching for matching public assets/hashed WOFF2, gzip for HTML/JSON when accepted; account HTML remains no-store. Static requests bypass account DB loading; private media keep authorization.
- Self-hosted official Inter + Material Symbols WOFF2 and license files in static/fonts; preloaded Latin and symbols. No Google Fonts network dependency per page; Google sign-in itself unchanged.
- Replaced global full Issue history loading with SQL aggregation only on stats pages. Eager-loaded book covers and loan/member/account relationships on relevant lists. Missing/present fee settings cached in request.environ only (no stale app-context cache). Announcement receipts eager-load announcements. Presence queries return live/recent/latest rows instead of materializing all historical tabs.
- Cached normalized search indexes + one update/frame for catalog/admin tables. Extracted catalog inline JS. interaction.js adds native POST pending state/duplicate prevention without disabling successful submit button values; canceled/AJAX handlers keep their lifecycle. Preserves sidebar scroll; stable scrollbar space; no opening animations.
- Live phone overlay avoids repeating inert/layout work when unchanged; presence device DOM retained when unchanged. Chat thread nodes reused by ID/signature; avoids duplicate peer updates, unchanged read receipt text writes, and redundant unread API polling while messenger/widget overview is active. Unread widget messages validate origin and iframe source.
- Synthetic 80-book probe: catalog 92->11 SQL queries, management books 90->9 (final request cache fix adds one query vs initial report 8), static CSS 2->0. Books HTML ~173 KB -> ~9.2 KB gzip, catalog ~52 KB -> ~4.3 KB. Wall times are machine-local samples, not guaranteed remote latency/FPS.
- Browser checked admin, catalog no-accent search/clear, admin book table search/clear, open/close Add Book modal (0s/none), profile, accounts live status, messenger overview with no console errors. No real messages/forms/accounts changed. Screenshot instance/performance-review.png; user tab returned to /admin.
- Keep local until user accepts. origin/main checkpoint remains 68654fa. Do not touch untracked user file ad.
- Final validation: 112 pytest passed (workspace-local unique basetemp to avoid Windows sandbox temp permissions), 8 Node tests passed; all modified JS syntax checks and git diff --check passed. Running server restarted with these changes. No push/commit performed.


## Separate reader discovery page (2026-11-06, local)
- User requested /catalog differ from the already accepted home page. Home keeps library.html hero/catalog; extracted unchanged book card into _catalog_card.html. /catalog now uses catalog.py + catalog.html/_catalog_results.html with a dedicated search/filter sidebar, counts, availability, four sorting modes, 12-item server pagination, empty state, responsive layout and reader navigation current-page marker.
- SQLite deterministic library_fold registered per engine for accent-insensitive title/author/ISBN search and sorting; LIKE wildcards autoescaped. No schema/database migration or new actual books/users.
- discovery.js debounces search, aborts obsolete fetches, replaces results only, synchronizes URL/reset/pagination/back navigation. GET form + associated sidebar fields work without JS. Form does not wrap borrowing POST forms; auth/CSRF and pending/active reader card states retained. No opening animations.
- Browser verified guest UI with 26 synthetic books on memory-only localhost:5001 preview using unique library_catalog_preview_20261106 cookie; checked live search, availability filter, reset, page 2, no console errors. Screenshot instance/discovery-preview.png uses demo data. Actual running /catalog also verified against real existing books; user tab left there. Preview tab closed/server stopped; real port 5000 remains running. No Git push; checkpoint 68654fa unchanged.


## Reader inbox redesign (2026-11-06, local)
- User screenshot /inbox showed oversized announcement cards and all unread. Replaced with inbox.css/js compact native details list, title/body preview, sender/date, unread dot, all/unread/read filter counts, accent-insensitive indexed search and empty state. Open details marks read via existing private CSRF-protected POST; an open item stays visible in Unread until closed. Read state and counters update without reload. Read-all button has new user-scoped /inbox/read-all POST; native forms redirect back when return_to=inbox, AJAX receives JSON. Read timestamp idempotent; read-all does not overwrite already-read timestamps.
- Times display UTC+7; list size text reflects actual rows (100-recent note only when limit reached). live_updates.js listens for library:notice-read to remove just-read items from toast queue/local seen state.
- Six test_messages tests passed including two new tests for layout/time/idempotence and private/CSRF bulk read. JS syntax/diff checks passed.
- Browser verified against disposable RAM-only preview localhost:5001, cookie library_inbox_preview_20261106, existing synthetic login inbox-preview@example.com. Open/read/filter/search/read-all tested only on sample receipts, no real notifications read or sent. Screenshot instance/inbox-redesign-preview.png uses demo data. Preview tab closed/server stopped; actual port5000 restarted with new code. No commit/push.


## Compact reader navigation and notification center (2026-11-06)
- User requested a rounded compact reader navbar, account actions below the name, login under the same menu, and admin notices folded into Notifications. Added reader_header.html + reader_navigation.css/js: main links Home/Discovery/My Books only; native details account menu Profile/Notifications/POST Logout, guest Login/Register. Closes on outside click, Escape (returns focus), and focus leaving. No opening animations. Admin sidebar/topbar preserved.
- /notifications is the unified notification center with Tin từ quản trị and Hạn trả sách categories. Prioritizes due loans when present unless tab specified; toast/admin links explicitly select tab=admin. /inbox remains compatible and renders admin category. Reuses existing inbox behavior and own-loan queries; read redirects stay in admin category. Category unread badge follows local read state. Due alert links select loans.
- Corrected old literal ?v= suffixes in base/messenger/announcement/live templates to url_for v args: they previously corrupted newly added rev hashes; new regression test verifies actual rendered static URLs use immutable cache headers.
- Validation: 14 message/due/catalog/embed tests + 7 performance tests passed; JS syntax/diff checks passed. Browser tested guest menu login, synthetic reader account menu, Escape, links to both notification categories, no console errors. Preview uses RAM and unique library_nav_preview_20261106 cookie; no actual users/messages changed. Screenshot instance/reader-navbar-preview.png is demo. Port5000 restarted; preview closed/stopped; no commit/push.


## Personal bookshelf redesign (2026-11-06, local)
- User requested improving /my-books layout and moving it into the account dropdown. reader_header.html now leaves Home/Discovery on the main navbar; account menu has Profile/My Books/Notifications/Logout with current-page marker.
- Rebuilt my_books.html with my_books.css/js: compact linked summary counters, overdue callout, Active/Pending/History panels switched locally via hash (no opening animation). Active loans are cards with cover/title/author, dates, remaining/overdue state, renewal action/pending/limit and fee. Pending requests have clear cancel action; history retains indexed search and processed-request accordion. Without JS all sections remain available through anchor links. When no loans exist but requests are pending, default panel is Pending.
- Existing borrow/cancel/renew/return authorization, CSRF and date/fee behavior retained; active book cover metadata eager-loaded. Suppressed generic due banner on my-books because the page already has dedicated due states/overdue callout.
- Five targeted tests passed (own-loan privacy, request lifecycle, ownership/cancel, renewal ownership/limit, reader menu). Browser verified synthetic reader preview in RAM with unique library_bookshelf_preview_20261106 cookie: access from menu, active/pending/history switch, empty search result, no console errors; no cancel/renew forms submitted. Screenshot instance/my-books-redesign-preview.png uses demo data. Preview closed/stopped, actual port5000 restarted. No Git push.

## Sticky reader navbar
- User requested the rounded navbar stay visible while scrolling every reader page. reader_navigation.css now uses position:sticky at 12px (8px on compact screens, safe-area aware), same z-index/dropdown, no scroll handlers or animation. Added scroll-padding so anchor targets clear the navbar. Verified deep catalog scroll in RAM-only preview: computed position sticky/top 12px and dropdown still usable. Screenshot instance/sticky-navbar-preview.png uses demo data; preview closed/stopped; actual server restarted. Local only.


## Color changes reverted at user request
- User asked to remove all color/background edits beginning with the message "web toàn màu trắng thôi", including its follow-up consistency correction. Removed palette.css and its base.html include entirely, restoring pre-palette component colors/backgrounds. Preserved all earlier layout/navigation/notification/bookshelf/performance changes and the sticky reader navbar. No Git reset, no other user work reverted; no push.


## Gỡ tin nhắn (16/11/2026)
- Đã gỡ blueprint chat, giao diện messenger/widget, badge/polling, camera và tài nguyên chat. Các ghi chú chat phía trên là lịch sử triển khai, không còn mô tả tính năng hiện tại.
- Ảnh đại diện chuyển sang app/avatars.py, /profile/avatar và /profile/avatars/<id>; người dùng xem ảnh của mình, admin xem được tất cả. Thông báo và nhắc trả sách vẫn dùng app/messages.py.
- Giữ nguyên bảng và dữ liệu chat cũ, mappings/schema tương thích; không cung cấp endpoint đọc/ghi tin nhắn. Không tự xóa dữ liệu trên database.


## Liên hệ admin (16/11/2026)
- Thêm app/contact.py, ContactRequest/ContactReply và các template/CSS contact. Navbar độc giả có /contact; menu admin có /admin/contact.
- Hỗ trợ yêu cầu có tiêu đề, trao đổi văn bản riêng, trạng thái waiting/replied/closed, mở lại, phân trang, lọc admin. Kiểm tra quyền chủ yêu cầu/admin ở cả đọc, trả lời và đổi trạng thái; CSRF dùng middleware chung.
- Phản hồi và đổi trạng thái dùng data-refresh của interaction.js; không polling. Giờ UTC lưu DB, hiển thị UTC+7 định dạng 24 giờ.
- tests/test_contact.py kiểm tra trao đổi hai phía, quyền truy cập, validation/XSS/CSRF, phân trang/lọc, xóa tài khoản.


## Mượn nhanh và QR (17/11/2026)
- Thêm app/circulation.py, templates circulation/return_loan/scan_qr/circulation_settings/shelves, circulation.css và qr_scanner.js. Model mới: LibraryQRPass, BookReservation, CirculationConfig, ReturnReceipt. Không thêm cột vào bảng cũ. Member.library_code tính DG theo ID; giữ member_id cũ.
- Quick loan serialize theo book với UPDATE no-op rồi kiểm tra stock/active loan/FIFO; partial unique index chặn đặt chỗ trùng. Manual issue decrement atomically. complete_return dùng chung cho thủ công và QR, bảo vệ tăng kho một lần, lưu người xác nhận và phí đã chốt.
- QR PNG tạo nội bộ bằng qrcode 8.2, payload LIBQR + chữ ký itsdangerous + nonce persisted. Routes protected owner/staff; scanner staff-only. Camera/file decoder html5-qrcode 2.3.8 vendored cùng LICENSE (Apache-2.0), chỉ tải tại trang scan. Không khôi phục chat/Android.
- VietQR Quick Link chỉ hiển thị nếu cấu hình đầy đủ; admin cấu hình bank BIN/account/owner, ngày mượn, fee và labels zone A-D. Không ngân hàng webhook, không giả định ảnh QR = đã trả tiền.
- QA dùng database in-memory và HTML giả lập có dữ liệu thử, không tạo giao dịch trên database thật. Đã đọc QR PNG thật bằng scanFile trong trình duyệt. Camera vật lý chưa thử. Các file HTML/PNG QA tạm đã xóa. SQLite backup trước chạy nằm trong instance/before-qr-20261117-080238.db.


## Trạm QR độc lập, bỏ kệ sách (17/11/2026)
- qr_portal_base.html + qr_login.html tạo giao diện riêng; /circulation/login kiểm tra role admin/librarian, active, password và CSRF; giữ chính sách thử đăng nhập hiện tại. portal_required bảo vệ quét/config/confirm-return/confirm-payment.
- /circulation/scan xử lý GET quét và POST cấu hình; _qr_settings.html nhúng trực tiếp. Cho cả admin và librarian chỉnh cấu hình theo yêu cầu mới; /admin/circulation-settings GET chỉ chuyển về #settings, POST giữ tương thích và cùng kiểm tra quyền.
- Nút Mở trạm QR trên dashboard; menu staff vẫn có lối mở quét. return_loan.html chọn portal shell cho staff, base thường cho độc giả. Logout trạm chuyển lại login trạm.
- Gỡ routes shelves/suggest_shelves, template sơ đồ, trường và hiển thị shelf trên giao diện, bộ lọc tìm mã kệ, settings zone và CSS kệ. BookInfo.shelf và các cấu hình cũ giữ nguyên trong DB, không xóa dữ liệu.


## Quét liên tục trong hộp thoại (17/11/2026)
- X-QR-Dialog=1 cho GET scan/return trả JSON {title,html}; chỉ staff được nhận partial. _return_details.html và _qr_member.html là partial đã escape dữ liệu.
- POST confirm-return/confirm-payment với cùng header trả JSON, không redirect/flash. JS dialog handler chặn submit trước interaction.js, đóng sau thành công, toast 3.5s (10s nếu còn phí), resume camera khi trước đó active và chống scan lại cùng mã vừa hoàn tất.
- Staff GET /loans/<id>/return chuyển tới /circulation/scan?loan=<id>; JS mở hộp thoại và dọn tham số khi đóng. Các xác nhận backend cũ vẫn giữ tương thích, kiểm tra quyền/CSRF và idempotency.
- Kiểm tra: 146 Python + 22 JavaScript pass; UI thật mở phiếu #4 đã trả trong dialog rồi đóng, giữ trạm sẵn sàng. Không tạo/thay đổi giao dịch thật khi kiểm tra UI. Camera vật lý chưa thử.


## Đồng bộ QR phía độc giả (17/11/2026)
- GET /loans/<id>/live-status kiểm tra accessible_issue, trả state/status/changed/complete, chỉ render _return_details khi state thay đổi. Cache-Control private,no-store.
- reader_loan_live.js chỉ tải trên trang QR độc giả: polling 3s lúc mượn, 10s khi đã nhận sách nhưng còn phí; pause hidden/pagehide, resume pageshow/online/visibility; abort/generation chặn response cũ. Dừng khi hoàn tất.
- Thay #returnDetails và heading tại chỗ, không location.reload; QR trả sách không còn trong partial khi đã nhận. Kiểm tra backend before/after xác nhận, quyền riêng tư và JS lifecycle trong tests/test_circulation.py, tests/reader_loan_live.test.cjs.
