# 📚 Library Management System

A full-stack web application built with **Flask**, containerised with **Docker**, and integrated with a **Jenkins CI/CD pipeline**.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, Flask 3.0 |
| Database | SQLite (via SQLAlchemy ORM) |
| Frontend | Jinja2 Templates, Vanilla CSS/JS |
| Containerisation | Docker (multi-stage build) |
| Orchestration | Docker Compose |
| CI/CD | Jenkins Pipeline (Declarative) |
| Testing | pytest, pytest-flask |

---

## Features

- **Books** – Add, view, and delete books with ISBN, genre, and quantity tracking
- **Members** – Register and manage library members with auto-generated IDs
- **Issue / Return** – Choose the borrowing date, due date, and actual return date for each loan
- **Dashboard** – Live stats: total books, members, active issues, and overdue count
- **REST API** – `/api/books`, `/api/members`, `/api/issues`
- **Health Check** – `/health` endpoint for Docker and Jenkins monitoring

---

## Project Structure

```
library-management-system/
├── app/
│   ├── __init__.py        # App factory
│   ├── models.py          # SQLAlchemy models (Book, Member, Issue)
│   ├── routes.py          # Flask blueprints & views
│   └── templates/         # Jinja2 HTML templates
│       ├── base.html
│       ├── index.html
│       ├── books.html
│       ├── members.html
│       └── issues.html
├── tests/
│   ├── conftest.py        # pytest fixtures
│   └── test_app.py        # Unit & integration tests
├── Dockerfile             # Multi-stage Docker build
├── docker-compose.yml     # App + Jenkins services
├── Jenkinsfile            # Declarative CI/CD pipeline
├── requirements.txt
├── run.py                 # WSGI entry point
├── .gitignore
└── .dockerignore
```

---

## Quick Start (Local)

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd library-management-system

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
python run.py
# Open http://localhost:5000
```

---

## Docker Deployment

```bash
# Build the image
docker build -t library-ms:latest .

# Run with Docker Compose (app + Jenkins)
docker-compose up -d

# App  →  http://localhost:5000
# Jenkins  →  http://localhost:8080
```

---

## Running Tests

```bash
# Install pytest
pip install pytest pytest-flask

# Run all tests
pytest tests/ -v

# With HTML report
pytest tests/ -v --html=reports/test-report.html
```

---

## Jenkins Pipeline Stages

| Stage | Description |
|-------|-------------|
| **Checkout** | Pull source code from Git |
| **Setup Environment** | Create Python venv & install deps |
| **Lint** | Run flake8 static analysis |
| **Unit Tests** | Run pytest & publish JUnit results |
| **Docker Build** | Build multi-stage Docker image |
| **Image Verification** | Spin up container & hit `/health` |
| **Push to Registry** | Push tagged image to Docker Hub (main branch) |
| **Deploy** | `docker-compose up -d` deployment |

### Setting up Jenkins

1. Start Jenkins: `docker-compose up -d jenkins`
2. Visit `http://localhost:8080`
3. Install plugins: **Git**, **Docker Pipeline**, **JUnit**, **HTML Publisher**
4. Create a **Pipeline** job → point to this repo
5. Set branch to `main` → Build Now

---

## Đưa code lên GitHub và cập nhật về sau

### Phân biệt GitHub và deploy

- **Git** lưu lịch sử thay đổi trên máy thông qua các commit.
- **GitHub** lưu repository online; dùng `git push` để đưa commit từ máy lên GitHub.
- **Deploy** là đưa ứng dụng lên server để người khác truy cập bằng URL online.

Đưa code lên GitHub chưa tự làm website chạy online. GitHub Pages chỉ phục vụ website tĩnh,
không chạy backend Python/Flask của dự án này. Muốn chạy đầy đủ đăng nhập, database và mượn/trả,
cần một dịch vụ hosting hỗ trợ Python hoặc Docker.

### Lần đầu đưa dự án lên GitHub

1. Tạo một repository trống trên GitHub. Không chọn tạo thêm README, `.gitignore` hoặc license
   trong bước này vì thư mục trên máy đã có các file của dự án.
