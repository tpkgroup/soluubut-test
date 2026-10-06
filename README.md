# Sổ lưu bút: web + database trên OpenStack Zun

Ứng dụng Flask lưu lời nhắn vào PostgreSQL.

```
Trình duyệt ──► floating IP ──► [ web ]  ──► [ db ]
 (mạng LAN)      cổng 80        Flask        PostgreSQL
                                192.168.50.x  192.168.50.10 (không có floating IP)
```

Database không có floating IP và chỉ nhận kết nối từ mạng nội bộ `web-net`.

## 0. Chuẩn bị

- Mạng `web-net` (192.168.50.0/24) và router đã có trong project (giảng viên tạo).
- Đưa `app.py` và `requirements.txt` lên một repo GitHub **Public** (thư mục gốc).
- Nạp thông tin đăng nhập của project (`source sv01-openrc.sh`).

## 1. Tạo security group

```bash
openstack security group create web-sg
openstack security group rule create --proto tcp --dst-port 80 --remote-ip 10.0.1.0/24 web-sg

openstack security group create db-sg
openstack security group rule create --proto tcp --dst-port 5432 --remote-ip 192.168.50.0/24 db-sg
```

Mỗi container phải được gán security group khi tạo, nếu không sẽ không truy cập được.

## 2. Tạo container database (làm trước)

Cố định IP của database để web biết địa chỉ cần kết nối:

```bash
openstack appcontainer run --name db \
  --net network=web-net,v4-fixed-ip=192.168.50.10 \
  --security-group db-sg \
  --environment POSTGRES_USER=app \
  --environment POSTGRES_PASSWORD=DoiMatKhauNay123 \
  --environment POSTGRES_DB=guestbook \
  postgres:16-alpine
```

Chờ trạng thái `Running`, rồi xem log:

```bash
openstack appcontainer logs db
```

Phải thấy dòng `database system is ready to accept connections`.
Nếu lệnh báo không nhận `--environment`, xem tên đúng bằng `openstack appcontainer run --help`.
Trong Horizon, các biến này nằm ở ô biến môi trường (Environment) của form tạo container.

## 3. Tạo container web

Thay `TEN_CUA_BAN`, `TEN_REPO` và mật khẩu cho khớp với bước 2:

```bash
openstack appcontainer run --name web \
  --net network=web-net \
  --security-group web-sg \
  --environment DB_HOST=192.168.50.10 \
  --environment DB_USER=app \
  --environment DB_PASSWORD=DoiMatKhauNay123 \
  --environment DB_NAME=guestbook \
  python:3.12-alpine \
  sh -c "apk add --no-cache git && git clone --depth 1 https://github.com/TEN_CUA_BAN/TEN_REPO /app && pip install --no-cache-dir -r /app/requirements.txt && cd /app && gunicorn -b 0.0.0.0:80 app:app"
```

Lần đầu mất vài phút vì phải cài git và các gói Python. Theo dõi bằng `openstack appcontainer logs web`.

## 4. Cấp floating IP cho web (chỉ web, không cấp cho db)

```bash
openstack floating ip create public
openstack appcontainer add floating ip web <FLOATING_IP>
```

## 5. Kiểm tra

```bash
curl http://<FLOATING_IP>/health
```

Kết quả `{"db":"ok","web":"ok"}` nghĩa là web đã nối được database.
Mở `http://<FLOATING_IP>` trên trình duyệt, gửi vài lời nhắn.

Xem dữ liệu ngay trong database:

```bash
openstack appcontainer exec db psql -U app -d guestbook -c "select name, body from messages;"
```

## 6. Thử nghiệm để hiểu về dữ liệu

1. **Khởi động lại web:** `openstack appcontainer restart web`. Lời nhắn vẫn còn vì dữ liệu nằm ở database.
2. **Xóa và tạo lại web** (bước 3). Lời nhắn vẫn còn, vì web không chứa dữ liệu.
3. **Xóa container db** rồi tạo lại (bước 2). Lời nhắn **mất hết**, vì dữ liệu nằm trong hệ thống file của container.
   Muốn giữ dữ liệu lâu dài cần gắn volume (Cinder) vào `/var/lib/postgresql/data`.

## 7. Khi có lỗi

| Hiện tượng | Kiểm tra |
|---|---|
| `/health` trả `"db":"error"` | Log của `web`; `db` đã `Running` chưa; mật khẩu hai bên có khớp không |
| Log web báo `Đang chờ database...` | Security group `db-sg` đã có luật cổng 5432 từ 192.168.50.0/24 chưa |
| Không mở được trang | `web-sg` mở cổng 80 chưa; floating IP đã gắn vào `web` chưa |
| Web thoát ngay | Log báo lỗi `git clone` hay `pip`: sai đường dẫn repo, hoặc không ra internet |

## 8. Dọn dẹp

```bash
openstack appcontainer delete --force web db
openstack floating ip delete <FLOATING_IP>
```

Lưu ý: mật khẩu đặt trong biến môi trường chỉ phù hợp cho học tập. Hệ thống thật nên dùng cơ chế quản lý bí mật riêng.
