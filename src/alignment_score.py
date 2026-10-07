"""Topic A mức Advanced: alignment score cho từng frame và ngưỡng phát hiện calibration drift.

Đọc results/extrinsic_perturb_per_object.csv (chạy `python -m src.extrinsic_sweep` trước).

  score của frame = trung bình, theo object, của % điểm LiDAR rơi trong 2D box (0-100, càng cao càng khớp)
  báo lệch        = score < ngưỡng

So sánh hai cách chọn object để tính score:
  all : mọi object đã qua bộ lọc của extrinsic_sweep
  far : chỉ object từ --min-distance trở lên (box hẹp nên nhạy với lệch, xem failure 1 trong REPORT)

Frame không có object nào phù hợp thì không có score, và được đếm riêng là "không đo được".

    python -m src.alignment_score
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

AXES = ["roll", "pitch", "yaw", "tx", "ty", "tz"]
DOT_COLOR, LINE_COLOR, THRESHOLD_COLOR = "#86b6ef", "#1c5cab", "#52514e"


def frame_scores(per_obj: pd.DataFrame, min_distance: float) -> pd.DataFrame:
    """Mỗi dòng: (variant, frame, axis, level) -> score của frame đó."""
    parts = []
    for variant, sub in (("all", per_obj), ("far", per_obj[per_obj["distance_m"] >= min_distance])):
        g = sub.groupby(["frame", "axis", "unit", "level"], sort=False)["in_box_pct"]
        parts.append(g.agg(n_objects="count", score="mean").reset_index().assign(variant=variant))
    out = pd.concat(parts, ignore_index=True)
    return out[["variant", "frame", "axis", "unit", "level", "n_objects", "score"]]


def detection_table(scores: pd.DataFrame, thresholds: list[float]) -> pd.DataFrame:
    """Mỗi dòng: (variant, ngưỡng, trục, mức lệch) -> số frame bị báo lệch.
    Ở mức 0 thì calib đúng, nên detect_rate_pct của dòng đó chính là tỉ lệ báo nhầm."""
    rows = []
    for threshold in thresholds:
        for (variant, axis, unit, level), g in scores.groupby(["variant", "axis", "unit", "level"], sort=False):
            detected = int((g["score"] < threshold).sum())
            rows.append({"variant": variant, "threshold": threshold, "axis": axis, "unit": unit, "level": level,
                         "n_frames": len(g), "score_mean": g["score"].mean(), "score_min": g["score"].min(),
                         "detected_frames": detected, "detect_rate_pct": 100 * detected / len(g)})
    return pd.DataFrame(rows).round(3)


def plot(scores: pd.DataFrame, variant: str, threshold: float, min_distance: float, out_path: Path) -> None:
    ink, muted, grid, surface = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
    s = scores[scores["variant"] == variant]
    fig, axes = plt.subplots(2, 3, figsize=(11, 6.4), dpi=150, facecolor=surface, sharey=True)
    for ax, name in zip(axes.ravel(), AXES):
        a = s[s["axis"] == name]
        unit = "độ" if a["unit"].iloc[0] == "deg" else "cm"
        median = a.groupby("level")["score"].median()
        ax.set_facecolor(surface)
        ax.scatter(a["level"], a["score"], s=16, color=DOT_COLOR, edgecolors=surface, linewidths=0.5, zorder=2)
        ax.plot(median.index, median.values, color=LINE_COLOR, lw=2, zorder=3)
        ax.axhline(threshold, color=THRESHOLD_COLOR, lw=1, ls="--", zorder=1)
        ax.set_title(f"{name} ({unit})", loc="left", fontsize=10, color=muted)
        ax.set_xticks(median.index, [f"{v:g}" for v in median.index])
        ax.set_ylim(-3, 103)
        ax.grid(axis="y", color=grid, lw=0.8)
        ax.tick_params(colors=muted, length=0, labelsize=8)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(grid)
    axes[1, 0].annotate(f"ngưỡng {threshold:g}%", (0, threshold), xytext=(0, -11), textcoords="offset points",
                        ha="center", fontsize=8, color=muted)
    for row in axes:
        row[0].set_ylabel("Alignment score của frame (%)", color=muted)
    handles = [plt.Line2D([], [], marker="o", ls="", color=DOT_COLOR, label="Score của một frame"),
               plt.Line2D([], [], color=LINE_COLOR, lw=2, label="Trung vị các frame"),
               plt.Line2D([], [], color=THRESHOLD_COLOR, lw=1, ls="--", label="Ngưỡng báo lệch")]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False, fontsize=9, labelcolor=muted)
    which = f"object từ {min_distance:g} m" if variant == "far" else "mọi object"
    fig.suptitle(f"Score ({which}) tụt dưới ngưỡng khi lệch yaw hoặc pitch, gần như đứng yên với roll và dịch tới 10 cm",
                 x=0.02, ha="left", fontsize=11, color=ink)
    fig.tight_layout(rect=(0, 0.05, 1, 0.95))
    fig.savefig(out_path, facecolor=surface)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description="Tính alignment score theo frame và tỉ lệ phát hiện drift theo ngưỡng")
    ap.add_argument("--per-object-csv", default="results/extrinsic_perturb_per_object.csv")
    ap.add_argument("--min-distance", type=float, default=20.0, help="khoảng cách tối thiểu (m) của variant 'far'")
    ap.add_argument("--thresholds", default="99,95,90", help="các ngưỡng cần so sánh (%%)")
    ap.add_argument("--threshold", type=float, default=95.0, help="ngưỡng được chọn, dùng để vẽ và in bảng")
    ap.add_argument("--plot-variant", default="far", choices=["all", "far"])
    ap.add_argument("--out-dir", default="results")
    args = ap.parse_args()

    per_obj = pd.read_csv(args.per_object_csv, dtype={"frame": str})
    scores = frame_scores(per_obj, args.min_distance)
    detection = detection_table(scores, [float(t) for t in args.thresholds.split(",")])

    out_dir = Path(args.out_dir)
    (out_dir / "figures").mkdir(parents=True, exist_ok=True)
    scores.round(3).to_csv(out_dir / "alignment_score_per_frame.csv", index=False)
    detection.to_csv(out_dir / "alignment_score_detection.csv", index=False)
    plot(scores, args.plot_variant, args.threshold, args.min_distance,
         out_dir / "figures" / "alignment_score_threshold.png")

    for variant in ("all", "far"):
        d = detection[(detection["variant"] == variant) & (detection["threshold"] == args.threshold)]
        n = int(d["n_frames"].iloc[0])
        print(f"\nvariant={variant}, ngưỡng {args.threshold:g}%, {n} frame có score: % frame bị báo lệch")
        print(d.pivot(index="axis", columns="level", values="detect_rate_pct").reindex(AXES).round(0).to_string(na_rep=""))
    print(f"\n-> {out_dir / 'alignment_score_per_frame.csv'}, {out_dir / 'alignment_score_detection.csv'}, "
          f"{out_dir / 'figures' / 'alignment_score_threshold.png'}")


if __name__ == "__main__":
    main()
