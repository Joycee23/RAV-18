# Kế hoạch triển khai RAV-18 – IncidentLens

## 1. Mục tiêu sản phẩm

Xây dựng web app hỗ trợ kỹ sư phân tích sự cố/disengagement của xe tự hành từ video và log đã ghi. Agent tạo timeline và báo cáo nháp, mỗi nhận định phải trỏ về bằng chứng có timestamp; kỹ sư xem lại và duyệt trước khi đưa báo cáo vào hàng đợi. Sản phẩm chỉ phân tích dữ liệu lưu sẵn, không điều khiển phương tiện.

**Giá trị cho hồ sơ cá nhân:** kết nối kinh nghiệm nhận diện biển báo/ADAS với AI đa phương thức, robotics, fullstack và đánh giá hệ thống AI.

## 2. Ranh giới MVP và cách trình bày trung thực

- MVP chạy được với dữ liệu tổng hợp và video/khung hình mẫu đã ẩn danh; log có timestamp, video có thể bắt đầu dưới dạng keyframe/clip đã chuẩn bị.
- Nếu chưa có VLM đọc video thực, giao diện và báo cáo phải ghi rõ “keyframe mô phỏng” hoặc “metadata tổng hợp”; không tuyên bố agent đã hiểu video.
- Tách adapter đọc video/VLM khỏi logic phân tích để có thể thay nguồn mô phỏng bằng video công khai/đã ẩn danh và mô hình phù hợp sau này.
- Không dùng dữ liệu nội bộ VinRobotics/Vingroup hay dữ liệu cá nhân/nhạy cảm nếu chưa được phép. Không nhận diện danh tính; làm mờ mặt/biển số khi dùng video.
- Phân biệt tương quan thời gian với nguyên nhân. Kết luận nguyên nhân chỉ là giả thuyết cần kỹ sư kiểm chứng.

## 3. Người dùng và luồng chính

**Vai trò:** Engineer (tạo/chạy phân tích, xem bằng chứng) và Reviewer/Admin (duyệt hoặc từ chối báo cáo). Bản demo có thể đăng nhập bằng tài khoản giả lập.

1. Engineer mở danh sách sự cố, lọc theo ngày/mức độ/trạng thái.
2. Mở sự cố, xem metadata, clip/keyframe và sự kiện log trên cùng timeline.
3. Chạy phân tích. Backend ghi trạng thái từng bước: nạp dữ liệu → trích sự kiện → đồng bộ timeline → tạo báo cáo nháp.
4. Mỗi finding hiển thị mức tin cậy, giới hạn và evidence link; bấm evidence đưa tới timestamp liên quan.
5. Reviewer chỉnh/ghi chú nếu cần, rồi approve/reject. Chỉ sau approve mới đánh dấu báo cáo đã duyệt.
6. Trường hợp thiếu dữ liệu hoặc không đủ bằng chứng, agent báo chưa kết luận và nêu rõ phần cần người kiểm tra.

## 4. Kiến trúc và stack đề xuất

- **Frontend:** React + TypeScript + Vite; màn hình dashboard, incident detail, player/timeline, evidence cards, workflow trace và review panel.
- **Backend:** Python + FastAPI + Pydantic; API incidents, analyze, review, health. Phân tầng `api → services/agent → data adapters`.
- **Agent pipeline:** các tool có input/output schema rõ: `load_incident`, `read_drive_logs`, `sample_video`, `align_timeline`, `draft_report`. LLM/VLM là provider adapter; rule-based/synthetic mode luôn có để demo ổn định.
- **Dữ liệu MVP:** JSON/JSONL có schema cho incident, log event, frame/clip, finding, evidence và review. Chuyển sang SQLite nếu cần lưu trạng thái giữa lần chạy; chưa cần hạ tầng phức tạp.
- **Quan sát:** log theo `run_id`, thời gian xử lý từng bước, lỗi và ước tính token/chi phí khi có model API.
- **Triển khai:** Docker Compose cho web + API; README có lệnh chạy local, biến môi trường và tài khoản demo. Không commit API key.

## 5. Phân vai và quy trình làm việc: 4 subagent + chủ dự án