2. Mở terminal PowerShell tại thư mục dự án.
3. Chạy các lệnh sau, thay URL mẫu bằng URL repository của bạn:

```powershell
git init
git branch -M main
git add .
git status
git diff --cached
git commit -m "Hoan thanh quan ly thu vien va luong muon sach"
git remote add origin https://github.com/TEN_CUA_BAN/TEN_REPO.git
git push -u origin main
```

Kiểm tra danh sách và nội dung file đã đưa vào vùng chờ trước khi commit.
Nếu Git yêu cầu danh tính, cấu hình tên và email cho repository rồi chạy lại lệnh commit:

```powershell
git config user.name "Ten cua ban"
git config user.email "email-cua-ban@example.com"
```

Khi push, làm theo hướng dẫn đăng nhập GitHub của Git trên máy.
Các lệnh khởi tạo ở trên dành cho thư mục chưa có Git và repository GitHub trống;
không cần chạy lại `git init` hoặc `git remote add` cho mỗi lần cập nhật.

### Sau mỗi lần sửa code

Nên commit sau mỗi phần việc hoàn chỉnh, đã kiểm tra; push khi phần đó chạy ổn hoặc trước khi nghỉ.
Không cần đợi hoàn thành toàn bộ website và cũng không cần commit sau mỗi lần lưu file.

```powershell
git status
git diff
git add .
git diff --cached
git commit -m "Sap xep lai giao dien Sach cua toi"
git push
```

Ví dụ các commit riêng: thêm đăng nhập và phân quyền, thêm yêu cầu mượn sách,
sửa lỗi phiên đăng nhập, sắp xếp lại giao diện. Đặt thông điệp mô tả đúng phần vừa sửa.
Nếu chỉ muốn commit một số file, thay `git add .` bằng `git add DUONG_DAN_FILE`.

Nếu đang thử nghiệm hoặc làm dở tính năng, có thể tạo nhánh riêng:

```powershell
git switch -c feature/ten-tinh-nang
# Sua code va kiem tra, sau do:
git add .
git commit -m "Mo ta thay doi"
git push -u origin feature/ten-tinh-nang
```

Giữ nhánh `main` là bản chạy ổn; chỉ gộp nhánh tính năng sau khi đã kiểm tra.
Nếu sửa từ nhiều máy hoặc làm việc cùng người khác, đồng bộ thay đổi từ GitHub trước khi bắt đầu.

### File không đưa lên GitHub

`.gitignore` hiện loại `instance/`, `*.db`, `*.sqlite3`, `.env` và `.venv/`.
Không commit database người dùng, mật khẩu, token khởi tạo quản trị, khóa phiên hoặc API key.
Hai file `instance/setup-token` và `instance/session-secret` nằm trong thư mục đã được loại.
GitHub lưu code; cần sao lưu database riêng. `.gitignore` không tự loại file đã được Git theo dõi từ trước.

### Khi muốn deploy website online

1. Đưa bản code chạy ổn lên GitHub.
2. Chọn hosting hỗ trợ Flask/Python hoặc Docker và kết nối repository.
3. Cấu hình biến môi trường, lệnh chạy và nơi lưu database.
4. Kiểm tra đăng nhập, phân quyền, yêu cầu mượn và dữ liệu sau khi triển khai.

Dự án dùng SQLite trong `instance/`, nên hosting phải có nơi lưu dữ liệu bền vững;
nếu chỉ lưu trên filesystem tạm, tài khoản và phiếu mượn có thể mất khi redeploy.
Có thể chuyển sang database được quản lý khi cần. Giữ `SECRET_KEY` ổn định giữa các lần deploy;
khi dùng HTTPS, đặt `COOKIE_SECURE=1`.

Nếu bật tự động deploy, mỗi lần push vào nhánh đã cấu hình có thể cập nhật website online.
Push lên GitHub và deploy có thể tách riêng; không nhất thiết mọi commit đều phải deploy.

Tài liệu tham khảo:

