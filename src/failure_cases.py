"""CP4 (topic A): vẽ các failure case của metric "% điểm LiDAR rơi ngoài 2D box".

Mỗi ô là một vùng cắt quanh 2D box của một object, ở một mức lệch yaw. Điểm LiDAR của object
(các điểm nằm trong 3D box theo calib gốc) được tô theo việc còn nằm trong 2D box hay không.

    python -m src.failure_cases
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

from starter.datasets import load_frame
from starter.projection import perturb_extrinsic, velo_to_cam
from src.yaw_sweep import in_bbox, points_in_box3d, project_all

IN_COLOR, OUT_COLOR = "#2a78d6", "#e34948"
INK, MUTED, SURFACE = "#0b0b0b", "#52514e", "#fcfcfb"


def draw_panel(ax, fr: dict, obj_idx: int, yaw: float, pad_px: int, title: str) -> float:
    """Vẽ một ô và trả về % điểm của object rơi ngoài 2D box."""
    obj = fr["labels"][obj_idx]
    pts = fr["points"][:, :3]
    pts = pts[np.isfinite(pts).all(axis=1)]
    idx = np.flatnonzero(points_in_box3d(velo_to_cam(pts, fr["calib"]), obj))
    uv, _ = project_all(pts, perturb_extrinsic(fr["calib"], yaw_deg=yaw))
    uv = uv[idx]
    inside = in_bbox(uv, obj.bbox)
    out_pct = 100 * (1 - inside.mean())

    x1, y1, x2, y2 = obj.bbox
    H, W = fr["image"].shape[:2]
    ax.imshow(cv2.cvtColor(fr["image"], cv2.COLOR_BGR2RGB))
    ax.add_patch(Rectangle((x1, y1), x2 - x1, y2 - y1, fill=False, ec="white", lw=2))
    size = 14 if len(idx) < 300 else 5
    for mask, color in ((inside, IN_COLOR), (~inside, OUT_COLOR)):
        ax.scatter(uv[mask, 0], uv[mask, 1], s=size, c=color, edgecolors="white", linewidths=0.3)
    ax.set_xlim(max(0, x1 - pad_px), min(W, x2 + pad_px))
    ax.set_ylim(min(H, y2 + pad_px), max(0, y1 - pad_px))
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title(f"{title}\n{out_pct:.1f}% điểm ngoài box", fontsize=9.5, color=INK, loc="left")
    return out_pct


def finish(fig, suptitle: str, out_path: Path) -> None:
    handles = [Line2D([], [], marker="o", ls="", color=IN_COLOR, label="Điểm LiDAR của xe, còn trong 2D box"),
               Line2D([], [], marker="o", ls="", color=OUT_COLOR, label="Điểm LiDAR của xe, rơi ngoài 2D box"),
               Line2D([], [], color="white", lw=2, label="2D box của label")]
    legend = fig.legend(handles=handles, loc="lower center", ncol=3, frameon=True, fontsize=9, labelcolor=MUTED)
    legend.get_frame().set_facecolor("#d9d8d3")
    legend.get_frame().set_edgecolor("none")
    fig.suptitle(suptitle, x=0.02, ha="left", fontsize=11.5, color=INK)
    fig.tight_layout(rect=(0, 0.07, 1, 0.93))
    fig.savefig(out_path, facecolor=SURFACE)
    plt.close(fig)
    print(f"-> {out_path}")


def fail_near_car_missed(data_root: str, out_dir: Path) -> None:
    """Cùng frame, cùng mức lệch: xe gần không mất điểm nào, xe xa mất rõ."""
    fr = load_frame(data_root, "000008")
    cases = [(1, 40, "Xe gần 7.9 m, box rộng 290 px"), (4, 25, "Xe xa 33.2 m, box rộng 51 px")]
    fig, axes = plt.subplots(2, 2, figsize=(9, 7), dpi=150, facecolor=SURFACE)
    for row, yaw in enumerate([0.0, 1.0]):
        for col, (obj_idx, pad, name) in enumerate(cases):
            draw_panel(axes[row, col], fr, obj_idx, yaw, pad, f"Yaw {yaw:+.0f}° | {name}".replace("+0°", "0°"))
    finish(fig, "Frame 000008: lệch yaw +1° không làm xe gần mất điểm nào, metric bỏ sót",
           out_dir / "fail_01_yaw1deg_near_car_missed.png")


def fail_occluded_asymmetric(data_root: str, out_dir: Path) -> None:
    """Xe bị che một phần: cùng độ lớn lệch nhưng hai chiều cho hai kết quả trái ngược."""
    fr = load_frame(data_root, "000025")
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.9), dpi=150, facecolor=SURFACE)
    for ax, yaw in zip(axes, [-1.0, 0.0, 1.0]):
        draw_panel(ax, fr, 5, yaw, 25, f"Yaw {yaw:+.0f}°".replace("+0°", "0°"))
    finish(fig, "Frame 000025, xe 22.3 m bị che một phần: −1° ra 0%, +1° ra 93%",
           out_dir / "fail_02_occluded_car_asymmetric.png")


def main() -> None:
    ap = argparse.ArgumentParser(description="Vẽ các failure case của metric % điểm ngoài 2D box")
    ap.add_argument("--data-root", default="data/kitti_mini")
    ap.add_argument("--out-dir", default="results/figures")
    args = ap.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fail_near_car_missed(args.data_root, out_dir)
    fail_occluded_asymmetric(args.data_root, out_dir)


if __name__ == "__main__":
    main()