| Vai trò | Trách nhiệm | Giới hạn và bàn giao |
|---|---|---|
| Planner | Đọc codebase liên quan, chuyển yêu cầu tính năng thành kế hoạch cụ thể | Không viết code. Ghi `.bangiao/ke-hoach.md`, gồm file cần tạo/sửa, interface, edge cases và quy ước nguồn. Câu hỏi chưa rõ phải đặt đầu file; không tự đoán. |
| Coder | Triển khai đúng kế hoạch đã chốt | Chỉ bắt đầu khi kế hoạch không có câu hỏi bỏ ngỏ. Không thêm phạm vi. Ghi `.bangiao/thay-doi.md` nêu file đã sửa, mục đích và điểm Tester cần soi. |
| Tester | Viết và chạy kiểm thử hành vi theo kế hoạch/thay đổi | Chỉ tạo/sửa file test, không sửa code sản phẩm. Ghi `.bangiao/ket-qua-test.md`; nếu test lỗi thì dừng dây chuyền, không tự vá. |
| Reviewer | Đọc kế hoạch, thay đổi, kết quả test và diff; đánh giá đúng/sai, chất lượng test, rủi ro | Chỉ đọc code sản phẩm; ghi `.bangiao/danh-gia.md` với phán quyết `CHOT`, `CAN SUA` hoặc `CHAN` và vị trí cần sửa nếu có. |
| Chủ dự án (bạn) | Đưa yêu cầu, trả lời câu hỏi, đọc kết quả và quyết định | Bạn tự quyết định việc tích hợp/gộp nhánh. Agent không gộp nhánh, push hoặc tạo PR. |

**Thứ tự bắt buộc:** yêu cầu → Planner → Coder → Tester → Reviewer → quyết định của bạn. Không nhảy chặng. Trước mỗi lần chạy, kiểm tra nhánh hiện tại; nếu là `main`/`master`, dừng. Làm việc trên nhánh riêng và không gộp/push/PR.

**Bàn giao mỗi chặng:** `.bangiao/ke-hoach.md` → `.bangiao/thay-doi.md` → `.bangiao/ket-qua-test.md` → `.bangiao/danh-gia.md`. `.bangiao/` được tạo khi chạy dây chuyền lần đầu. Chỉ xóa các bản bàn giao cũ khi bắt đầu lần chạy mới để tránh nhầm kết quả.

## 6. Các giai đoạn triển khai

### Giai đoạn 0 – Khởi tạo và chốt phạm vi (0.5–1 ngày)

- Planner cùng chủ dự án chốt người dùng, pain point, dữ liệu đầu vào/đầu ra và phạm vi demo; nếu còn mơ hồ, ghi thành câu hỏi và dừng để chủ dự án trả lời.
- Chọn 2–3 tình huống sự cố mô phỏng, ví dụ phanh gấp gần vạch sang đường, suy giảm lane confidence khi mưa, và object perception bất ổn.
- Chốt MVP: log + keyframe/clip mẫu; phân tích có bằng chứng; báo cáo chờ duyệt.
- Planner ghi kế hoạch vào `.bangiao/ke-hoach.md`; Coder chỉ triển khai sau khi kế hoạch không còn câu hỏi bỏ ngỏ.

**Cổng hoàn thành:** mọi thành viên hiểu cùng một luồng demo và biết rõ phần nào là mô phỏng.

### Giai đoạn 1 – Thiết kế dữ liệu và API (1–2 ngày)

- Planner ghi acceptance criteria cho từng luồng trong kế hoạch tính năng.
- Dev 3 định nghĩa schema và tạo dữ liệu synthetic có ground truth: event, thời điểm, loại sự cố, expected evidence và nhãn.
- Dev 1 chốt API: `GET /api/incidents`, `GET /api/incidents/{id}`, `POST /api/incidents/{id}/analyze`, `POST /api/incidents/{id}/actions/{action_id}/review`.
- Dev 2 dựng wireframe và skeleton UI theo response schema.

**Cổng hoàn thành:** API contract ổn định, dữ liệu mẫu có thể nạp bằng một lệnh, mỗi finding truy ngược về evidence ID/timestamp.

### Giai đoạn 2 – Vertical slice đầu tiên (2–3 ngày)

- Backend hoàn tất list/detail incident và phân tích giả lập deterministic.
- Frontend hiển thị một incident từ API, timeline log/keyframe và finding có evidence link.
- Reviewer approve/reject được một báo cáo; trạng thái hiển thị đồng nhất sau refresh.
- Tạo một kịch bản lỗi: incident thiếu log hoặc evidence không khớp, UI báo rõ và cho phép thử lại.

**Cổng hoàn thành:** demo đầu-cuối một sự cố mà không cần gọi model bên ngoài.

### Giai đoạn 3 – Agent và phân tích đa phương thức (3–5 ngày)

- Thay từng bước giả lập bằng tool adapter độc lập: đọc log, đọc metadata video/keyframe, căn chỉnh timestamp, lập timeline và tạo draft.
- Nếu có model phù hợp: thêm VLM tóm tắt khung hình/đoạn clip đã ẩn danh; bắt buộc output có evidence references. Nếu không có, giữ chế độ mô phỏng minh thị.
- Structured output có validation; thông tin không hỗ trợ bởi dữ liệu phải được đánh dấu “chưa xác minh”.
- Thêm retry/timeout, model unavailable fallback, run trace, trạng thái processing/completed/failed/awaiting review.

