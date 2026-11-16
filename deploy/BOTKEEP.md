# Đưa web thư viện lên Botkeep Free

## 1. Chuẩn bị code

Cập nhật mã nguồn mới nhất lên GitHub trước. Repo hiện dùng:
https://github.com/ducngo080905/WebQuanLyThuVienCloud

Không đưa `.env`, `instance/`, khóa phiên, database, `.venv` hoặc bản nén dự phòng lên GitHub. File `botkeep.py` và phiên bản mới của `requirements.txt` phải có trên nhánh triển khai.

## 2. Tạo máy chủ

Trong Botkeep, tạo một ứng dụng với profile **Python**, chọn Python **3.12** nếu có. Dành 512 MB RAM, 50% CPU và 1 GB lưu trữ cho ứng dụng này. Chọn nguồn GitHub, repo trên, nhánh `main`, thư mục gốc dự án. Nếu repo riêng tư, cấp GitHub App quyền vào đúng repo đó.

Botkeep hỗ trợ ứng dụng Python qua profile; không cần chạy Docker Compose hoặc Jenkins của dự án. Một slot chỉ chạy web; tiếp tục dùng database Neon bên ngoài.

## 3. Cấu hình Environment

| Tên | Giá trị |
| --- | --- |
| `DATABASE_URL` | Chuỗi kết nối Neon đang dùng cho web Vercel, có TLS |
| `SECRET_KEY` | Giữ đúng khóa hiện tại trên Vercel để đọc dữ liệu khôi phục đã mã hóa |
| `GOOGLE_CLIENT_ID` | Client ID Google OAuth của dự án |
| `COOKIE_SECURE` | `1` khi dùng HTTPS |
| `APP_VERSION` | Mã commit hoặc nhãn phiên bản vừa phát hành |
| `SERVER_PORT` | Cổng Botkeep cấp trong Network; nếu runtime đã cấp biến này thì giữ nguyên |

Không gửi chuỗi kết nối hoặc khóa bí mật qua chat. Điền chúng trực tiếp trong Environment của máy chủ.

`botkeep.py` đọc `.env` được quản lý bởi panel; biến môi trường thực tế có ưu tiên cao hơn. File này yêu cầu Neon và khóa cố định, tránh vô tình tạo SQLite trống trên host mới. Kết nối cùng Neon nghĩa là Botkeep và Vercel cùng đọc/ghi dữ liệu thật; không dùng database đó để thử xóa tài khoản hoặc bật bảo trì.

## 4. Cài và chạy

Nếu panel tự cài từ `requirements.txt`, giữ chế độ đó. Nếu có ô lệnh cài đặt, dùng:

```sh
pip install -r requirements.txt
```

Lệnh khởi động:

```sh
python botkeep.py
```

Script chạy Gunicorn trên `0.0.0.0:SERVER_PORT`, mặc định một worker, hai thread để phù hợp RAM 512 MB. Đây là lệnh cho Linux trên Botkeep; local Windows tiếp tục chạy `python run.py` ở cổng 5000.

## 5. Mở tên miền và xác minh

Trong Domains, tạo alias hoặc thêm domain theo lựa chọn panel và bật HTTPS. Trong Google Auth Platform, thêm origin HTTPS mới vào OAuth client đang dùng; nhập origin gồm giao thức và tên miền, không có `/login`. Giữ các origin cũ nếu còn sử dụng Vercel/local.

Sau khi Start, đọc Console. Mở lần lượt `/health`, trang chủ, kho sách, đọc thử PDF, đăng nhập thường/Google, quản trị và chat. Kiểm tra dữ liệu cũ có sẵn, đo RAM/CPU khi dùng đồng thời; số đo trên Windows không thay thế thử tải trên Botkeep.

Chưa xác nhận đã triển khai chỉ vì panel nhận lệnh. Cần thấy tiến trình chạy và web thật trả lời thành công.

## 6. Những lần cập nhật sau

Push GitHub rồi dùng tab GitHub của Botkeep để xem và áp dụng revision mới; tùy chọn cập nhật tự động phải bật riêng. Redeploy không mặc định kéo code mới và có thể ngắt dịch vụ khi restart. Giữ một bản sao dữ liệu riêng trước khi đổi schema.

Tài liệu chính thức: [ứng dụng và cổng mạng](https://botkeep.cloud/docs/hosting), [GitHub](https://botkeep.cloud/docs/github), [Environment Python](https://botkeep.cloud/docs/python), [cập nhật và giới hạn](https://botkeep.cloud/faq).
