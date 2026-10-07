# Báo cáo Day 6: [ĐIỀN tên đề tài ngắn]

> Thay **mọi** ô có chữ ĐIỀN nằm trong ngoặc vuông bằng nội dung của bạn, xoá luôn cả dấu ngoặc vuông. Lệnh `python tools/check_submission.py` sẽ báo FAIL nếu còn sót bất kỳ chỗ nào.

- **Họ tên:** Đoàn Anh Quân
- **MSSV:** 2A202602803
- **Lớp:** AI20K-T4
- **Link repo:** https://github.com/DAQuan-VinAI/DoanAnhQuan-2A202602803-Track4-Day21
- **Topic:** A — LiDAR - camera projection QA
- **Dataset:**  data/synthetic, data/kitti_mini
- **Các frame đã dùng:**  thí nghiệm quét yaw dùng cả 20 frame của `data/kitti_mini`; ảnh demo dùng `data/synthetic` frame 000000 và `data/kitti_mini` frame 000008, 000009, 000011

> Hãy viết ngắn: mỗi mục từ 3 đến 8 dòng, ưu tiên số liệu và hình ảnh.

## 1. Claim

Một câu khẳng định kỹ thuật có thể kiểm chứng. Ví dụ: *"Lệch yaw 1° làm 12% điểm LiDAR rơi ra khỏi vật thể ở 30 m, phát hiện được bằng edge-alignment score với ngưỡng X."*

Lệch yaw 1° làm điểm chiếu dịch khoảng 13–15 px, gần như không phụ thuộc khoảng cách, trong khi 2D box hẹp dần khi xe ở xa (rộng trung bình 268 px ở dưới 10 m, 42 px ở từ 30 m). Vì vậy tỉ lệ điểm LiDAR rơi ra ngoài 2D box tăng theo khoảng cách: dưới 5% với xe ở gần hơn 10 m, nhưng 26–31% với xe ở 30 m trở lên.


## 2. Evidence

Bảng hoặc plot số liệu, kèm ảnh/video demo. Ghi rõ đường dẫn file trong `results/`.

**Thí nghiệm chính (CP3): quét lệch yaw từ −3° đến +3°, 9 mức.** Số liệu: `results/yaw_perturb_sweep.csv` (mỗi dòng một mức yaw) và `results/yaw_perturb_per_object.csv` (từng object). Biểu đồ: `results/figures/yaw_perturb_sweep.png`.

- **Cách đo:** với mỗi xe, lấy các điểm LiDAR nằm trong 3D box của label (dùng calib gốc), chiếu lại bằng calib đã lệch yaw, rồi đếm tỉ lệ điểm không rơi vào 2D box của label.
- **Cấu hình giữ nguyên ở mọi mức:** 20 frame `data/kitti_mini`, class Car + Van + Truck, chỉ lấy object có từ 20 điểm LiDAR, occluded ≤ 1, truncated ≤ 0.5. Còn lại 47 xe: 7 xe dưới 10 m, 16 xe ở 10–20 m, 11 xe ở 20–30 m, 13 xe từ 30 m.
- **Seed:** thí nghiệm không có bước ngẫu nhiên nào; chạy lại hai lần cho hai file CSV giống hệt nhau (đã so md5).

| Lệch yaw | % điểm trong FOV | Dịch pixel trung bình (px) | % ngoài box, <10 m | % ngoài box, 10–20 m | % ngoài box, 20–30 m | % ngoài box, ≥30 m |
|---|---|---|---|---|---|---|
| -3.0° | 15.73 | 41.6 | 12.1 | 31.3 | 57.6 | 91.8 |
| -2.0° | 15.74 | 27.7 | 6.8 | 17.6 | 33.6 | 67.2 |
| -1.0° | 15.74 | 13.9 | 2.4 | 5.5 | 13.5 | 26.3 |
| -0.5° | 15.75 | 6.9 | 1.8 | 0.8 | 4.6 | 10.5 |
| 0.0° | 15.75 | 0.0 | 2.0 | 0.0 | 0.0 | 0.0 |
| +0.5° | 15.76 | 6.9 | 2.6 | 0.4 | 9.4 | 10.7 |
| +1.0° | 15.76 | 13.9 | 4.0 | 3.2 | 22.6 | 30.8 |
| +2.0° | 15.77 | 27.7 | 8.3 | 12.5 | 45.4 | 72.0 |
| +3.0° | 15.77 | 41.6 | 12.4 | 25.5 | 66.1 | 94.6 |

