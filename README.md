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

### Điện thoại bắt buộc và thông báo admin trực tiếp

Tài khoản đăng nhập nhưng thiếu số điện thoại hợp lệ sẽ thấy hộp thoại bắt buộc bổ sung,
bao gồm người mới đăng nhập Google và tài khoản đã có trước đây. Nhập 9–15 chữ số,
có thể bắt đầu bằng `+`; đây là kiểm tra định dạng, chưa phải xác minh OTP.
Hộp thoại không đóng bằng Escape/click ngoài; có thể lưu hoặc đăng xuất.
Gửi yêu cầu mượn/gia hạn cũng được chặn ở backend nếu còn thiếu điện thoại.

Admin soạn tại `/admin/announcements`: gửi tất cả tài khoản đang hoạt động, nhóm độc giả,
nhóm thủ thư hoặc một người. Người nhận được chốt lúc gửi; tài khoản tạo sau không nhận thông báo cũ.
Người dùng đang mở web có polling mỗi 5 giây (`/live-updates`), hiện hộp thoại nội dung an toàn
bằng textContent, không render HTML do người soạn nhập. Bấm **Đã đọc** để xác nhận;
người ngoại tuyến nhận khi quay lại, xem lại tại `/inbox`. Trạng thái đã đọc đồng bộ giữa các tab.
Hộp thoại bổ sung điện thoại được ưu tiên trước thông báo admin; không bỏ sót thông báo trong lúc bổ sung.
Không phải push notification của hệ điều hành, không hiện khi trình duyệt đã đóng.
Sau lần nâng cấp này cần tải lại tab cũ một lần để nhận JS mới, sau đó thông báo không cần reload.

Thông báo admin (cập nhật): không gửi/hiện thông báo cho vai trò admin, không bắt admin nhập điện thoại.
Người dùng nhận ô nhỏ góc phải dưới, tự ẩn sau 7 giây, không khóa trang hoặc giành focus.
Ẩn thông báo được ghi nhận trong localStorage của trình duyệt để không lặp lại qua polling;
không tự đánh dấu đã đọc chỉ vì hết thời gian. Nội dung vẫn xem lại ở `/inbox`.


### Tin nhắn

Chức năng tin nhắn đã được gỡ khỏi web, bao gồm chat riêng/nhóm, tệp đính kèm và kiểm tra tin mới.
Thông báo quản trị, nhắc hạn trả sách và ảnh đại diện trong hồ sơ vẫn hoạt động.
Các bảng tin nhắn cũ được giữ để tương thích dữ liệu; không còn API truy cập chat.

### Đăng ký có xác nhận và liên kết Google

- Đăng ký độc giả gồm 2 bước: chọn Google để xác nhận email, sau đó hoàn tất họ tên/điện thoại và đặt mật khẩu riêng cho website. Email lấy từ Google; không nhập mật khẩu Gmail vào website.
- Máy chủ kiểm tra chữ ký token Google, client ID, thời hạn, nonce, email_verified và email khớp trước khi tạo tài khoản. User và GoogleIdentity được lưu trong cùng giao dịch; không có tài khoản mới bị bỏ lại chưa liên kết khi gặp lỗi.
- Nút Google trên trang đăng nhập vẫn có thể tạo độc giả mới đã liên kết ngay, không có mật khẩu riêng như luồng trước.
- Tài khoản cũ, tài khoản bootstrap hoặc do admin cấp chưa liên kết vẫn đăng nhập bằng mật khẩu. Banner “Tài khoản chưa liên kết Google” dẫn đến Hồ sơ → Phương thức đăng nhập. Người dùng nhập mật khẩu thư viện hiện tại rồi chọn đúng Google cùng email để liên kết. Không tự gắn danh tính Google chỉ dựa trên email đã nhập.
- Banner có ở tất cả vai trò chưa liên kết; trạng thái cập nhật mỗi 5 giây qua live-updates, không cần reload. Admin thấy trạng thái Google rõ ở Tài khoản và Chỉnh sửa tài khoản. Chỉ người sở hữu tài khoản có thể xác nhận Google; admin không liên kết thay.

