import socket
import json
import time
import threading
from dataclasses import dataclass
from typing import List, Optional, Tuple

# ========== 配置：投篮姿态标准库（按部位定制检测项） ==========
@dataclass
class JointRule:
    name: str           # 中文名
    check_pitch: bool   # 是否检测俯仰角
    check_roll: bool    # 是否检测翻滚角
    pitch_min: float
    pitch_max: float
    roll_min: float
    roll_max: float
    pitch_tip: str      # 俯仰角异常提示
    roll_tip: str       # 翻滚角异常提示
    pitch_relative: bool = False       # 俯仰角是否为相对检查
    pitch_relative_to: str = ""        # 相对于哪个节点的俯仰（如 "UPPERARM"）
    pitch_ranges: List[Tuple[float, float]] = None  # 多段有效范围，如 [(150,190),(-185,-160)]

# ★★★ 俯仰/翻滚交换开关 ★★★
# YJ931 绑在身体上后，传感器X/Y轴方向可能与人体动作不一致
# 用 raw_view.py 标定：做大臂上抬→看是 p 还是 r 在变；做小臂倾斜同理
# 如果发现物理动作对应的角度字段反了，把对应节点改为 True
SWAP_PR = {
    "WRIST":    True,   # 压腕时，如果 r 在变而非 p → 改 True
    "FOREARM":  True,   # 小臂倾斜时，如果 p 在变而非 r → 改 True
    "UPPERARM": True,   # 大臂上抬时，如果 r 在变而非 p → 改 True
}

# 阈值根据实际佩戴方向微调，这里给一套通用基准
RULES = {
    "UPPERARM": JointRule(
        name="大臂",
        check_pitch=True,
        check_roll=True,
        pitch_min=-10, pitch_max=180,      # 大臂俯仰 -10°~180°
        roll_min=-10, roll_max=10,        # 翻滚 ±10°
        pitch_tip="大臂抬升角度不当，应保持-10°~180°",
        roll_tip="大臂左右偏移，请夹紧大臂"
    ),
    "FOREARM": JointRule(
        name="小臂",
        check_pitch=True,
        check_roll=True,
        pitch_min=40, pitch_max=110,       # 肘关节弯曲角 = 小臂俯仰 - 大臂俯仰
        roll_min=-10, roll_max=10,        # 翻滚 ±10°
        pitch_tip="肘部弯曲角度不当，应保持40°~110°",
        roll_tip="小臂左右倾斜，请保持小臂竖直",
        pitch_relative=True,
        pitch_relative_to="UPPERARM"      # 相对大臂的俯仰
    ),
    "WRIST": JointRule(
        name="手背(压腕)",
        check_pitch=True,
        check_roll=True,
        pitch_min=150, pitch_max=190,     # 手背俯仰 150°~190° 或 -185°~-160°
        roll_min=-10, roll_max=10,        # 翻滚 ±10°
        pitch_tip="压腕角度不足，出手后手腕未充分下压",
        roll_tip="手背侧翻过度",
        pitch_ranges=[(150, 190), (-185, -160)]  # 两段有效范围
    ),
}

# ========== UDP 接收器 ==========
class SensorHub:
    def __init__(self, port=8888):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("0.0.0.0", port))
        self.sock.settimeout(1.0)
        self.data = {k: {"p": 0.0, "r": 0.0, "y": 0.0, "ts": 0} for k in RULES.keys()}
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self):
        while self.running:
            try:
                buf, addr = self.sock.recvfrom(1024)
                msg = json.loads(buf.decode())
                node_id = msg.get("id")
                if node_id in self.data:
                    p_val = msg.get("p", 0)
                    r_val = msg.get("r", 0)
                    # ★ 如果传感器安装方向导致 p/r 反了，在此交换
                    if SWAP_PR.get(node_id, False):
                        p_val, r_val = r_val, p_val
                    self.data[node_id] = {
                        "p": p_val,
                        "r": r_val,
                        "y": msg.get("y", 0),
                        "ts": time.time()
                    }
            except (socket.timeout, json.JSONDecodeError):
                pass

    def get(self, node_id):
        d = self.data[node_id]
        if time.time() - d["ts"] > 2.0:
            return None
        return d

    def stop(self):
        self.running = False
        self.sock.close()