"% ngoài box" là trung bình theo từng xe, không theo từng điểm, để vài xe ở gần có hàng nghìn điểm không lấn át các xe ở xa.

![yaw sweep](../results/figures/yaw_perturb_sweep.png)

**Xu hướng:** độ dịch pixel tăng tuyến tính theo yaw (khoảng 14 px mỗi độ), còn % điểm trong FOV gần như không đổi (15.73–15.77%) nên không dùng được để phát hiện lệch yaw. % ngoài box tăng theo cả yaw lẫn khoảng cách: ở ±1°, xe dưới 10 m chỉ mất 2–4% điểm, xe từ 30 m mất 26–31%; ở ±3°, xe từ 30 m mất 92–95%. Ở 0° nhóm dưới 10 m vẫn có 2.0% ngoài box, do một xe bị cắt ở rìa ảnh (frame 000016, truncated 0.5, 14.1% ngoài box).

**Demo CP2 — điểm LiDAR chiếu lên camera, có vẽ 2D box của label (chưa perturb: roll/pitch/yaw = 0°, t = 0):**

`data/synthetic`, frame `000000` — `results/figures/overlay_000000_r0.0_p0.0_y0.0_t0.0_0.0_0.0.png`

![demo synthetic 000000](../results/figures/overlay_000000_r0.0_p0.0_y0.0_t0.0_0.0_0.0.png)

`data/kitti_mini`, frame `000008` — `results/figures/overlay_000008_r0.0_p0.0_y0.0_t0.0_0.0_0.0.png`

![demo kitti 000008](../results/figures/overlay_000008_r0.0_p0.0_y0.0_t0.0_0.0_0.0.png)

`data/kitti_mini`, frame `000009` — `results/figures/overlay_000009_r0.0_p0.0_y0.0_t0.0_0.0_0.0.png`

![demo kitti 000009](../results/figures/overlay_000009_r0.0_p0.0_y0.0_t0.0_0.0_0.0.png)

`data/kitti_mini`, frame `000011` — `results/figures/overlay_000011_r0.0_p0.0_y0.0_t0.0_0.0_0.0.png`

![demo kitti 000011](../results/figures/overlay_000011_r0.0_p0.0_y0.0_t0.0_0.0_0.0.png)

## 3. Failure case

Nêu khi nào hệ thống hoặc phương pháp fail, vì sao fail, và liên hệ tới lớp nào trong 6 lớp debug: I/O, Geometry, Time, Preprocess, Model, Metric.

**Failure 1: metric bỏ sót lệch yaw trên xe ở gần** — `results/figures/fail_01_yaw1deg_near_car_missed.png`

![failure 1](../results/figures/fail_01_yaw1deg_near_car_missed.png)

- **Khi nào sai:** frame 000008, lệch yaw +1°. Xe ở 7.9 m vẫn ra 0.0% điểm ngoài box, giống hệt lúc chưa lệch, và chỉ lên 0.6% ở +2°. Trong cùng frame, xe ở 33.2 m ra 24.5%.
- **Vì sao sai:** lệch 1° chỉ dịch điểm khoảng 14 px. Box của xe gần rộng 290 px và điểm LiDAR cách mép trái box 21 px, nên dịch 14 px vẫn nằm trọn trong box. Box của xe xa chỉ rộng 51 px nên cùng độ dịch đó đã đẩy một phần tư số điểm ra ngoài.
- **Lớp debug:** lỗi thật nằm ở **Geometry** (extrinsic sai), nhưng không phát hiện được là do lớp **Metric**: "% điểm ngoài box" đo việc điểm có vượt mép box hay không, chứ không đo độ lệch pixel, nên độ nhạy phụ thuộc bề rộng box.

**Failure 2: cùng độ lớn lệch, hai chiều cho hai kết quả trái ngược** — `results/figures/fail_02_occluded_car_asymmetric.png`

![failure 2](../results/figures/fail_02_occluded_car_asymmetric.png)