### Mốc khôi phục trước khi thêm hiệu ứng giao diện

Phiên bản sau khi bỏ ô Email lặp ở bước 2 đăng ký được lưu lên GitHub trước khi thêm hiệu ứng chuyển động. Email đăng ký được lấy ở máy chủ từ xác nhận Google của bước 1; người dùng không cần nhập lại.

Các thay đổi làm giao diện mượt hơn sẽ được giữ riêng trên máy để xem thử trước khi cập nhật tiếp lên GitHub. Có thể xem thay đổi bằng `git diff` và tìm mốc đã lưu bằng lịch sử commit trên GitHub. Database SQLite và tệp phiên làm việc trong `instance/` không thuộc bản lưu mã nguồn.


### Hiệu năng và tài nguyên giao diện

- Font Inter và Material Symbols được phục vụ trong `app/static/fonts/`, kèm giấy phép; giao diện không cần kết nối Google Fonts khi mở trang.
- CSS/JS có mã phiên bản theo nội dung và được trình duyệt dùng lại. Sau khi sửa code, khởi động lại ứng dụng để cập nhật mã phiên bản; không cần xóa cache mỗi lần.
- HTML tài khoản vẫn dùng `Cache-Control: no-store`. Tài nguyên công khai được cache riêng; ảnh đại diện chỉ dành cho chính tài khoản đó và quản trị viên.
- Phản hồi HTML/JSON lớn được nén gzip nếu trình duyệt hỗ trợ. Thống kê dùng SQL tổng hợp; danh sách sách và khoản mượn tải các dữ liệu liên quan cùng lượt thay vì truy vấn theo từng dòng.
- Biểu mẫu POST thông thường hiện trạng thái đang gửi và ngăn bấm gửi lặp. Các trang và hộp thoại mở trực tiếp, không dùng hiệu ứng chuyển cảnh.
- Kiểm tra hồi quy hiệu năng: `python -m pytest tests/test_performance.py -q`; kiểm tra gửi biểu mẫu: `node --test tests/interaction.test.cjs`.


### Bảo trì và phát hành phiên bản

- Quản trị viên bật/tắt bảo trì tại ô **Cơ sở chính** ở cuối thanh bên. Có hộp xác nhận và trang xem trước, không cần bật thật để xem giao diện.
- Bảo trì chặn các yêu cầu mới của người dùng/thủ thư ở server với HTTP 503; admin vẫn truy cập để điều khiển. Tab đang mở kiểm tra mỗi giây và tự chuyển sang trang bảo trì, tự quay lại khi mở web. Tab nền có thể bị trình duyệt giới hạn; không thể hủy thao tác đã hoàn tất trước thời điểm bật.
- Web kiểm tra phiên bản, hiện **Cập nhật / Để sau**, không tự tải lại làm mất thao tác. Lần đầu triển khai chức năng này, các tab cũ phải tải lại một lần.
- Mỗi phiên bản production đặt `APP_VERSION` bằng ID release/commit; local tự tính từ code. Giữ SECRET_KEY và dữ liệu bền vững khi đổi release.
- Xem [hướng dẫn Vercel/Neon, chuyển SQLite, staging và bảo trì](deploy/README.md), hoặc [đưa lên Botkeep Free](deploy/BOTKEEP.md). Production dùng PostgreSQL qua `DATABASE_URL`; local vẫn dùng SQLite nếu không cấu hình database ngoài.
- Kiểm tra: `python -m pytest tests/test_operations.py -q` và `node --test tests/operations.test.cjs`.


### Liên hệ quản trị viên

