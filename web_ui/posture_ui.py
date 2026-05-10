"""
🏀 投篮姿态实时监测 UI v2
三连杆模型 + 标准姿态对比 + 纠正建议面板 + 投篮记录 + 回放分析
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tkinter as tk
from tkinter import ttk
import math
import json
import time
import threading
from datetime import datetime
from shot_monitor import SensorHub, PoseCoach, RULES

# ==================== 颜色主题 ====================
BG_DARK   = "#0f0e17"
BG_CANVAS = "#0a0a1a"
BG_CARD   = "#1a1a2e"
BG_OK     = "#0d2818"
BG_ERR    = "#3c1111"
CLR_OK    = "#00ff88"
CLR_ERR   = "#ff4455"
CLR_GHOST = "#444466"
CLR_JOINT = "#ffffff"
CLR_TEXT  = "#e0e0e0"
CLR_GOLD  = "#ffd700"
CLR_ARC   = "#ffaa00"
CLR_REC   = "#ff6622"

# ==================== 标准姿态 ====================
STD_UPPERARM_PITCH = 0
STD_ELBOW_ANGLE    = 70
STD_FOREARM_PITCH  = STD_UPPERARM_PITCH + STD_ELBOW_ANGLE
STD_WRIST_PITCH    = 150

# ==================== 连杆参数 ====================
UPPER_LEN  = 160
FORE_LEN   = 140
HAND_LEN   = 65
SHOULDER   = (260, 440)
CANVAS_W   = 560
CANVAS_H   = 740

DETAIL_W   = 270
DETAIL_H   = 180
PANEL_W    = 580

# ==================== 记录保存路径 ====================
RECORDS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "records")
os.makedirs(RECORDS_DIR, exist_ok=True)

# ==================== 坐标计算 ====================
def joint_pos(sx, sy, length, pitch_deg):
    rad = math.radians(pitch_deg)
    return sx + length * math.cos(rad), sy - length * math.sin(rad)


# ==================== 卡尔曼滤波 ====================
def kalman_filter(data, process_noise=1.0, measure_noise=4.0):
    """一维卡尔曼滤波，平滑传感器数据
    process_noise: 过程噪声Q，越大越跟随原始数据
    measure_noise: 测量噪声R，越大越平滑
    """
    if not data:
        return data
    n = len(data)
    filtered = [0.0] * n
    x = data[0]       # 初始状态估计
    p = 1.0            # 初始协方差
    q = process_noise  # 过程噪声
    r = measure_noise  # 测量噪声

    for i in range(n):
        # 预测
        p = p + q
        # 更新
        k = p / (p + r)         # 卡尔曼增益
        x = x + k * (data[i] - x)
        p = (1 - k) * p
        filtered[i] = x

    return filtered


# ==================== 主界面 ====================
class PostureUI:

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🏀 投篮姿态实时监测 v2")
        self.root.configure(bg=BG_DARK)
        self.root.geometry("1170x910")
        self.root.resizable(False, False)

        self.hub  = SensorHub(port=8888)
        self.coach = PoseCoach()

        # 投篮记录相关
        self.recording = False
        self.record_buffer = []   # [{ts, UPPERARM:{p,r}, FOREARM:{p,r}, WRIST:{p,r}}, ...]
        self.rec_start = 0
        self.records_list = []    # 保存的记录文件名

        self._build_ui()
        self._refresh_records_list()
        self._tick()

    # ---------- 构建 UI ----------
    def _build_ui(self):
        # 标题行
        title_row = tk.Frame(self.root, bg=BG_DARK)
        title_row.pack(fill=tk.X, padx=10, pady=(10, 5))
        tk.Label(title_row, text="🏀 投篮姿态实时监测",
                 font=("Microsoft YaHei", 20, "bold"),
                 fg=CLR_GOLD, bg=BG_DARK).pack(side=tk.LEFT)

        # 投篮记录按钮
        self.rec_btn = tk.Button(title_row, text="🏀 投篮记录",
                                  font=("Microsoft YaHei", 14, "bold"),
                                  fg="#fff", bg=CLR_REC,
                                  activebackground="#cc5500",
                                  relief=tk.FLAT, padx=20, pady=4,
                                  command=self._toggle_record)
        self.rec_btn.pack(side=tk.RIGHT)

        # 回放按钮
        self.playback_btn = tk.Button(title_row, text="📂 回放分析",
                                       font=("Microsoft YaHei", 12, "bold"),
                                       fg="#fff", bg="#3355aa",
                                       activebackground="#2244aa",
                                       relief=tk.FLAT, padx=15, pady=4,
                                       command=self._open_playback)
        self.playback_btn.pack(side=tk.RIGHT, padx=(0, 10))

        # 录制状态指示
        self.rec_label = tk.Label(title_row, text="",
                                   font=("Microsoft YaHei", 12, "bold"),
                                   fg=CLR_REC, bg=BG_DARK)
        self.rec_label.pack(side=tk.RIGHT, padx=(0, 10))

        body = tk.Frame(self.root, bg=BG_DARK)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # ---- 左侧画布 ----
        self.canvas = tk.Canvas(body, width=CANVAS_W, height=CANVAS_H,
                                bg=BG_CANVAS, highlightthickness=1,
                                highlightbackground="#333")
        self.canvas.pack(side=tk.LEFT, padx=(0, 10))

        # ---- 右侧纠正面板 ----
        panel = tk.Frame(body, bg=BG_DARK, width=PANEL_W)
        panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        panel.pack_propagate(False)

        tk.Label(panel, text="🔍 姿态纠正建议",
                 font=("Microsoft YaHei", 14, "bold"),
                 fg=CLR_GOLD, bg=BG_DARK).pack(anchor="w", pady=(0, 8))

        # ---- 特写区域 ----
        detail_row = tk.Frame(panel, bg=BG_DARK)
        detail_row.pack(fill=tk.X, pady=(0, 6))

        roll_frame = tk.Frame(detail_row, bg=BG_CARD, highlightbackground="#333",
                               highlightthickness=1)
        roll_frame.pack(side=tk.LEFT, padx=(0, 6))
        tk.Label(roll_frame, text="小臂翻滚角",
                 font=("Microsoft YaHei", 11, "bold"),
                 fg=CLR_GOLD, bg=BG_CARD).pack(anchor="w", padx=8, pady=(6, 0))
        self.roll_canvas = tk.Canvas(roll_frame, width=DETAIL_W, height=DETAIL_H,
                                      bg=BG_CANVAS, highlightthickness=0)
        self.roll_canvas.pack(padx=6, pady=(4, 6))

        wrist_frame = tk.Frame(detail_row, bg=BG_CARD, highlightbackground="#333",
                                highlightthickness=1)
        wrist_frame.pack(side=tk.LEFT)
        tk.Label(wrist_frame, text="手背俯仰角",
                 font=("Microsoft YaHei", 11, "bold"),
                 fg=CLR_GOLD, bg=BG_CARD).pack(anchor="w", padx=8, pady=(6, 0))
        self.wrist_canvas = tk.Canvas(wrist_frame, width=DETAIL_W, height=DETAIL_H,
                                       bg=BG_CANVAS, highlightthickness=0)
        self.wrist_canvas.pack(padx=6, pady=(4, 6))

        # ---- 三个纠正卡片 ----
        self.cards = {}
        for nid in ["UPPERARM", "FOREARM", "WRIST"]:
            rule = RULES[nid]
            card = tk.Frame(panel, bg=BG_CARD, padx=15, pady=12,
                            highlightbackground="#333", highlightthickness=1)
            card.pack(fill=tk.X, pady=4)

            hdr = tk.Frame(card, bg=BG_CARD)
            hdr.pack(fill=tk.X)
            tk.Label(hdr, text=rule.name,
                     font=("Microsoft YaHei", 15, "bold"),
                     fg=CLR_TEXT, bg=BG_CARD).pack(side=tk.LEFT)
            st_lbl = tk.Label(hdr, text="⏳ 等待",
                              font=("Microsoft YaHei", 14, "bold"),
                              fg="#888", bg=BG_CARD)
            st_lbl.pack(side=tk.RIGHT)

            ang_lbl = tk.Label(card, text="俯仰: --   翻滚: --",
                               font=("Microsoft YaHei", 11),
                               fg=CLR_TEXT, bg=BG_CARD, anchor="w")
            ang_lbl.pack(fill=tk.X, pady=(6, 0))

            tip_lbl = tk.Label(card, text="",
                               font=("Microsoft YaHei", 12, "bold"),
                               fg=CLR_OK, bg=BG_CARD, anchor="w",
                               wraplength=540, justify=tk.LEFT)
            tip_lbl.pack(fill=tk.X, pady=(6, 0))

            self.cards[nid] = {"frame": card, "status": st_lbl,
                               "angle": ang_lbl, "tip": tip_lbl}

        self.overall = tk.Label(panel, text="",
                                font=("Microsoft YaHei", 18, "bold"),
                                fg=CLR_OK, bg=BG_DARK)
        self.overall.pack(pady=10)

    # ==================== 投篮记录功能 ====================
    def _toggle_record(self):
        if not self.recording:
            self.recording = True
            self.record_buffer = []
            self.rec_start = time.time()
            self.rec_btn.config(text="⏹ 停止记录", bg=CLR_ERR)
            self.rec_label.config(text="● 录制中 0.0s")
            # 2秒后自动停止
            self.root.after(2000, self._auto_stop_record)
        else:
            self._stop_record()

    def _auto_stop_record(self):
        if self.recording:
            self._stop_record()

    def _stop_record(self):
        self.recording = False
        self.rec_btn.config(text="🏀 投篮记录", bg=CLR_REC)
        elapsed = time.time() - self.rec_start
        self.rec_label.config(text=f"已录制 {elapsed:.1f}s")

        if len(self.record_buffer) < 5:
            self.rec_label.config(text="录制时间过短，丢弃")
            return

        # 保存记录
        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"shot_{ts_str}.json"
        filepath = os.path.join(RECORDS_DIR, filename)
        record_data = {
            "timestamp": ts_str,
            "duration": elapsed,
            "frames": self.record_buffer,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(record_data, f, ensure_ascii=False, indent=2)

        self.rec_label.config(text=f"✅ 已保存 {filename}")
        self._refresh_records_list()

        # 3秒后清除提示
        self.root.after(3000, lambda: self.rec_label.config(text=""))

    # ==================== 回放分析窗口 ====================
    def _open_playback(self):
        win = tk.Toplevel(self.root)
        win.title("📂 投篮记录回放分析")
        win.configure(bg=BG_DARK)
        win.geometry("1100x820")
        win.resizable(False, False)

        # 左侧：记录列表
        left = tk.Frame(win, bg=BG_DARK, width=250)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        left.pack_propagate(False)

        tk.Label(left, text="记录列表",
                 font=("Microsoft YaHei", 14, "bold"),
                 fg=CLR_GOLD, bg=BG_DARK).pack(anchor="w", pady=(0, 8))

        listbox_frame = tk.Frame(left)
        listbox_frame.pack(fill=tk.BOTH, expand=True)
        scrollbar = tk.Scrollbar(listbox_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.rec_listbox = tk.Listbox(listbox_frame, bg=BG_CARD, fg=CLR_TEXT,
                                       font=("Microsoft YaHei", 11),
                                       selectbackground="#3355aa",
                                       yscrollcommand=scrollbar.set)
        self.rec_listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.rec_listbox.yview)

        # 删除按钮
        tk.Button(left, text="🗑 删除选中", font=("Microsoft YaHei", 11),
                  fg="#fff", bg="#883333", relief=tk.FLAT,
                  command=lambda: self._delete_selected_record()).pack(fill=tk.X, pady=(8, 0))

        # 右侧：分析画布
        right = tk.Frame(win, bg=BG_DARK)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        tk.Label(right, text="📊 轨迹分析",
                 font=("Microsoft YaHei", 14, "bold"),
                 fg=CLR_GOLD, bg=BG_DARK).pack(anchor="w", pady=(0, 8))

        # 分析画布 — 翻滚角曲线
        tk.Label(right, text="翻滚角变化 (主要指标)",
                 font=("Microsoft YaHei", 11, "bold"),
                 fg=CLR_ARC, bg=BG_DARK).pack(anchor="w")
        self.roll_chart = tk.Canvas(right, width=780, height=240,
                                     bg=BG_CANVAS, highlightthickness=1,
                                     highlightbackground="#333")
        self.roll_chart.pack(fill=tk.X, pady=(2, 8))

        # 分析画布 — 俯仰角曲线
        tk.Label(right, text="俯仰角变化",
                 font=("Microsoft YaHei", 11, "bold"),
                 fg=CLR_OK, bg=BG_DARK).pack(anchor="w")
        self.pitch_chart = tk.Canvas(right, width=780, height=240,
                                      bg=BG_CANVAS, highlightthickness=1,
                                      highlightbackground="#333")
        self.pitch_chart.pack(fill=tk.X, pady=(2, 8))

        # 分析摘要
        self.analysis_label = tk.Label(right, text="请选择一条记录进行分析",
                                        font=("Microsoft YaHei", 12),
                                        fg="#888", bg=BG_DARK, anchor="w",
                                        justify=tk.LEFT, wraplength=580)
        self.analysis_label.pack(fill=tk.X, pady=(8, 0))

        # 填充列表
        self._refresh_records_list()
        for fn in self.records_list:
            self.rec_listbox.insert(tk.END, fn)

        # 选择事件
        self.rec_listbox.bind("<<ListboxSelect>>",
                               lambda e: self._on_record_select(win))

    def _refresh_records_list(self):
        self.records_list = sorted(
            [f for f in os.listdir(RECORDS_DIR) if f.endswith(".json")],
            reverse=True
        )

    def _delete_selected_record(self):
        sel = self.rec_listbox.curselection()
        if not sel:
            return
        fn = self.rec_listbox.get(sel[0])
        filepath = os.path.join(RECORDS_DIR, fn)
        if os.path.exists(filepath):
            os.remove(filepath)
        self.rec_listbox.delete(sel[0])
        self._refresh_records_list()

    def _on_record_select(self, win):
        sel = self.rec_listbox.curselection()
        if not sel:
            return
        fn = self.rec_listbox.get(sel[0])
        filepath = os.path.join(RECORDS_DIR, fn)
        if not os.path.exists(filepath):
            return
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        frames = data["frames"]
        self._draw_analysis_charts(frames)

    def _draw_analysis_charts(self, frames):
        rc = self.roll_chart
        pc = self.pitch_chart
        rc.delete("all")
        pc.delete("all")

        if not frames:
            return

        # 提取数据
        ts0 = frames[0]["ts"]
        times = [f["ts"] - ts0 for f in frames]

        # 翻滚角数据
        up_roll = [f["UPPERARM"]["r"] if f.get("UPPERARM") else 0 for f in frames]
        fp_roll = [f["FOREARM"]["r"] if f.get("FOREARM") else 0 for f in frames]
        wp_roll = [f["WRIST"]["r"] if f.get("WRIST") else 0 for f in frames]

        # 俯仰角数据
        up_pitch = [f["UPPERARM"]["p"] if f.get("UPPERARM") else 0 for f in frames]
        fp_pitch = [f["FOREARM"]["p"] if f.get("FOREARM") else 0 for f in frames]
        wp_pitch = [f["WRIST"]["p"] if f.get("WRIST") else 0 for f in frames]

        # 卡尔曼滤波
        up_roll_k  = kalman_filter(up_roll)
        fp_roll_k  = kalman_filter(fp_roll)
        wp_roll_k  = kalman_filter(wp_roll)
        up_pitch_k = kalman_filter(up_pitch)
        fp_pitch_k = kalman_filter(fp_pitch)
        wp_pitch_k = kalman_filter(wp_pitch)

        t_max = max(times) if times else 2.0

        # ---- 翻滚角图表 ----
        self._draw_chart(rc, times, [
            ("大臂翻滚", up_roll, "#663333"),
            ("小臂翻滚(原始)", fp_roll, "#553333"),
            ("手背翻滚(原始)", wp_roll, "#443322"),
            ("大臂翻滚(KF)", up_roll_k, "#ff6666"),
            ("小臂翻滚(KF)", fp_roll_k, CLR_ERR),
            ("手背翻滚(KF)", wp_roll_k, "#ff8844"),
        ], t_max, "翻滚角(°)", y_range=(-45, 45))

        # ---- 俯仰角图表 ----
        self._draw_chart(pc, times, [
            ("大臂俯仰(原始)", up_pitch, "#1a3355"),
            ("小臂俯仰(原始)", fp_pitch, "#1a3344"),
            ("手背俯仰(原始)", wp_pitch, "#1a4433"),
            ("大臂俯仰(KF)", up_pitch_k, "#66aaff"),
            ("小臂俯仰(KF)", fp_pitch_k, CLR_OK),
            ("手背俯仰(KF)", wp_pitch_k, "#44ddaa"),
        ], t_max, "俯仰角(°)", y_range=(-30, 200))

        # ---- 分析摘要 ----
        self._compute_analysis(frames)

    def _draw_chart(self, canvas, times, series, t_max, y_label, y_range=(-45, 45)):
        cw = int(canvas.cget("width"))
        ch = int(canvas.cget("height"))
        margin_l, margin_r, margin_t, margin_b = 50, 20, 20, 45
        pw = cw - margin_l - margin_r
        ph = ch - margin_t - margin_b

        y_min, y_max = y_range

        # 网格线
        for y_val in range(int(y_min), int(y_max) + 1, 15):
            y_px = margin_t + ph * (1 - (y_val - y_min) / (y_max - y_min))
            canvas.create_line(margin_l, y_px, cw - margin_r, y_px,
                               fill="#1a1a3a", width=1)
            canvas.create_text(margin_l - 5, y_px, text=f"{y_val}°",
                               fill="#556677", font=("Microsoft YaHei", 8), anchor="e")

        # 0°参考线
        if y_min <= 0 <= y_max:
            y0 = margin_t + ph * (1 - (0 - y_min) / (y_max - y_min))
            canvas.create_line(margin_l, y0, cw - margin_r, y0,
                               fill="#334455", width=2, dash=(4, 3))

        # 时间轴
        for t in [0, 0.5, 1.0, 1.5, 2.0]:
            if t <= t_max:
                x_px = margin_l + pw * (t / t_max)
                canvas.create_line(x_px, margin_t, x_px, ch - margin_b,
                                   fill="#1a1a3a", width=1)
                canvas.create_text(x_px, ch - margin_b + 12, text=f"{t:.1f}s",
                                   fill="#556677", font=("Microsoft YaHei", 8))

        # 绘制曲线
        for name, values, color in series:
            points = []
            for i, (t, v) in enumerate(zip(times, values)):
                x_px = margin_l + pw * (t / t_max)
                y_px = margin_t + ph * (1 - (v - y_min) / (y_max - y_min))
                y_px = max(margin_t, min(ch - margin_b, y_px))
                points.append((x_px, y_px))
            if len(points) > 1:
                flat = []
                for p in points:
                    flat.extend(p)
                canvas.create_line(*flat, fill=color, width=2, smooth=True)

        # 图例（3列2行）
        for i, (name, _, color) in enumerate(series):
            row = i // 3
            col = i % 3
            lx = margin_l + col * 200
            ly = ch - 28 + row * 16
            canvas.create_line(lx, ly, lx + 20, ly, fill=color, width=2)
            canvas.create_text(lx + 24, ly, text=name,
                               fill=color, font=("Microsoft YaHei", 8), anchor="w")

    def _compute_analysis(self, frames):
        """分析翻滚角偏移和俯仰角变化（使用卡尔曼滤波后数据）"""
        if not frames:
            return

        summary_parts = []

        for nid, label in [("UPPERARM", "大臂"), ("FOREARM", "小臂"), ("WRIST", "手背")]:
            rolls = [f[nid]["r"] for f in frames if f.get(nid)]
            pitchs = [f[nid]["p"] for f in frames if f.get(nid)]

            if not rolls:
                continue

            # 卡尔曼滤波
            rolls_k = kalman_filter(rolls)
            pitchs_k = kalman_filter(pitchs)

            # 翻滚角分析（滤波后）
            roll_avg = sum(rolls_k) / len(rolls_k)
            roll_max_dev = max(abs(r) for r in rolls_k)
            roll_std = (sum((r - roll_avg) ** 2 for r in rolls_k) / len(rolls_k)) ** 0.5

            # 俯仰角分析（滤波后）
            pitch_start = pitchs_k[0]
            pitch_end = pitchs_k[-1]
            pitch_range = max(pitchs_k) - min(pitchs_k)

            roll_ok = roll_max_dev <= 10

            summary_parts.append(
                f"【{label}】翻滚(KF): 均值{roll_avg:.1f}° 最大偏移{roll_max_dev:.1f}° 波动±{roll_std:.1f}° "
                f"{'✅' if roll_ok else '❌偏移过大'} | "
                f"俯仰(KF): {pitch_start:.1f}°→{pitch_end:.1f}° 变化幅度{pitch_range:.1f}°"
            )

        self.analysis_label.config(text="\n".join(summary_parts), fg=CLR_TEXT)

    # ---------- 绘制连杆 ----------
    def _draw_links(self, up_p, fore_p, wrist_p,
                    seg_colors, width, dash=(), joint_r=9):
        sx, sy = SHOULDER
        ex, ey = joint_pos(sx, sy, UPPER_LEN, up_p)
        wx, wy = joint_pos(ex, ey, FORE_LEN, fore_p)
        hx, hy = joint_pos(wx, wy, HAND_LEN, wrist_p)

        segs = [(sx, sy, ex, ey), (ex, ey, wx, wy), (wx, wy, hx, hy)]
        for i, (x1, y1, x2, y2) in enumerate(segs):
            self.canvas.create_line(x1, y1, x2, y2,
                                    fill=seg_colors[i], width=width,
                                    dash=dash, capstyle=tk.ROUND)
        for jx, jy in [(sx, sy), (ex, ey), (wx, wy)]:
            r = joint_r
            fill = CLR_GHOST if dash else CLR_JOINT
            self.canvas.create_oval(jx-r, jy-r, jx+r, jy+r,
                                    fill=fill, outline="")

    # ---------- 绘制角度弧 ----------
    def _draw_arc(self, cx, cy, from_angle, to_angle, radius, label=""):
        delta = to_angle - from_angle
        if abs(delta) < 2:
            return
        self.canvas.create_arc(cx - radius, cy - radius,
                               cx + radius, cy + radius,
                               start=from_angle, extent=delta,
                               style=tk.ARC, outline=CLR_ARC, width=2)
        if label:
            mid = from_angle + delta / 2
            lr = radius + 16
            lx = cx + lr * math.cos(math.radians(mid))
            ly = cy - lr * math.sin(math.radians(mid))
            self.canvas.create_text(lx, ly, text=label,
                                    fill=CLR_ARC,
                                    font=("Microsoft YaHei", 10, "bold"))

    # ---------- 小臂翻滚角特写 ----------
    def _draw_forearm_roll(self, all_data, results):
        c = self.roll_canvas
        c.delete("all")
        cx, cy = DETAIL_W // 2, DETAIL_H // 2 + 5
        R = 55

        c.create_oval(cx - R, cy - R, cx + R, cy + R,
                       outline="#333366", width=2)
        c.create_line(cx, cy - R - 10, cx, cy + R + 10,
                       fill=CLR_GHOST, width=2, dash=(5, 3))
        c.create_text(cx + R + 8, cy - R - 2, text="0°标准",
                       fill=CLR_GHOST, font=("Microsoft YaHei", 8), anchor="w")

        fd = all_data.get("FOREARM") if all_data else None
        if fd is not None:
            roll = fd.get("r", 0)
            fp_ok = results.get("FOREARM") and results["FOREARM"]["status"] == "✅ 标准"
            clr = CLR_OK if fp_ok else CLR_ERR

            rad = math.radians(roll)
            dx = R * math.sin(rad)
            dy = R * math.cos(rad)
            c.create_line(cx - dx, cy + dy, cx + dx, cy - dy,
                           fill=clr, width=4, capstyle=tk.ROUND)

            if abs(roll) > 2:
                c.create_arc(cx - R - 10, cy - R - 10,
                              cx + R + 10, cy + R + 10,
                              start=90, extent=-roll,
                              style=tk.ARC, outline=CLR_ARC, width=2)

            c.create_text(cx, cy + R + 22,
                           text=f"翻滚: {roll:.1f}°",
                           fill=clr, font=("Microsoft YaHei", 12, "bold"))
        else:
            c.create_text(cx, cy + R + 22, text="信号丢失",
                           fill="#555", font=("Microsoft YaHei", 10))

    # ---------- 手背角度特写 ----------
    def _draw_wrist_closeup(self, all_data, results):
        c = self.wrist_canvas
        c.delete("all")
        ox, oy = DETAIL_W // 2 - 20, DETAIL_H // 2 + 20
        seg_len = 110

        end_180_x = ox - seg_len - 20
        c.create_line(ox, oy, end_180_x, oy,
                       fill="#334455", width=1, dash=(4, 4))
        c.create_text(end_180_x - 5, oy, text="180°",
                       fill="#556677", font=("Microsoft YaHei", 8), anchor="e")

        end_90_y = oy - seg_len - 10
        c.create_line(ox, oy, ox, end_90_y,
                       fill="#334455", width=1, dash=(4, 4))
        c.create_text(ox - 5, end_90_y - 5, text="90°",
                       fill="#556677", font=("Microsoft YaHei", 8), anchor="e")

        std_hx, std_hy = joint_pos(ox, oy, seg_len, STD_WRIST_PITCH)
        c.create_line(ox, oy, std_hx, std_hy,
                       fill=CLR_GHOST, width=2, dash=(5, 3))
        c.create_text(std_hx + 8, std_hy - 8, text="标准",
                       fill=CLR_GHOST, font=("Microsoft YaHei", 8), anchor="w")

        c.create_oval(ox - 6, oy - 6, ox + 6, oy + 6,
                       fill=CLR_JOINT, outline="")

        wd = all_data.get("WRIST") if all_data else None
        if wd is not None:
            wp = wd.get("p", 0)
            wp_ok = results.get("WRIST") and results["WRIST"]["status"] == "✅ 标准"
            clr = CLR_OK if wp_ok else CLR_ERR

            cur_hx, cur_hy = joint_pos(ox, oy, seg_len, wp)
            c.create_line(ox, oy, cur_hx, cur_hy,
                           fill=clr, width=5, capstyle=tk.ROUND)

            if abs(wp) > 2:
                c.create_arc(ox - 35, oy - 35, ox + 35, oy + 35,
                              start=0, extent=wp,
                              style=tk.ARC, outline=CLR_ARC, width=2)

            c.create_text(cur_hx + 8, cur_hy - 5, text="手背",
                           fill=clr, font=("Microsoft YaHei", 9, "bold"), anchor="w")
            c.create_text(DETAIL_W // 2, DETAIL_H - 14,
                           text=f"俯仰: {wp:.1f}°",
                           fill=clr, font=("Microsoft YaHei", 12, "bold"))
        else:
            c.create_text(DETAIL_W // 2, DETAIL_H - 14, text="信号丢失",
                           fill="#555", font=("Microsoft YaHei", 10))

    # ---------- 绘制完整画面 ----------
    def _render_canvas(self, all_data, results):
        self.canvas.delete("all")

        sx, sy = SHOULDER
        self.canvas.create_line(sx, sy - 60, sx, sy + 120,
                                fill="#222244", width=3, dash=(6, 4))
        self.canvas.create_text(sx, sy - 72, text="肩",
                                fill="#555577", font=("Microsoft YaHei", 10))

        ghost_colors = [CLR_GHOST] * 3
        self._draw_links(STD_UPPERARM_PITCH, STD_FOREARM_PITCH, STD_WRIST_PITCH,
                         ghost_colors, width=3, dash=(8, 5), joint_r=5)

        _, sey = joint_pos(sx, sy, UPPER_LEN, STD_UPPERARM_PITCH)
        self.canvas.create_text(sx - 50, (sy + sey) / 2,
                                text="标准", fill=CLR_GHOST,
                                font=("Microsoft YaHei", 9), anchor="e")

        if all_data:
            up_p = all_data.get("UPPERARM", {}).get("p", 0)
            fp   = all_data.get("FOREARM",  {}).get("p", 0)
            wp   = all_data.get("WRIST",    {}).get("p", 0)

            up_ok = results.get("UPPERARM") and results["UPPERARM"]["status"] == "✅ 标准"
            fp_ok = results.get("FOREARM")  and results["FOREARM"]["status"]  == "✅ 标准"
            wp_ok = results.get("WRIST")    and results["WRIST"]["status"]    == "✅ 标准"

            seg_colors = [
                CLR_OK if up_ok else CLR_ERR,
                CLR_OK if fp_ok else CLR_ERR,
                CLR_OK if wp_ok else CLR_ERR,
            ]
            self._draw_links(up_p, fp, wp, seg_colors, width=9)

            ex, ey = joint_pos(sx, sy, UPPER_LEN, up_p)
            wx, wy = joint_pos(ex, ey, FORE_LEN, fp)

            self._draw_arc(sx, sy, 0, up_p, 40, f"{up_p:.0f}°")
            elbow = fp - up_p
            self._draw_arc(ex, ey, up_p, fp, 35, f"{elbow:.0f}°")
            self._draw_arc(wx, wy, fp, wp, 30, f"{wp - fp:.0f}°")

            mx, my = (sx + ex) / 2, (sy + ey) / 2
            self.canvas.create_text(mx + 30, my - 10, text="大臂",
                                    fill=seg_colors[0],
                                    font=("Microsoft YaHei", 10, "bold"))
            mx2, my2 = (ex + wx) / 2, (ey + wy) / 2
            self.canvas.create_text(mx2 + 30, my2, text="小臂",
                                    fill=seg_colors[1],
                                    font=("Microsoft YaHei", 10, "bold"))
            hx, hy = joint_pos(wx, wy, HAND_LEN, wp)
            self.canvas.create_text(hx + 10, hy - 15, text="手背",
                                    fill=seg_colors[2],
                                    font=("Microsoft YaHei", 10, "bold"))

            # 录制时画布边框变红
            if self.recording:
                self.canvas.create_rectangle(2, 2, CANVAS_W - 2, CANVAS_H - 2,
                                              outline=CLR_REC, width=3)
        else:
            self.canvas.create_text(CANVAS_W // 2, CANVAS_H // 2,
                                    text="等待传感器数据…",
                                    fill="#555",
                                    font=("Microsoft YaHei", 16))

        self.canvas.create_line(20, CANVAS_H - 35, 55, CANVAS_H - 35,
                                fill=CLR_GHOST, width=2, dash=(6, 4))
        self.canvas.create_text(60, CANVAS_H - 35, text="标准姿态",
                                fill=CLR_GHOST, anchor="w",
                                font=("Microsoft YaHei", 9))
        self.canvas.create_line(20, CANVAS_H - 15, 55, CANVAS_H - 15,
                                fill=CLR_OK, width=4)
        self.canvas.create_text(60, CANVAS_H - 15, text="当前姿态",
                                fill=CLR_TEXT, anchor="w",
                                font=("Microsoft YaHei", 9))

    # ---------- 更新纠正面板 ----------
    def _update_panel(self, all_data, results):
        all_ok = True
        for nid in ["UPPERARM", "FOREARM", "WRIST"]:
            c = self.cards[nid]
            res = results.get(nid)
            rule = RULES[nid]

            if res is None:
                c["status"].config(text="⚠️ 信号丢失", fg="#888")
                c["angle"].config(text="俯仰: --   翻滚: --")
                c["tip"].config(text="等待传感器数据…", fg="#888")
                c["frame"].config(bg=BG_CARD)
                all_ok = False
                continue

            ok = res["status"] == "✅ 标准"
            if not ok:
                all_ok = False

            c["status"].config(text="✅ 标准" if ok else "❌ 偏差",
                               fg=CLR_OK if ok else CLR_ERR)

            if rule.pitch_relative and "elbow_angle" in res:
                atxt = f"弯曲: {res['elbow_angle']:.1f}°   翻滚: {res['roll']:.1f}°"
            else:
                atxt = f"俯仰: {res['pitch']:.1f}°   翻滚: {res['roll']:.1f}°"
            c["angle"].config(text=atxt)

            if ok:
                c["tip"].config(text="✓ 姿态良好", fg=CLR_OK)
                c["frame"].config(bg=BG_OK)
            else:
                c["tip"].config(text=res["brief"], fg=CLR_ERR)
                c["frame"].config(bg=BG_ERR)

        if all_ok and results:
            self.overall.config(text="✅ 投篮姿态标准", fg=CLR_OK)
        elif results:
            self.overall.config(text="❌ 请调整姿态", fg=CLR_ERR)
        else:
            self.overall.config(text="⏳ 等待传感器…", fg="#888")

    # ---------- 主循环 ----------
    def _tick(self):
        all_data = {}
        for nid in ["UPPERARM", "FOREARM", "WRIST"]:
            d = self.hub.get(nid)
            if d is not None:
                all_data[nid] = d

        # 录制中则采集数据
        if self.recording:
            frame = {"ts": time.time()}
            for nid in ["UPPERARM", "FOREARM", "WRIST"]:
                d = all_data.get(nid)
                if d:
                    frame[nid] = {"p": d["p"], "r": d["r"], "y": d["y"]}
                else:
                    frame[nid] = None
            self.record_buffer.append(frame)
            elapsed = time.time() - self.rec_start
            self.rec_label.config(text=f"● 录制中 {elapsed:.1f}s")

        results = {}
        for nid in ["UPPERARM", "FOREARM", "WRIST"]:
            rule = RULES[nid]
            d = all_data.get(nid)
            if d is None:
                results[nid] = None
                continue
            ref = 0.0
            if rule.pitch_relative and rule.pitch_relative_to in all_data:
                ref = all_data[rule.pitch_relative_to]["p"]
            elif rule.pitch_relative:
                results[nid] = None
                continue
            results[nid] = self.coach.analyze(nid, d["p"], d["r"], ref)

        self._render_canvas(all_data, results)
        self._update_panel(all_data, results)
        self._draw_forearm_roll(all_data, results)
        self._draw_wrist_closeup(all_data, results)

        self.root.after(50, self._tick)

    def run(self):
        try:
            self.root.mainloop()
        finally:
            self.hub.stop()


if __name__ == "__main__":
    PostureUI().run()
