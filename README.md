# IncidentLens · RAV-18

IncidentLens hỗ trợ xem xét sự cố lái xe bằng dữ liệu demo deterministic, hoặc tùy chọn tải clip được phép lên Supabase Storage private và phân tích video bằng Gemini. Các finding thật chỉ xuất hiện khi đã gọi model và vượt qua kiểm tra grounding; mọi finding vẫn chờ reviewer approve/reject.

## Stack và yêu cầu

- Python 3.11+; FastAPI, Pydantic Settings, SQLAlchemy 2, psycopg 3, Uvicorn, OpenCV, Supabase Python, Google GenAI SDK.
- Node.js 20+; React 18, TypeScript strict, Vite.
- Supabase PostgreSQL là database ngoài; không có database local trong Docker Compose.
- Docker Compose tùy chọn.

## Cấu hình Supabase

1. Tạo project Supabase và lấy PostgreSQL connection string. Dùng URL dạng `postgresql+psycopg://...`; dùng session pooler khi môi trường mạng không truy cập được host direct. Mã nguồn chỉ cần `DATABASE_URL` để kết nối PostgreSQL.
2. Tạo `backend/.env` từ `backend/.env.example`, điền connection string, `SUPABASE_URL` và backend-only `SUPABASE_SERVICE_ROLE_KEY`. Để bật video analysis, điền `GOOGLE_API_KEY`; mặc định model là `gemini-3.8-flash` (có thể đổi qua `GEMINI_MODEL`). Không cần key Gemini để dùng synthetic path.
3. Trong Supabase Storage tạo bucket có tên `SUPABASE_MEDIA_BUCKET` (mặc định `incident-media`) ở chế độ **private**. Service-role key chỉ nằm trong backend. Clip được cấp signed URL 5 phút khi người dùng mở xem.
4. Không commit `.env`, không đưa service-role key/API key vào frontend, và không bật public bucket cho dữ liệu media thực. Dùng clip mà người upload có quyền sử dụng.

Upload nhận MP4, MOV, WebM; mặc định tối đa 100 MB và 300 giây (`MAX_VIDEO_BYTES`, `MAX_VIDEO_DURATION_SECONDS`). Backend kiểm tra MIME, container signature và khả năng decode qua OpenCV trước khi ghi object. Model/API timeout mặc định 120 giây (`VIDEO_ANALYSIS_TIMEOUT_SECONDS`). Google Files API object và file tạm bị dọn sau xử lý; clip trong Supabase được giữ lại.

Schema `public` được tạo cho demo bởi `Base.metadata.create_all()` khi chạy seed lần đầu. Đây chỉ là cách dựng schema MVP, chưa thay thế migration quản lý phiên bản. Cấu hình DB Supabase bằng role có quyền tạo bảng. Các bảng: `incidents`, `log_events`, `evidence`, `analysis_runs`, `findings`, `review_actions`.

## Chạy local

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env  # sau đó điền DATABASE_URL
python -m scripts.seed_demo
uvicorn app.main:app --reload
```

Trong terminal khác:

```bash
cd frontend
npm install
npm run dev
```

Mở `http://localhost:5173`; API ở `http://localhost:8000`, tài liệu OpenAPI ở `/docs`. Frontend Vite proxy `/api` tới API local. Health `/api/health` chỉ xác nhận tiến trình API đang phản hồi, **không xác nhận database sẵn sàng**.

## Chạy bằng Docker Compose

Compose có thể khởi động frontend và API mà không cần `backend/.env` hoặc thông tin Supabase:

```bash
docker compose up --build
```

Kiểm tra nhanh trong terminal khác:

```bash
curl -i http://localhost:8000/api/health
curl -i http://localhost:5173
```

`/api/health` chỉ xác nhận process API đang phản hồi; nó không kiểm tra kết nối database. Trang frontend cần trả HTML tại cổng `5173`. Khi chưa cấu hình database, các API incident có thể trả `503`/`500`; điều đó không có nghĩa là container không khởi động được.

