# Bàn giao dự án Thư viện

Cập nhật: 06/11/2026 (giờ Việt Nam).

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
