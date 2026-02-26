# Base.vn Work Analysis System (app_v2_all)

Hệ thống tự động thu thập dữ liệu, phân tích hiệu suất và gửi báo cáo tổng hợp cho nhân viên sử dụng hệ sinh thái Base.vn.

## 🚀 Tính năng chính

- **Tích hợp đa nền tảng Base.vn**:
  - **Base WeWork**: Theo dõi tiến độ công việc, deadline, tỷ lệ hoàn thành.
  - **Base Goal**: Phân tích OKR, mục tiêu cá nhân và sự thay đổi theo tuần.
  - **Base Checkin**: Đánh giá chấm công, thói quen đi làm (Early Bird/Punctual/Late).
  - **Base Inside**: Phân tích mức độ tương tác, vai trò trong cộng đồng nội bộ.
  - **Base Workflow**: Quản lý quy trình và nhiệm vụ.
- **AI Analysis (Ollama)**: Sử dụng mô hình `gemini-3-flash-preview` để đưa ra nhận xét (Insights) và gợi ý hành động (Recommendations) cá nhân hóa.
- **Email Report HTML**: Gởi báo cáo định kỳ qua email với giao diện HTML hiện đại, trực quan.

## 🛠️ Yêu cầu hệ thống

- **Python**: 3.8+
- **Libaries**: `requests`, `pandas`, `pydantic`, `python-dotenv`, `ollama`
- **Ollama**: Cần cài đặt và chạy Ollama local hoặc trỏ tới server Ollama.

## ⚙️ Cấu hình (.env)

Tạo file `.env` tại thư mục gốc và điền các thông tin sau:

```env
# Base.vn API Tokens
WEWORK_ACCESS_TOKEN=your_wework_token
ACCOUNT_ACCESS_TOKEN=your_account_token
GOAL_ACCESS_TOKEN=your_goal_token

# Email Configuration (Gmail SMTP)
EMAIL_GUI=your_email@gmail.com
MAT_KHAU=your_app_password

# AI Configuration (Ollama)
OLLAMA_API_KEY=your_ollama_key
# Backup keys (optional)
OLLAMA_API_KEY_BACKUP_1=backup_key_1
OLLAMA_API_KEY_BACKUP_2=backup_key_2
```

## 📦 Cài đặt

1.  Clone repo về máy.
2.  Cài đặt các thư viện cần thiết:
    ```bash
    pip install -r requirements.txt
    ```
    _(Nếu chưa có `requirements.txt`, cài thủ công: `pip install requests pandas pydantic python-dotenv ollama pytz`)_

## ▶️ Sử dụng

Chạy script chính để gửi báo cáo cho một hoặc toàn bộ nhân viên:

```bash
python app_v2_all.py
```

**Lưu ý**: Script mặc định sẽ quét danh sách nhân viên từ nhóm quy định (ví dụ: `nvvanphong`) và gửi email báo cáo nếu có dữ liệu hoạt động trong 1 tháng gần nhất.

## 📂 Cấu trúc dự án

- `app_v2_all.py`: Script chính (Main orchestrator).
- `checkin_timeoff.py`: Module xử lý dữ liệu chấm công.
- `wework.py`: Module xử lý dữ liệu công việc.
- `goal.py`: Module xử lý dữ liệu OKR.
- `inside.py`: Module xử lý dữ liệu truyền thông nội bộ.
- `workflow.py`: Module xử lý quy trình.
- `app_v2_logic.py`: Logic xử lý và tổng hợp dữ liệu bổ sung.

---

**Author**: [Your Name/Team]
**Phiên bản**: 2.0