- [Đưa dự án có sẵn lên GitHub](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github)
- [Giới hạn của GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site)

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Public library home |
| `/admin` | GET | Staff dashboard |
| `/book/<id>` | GET | Book information and reading sample |
| `/admin/books/<id>/edit` | GET/POST | Edit book and upload reading sample |
| `/admin/renewals` | GET | Review renewal requests |
| `/admin/reports` | GET/POST | Reports, Excel, print/PDF and fine configuration |
| `/books` | GET | List all books |
| `/books/add` | POST | Add a book |
| `/books/delete/<id>` | POST | Delete a book |
| `/members` | GET | List members |
| `/members/add` | POST | Register a member |
| `/issues` | GET | List all issues |
| `/issues/add` | POST | Issue a book |
| `/issues/return/<id>` | POST | Return a book |
| `/api/books` | GET | JSON – all books |
| `/api/members` | GET | JSON – all members |
| `/api/issues` | GET | JSON – all issues |
| `/health` | GET | Health check |


## Accounts and permissions

- `/login`, `/register`: sign in or create a reader account. Passwords are hashed.
- `/profile`: edit your name/phone or change your password with your current password.
- `/my-books`: see only your own borrowing history and overdue loans.
- `/accounts`: administrators can issue accounts, assign roles, and disable sign-in.
- Readers can browse books. Librarians manage books, members and circulation. Administrators also manage accounts.
- Existing member records are linked to a login only by an administrator, not by public registration.
- Members with login accounts cannot be deleted; disable the account instead.

### First administrator

Start the app, read `instance/setup-token`, then visit
`http://127.0.0.1:5000/setup?token=YOUR_TOKEN` to choose the first administrator email and password.
This setup page is disabled once an administrator exists. Keep the setup token private.
Existing books, members and loans remain in the current database; a new `users` table is added automatically.

The session signing key persists in `instance/session-secret` (or use the `SECRET_KEY` environment variable).
All POST forms require a CSRF token. Set `COOKIE_SECURE=1` when serving over HTTPS.
The login form temporarily limits repeated failed attempts within the same browser session.


### Separate reader and staff flows

The public library is at `/`, with book discovery at `/catalog`.
Reader registration and sign-in lead to `/`. Staff sign-in leads to `/admin`.
The admin dashboard, member records, circulation and account management remain protected by role checks.
Stale POST forms are rejected without applying changes, then redirected to a fresh page with a message.
The dedicated `library_session` cookie avoids collisions with other Flask apps on localhost.


### Reader borrowing requests

Readers choose **Yêu cầu mượn** on a catalog card and track or cancel pending requests in **Sách của tôi**.
Staff review requests at `/admin/borrow-requests`, choose a due date and approve or reject.
Approval creates one loan and atomically decrements available stock; pending requests do not reserve stock.
Repeated submissions/approvals do not create duplicate pending requests or deduct stock twice.
If no copy remains, the request stays pending. Returning the resulting loan uses the existing return workflow.

### Đăng nhập bằng Google

Trang `/login` và `/register` có nút Google Identity Services. Client ID của dự án đã được cấu hình;
có thể thay bằng biến môi trường `GOOGLE_CLIENT_ID` khi triển khai. Client ID là định danh công khai,
không phải Client Secret. Luồng popup này không cần Client Secret hay redirect URI.

Trong Google Auth Platform → Clients → Web application, khai báo Authorized JavaScript origins
khớp địa chỉ bạn mở web, gồm `http://localhost`, `http://localhost:5000`,
`http://127.0.0.1`, `http://127.0.0.1:5000` khi phát triển. Thêm origin HTTPS thật khi deploy.

- Flask dùng `google-auth` xác minh chữ ký, audience, issuer, hạn dùng của ID token; kiểm tra thêm nonce,
  email đã xác minh và CSRF của biểu mẫu cùng origin. Không chỉ giải mã JWT để tin danh tính.