- **Khi nào sai:** frame 000025, xe ở 22.3 m, label ghi occluded = 1, chỉ có 27 điểm LiDAR. Lệch −1° ra 0% ngoài box, lệch +1° ra 92.6%.
- **Vì sao sai:** 27 điểm chỉ trải ngang 14 px và nằm sát mép trái của box rộng 59 px. Lệch +1° đẩy điểm sang trái, ra khỏi box gần hết; lệch −1° đẩy sang phải, vào giữa box. Lớp debug: **Metric**, vì con số phụ thuộc vị trí điểm trong box và chiều lệch, không chỉ phụ thuộc độ lớn lệch.

**Cách phát hiện khi chạy thật (đề xuất, chưa thử nghiệm trong bài này):** chỉ tính metric trên object có box hẹp (ở bảng mục 2, nhóm từ 30 m đã ra 10.5% ngay ở ±0.5°); lấy trung bình trên nhiều object và nhiều frame thay vì tin một object; và đo thêm độ lệch ngang có dấu giữa tâm cụm điểm và tâm box để biết cả chiều lệch.

## 4. Khuyến nghị nếu triển khai thật

Use-case cụ thể (ADAS / robot / drone), trade-off và bước tiếp theo.

[ĐIỀN]

## 5. Cách chạy lại

Các lệnh tái tạo lại toàn bộ kết quả từ repo sạch.

```bash
# CP2: ảnh demo đầu tiên (điểm LiDAR chiếu lên camera + 2D box của label), lưu vào results/figures/
python -m starter.projection --data-root data/synthetic --frame 000000
python -m starter.projection --data-root data/kitti_mini --frame 000008
python -m starter.projection --data-root data/kitti_mini --frame 000009
python -m starter.projection --data-root data/kitti_mini --frame 000011
python -m starter.projection --data-root data/nuscenes_mini_subset --frame scene-0103_010

# CP3: quét lệch yaw -3° đến +3° trên 20 frame kitti_mini.
# Tạo results/yaw_perturb_sweep.csv, results/yaw_perturb_per_object.csv, results/figures/yaw_perturb_sweep.png
python -m src.yaw_sweep

# CP4: vẽ 2 ảnh failure case vào results/figures/fail_01_*.png và fail_02_*.png
python -m src.failure_cases
```

## 6. Khai báo sử dụng AI

Ghi rõ đã dùng công cụ AI nào, dùng vào việc gì, và bạn đã tự kiểm chứng kết quả đó bằng cách nào. Nếu không dùng AI, ghi "Không sử dụng". Xem quy định ở `RULES.md` mục 2.

| Công cụ | Dùng cho việc gì | Bạn đã kiểm chứng thế nào |
|---|---|---|
| Claude Code (Opus) | Viết 2 hàm `velo_to_cam` và `cam_to_image` trong `starter/projection.py`, chạy demo CP2 | Test điểm LiDAR `(10, 0, 0)` với calib `data/synthetic` frame `000000`: ra `z_cam = 9.73`, pixel `(614, 175)` đúng như CHECKPOINTS.md; test đầu vào có NaN/Inf/điểm sau camera không lỗi; xem bằng mắt 3 ảnh overlay, điểm khớp lên xe, người, cột, mặt đường |
| Claude Code (Opus) | Viết `src/yaw_sweep.py` (quét yaw, xuất CSV, vẽ biểu đồ), chạy thí nghiệm CP3 và điền bảng số liệu ở mục 2 | Chạy script hai lần, md5 của hai file CSV giống nhau; ở yaw 0° các nhóm từ 10 m trở lên đều ra 0% ngoài box; độ dịch pixel ở 1° ra khoảng 13–15 px, khớp với ước lượng `f · tan(1°) ≈ 721 × 0.0175 ≈ 12.6 px` ở giữa ảnh |
| Claude Code (Opus) | Viết `src/failure_cases.py`, tìm và vẽ 2 failure case ở CP4, soạn mục 3 | Đối chiếu con số trên ảnh với `results/yaw_perturb_per_object.csv` (frame 8 object 1 và 4, frame 25 object 5); xem bằng mắt hai ảnh `fail_*.png`, điểm đỏ đúng là các điểm nằm ngoài khung trắng |
