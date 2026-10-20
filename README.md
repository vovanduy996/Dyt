# Aster AI Desktop

Ứng dụng Windows viết bằng Python/Tkinter, kết nối Cloud API theo các endpoint `POST /v1/auth/activate`, `POST /v1/chat/completions` và (tùy chọn) `GET /v1/models`.

## Tốc độ trả lời

Giao diện đã dùng streaming để hiện chữ ngay khi API gửi token đầu tiên. Ứng dụng chỉ gửi tối đa 16 tin nhắn gần nhất hoặc 24.000 ký tự làm ngữ cảnh; toàn bộ lịch sử vẫn còn trên giao diện. Tốc độ tạo câu trả lời còn phụ thuộc vào model/backend đang được chọn. App không tự ép một tham số “reasoning” không được API công bố hỗ trợ.

## Lịch sử và tính riêng tư

- Lịch sử tự lưu sau khi gửi/nhận tin và khi đóng app, tại `%APPDATA%\AsterAI\chats.dat`.
- File được mã hóa bằng Windows DPAPI, nên chỉ cùng tài khoản Windows trên cùng máy mới đọc được. Không thể chỉ chép `chats.dat` sang máy khác để mang lịch sử theo.
- Phiên đăng nhập nằm trong `%APPDATA%\AsterAI\config.json` và cũng được DPAPI bảo vệ. Máy khác cần kích hoạt lại API key.

## Build bản độc lập

Trên máy build, mở PowerShell trong thư mục dự án và chạy:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\build-standalone.ps1
```

Script tạo icon màu `aster.ico`, cài PyInstaller nếu chưa có và sinh file `dist\Aster-AI-Desktop.exe`. Đây là một file `.exe` độc lập, không cần cài Python trên máy đích. Máy đích vẫn cần Internet và Cloud API hoạt động; SmartScreen có thể cảnh báo cho tới khi ứng dụng được code-sign.

Không dùng `build-installer.sed` cho bản phát hành: đó là gói IExpress cũ, phụ thuộc Python 3.13 và không gắn icon ứng dụng thật.