- Tài khoản Gmail/Google Workspace mới mặc định là độc giả, không có mật khẩu riêng.
- Danh tính Google được lưu theo `sub` trong bảng `google_identities`, không đổi quyền tài khoản hiện có.
- Email đã có tài khoản: đăng nhập bằng mật khẩu → Hồ sơ cá nhân → nhập mật khẩu hiện tại và chọn
  Google cùng email để liên kết. Không tự gộp tài khoản chỉ vì trùng email.
- Email có trong danh bạ nhưng chưa có tài khoản: nhờ quản trị viên cấp tài khoản, sau đó liên kết.
- Tài khoản bị khóa không thể dùng Google để vượt qua việc khóa.
- Nút cần tải script từ `accounts.google.com`; backend cần kết nối Google để xác minh token.
  Các test tự động giả lập phản hồi Google; bước chọn tài khoản và chấp thuận thực tế cần thử bằng trình duyệt.

Hướng dẫn chính thức: [xác minh Google ID token](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token).


### Trạng thái truy cập trực tiếp trong Tài khoản

Admin xem tại `/accounts`. Không có tab nhật ký riêng, không ghi thêm sự kiện sử dụng.
Bảng tự lấy trạng thái mỗi 5 giây, không tải lại trang hoặc làm mất dữ liệu đang nhập trong biểu mẫu.
Mỗi tab gửi heartbeat 15 giây/lần; mất tín hiệu quá 45 giây được coi là ngoại tuyến.
Phân biệt **Đang xem web**, **Đang mở web · tab nền**, **Ngoại tuyến** và **Đã khóa**.
Trạng thái phản ánh tín hiệu trình duyệt, không chứng minh người dùng đang thao tác liên tục.

- Hiển thị thiết bị/hệ điều hành và trình duyệt từ User-Agent, không phải tên máy vật lý chính xác.
- IP lấy từ kết nối đến server; chạy localhost sẽ thấy `127.0.0.1` hoặc `::1`.
- Không tin trực tiếp `X-Forwarded-For`. Khi deploy sau reverse proxy cần cấu hình proxy tin cậy
  đúng hạ tầng trước khi muốn hiển thị IP gốc của người dùng.
- Nhiều tab và nhiều trình duyệt được tính riêng; ẩn/đóng một tab không làm mất trạng thái của tab khác.
- Đăng xuất kết thúc các tab của phiên đó. Mất mạng/đóng tab có thể cần tối đa 45 giây để hết trạng thái online.
- API `/admin/accounts/presence` chỉ dành cho admin. `/admin/activity` cũ chuyển về `/accounts`.
- Nhật ký cũ không bị xóa, nhưng không được hiển thị và không ghi mới.

### Xóa tài khoản và chặn đăng ký lại

Trong `/accounts`, admin chọn **Xóa tài khoản** rồi chọn:

- **Chỉ xóa:** xóa thông tin đăng nhập, liên kết Google và phiên truy cập; email được đăng ký lại.
- **Xóa và chặn đăng ký lại:** ngoài việc xóa còn chặn email và Google subject đã liên kết.
  Gmail được chuẩn hóa để dấu chấm, `+tag` hoặc `googlemail.com` không vượt qua chặn cùng hộp thư.
- **Danh sách chặn đăng ký** nằm ngay trên trang Tài khoản; admin có thể bỏ chặn để cho đăng ký lại.

Tài khoản đang giữ vai trò admin không thể bị xóa. Hộp thoại yêu cầu chọn một tài khoản khác
đang hoạt động nhận quyền quản trị; tài khoản cũ trở thành thủ thư. Sau đó admin có thể xóa tài khoản cũ.
Nếu chuyển quyền của chính mình, cần đăng nhập bằng tài khoản quản trị mới để tiếp tục.

Phiếu mượn/trả và hồ sơ thành viên cũ được giữ để xử lý sách chưa trả; email trong hồ sơ cũ được thay bằng
địa chỉ lưu trữ nội bộ. Các yêu cầu mượn đang chờ bị hủy. Người đăng ký lại nhận hồ sơ mới,
không tự nhận lịch sử hoặc quyền của tài khoản cũ. Các phiên cũ không thể dùng lại tài khoản mới.
Chặn theo email/danh tính Google không ngăn một người dùng đăng ký bằng một email khác.

