"""Topic A mức Good: quét lệch extrinsic theo 6 trục (roll, pitch, yaw, tx, ty, tz).

Cách đo giống src/yaw_sweep.py, chỉ khác là mỗi lần chạy làm lệch một trục:
  1. Lấy các điểm LiDAR nằm trong 3D box của object (dùng calib GỐC).
  2. Chiếu các điểm đó lên ảnh bằng calib đã lệch.
  3. in_box = tỉ lệ điểm rơi đúng vào 2D box của label (= 100 - out_of_box của yaw_sweep).
  4. px_shift = độ dịch pixel trung bình so với khi chiếu bằng calib gốc.

Trục lấy theo velodyne frame: roll quanh x (hướng trước), pitch quanh y (sang trái), yaw quanh z (lên trên);
tx, ty, tz là dịch LiDAR dọc 3 trục đó. Mỗi lần chỉ một trục khác 0. Không có bước ngẫu nhiên nào.

    python -m src.extrinsic_sweep
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
from starter.projection import perturb_extrinsic, velo_to_cam
from src.yaw_sweep import BIN_EDGES, BIN_LABELS, in_bbox, in_image, points_in_box3d, project_all

ROT_AXES = ["roll", "pitch", "yaw"]
TRANS_AXES = ["tx", "ty", "tz"]
AXIS_COLORS = ["#2a78d6", "#eb6834", "#1baf7a"]  # 3 slot categorical đầu, cùng thứ tự cho cả hai ô


def perturb_kwargs(axis: str, level: float) -> dict:
    """level tính bằng độ với trục xoay, bằng cm với trục dịch."""
    if axis in ROT_AXES:
        return {f"{axis}_deg": level}
    t = [0.0, 0.0, 0.0]
    t[TRANS_AXES.index(axis)] = level / 100.0
    return {"t_xyz_m": tuple(t)}


def run_sweep(data_root: str, frames: list[str], levels: dict[str, list[float]], classes: list[str],
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

        for axis, axis_levels in levels.items():
            unit = "deg" if axis in ROT_AXES else "cm"
            for level in axis_levels:
                calib = perturb_extrinsic(fr["calib"], **perturb_kwargs(axis, level))
                uv, front = project_all(pts, calib)
                fov_rows.append({"frame": frame, "axis": axis, "level": level,
                                 "inside_fov_pct": 100 * (front & in_image(uv, fr["image"].shape)).mean()})
                for i, obj, idx in objects:
                    shift = np.linalg.norm(uv[idx] - uv0[idx], axis=1)
                    obj_rows.append({
                        "frame": frame, "obj_idx": i, "class": obj.type,
                        "distance_m": round(float(obj.location[2]), 2),
                        "bbox_width_px": round(float(obj.bbox[2] - obj.bbox[0]), 1),
                        "n_points": len(idx), "axis": axis, "unit": unit, "level": level,
                        "px_shift_mean": float(np.nanmean(shift)),
                        "in_box_pct": 100 * in_bbox(uv[idx], obj.bbox).mean(),
                    })
    return pd.DataFrame(obj_rows), pd.DataFrame(fov_rows)


def summarize(per_obj: pd.DataFrame, fov: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Mỗi dòng là một cặp (trục, mức lệch). in_box là trung bình theo OBJECT, như yaw_sweep."""
    per_obj = per_obj.assign(dist_bin=pd.cut(per_obj["distance_m"], BIN_EDGES, labels=BIN_LABELS, right=False))
    rows = []
    for (axis, unit, level), g in per_obj.groupby(["axis", "unit", "level"], sort=False):
        f = fov[(fov["axis"] == axis) & (fov["level"] == level)]
        row = {"axis": axis, "unit": unit, "level": level, **config,
               "n_frames": fov["frame"].nunique(), "n_objects": len(g),
               "inside_fov_pct": f["inside_fov_pct"].mean(),
               "px_shift_mean": g["px_shift_mean"].mean(),
               "in_box_pct_all": g["in_box_pct"].mean()}
        for label in BIN_LABELS:
            gb = g[g["dist_bin"] == label]
            row[f"n_objects_{label}"] = len(gb)
            row[f"in_box_pct_{label}"] = gb["in_box_pct"].mean()
        rows.append(row)
    return pd.DataFrame(rows).round(3)


