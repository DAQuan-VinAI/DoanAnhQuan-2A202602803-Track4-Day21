"""CP3 (topic A): quét mức lệch yaw của extrinsic và đo điểm LiDAR rơi ra ngoài 2D box.

Cách đo, cho từng object trong label:
  1. Lấy các điểm LiDAR nằm trong 3D box của object (dùng calib GỐC). Đây là "điểm của object".
  2. Chiếu các điểm đó lên ảnh bằng calib đã lệch yaw.
  3. out_of_box = tỉ lệ điểm KHÔNG rơi vào 2D box của label (điểm chiếu ra ngoài ảnh cũng tính là ra ngoài).
  4. px_shift = độ dịch pixel trung bình so với khi chiếu bằng calib gốc.

Mỗi lần chạy chỉ thay đổi yaw. Frame, class, ngưỡng lọc object và các bin khoảng cách giữ nguyên.
Không có bước ngẫu nhiên nào nên chạy lại cho đúng cùng số liệu.

    python -m src.yaw_sweep
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from starter.datasets import list_frames, load_frame
from starter.kitti_io import KittiCalib, KittiObject
from starter.projection import perturb_extrinsic, velo_to_cam

BIN_EDGES = [0.0, 10.0, 20.0, 30.0, np.inf]
BIN_LABELS = ["<10m", "10-20m", "20-30m", ">=30m"]
BIN_COLORS = ["#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]  # một hue, nhạt -> đậm theo khoảng cách


def points_in_box3d(points_cam: np.ndarray, obj: KittiObject) -> np.ndarray:
    """Mask (N,) các điểm camera frame nằm trong 3D box của object."""
    h, w, l = obj.dimensions
    d = points_cam - obj.location
    c, s = np.cos(obj.rotation_y), np.sin(obj.rotation_y)
    # Đưa về hệ toạ độ của box: xoay ngược rotation_y quanh trục y
    x_box = c * d[:, 0] - s * d[:, 2]
    z_box = s * d[:, 0] + c * d[:, 2]
    return (np.abs(x_box) <= l / 2) & (np.abs(z_box) <= w / 2) & (d[:, 1] <= 0) & (d[:, 1] >= -h)


def project_all(points_velo: np.ndarray, calib: KittiCalib) -> tuple[np.ndarray, np.ndarray]:
    """Chiếu mọi điểm, giữ nguyên thứ tự để so sánh từng điểm trước và sau khi lệch.
    Trả về uv (N, 2) và front (N,) bool, True nếu điểm nằm trước camera."""
    cam = velo_to_cam(points_velo, calib)
    front = cam[:, 2] > 0.1
    proj = np.hstack([cam, np.ones((len(cam), 1))]) @ calib.P2.T
    uv = np.full((len(cam), 2), np.nan)
    uv[front] = proj[front, :2] / proj[front, 2:3]
    return uv, front


def in_bbox(uv: np.ndarray, bbox: np.ndarray) -> np.ndarray:
    x1, y1, x2, y2 = bbox
    with np.errstate(invalid="ignore"):
        return (uv[:, 0] >= x1) & (uv[:, 0] <= x2) & (uv[:, 1] >= y1) & (uv[:, 1] <= y2)


def in_image(uv: np.ndarray, image_shape: tuple[int, ...]) -> np.ndarray:
    H, W = image_shape[:2]
    with np.errstate(invalid="ignore"):
        return (uv[:, 0] >= 0) & (uv[:, 0] < W) & (uv[:, 1] >= 0) & (uv[:, 1] < H)


def run_sweep(data_root: str, frames: list[str], yaws: list[float], classes: list[str],
              min_points: int, max_occluded: int, max_truncated: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    obj_rows, fov_rows = [], []
    for frame in frames:
        fr = load_frame(data_root, frame)
        pts = fr["points"][:, :3]
        pts = pts[np.isfinite(pts).all(axis=1)]
        uv0, _ = project_all(pts, fr["calib"])
        cam0 = velo_to_cam(pts, fr["calib"])

        objects = []
        for i, obj in enumerate(fr["labels"]):
            if obj.type not in classes or obj.occluded > max_occluded or obj.truncated > max_truncated:
                continue
            idx = np.flatnonzero(points_in_box3d(cam0, obj))
            if len(idx) >= min_points:
                objects.append((i, obj, idx))

        for yaw in yaws:
            calib = perturb_extrinsic(fr["calib"], yaw_deg=yaw)
            uv, front = project_all(pts, calib)
            fov_rows.append({"frame": frame, "yaw_deg": yaw,
                             "inside_fov_pct": 100 * (front & in_image(uv, fr["image"].shape)).mean()})
            for i, obj, idx in objects:
                shift = np.linalg.norm(uv[idx] - uv0[idx], axis=1)
                obj_rows.append({
                    "frame": frame, "obj_idx": i, "class": obj.type,
                    "distance_m": round(float(obj.location[2]), 2),
                    "bbox_width_px": round(float(obj.bbox[2] - obj.bbox[0]), 1),
                    "n_points": len(idx), "yaw_deg": yaw,
                    "px_shift_mean": float(np.nanmean(shift)),
                    "out_of_box_pct": 100 * (1 - in_bbox(uv[idx], obj.bbox).mean()),
                })
    return pd.DataFrame(obj_rows), pd.DataFrame(fov_rows)


def summarize(per_obj: pd.DataFrame, fov: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Mỗi dòng là một mức yaw. Mọi metric out_of_box là trung bình theo OBJECT, không theo điểm,
    để vài xe ở gần có hàng nghìn điểm không lấn át các xe ở xa."""
    per_obj = per_obj.assign(dist_bin=pd.cut(per_obj["distance_m"], BIN_EDGES, labels=BIN_LABELS, right=False))
    rows = []
    for yaw, g in per_obj.groupby("yaw_deg"):
        row = {"yaw_deg": yaw, **config,
               "n_frames": fov["frame"].nunique(), "n_objects": len(g),
               "inside_fov_pct": fov.loc[fov["yaw_deg"] == yaw, "inside_fov_pct"].mean(),
               "px_shift_mean": g["px_shift_mean"].mean(),
               "out_of_box_pct_all": g["out_of_box_pct"].mean()}
        for label in BIN_LABELS:
            gb = g[g["dist_bin"] == label]
            row[f"n_objects_{label}"] = len(gb)
            row[f"out_of_box_pct_{label}"] = gb["out_of_box_pct"].mean()
        rows.append(row)
    return pd.DataFrame(rows).round(3)