### Ảnh bìa sách

Admin/thủ thư tải ảnh khi **Thêm sách**, hoặc chọn **Ảnh bìa** trong bảng Sách để đổi/gỡ ảnh.
Có xem trước trước khi lưu. Hỗ trợ JPG, PNG, WebP tối đa 5 MB, dưới 20 triệu điểm ảnh.
Backend kiểm tra nội dung ảnh bằng Pillow, thu nhỏ tối đa 1200 × 1600 và lưu lại JPEG đã loại metadata.
Ảnh lưu trong bảng `book_covers` của database, không thay đổi schema bảng sách cũ.
Ảnh hiển thị công khai tại kho sách, bảng quản lý và sách đang mượn; chỉ thủ thư/admin được thay đổi.
Sách chưa có ảnh dùng biểu tượng mặc định. Sao lưu database cũng bao gồm ảnh bìa.

### Thông tin sách và bản đọc thử

Từ bảng **Sách**, chọn **Chỉnh sửa**, hoặc mở chi tiết sách → **Chỉnh sửa sách & đọc thử**.
Có thể sửa tên, tác giả, ISBN, thể loại, số lượng, mô tả, nhà xuất bản, năm xuất bản, số trang,
ngôn ngữ và vị trí kệ. Tổng số lượng không được thấp hơn số bản đang cho mượn.

Admin/thủ thư tải PDF hoặc nhiều ảnh làm bản đọc thử: tối đa 10 trang tổng cộng,
PDF 10 MB/tệp, ảnh 5 MB/tệp, tổng một lần tải 32 MB. Tệp mới thay thế toàn bộ bản cũ;
để trống giữ nguyên, hoặc chọn gỡ bản đọc thử. Chỉ tải tài liệu được phép chia sẻ.
PDF được kiểm tra và sao chép các trang sang PDF mới, loại annotation/action tương tác;
ảnh được xử lý giống ảnh bìa. Khách chưa đăng nhập cũng được đọc thử tại `/book/<id>`.
Không cần thay đổi bảng dữ liệu cũ; các bảng bổ sung được tạo khi khởi động app.

### Gia hạn, phí trễ hạn và báo cáo

Độc giả vào **Sách của tôi** → **Xin gia hạn +7 ngày** khi sách chưa quá hạn.
Thủ thư/admin duyệt tại **Gia hạn mượn**. Mỗi lượt mượn tối đa hai lần gia hạn,
mỗi lần 7 ngày. Không gia hạn phiếu đã trả, quá hạn, tài khoản bị khóa hoặc yêu cầu đã xử lý.

**Báo cáo & phí trễ hạn** lọc theo tháng có ngày mượn, xuất Excel hoặc mở bản in để lưu PDF.
Admin đặt mức phí/ngày; mặc định 0 đồng (chưa áp dụng). Phí hiển thị là **tạm tính theo mức hiện tại**,
không phải sổ thu tiền và không ghi nhận thanh toán. Thay đổi mức phí tính lại cả các phiếu lịch sử.

### Thông báo trên web và khôi phục tài khoản qua admin

Không gửi email nhắc hạn hay email đặt lại mật khẩu; không cần SMTP.
Lệnh `send-reminders`, API gửi email và luồng token email đã được gỡ.
Liên kết email cũ chuyển về biểu mẫu hỗ trợ, không còn đặt lại được mật khẩu.

**Thông báo hạn trả:** độc giả có mục `/notifications`, huy hiệu số lượng và nhắc trên các trang
khi có sách đến hạn trong 3 ngày hoặc quá hạn. Sách đã trả không còn trong thông báo.

**Quên mật khẩu:** người dùng điền email, họ tên, điện thoại, mã thành viên nếu nhớ,
cách liên hệ và thông tin bổ sung. Yêu cầu gửi vào `/admin/account-recovery`, chỉ admin được xem.
Biểu mẫu không tự xác thực danh tính hoặc tự đặt lại mật khẩu khi thông tin trùng khớp.
Admin đối chiếu hồ sơ và xác minh qua kênh đáng tin cậy, tích xác nhận rồi cấp mật khẩu tạm.
Có thể từ chối yêu cầu; không thể tự duyệt yêu cầu cho chính tài khoản admin đang dùng.