Để dùng các API incident với dữ liệu demo, cấu hình Supabase và điền `backend/.env` như phần [Cấu hình Supabase](#cấu-hình-supabase), sau đó chạy lệnh seed bên dưới.

Seed dữ liệu một lần trong container API:

```bash
docker compose exec api python -m scripts.seed_demo
```

## Demo workflow và API

- `GET /api/incidents?status=&severity=` — danh sách và bộ lọc.
- `GET /api/incidents/{incident_id}` — chi tiết, events theo UTC, evidence, runs và review.
- `POST /api/incidents/{incident_id}/media` — multipart field `file`; kiểm tra clip rồi lưu trong private bucket và metadata evidence.
- `GET /api/incidents/{incident_id}/media/{evidence_id}/url` — signed URL tạm thời để xem clip.
- `POST /api/incidents/{incident_id}/analyze` — không có clip: giữ workflow deterministic hiện có. Có clip và cấu hình Gemini: gọi model thật; clip nhưng thiếu key/storage hoặc provider lỗi sẽ có warning/run failed, không tạo synthetic video finding.
- `POST /api/incidents/{incident_id}/actions/{run_id}/review` — body ví dụ `{"decision":"approve","actor_role":"reviewer","actor_name":"Reviewer demo","note":"Reviewed"}`.
- `GET /api/health` — tình trạng process API.

Incident đầu và thứ ba có log/evidence mẫu; incident thứ hai thiếu evidence để thể hiện trường hợp chưa đủ dữ liệu. Synthetic finding chỉ là tương quan heuristic, không xác nhận nguyên nhân. Với clip thật, Gemini chỉ được yêu cầu mô tả quan sát và trích dẫn evidence ID; backend loại citation ngoài incident, timestamp ngoài thời lượng clip, và claim nhân quả. Một run có findings luôn chờ reviewer.

Engineer/Reviewer là vai trò trình diễn ở UI/request, không phải phân quyền an toàn. Không dùng môi trường demo này với dữ liệu xe/người thật. Review lưu actor, quyết định, ghi chú và thời gian; một run chỉ được review một lần.

## Benchmark offline

Từ thư mục `backend`, chạy benchmark deterministic trên SQLite in-memory:

```bash
python -m scripts.evaluate_demo
```

Tuỳ chọn: `--cases PATH` chọn dataset khác, `--warmup N` đặt số lần chạy bỏ qua để khởi động (mặc định 1), `--repetitions N` đặt số lần đo mỗi ca (mặc định 5, tối thiểu 1), và `--json PATH` ghi bản JSON giống stdout ra file. Benchmark không đọc `.env`, không kết nối Supabase, không gọi mạng hoặc model.

Dataset nhỏ trong `backend/evaluation/cases.json` gồm các ca synthetic cho evidence đúng ngưỡng 15 giây, trước ngưỡng, không có evidence, ngoài cửa sổ và loại evidence không được hỗ trợ. Các metric gồm classification theo ca (accuracy/precision/recall/F1), evidence grounding micro precision/recall/F1, độ lệch timestamp MAE và tỷ lệ trong 1 giây, completeness của các bước workflow, cùng median/p95 latency. Timestamp chỉ được tính khi cả expected và predicted finding có timestamp; mẫu số bằng 0 được thể hiện là `null`.

Kết quả benchmark chỉ đo pipeline deterministic với metadata/log synthetic. Nó không phản ánh chất lượng VLM hay khả năng hiểu video thật. Latency phụ thuộc máy và môi trường chạy; benchmark không đặt ngưỡng pass/fail hay tiêu chí nghiệm thu.

## Giới hạn và xử lý lỗi

- API trả 503/500 khi database không cấu hình/không truy cập được; lỗi không bao gồm URL/key hay stack trace.
- Dữ liệu seed idempotent theo UUID cố định, chỉ thêm record/con khi chưa có; để reset demo hãy xóa các incident `SIMULATED` trong database theo quy trình quản trị Supabase của bạn.
- Authentication/authorization người dùng và RLS cho các bảng ứng dụng chưa triển khai; demo API review không phải kiểm soát truy cập sản xuất. Supabase bucket phải private, credentials backend-only. Video có thể chứa dữ liệu nhạy cảm; chỉ tải nội dung có quyền xử lý và xóa object theo chính sách lưu trữ của môi trường.
- Google model/API có thể có quota, chi phí và vùng lưu trữ/xử lý riêng; kiểm tra điều khoản hiện hành trước khi gửi video nhạy cảm. Lỗi provider được lưu thành run failed mà không lưu findings video. Không có parser rosbag hoặc deploy cloud production.