def plot(summary: pd.DataFrame, out_path: Path) -> None:
    ink, muted, grid, surface = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
    fig, ax = plt.subplots(figsize=(8.2, 4.8), dpi=150, facecolor=surface)
    ax.set_facecolor(surface)
    last = summary["yaw_deg"].max()
    for label, color in zip(BIN_LABELS, BIN_COLORS):
        n = int(summary[f"n_objects_{label}"].iloc[0])
        ax.plot(summary["yaw_deg"], summary[f"out_of_box_pct_{label}"], color=color, lw=2,
                marker="o", ms=5, mec=surface, mew=1, label=f"{label} (n={n} object)")
        y_end = summary.loc[summary["yaw_deg"] == last, f"out_of_box_pct_{label}"].iloc[0]
        ax.annotate(label, (last, y_end), xytext=(8, 0), textcoords="offset points",
                    va="center", fontsize=9, color=muted)
    ax.set_xlabel("Lệch yaw của LiDAR (độ)", color=muted)
    ax.set_ylabel("Điểm LiDAR của object rơi ngoài 2D box (%)", color=muted)
    ax.set_title("Lệch yaw càng lớn, object càng xa thì càng nhiều điểm rơi ngoài 2D box",
                 loc="left", fontsize=11, color=ink)
    ax.set_xticks(summary["yaw_deg"])
    ax.set_ylim(0, 100)
    ax.grid(axis="y", color=grid, lw=0.8)
    ax.tick_params(colors=muted, length=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(grid)
    ax.legend(title="Khoảng cách tới object", frameon=False, fontsize=9, title_fontsize=9,
              loc="upper center", labelcolor=muted)
    fig.subplots_adjust(right=0.9)
    fig.savefig(out_path, facecolor=surface, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description="Quét lệch yaw và đo tỉ lệ điểm LiDAR rơi ngoài 2D box theo khoảng cách")
    ap.add_argument("--data-root", default="data/kitti_mini")
    ap.add_argument("--frames", default="all", help="'all' hoặc danh sách cách nhau bởi dấu phẩy, ví dụ 000008,000011")
    ap.add_argument("--yaws", default="-3,-2,-1,-0.5,0,0.5,1,2,3", help="các mức lệch yaw (độ)")
    ap.add_argument("--classes", default="Car,Van,Truck")
    ap.add_argument("--min-points", type=int, default=20, help="bỏ object có ít điểm LiDAR hơn mức này")
    ap.add_argument("--max-occluded", type=int, default=1, help="mức occluded tối đa của KITTI (0-3)")
    ap.add_argument("--max-truncated", type=float, default=0.5)
    ap.add_argument("--out-dir", default="results")
    args = ap.parse_args()

    frames = list_frames(args.data_root) if args.frames == "all" else args.frames.split(",")
    yaws = [float(y) for y in args.yaws.split(",")]
    classes = args.classes.split(",")
    per_obj, fov = run_sweep(args.data_root, frames, yaws, classes,
                             args.min_points, args.max_occluded, args.max_truncated)
    config = {"data_root": args.data_root, "classes": "+".join(classes), "min_points": args.min_points,
              "max_occluded": args.max_occluded, "max_truncated": args.max_truncated}
    summary = summarize(per_obj, fov, config)

    out_dir = Path(args.out_dir)
    (out_dir / "figures").mkdir(parents=True, exist_ok=True)
    summary.to_csv(out_dir / "yaw_perturb_sweep.csv", index=False)
    per_obj.round(3).to_csv(out_dir / "yaw_perturb_per_object.csv", index=False)
    plot(summary, out_dir / "figures" / "yaw_perturb_sweep.png")

    cols = ["yaw_deg", "n_objects", "inside_fov_pct", "px_shift_mean", "out_of_box_pct_all"] + \
           [f"out_of_box_pct_{b}" for b in BIN_LABELS]
    print(summary[cols].to_string(index=False))
    print(f"-> {out_dir / 'yaw_perturb_sweep.csv'}, {out_dir / 'yaw_perturb_per_object.csv'}, "
          f"{out_dir / 'figures' / 'yaw_perturb_sweep.png'}")


if __name__ == "__main__":
    main()
