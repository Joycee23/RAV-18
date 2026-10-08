# Kế hoạch sửa hai lỗi Reviewer đã nêu

## CÂU HỎI CÒN BỎ NGỎ

Không có.

## Phạm vi

Chỉ sửa hai lỗi: timestamp `incident.occurred_at` dạng naive do SQLite trả về bị diễn giải theo timezone máy khi dùng làm `recorded_at` mặc định; và chuẩn hóa tiếng Việt bỏ sót chữ `đ/Đ`, khiến mẫu nhân quả “dẫn đến” không bị phát hiện. Không thay đổi hành vi khác.

## File cần sửa

1. `backend/app/routers/incidents.py`
   - Thêm helper nội bộ `_normalize_timestamp_utc(value: datetime) -> datetime`.
   - Nếu `value.tzinfo is None` hoặc `value.utcoffset() is None`, gắn UTC bằng `replace(tzinfo=UTC)`; không gọi `astimezone()` trên datetime naive.
   - Nếu datetime đã có offset, đổi sang UTC bằng `astimezone(UTC)`.
   - Trong `upload_media(...)`, áp dụng helper cho `recorded_at or incident.occurred_at` trước khi lưu evidence và metadata. Giữ nguyên việc trả HTTP 422 khi `recorded_at` người dùng gửi vào là naive.

2. `backend/app/services/video_analysis.py`
   - Sửa `contains_causal_language(text: str) -> bool`: sau `casefold()`, ánh xạ `đ` thành `d` trước khi bỏ dấu bằng NFKD; giữ nguyên các mẫu và hành vi phát hiện hiện có.

3. `backend/tests/test_media_upload.py`
   - Thêm hồi quy đường upload không truyền `recorded_at`, với `Incident.occurred_at` naive như SQLite trả về. Chứng minh timestamp mặc định luôn là UTC, độc lập timezone host (đổi `TZ` và gọi `time.tzset()` nếu có; khôi phục TZ và timezone process sau test).
   - Giữ/đảm bảo kiểm tra offset có sẵn: input `2026-10-08T20:30:00+05:30` được lưu thành `2026-10-08T15:00:00+00:00`.
   - Bám cấu trúc fixture `client`, `FakeStorage`, `_install_storage` và cách assert response/database trong chính file này.

4. `backend/tests/test_video_analysis.py`
   - Bổ sung regression cho `Tình huống này dẫn đến phanh gấp.` và câu bắt đầu bằng `Đ` để bao phủ cả `đ` lẫn `Đ`; analyzer phải loại finding nhân quả như các case hiện có.
   - Theo mẫu `@pytest.mark.parametrize` và `FakeClient`/test `test_causal_language_is_rejected_even_when_claim_type_is_observation` trong file này.

## Trường hợp biên bắt buộc

- Timestamp naive lấy từ ORM: được hiểu là UTC, không phụ thuộc timezone host.
- Timestamp aware có offset khác UTC: chuyển đúng instant sang UTC.
- `recorded_at` naive do request gửi: tiếp tục trả 422, không tải/lưu video.
- Nhận diện nhân quả phải không phân biệt hoa thường và bắt được cả `đ` lẫn `Đ`; các mẫu nhân quả tiếng Anh và tiếng Việt đang có phải tiếp tục hoạt động.

## Quy ước cần bám theo

- Timestamp/API upload và fixture: `backend/app/routers/incidents.py`, `backend/tests/test_media_upload.py`.
- UTC dùng `datetime.UTC`; style helper/module: `backend/app/routers/incidents.py`.
- Chuẩn hóa và mẫu kiểm thử causal: `backend/app/services/video_analysis.py`, `backend/tests/test_video_analysis.py`.
- Chạy test bằng pytest theo cấu hình `backend/pyproject.toml`.