def plot(summary: pd.DataFrame, out_path: Path) -> None:
    ink, muted, grid, surface = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.6), dpi=150, facecolor=surface, sharey=True)
    panels = [(ROT_AXES, "Lệch góc của LiDAR (độ)", "Xoay 0.5–3°"),
              (TRANS_AXES, "Dịch vị trí của LiDAR (cm)", "Dịch 2–10 cm")]
    for ax, (names, xlabel, subtitle) in zip(axes, panels):
        ax.set_facecolor(surface)
        for name, color in zip(names, AXIS_COLORS):
            s = summary[summary["axis"] == name].sort_values("level")
            ax.plot(s["level"], s["in_box_pct_all"], color=color, lw=2, marker="o", ms=5,
                    mec=surface, mew=1, label=name)
            ax.set_xticks(s["level"], [f"{v:g}" for v in s["level"]])
        ax.set_xlabel(xlabel, color=muted)
        ax.set_title(subtitle, loc="left", fontsize=10, color=muted)
        ax.set_ylim(0, 102)
        ax.grid(axis="y", color=grid, lw=0.8)
        ax.tick_params(colors=muted, length=0, labelsize=8)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(grid)
        ax.legend(frameon=False, fontsize=9, loc="lower center", ncol=3, labelcolor=muted)
    axes[0].set_ylabel("Điểm LiDAR của object rơi trong 2D box (%)", color=muted)
    fig.suptitle("Yaw và pitch làm điểm rơi khỏi 2D box, roll ảnh hưởng ít, dịch tới 10 cm gần như không đổi",
                 x=0.02, ha="left", fontsize=11, color=ink)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(out_path, facecolor=surface)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description="Quét lệch extrinsic theo 6 trục, đo % điểm trong FOV và trong 2D box")
    ap.add_argument("--data-root", default="data/kitti_mini")
    ap.add_argument("--frames", default="all", help="'all' hoặc danh sách cách nhau bởi dấu phẩy, ví dụ 000008,000011")
    ap.add_argument("--rot-levels", default="-3,-2,-1,-0.5,0,0.5,1,2,3", help="các mức lệch roll/pitch/yaw (độ)")
    ap.add_argument("--trans-levels", default="-10,-5,-2,0,2,5,10", help="các mức dịch tx/ty/tz (cm)")
    ap.add_argument("--classes", default="Car,Van,Truck")
    ap.add_argument("--min-points", type=int, default=20, help="bỏ object có ít điểm LiDAR hơn mức này")
    ap.add_argument("--max-occluded", type=int, default=1, help="mức occluded tối đa của KITTI (0-3)")
    ap.add_argument("--max-truncated", type=float, default=0.5)
    ap.add_argument("--out-dir", default="results")
    args = ap.parse_args()

    frames = list_frames(args.data_root) if args.frames == "all" else args.frames.split(",")
    rot = [float(v) for v in args.rot_levels.split(",")]
    trans = [float(v) for v in args.trans_levels.split(",")]
    levels = {**{a: rot for a in ROT_AXES}, **{a: trans for a in TRANS_AXES}}
    classes = args.classes.split(",")
    per_obj, fov = run_sweep(args.data_root, frames, levels, classes,
                             args.min_points, args.max_occluded, args.max_truncated)
    config = {"data_root": args.data_root, "classes": "+".join(classes), "min_points": args.min_points,
              "max_occluded": args.max_occluded, "max_truncated": args.max_truncated}
    summary = summarize(per_obj, fov, config)

    out_dir = Path(args.out_dir)
    (out_dir / "figures").mkdir(parents=True, exist_ok=True)
    summary.to_csv(out_dir / "extrinsic_perturb_sweep.csv", index=False)
    per_obj.round(3).to_csv(out_dir / "extrinsic_perturb_per_object.csv", index=False)
    plot(summary, out_dir / "figures" / "extrinsic_perturb_sweep.png")

    cols = ["axis", "unit", "level", "n_objects", "inside_fov_pct", "px_shift_mean", "in_box_pct_all"] + \
           [f"in_box_pct_{b}" for b in BIN_LABELS]
    print(summary[cols].to_string(index=False))
    print(f"-> {out_dir / 'extrinsic_perturb_sweep.csv'}, {out_dir / 'extrinsic_perturb_per_object.csv'}, "
          f"{out_dir / 'figures' / 'extrinsic_perturb_sweep.png'}")


if __name__ == "__main__":
    main()