Mật khẩu tạm được sinh ngẫu nhiên; thông tin đăng nhập lưu dạng băm. Admin có thể xem lại bản mã hóa trong danh sách khôi phục tối đa 24 giờ, trước khi người dùng đổi mật khẩu.
Admin giao lại mật khẩu qua kênh đã xác minh. Người dùng phải đổi sang mật khẩu khác ngay sau khi
đăng nhập; các phiên cũ hết hiệu lực. Không cấp theo yêu cầu đã xử lý, tài khoản bị khóa/xóa hoặc
mật khẩu tài khoản đã thay đổi từ lúc gửi yêu cầu. Tối đa 3 yêu cầu/email trong 24 giờ.
Không yêu cầu gửi mật khẩu cũ hoặc giấy tờ định danh qua biểu mẫu.
Các bảng email cũ được giữ để không xóa dữ liệu ngoài ý muốn, nhưng không còn được sử dụng.

### Gộp Thành viên và Tài khoản

Giao diện quản lý tập trung tại `/accounts` (chỉ admin). Menu Thành viên đã được gỡ;
URL `/members` cũ chuyển về `/accounts` cho admin, hoặc Mượn/Trả cho thủ thư.
Dữ liệu `Member` vẫn giữ bên dưới để không làm mất liên kết phiếu mượn/trả.
Trang tài khoản chia hai nhóm: **Quản trị viên** và **Người dùng** (thủ thư/độc giả).
Hồ sơ cũ chưa có đăng nhập nằm trong mục thu gọn, có thể cấp tài khoản bằng cùng email để liên kết.

Nút **Chỉnh sửa** mở `/accounts/<id>/edit`, cho admin cập nhật tên, email, điện thoại,
mã thành viên, ngày đăng ký, vai trò, trạng thái, mật khẩu mới và gỡ liên kết Google.
Không hiển thị mật khẩu cũ; để trống giữ nguyên. Đổi mật khẩu người khác bắt buộc đổi lại sau đăng nhập.
Email đồng bộ giữa tài khoản và hồ sơ; không cho trùng email/mã thành viên hoặc sử dụng email đang bị chặn.
Đổi email đã liên kết Google phải gỡ liên kết cũ; tài khoản chỉ có Google cần đặt mật khẩu trước khi gỡ.
Không được tự khóa/hạ quyền admin đang sử dụng, cần dùng chức năng chuyển quyền quản trị.
ID nội bộ, IP/thiết bị tự ghi nhận và liên kết phiếu mượn không được sửa thủ công.


### Danh sách khôi phục gọn và xem lại mật khẩu tạm

`/admin/account-recovery` hiển thị bảng gọn; bấm **Chi tiết** để mở đối chiếu và thao tác duyệt.
Sau khi cấp hoặc cấp lại, mật khẩu tạm có nút **Hiện/Ẩn** và **Sao chép** ngay tại dòng yêu cầu.
Bản xem lại lưu bằng Fernet, khóa dẫn xuất từ `SECRET_KEY` ổn định; không lưu plaintext trong DB,
flash message hoặc cookie. Chỉ admin được xem; không hiển thị sau 24 giờ, khi tài khoản bị khóa,
mật khẩu đã thay đổi hoặc không còn yêu cầu đổi mật khẩu bắt buộc.
Mật khẩu đăng nhập vẫn được kiểm tra bằng bản băm như trước.

Yêu cầu cũ chỉ có bản băm không thể khôi phục lại mật khẩu cũ. Admin mở **Chi tiết**, xác minh lại
và chọn **Cấp lại mật khẩu tạm** khi người dùng chưa đổi mật khẩu. Mật khẩu tạm trước mất hiệu lực.
Không cấp lại theo yêu cầu cũ nếu tài khoản đã đổi mật khẩu hoặc có yêu cầu khác được xử lý mới hơn.