# ========== 姿态纠正引擎（按部位定制） ==========
class PoseCoach:
    def analyze(self, node_id: str, pitch: float, roll: float, ref_pitch: float = 0.0):
        rule = RULES[node_id]
        errors: List[str] = []
        status = "✅ 标准"
        
        # 俯仰角判定
        if rule.check_pitch:
            if rule.pitch_relative:
                # ★ 相对检查：小臂俯仰 - 大臂俯仰 = 肘关节弯曲角
                elbow_angle = pitch - ref_pitch
                if elbow_angle < rule.pitch_min:
                    errors.append(f"【俯仰】{rule.pitch_tip} (当前弯曲{elbow_angle:.1f}° < {rule.pitch_min}°)")
                elif elbow_angle > rule.pitch_max:
                    errors.append(f"【俯仰】{rule.pitch_tip} (当前弯曲{elbow_angle:.1f}° > {rule.pitch_max}°)")
            else:
                # 绝对检查
                if rule.pitch_ranges:
                    # ★ 多段有效范围：命中任意一段即合格
                    in_any = any(lo <= pitch <= hi for lo, hi in rule.pitch_ranges)
                    if not in_any:
                        ranges_str = " 或 ".join(f"{lo}°~{hi}°" for lo, hi in rule.pitch_ranges)
                        errors.append(f"【俯仰】{rule.pitch_tip} (当前{pitch:.1f}°，应在{ranges_str})")
                else:
                    if pitch < rule.pitch_min:
                        errors.append(f"【俯仰】{rule.pitch_tip} (当前{pitch:.1f}° < {rule.pitch_min}°)")
                    elif pitch > rule.pitch_max:
                        errors.append(f"【俯仰】{rule.pitch_tip} (当前{pitch:.1f}° > {rule.pitch_max}°)")
        
        # 翻滚角判定
        if rule.check_roll:
            if roll < rule.roll_min:
                errors.append(f"【翻滚】{rule.roll_tip} (当前{roll:.1f}° < {rule.roll_min}°)")
            elif roll > rule.roll_max:
                errors.append(f"【翻滚】{rule.roll_tip} (当前{roll:.1f}° > {rule.roll_max}°)")
        
        if errors:
            status = "❌ 姿态偏差"
        
        # 返回结果（相对模式时额外返回肘关节角）
        result = {
            "node": node_id,
            "name": rule.name,
            "status": status,
            "pitch": pitch,
            "roll": roll,
            "errors": errors,
            "brief": "；".join(errors) if errors else "姿态良好"
        }
        if rule.pitch_relative:
            result["elbow_angle"] = pitch - ref_pitch
        return result

# ========== 终端实时看板 ==========
def print_dashboard(hub: SensorHub, coach: PoseCoach):
    print("\033[2J\033[H", end="")  # 清屏
    print("=" * 65)
    print("      🏀 投篮姿态实时监测 — 大臂 | 小臂 | 压腕")
    print("=" * 65)
    
    # 先获取所有节点数据
    all_data = {}
    for node_id in ["UPPERARM", "FOREARM", "WRIST"]:
        d = hub.get(node_id)
        if d is not None:
            all_data[node_id] = d
    
    for node_id in ["UPPERARM", "FOREARM", "WRIST"]:
        rule = RULES[node_id]
        d = all_data.get(node_id)
        
        if d is None:
            print(f"\n【{rule.name}】 ⚠️  信号丢失")
            continue
        
        # ★ 小臂需要大臂俯仰作为参考
        ref_pitch = 0.0
        if rule.pitch_relative and rule.pitch_relative_to in all_data:
            ref_pitch = all_data[rule.pitch_relative_to]["p"]
        elif rule.pitch_relative and rule.pitch_relative_to not in all_data:
            print(f"\n【{rule.name}】 ⚠️  参考节点({rule.pitch_relative_to})信号丢失，无法判定")
            continue
        
        result = coach.analyze(node_id, d["p"], d["r"], ref_pitch)
        color = "\033[32m" if result["status"] == "✅ 标准" else "\033[31m"
        reset = "\033[0m"
        
        # 显示角度
        if rule.pitch_relative:
            elbow = result.get("elbow_angle", 0)
            p_display = f"弯曲{elbow:6.1f}° (小臂{d['p']:.1f}° - 大臂{ref_pitch:.1f}°)"
        else:
            p_display = f"{d['p']:7.2f}°"
        r_display = f"{d['r']:7.2f}°"
        
        print(f"\n【{rule.name}】 {color}{result['status']}{reset}")
        print(f"   俯仰角: {p_display}  |  翻滚角: {r_display}")
        print(f"   💡 {result['brief']}")
    
    print("\n" + "=" * 65)
    print("按 Ctrl+C 退出")

# ========== 主程序 ==========
if __name__ == "__main__":
    hub = SensorHub(port=8888)
    coach = PoseCoach()
    
    print("等待 ESP32 节点接入... (UPPERARM/FOREARM/WRIST)")
    try:
        while True:
            print_dashboard(hub, coach)
            time.sleep(0.05)
    except KeyboardInterrupt:
        hub.stop()
        print("\n系统已关闭")