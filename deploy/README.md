# Phát hành và bảo trì

Không sửa trực tiếp thư mục ứng dụng đang phục vụ khách hàng. Cấu hình Linux bên dưới là phương án VPS riêng; bản web hiện triển khai trên Vercel.

## Vercel và Neon PostgreSQL

- Production dùng `DATABASE_URL` do tích hợp Neon cung cấp. Ứng dụng cũng nhận `POSTGRES_URL`; nếu không có cả hai thì dùng SQLite tại `instance/library.db` cho local.
- Đặt `SECRET_KEY` cố định và `COOKIE_SECURE=1` trong môi trường Production trước khi deploy. Giữ khóa cũ khi chuyển dữ liệu để thông tin khôi phục tài khoản đã mã hóa vẫn đọc được. Không đưa khóa hoặc chuỗi kết nối lên Git.
- Neon được kết nối với Production; Preview/staging cần database và khóa riêng. Không cho bản thử nghiệm ghi dữ liệu production.
- Ảnh sách, avatar, PDF đọc thử và tệp chat nằm trong database, nên được chuyển cùng dữ liệu. Thư mục `/tmp` trên Vercel chỉ là vùng tạm; không dùng SQLite tại đó để lưu dữ liệu thật.
- Đẩy code lên nhánh `main` sẽ tạo deployment mới. Database Neon tồn tại độc lập với deployment. Trước khi đổi schema, sao lưu và kiểm tra tương thích; `create_all` chỉ tạo bảng còn thiếu, không tự sửa cột của bảng PostgreSQL đã có.

### Chuyển SQLite sang database trống

Sao lưu SQLite bằng `sqlite3.Connection.backup` trước khi chuyển; không sao chép file đang ghi bằng lệnh copy thông thường. Đặt `DATABASE_URL` trong môi trường riêng, ưu tiên kết nối trực tiếp (unpooled) khi nhập dữ liệu.

```powershell
python deploy/import_sqlite.py path/to/snapshot.db
python deploy/import_sqlite.py path/to/snapshot.db --apply
```

Lệnh đầu kiểm tra nhập toàn bộ rồi rollback; `--apply` mới lưu. Công cụ từ chối database đích đã có dữ liệu, giữ ID, quan hệ và đặt lại bộ đếm ID. Nếu lỗi, toàn bộ giao dịch bị hủy. Không chạy lại để gộp hai database đang có giao dịch riêng.

Trên Windows nếu trình điều khiển `psycopg` bị chính sách máy chặn, có thể dùng `pg8000` từ PyPI cho công cụ nhập: chuỗi kết nối `postgresql+pg8000://...` không kèm tham số `sslmode`/`channel_binding`; công cụ vẫn bắt buộc TLS và xác minh chứng chỉ. Production dùng `psycopg` trong requirements.

## Chế độ bảo trì đã có trong ứng dụng

- Admin: ô **Cơ sở chính → Bật bảo trì**, đọc xác nhận rồi bật. Chỉ admin có quyền điều khiển; POST yêu cầu CSRF.
- Khi bật, các yêu cầu mới của khách/độc giả/thủ thư bị server trả 503 trước khi thực hiện thao tác. Admin vẫn truy cập. Login và Google cho tài khoản admin đã liên kết vẫn dùng được; không tạo tài khoản Google mới khi bảo trì.
- Các tab đã tải operations.js kiểm tra trạng thái mỗi 1 giây. Tab nền có thể bị trình duyệt làm chậm; khi quay lại sẽ kiểm tra ngay. Yêu cầu API bị chặn sẽ kích hoạt trang bảo trì ngay khi nhận phản hồi. Không hứa độ trễ bằng 0 và không thu hồi được giao dịch đã hoàn tất trước lúc bật.
- Tắt bảo trì mở lại truy cập; trang bảo trì tự quay về đường dẫn người dùng đã mở. Có bản xem trước riêng, không cần bật thật.
- Trạng thái nằm trong bảng library_settings của database thật, không trong bộ nhớ từng worker. Không chép database thử nghiệm đè lên production.
- Nếu chính Flask dừng hẳn thì Flask không thể phục vụ trang bảo trì: dùng Nginx và unavailable.html để hiện trang dự phòng ngay cả khi backend không chạy.

## Nhận bản cập nhật

APP_VERSION là ID release/commit ổn định giữa các worker. Local tự tính hash code. Tab đang mở phát hiện bản mới, hiện **Cập nhật / Để sau**, không tự reload và không tự bỏ biểu mẫu/tệp chưa lưu. Tab mở từ trước khi cơ chế này được triển khai cần tải lại một lần. Không cache HTML tài khoản hoặc bỏ kiểm tra quyền.

## Production trên Linux

1. Tạo staging dùng database, SECRET_KEY và OAuth URL riêng. Chạy tests; kiểm tra staging; không dùng dữ liệu thật để thử nút bảo trì.
2. Tạo image bằng deploy/Dockerfile.production; file này chỉ COPY source cần thiết, không đóng gói instance/, .env, database hay tài liệu đính kèm.
3. Đặt APP_IMAGE (tag phiên bản), APP_VERSION, SECRET_KEY (mạnh và giữ ổn định), GOOGLE_CLIENT_ID, LIBRARY_DATA_DIR (thư mục instance bền vững), COOKIE_SECURE=1 cho HTTPS. Dữ liệu gắn vào container phải có quyền ghi cho appuser. Không dùng SECRET_KEY mặc định.
4. Dùng `docker compose --env-file /path/private-production.env -f deploy/compose.production.yml up -d --build`. Đây là cập nhật một instance, có thể gián đoạn ngắn; không phải blue-green tự động.
5. Cấu hình reverse proxy/TLS và OAuth origin/URL theo domain thật. Nginx ví dụ cần sửa domain, upstream, cài chứng chỉ HTTPS; chép unavailable.html sang /var/www/library/unavailable.html.
6. Nếu triển khai sau proxy, cần cấu hình việc tin cậy proxy/IP theo đúng số hop. Không tự tin X-Forwarded-For từ Internet; hiện ứng dụng vẫn ghi socket peer.

## Cập nhật không gián đoạn: quy trình cần cấu hình trên hạ tầng thật

- Giữ release A phục vụ. Khởi chạy B ở cổng khác, cùng SECRET_KEY và database production nếu schema tương thích; health-check B, sau đó đổi upstream của reverse proxy sang B và reload Nginx. A xử lý nốt request đang chạy rồi mới dừng.
- Giữ A và image cũ để rollback; kiểm tra cả schema và dữ liệu trước khi rollback. Không rollback file SQLite bằng bản cũ khi đã có giao dịch mới.
- Với SQLite local, không tạo hai bản database độc lập cho A/B, không đặt SQLite trên ổ mạng. Với PostgreSQL, hai release có thể dùng chung database khi schema tương thích; luôn kiểm tra migration trước khi phát hành.
- Cơ chế nâng cấp schema hiện chạy lúc khởi động. Với thay đổi schema, phải kiểm tra tương thích A/B và khóa database; có thể cần cửa sổ bảo trì. Không mặc định coi mọi lần phát hành đều zero downtime.
- Giữ tài nguyên release cũ khi còn tab dùng bản cũ; không xóa ngay image/static assets cũ. Chỉ tự động hóa chuyển upstream sau khi đã chọn host, đường dẫn dữ liệu và cơ chế kiểm tra/rollback thực tế.
- Sao lưu bằng công cụ backup SQLite nhất quán hoặc snapshot dịch vụ DB; thử khôi phục trên staging trước. Chế độ bảo trì không thay thế việc drain các request đang chạy hoặc sao lưu.