- Độc giả chọn **Liên hệ admin** trên navbar (`/contact`), nhập tiêu đề và nội dung, sau đó xem phản hồi trong từng yêu cầu. Đăng nhập để gửi và xem lịch sử riêng.
- Admin chọn **Liên hệ độc giả** trong menu quản trị (`/admin/contact`) để lọc yêu cầu, trả lời và đánh dấu đã giải quyết. Người gửi hoặc admin có thể mở lại yêu cầu.
- Các phản hồi được lưu vào database dùng chung (`contact_requests`, `contact_replies`). Chỉ chủ yêu cầu và admin truy cập được nội dung; thủ thư không được đọc hộp thư admin.
- Gửi phản hồi/đổi trạng thái cập nhật tại chỗ, không chạy polling nền. Chọn **Làm mới** để kiểm tra phản hồi mới. Không gửi email hay thông báo đẩy.
- Bảng mới được tạo tự động khi khởi động ứng dụng; không cần thay đổi dữ liệu sách, tài khoản hoặc chat cũ.


### Mượn nhanh, đặt chỗ và trả sách bằng QR

- Độc giả chọn **Mượn nhanh** trong danh mục hoặc trang sách. Web lập phiếu ngay, trừ kho trong giao dịch và dùng thời hạn mặc định 14 ngày (admin có thể đổi). Chọn **Sách của tôi** hoặc **Mượn trả tự động** để xem phiếu và QR trả sách.
- Mỗi hồ sơ có mã thư viện ổn định `DG-001`, `DG-002`… dựa trên ID hồ sơ; có thể có khoảng trống do hồ sơ đã xóa hoặc tài khoản nhân viên. Mã hồ sơ cũ vẫn được giữ cho tương thích dữ liệu. Thẻ QR được tạo/tải tại **Hồ sơ cá nhân**.
- Có hai luồng trả: (1) admin/thủ thư chọn trả tại **Mượn / Trả sách**, (2) độc giả xuất trình QR, admin/thủ thư mở **Quét QR mượn trả**, quét camera hoặc chọn ảnh, kiểm tra rồi bấm **Xác nhận đã nhận sách**. Quét mã đơn thuần không thay đổi kho. Các lần xác nhận lặp không tăng kho thêm.
- Chỉ chủ phiếu và admin/thủ thư được xem QR/biên nhận; chỉ admin/thủ thư được nhận sách và xác nhận thu phí. QR có chữ ký và mã bảo vệ lưu trong database; không chứa mật khẩu, không thay thế đăng nhập, không phụ thuộc hostname. Giữ ổn định SECRET_KEY khi deploy để QR đã cấp còn dùng được.
- Phiếu quá hạn hiển thị số ngày và phí. Vào **Cấu hình** ngay trong trạm QR (`/circulation/scan#settings`) để nhập mã BIN ngân hàng 6 số, tài khoản, chủ tài khoản và phí/ngày. Để trống cả ba thông tin ngân hàng nếu chưa dùng QR. Phí mặc định 5.000 đ/ngày khi chưa cấu hình, cho phép đặt 0. Khoản phí được chốt tại lúc nhận sách.
- QR chuyển khoản sử dụng [Quick Link VietQR.io](https://www.vietqr.io/qr-dong). Thông tin nhận tiền, số tiền và mã phiếu được gửi cho dịch vụ tạo ảnh; không gửi tên/email độc giả. Không tích hợp webhook hoặc tự động xác minh giao dịch ngân hàng: nhân viên đối soát thực tế rồi đánh dấu đã thu. Có thể nhận sách trước và giữ khoản phí chưa thanh toán.
- Hết sách: độc giả đặt chỗ tại trang chi tiết. Hàng đợi được ưu tiên theo thứ tự đăng ký cho luồng mượn nhanh; khi có bản trả về, quay lại trang sách để kiểm tra và nhận lượt. Admin/thủ thư vẫn quyết định việc lập phiếu trực tiếp tại quầy. Không gửi email/push tự động.
- Phần sơ đồ và vị trí kệ đã được gỡ. Dữ liệu kệ cũ được giữ trong database để tương thích, không còn giao diện/API quản lý.
- Camera cần HTTPS hoặc localhost và quyền của trình duyệt. Ở địa chỉ IP qua HTTP, dùng chọn ảnh QR hoặc máy quét nhập văn bản. QR được đọc trên thiết bị; camera tắt khi dừng/rời trang.
- Các bảng mới tự tạo khi khởi động trên SQLite hoặc PostgreSQL; không xóa phiếu cũ. Các yêu cầu chờ từ phiên bản trước vẫn xử lý tại **Yêu cầu mượn cũ**; endpoint yêu cầu mượn cũ chuyển sang mượn nhanh.
- Cài dependency: `pip install -r requirements.txt`; chạy `python run.py` tại cổng 5000. Kiểm tra Python: `python -m pytest -q`; JavaScript: `node --test tests/qr_scanner.test.cjs tests/interaction.test.cjs tests/page_motion.test.cjs tests/operations.test.cjs`.


### Trạm QR riêng cho admin và thủ thư

- Trang quản trị có nút **Mở trạm QR mượn trả**. Trạm tại `/circulation/scan` có giao diện riêng, không kèm sidebar quản trị hoặc navbar độc giả.
- Người chưa đăng nhập được đưa tới `/circulation/login`; chỉ tài khoản admin/thủ thư đang hoạt động đăng nhập được. Tài khoản độc giả bị chặn cả ở giao diện lẫn backend, bao gồm thao tác cấu hình. Dùng cùng tài khoản/phiên của web; tài khoản Google có thể đăng nhập trên web trước rồi mở trạm.
- **Quét QR** và **Cấu hình mượn trả & nhận phí** nằm trên cùng trang. Cả admin và thủ thư được chỉnh số ngày mượn, phí/ngày và tài khoản nhận phí. Đường dẫn cấu hình cũ chuyển về trạm QR.
- Màn xem phiếu sau quét và xác nhận nhận sách của nhân viên dùng cùng giao diện trạm; độc giả vẫn có trang QR phiếu của mình.
- `/shelves` và `/admin/shelves/suggest` đã bị gỡ; không còn phân kệ, sơ đồ, bộ lọc mã kệ hoặc thông tin tầng/cánh trong cấu hình.


### Quét nhiều QR liên tục

- Trạm QR tải kết quả vào hộp thoại ngay trên trang quét. Mở thẻ DG sẽ hiện các phiếu đang mượn; chọn phiếu để kiểm tra trong cùng hộp thoại.
- Xác nhận nhận sách/thu phí thành công sẽ đóng hộp thoại và hiện thông báo ngắn, giữ nguyên trang quét. Camera được bật lại nếu đang dùng camera trước đó; quét lại mã vừa hoàn tất bị bỏ qua để tránh lặp.
- Khoản phí chưa thu được nhắc trong thông báo và có nút xem lại; không tự đánh dấu đã thanh toán. Có thể đóng hộp thoại hoặc dùng Escape để quét tiếp; không đóng giữa lúc yêu cầu xác nhận đang gửi.
- Khi mở link phiếu trực tiếp bằng tài khoản nhân viên, web đưa về trạm và mở phiếu trong hộp thoại. Trang QR/biên nhận của độc giả vẫn hoạt động như trước.


### Trang QR độc giả tự cập nhật

Trang QR trả sách của độc giả kiểm tra trạng thái mỗi 3 giây khi đang hiển thị. Sau khi nhân viên xác nhận nhận sách (QR hoặc thủ công), QR được thay bằng biên nhận ngay tại chỗ, không tải lại trang. Nếu còn phí chưa thu, kiểm tra trạng thái thanh toán mỗi 10 giây; dừng khi hoàn tất. Tab ẩn sẽ tạm dừng, mở lại kiểm tra ngay. Endpoint chỉ cho chủ phiếu hoặc nhân viên đọc, phản hồi không được cache và chỉ trả nội dung giao diện khi trạng thái thay đổi.