**Cổng hoàn thành:** pipeline giải thích được từng tool, không tạo finding không có nguồn, có đường chạy fallback.

### Giai đoạn 4 – Hoàn thiện sản phẩm và đánh giá (2–3 ngày)

- Hoàn thiện lọc/tìm sự cố, timeline, evidence, reviewer notes và audit trail.
- Dev 3 chuẩn bị benchmark nhỏ có nhãn tham chiếu; đo đúng loại sự cố, evidence precision/recall, timestamp tolerance, completeness và latency/cost.
- Reviewer đối chiếu kết quả với acceptance criteria và demo script; chủ dự án xác nhận giới hạn sản phẩm.
- Phân tích failure cases: log sai timestamp, frame thiếu, model nói quá bằng chứng, mâu thuẫn giữa video/log, model/API timeout.

**Cổng hoàn thành:** có bảng metric trên tập mẫu, có giới hạn và failure cases được trình bày.

### Giai đoạn 5 – Deploy, tài liệu và bàn giao (1–2 ngày)

- Docker Compose chạy frontend + backend; triển khai lên môi trường demo online.
- README: kiến trúc, setup, cấu hình provider, dữ liệu demo, API, giới hạn và xử lý lỗi.
- Hoàn thiện tài khoản demo cho 2 vai trò, video demo ngắn, sơ đồ workflow, benchmark và quyết định kiến trúc.
- Diễn tập demo theo thứ tự: chọn incident → analyze → mở evidence tại timestamp → review → approve/reject → xem failure case.

**Cổng hoàn thành:** người khác clone repo, cấu hình theo README, chạy được demo và hiểu rõ kết quả AI có thể/không thể khẳng định.

**Ước lượng tổng:** khoảng 9–16 ngày làm việc cho MVP nhóm 4 người, tùy việc có video/VLM thật và môi trường deploy hay không.

## 7. Tiêu chí nghiệm thu MVP

- App online hoặc chạy bằng Docker; có hai vai trò Engineer và Reviewer.
- Có tối thiểu 3 incident mẫu và 1 tình huống lỗi có chủ đích.
- Agent workflow có trạng thái, tool trace và xử lý timeout/lỗi.
- Timeline sắp xếp theo thời gian; từng finding có evidence ID/timestamp mở được nguồn.
- Không tự publish báo cáo; reviewer approve/reject và có audit record.
- Có benchmark trên dữ liệu mẫu: classification, evidence grounding, timestamp accuracy, latency và chi phí khi dùng model.
- UI/tài liệu phân biệt rõ phân tích video thật với keyframe/metadata mô phỏng; không nhận diện cá nhân.

## 8. Rủi ro cần quản lý

- **Thiếu video hoặc dữ liệu rosbag:** dùng dữ liệu tổng hợp; thiết kế parser/provider adapter để thay thế khi được cấp dữ liệu.
- **VLM bịa hoặc suy diễn nguyên nhân:** yêu cầu evidence references, dùng ngôn ngữ giả thuyết, reviewer bắt buộc duyệt.
- **Khối lượng vượt thời gian:** ưu tiên một luồng vertical slice; để voice, multi-agent phức tạp, nhiều định dạng log và phân tích nguyên nhân tự động ra ngoài MVP.
- **Khó tái lập demo do API model:** giữ deterministic fallback, ghi cấu hình model và chi phí.
- **Quyền riêng tư:** chỉ dùng video đã được phép, làm mờ danh tính và xóa metadata không cần thiết.

## 9. Trạng thái repo hiện tại và bước tiếp theo

Thư mục `/Users/jerry/AI-Vin/RAV-18` hiện có cấu hình bốn vai trò tại `.codex/agents/` và lệnh dây chuyền tại `.codex/commands/ship.md`; chưa có mã nguồn ứng dụng. Bản demo backend và dữ liệu synthetic trước đó nằm ở workspace khác, chưa được chuyển vào thư mục dự án này. Khi bắt đầu tính năng đầu tiên, chạy `ship` trên nhánh làm việc; Planner tạo `.bangiao/ke-hoach.md`, rồi lần lượt bàn giao qua Coder, Tester và Reviewer. Phạm vi MVP vẫn bắt đầu bằng vertical slice dùng dữ liệu mô phỏng; VLM/video thật chỉ thêm sau khi được lên kế hoạch và có nguồn dữ liệu phù hợp.
