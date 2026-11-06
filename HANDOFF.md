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
