<div align="center">

# 🎯 WitMotion Sensor Toolkit

**维特智能（WitMotion）陀螺仪传感器 Python SDK & ESP32 固件**

<p>
  <img src="https://img.shields.io/badge/Python-3.6+-blue?logo=python" alt="Python 3.6+">
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20ESP32-green" alt="Platform">
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License">
</p>

<p>
  <b>支持 JY901S / JY931 / WT901C485 等 6/9 轴倾角传感器</b>
</p>

</div>

---

## 📑 目录

- [✨ 功能特性](#-功能特性)
- [📁 项目结构](#-项目结构)
- [🚀 快速开始](#-快速开始)
- [💻 Python SDK](#-python-sdk)
  - [基础数据读取](#基础数据读取)
  - [可视化应用](#可视化应用)
  - [诊断工具](#诊断工具)
  - [SDK 核心架构](#sdk-核心架构)
- [📡 ESP32 无线网关](#-esp32-无线网关)
- [⚙️ 串口配置参考](#️-串口配置参考)
- [📚 参考资料](#-参考资料)

---

## ✨ 功能特性

<table>
<tr>
<td width="50%">

### 🐍 Python 部分
- 串口通信 SDK（维特协议 + RS485/Modbus）
- JY931 3D 姿态可视化
- 投篮姿势纠正系统
- 原始数据诊断工具

</td>
<td width="50%">

### 📡 ESP32 部分
- WiFi 热点 + Web 服务器
- 实时欧拉角展示
- 响应式 Web 页面
- 零配置即用

</td>
</tr>
</table>

---

## 📁 项目结构

```
📦 Python-WitProtocol/
├── 📂 chs/
│   ├── 📂 lib/                          # 核心 SDK 库
│   │   ├── 📄 device_model.py           # 设备模型（串口管理）
│   │   ├── 📂 data_processor/roles/
│   │   │   └── 📄 jy901s_dataProcessor.py
│   │   ├── 📂 protocol_resolver/roles/
│   │   │   ├── 📄 wit_protocol_resolver.py    # 维特标准协议
│   │   │   └── 📄 protocol_485_resolver.py    # RS485/Modbus
│   │   └── 📂 utils/
│   │       └── 📄 byte_array_converter.py
│   ├── 📄 JY901S.py                     # JY901S 基础示例
│   ├── 📄 WT901C485.py                  # RS485 传感器示例
│   ├── 📄 test_jy931.py                 # JY931 测试脚本
│   ├── 📄 jy931_visualizer.py           # 3D 可视化程序 ⭐
│   ├── 📄 shooting_posture_corrector.py # 投篮姿势纠正 ⭐
│   ├── 📄 diagnose.py                   # 数据诊断工具
│   └── 📄 test_raw.py                   # 原始数据测试
│
📦 ESP32CODE/
└── 📄 main.ino                          # ESP32 WiFi 网关固件
```

---

## 🚀 快速开始

### 环境准备

```bash
# 安装依赖
python -m pip install pyserial
```

> 💡 多 Python 版本环境建议使用 `python -m pip`，确保安装到正确的环境。

### 运行示例

```bash
cd Python-WitProtocol/chs

# 基础数据读取
python JY901S.py

# 3D 可视化（推荐）
python jy931_visualizer.py

# 投篮姿势纠正系统
python shooting_posture_corrector.py
```

---

## 💻 Python SDK

### 基础数据读取

```python
import lib.device_model as deviceModel
from lib.data_processor.roles.jy901s_dataProcessor import JY901SDataProcessor
from lib.protocol_resolver.roles.wit_protocol_resolver import WitProtocolResolver

# ── 初始化设备 ──
device = deviceModel.DeviceModel(
    "JY901S", WitProtocolResolver(), JY901SDataProcessor(), "51_0"
)
device.serialConfig.portName = "COM3"
device.serialConfig.baud = 115200
device.openDevice()

# ── 数据回调 ──
def onUpdate(dm):
    print(f"Roll={dm.getDeviceData('angleX'):.1f}°  "
          f"Pitch={dm.getDeviceData('angleY'):.1f}°  "
          f"Yaw={dm.getDeviceData('angleZ'):.1f}°")

device.dataProcessor.onVarChanged.append(onUpdate)
input()
device.closeDevice()
```

### 可视化应用

#### 🎮 JY931 3D 可视化 — `jy931_visualizer.py`

| 特性 | 说明 |
|:-----|:-----|
| 3D 立方体 | 随传感器姿态实时旋转 |
| 欧拉角 | Roll / Pitch / Yaw 数值 + 进度条 |
| 帧率统计 | 实时帧率 + 平均帧率 + 帧类型计数 |
| 历史曲线 | 三轴角度变化趋势图 |

#### 🏀 投篮姿势纠正系统 — `shooting_posture_corrector.py`

<div align="center">

| 功能 | 描述 |
|:-----|:-----|
| 姿态检测 | 实时监测 Roll / Pitch 角度 |
| 阈值纠正 | ±15° 可调阈值触发震动 |
| 四向震动 | 上/下/左/右方向可视化 |
| 统计面板 | 正确率、纠正次数统计 |

</div>

### 诊断工具

| 工具 | 用途 |
|:-----|:-----|
| `diagnose.py` | 分析串口原始帧，验证 0x55 协议完整性 |
| `test_raw.py` | 原始数据读取 + Modbus CRC16 校验 |

### SDK 核心架构

```
┌─────────────────────────────────────────────────────┐
│                    DeviceModel                       │
│            串口管理 · 数据收发 · 寄存器读写            │
├──────────────────────┬──────────────────────────────┤
│  WitProtocolResolver │   Protocol485Resolver        │
│     维特标准协议      │      RS485/Modbus 协议        │
├──────────────────────┴──────────────────────────────┤
│              JY901SDataProcessor                     │
│    加速度 · 角速度 · 角度 · 磁场 · 四元数 · 温度      │
└─────────────────────────────────────────────────────┘
```

### 传感器数据 Key

| 数据类型 | Key | 单位 |
|:---------|:----|:-----|
| 芯片时间 | `Chiptime` | — |
| 温度 | `temperature` | °C |
| 加速度 | `accX` / `accY` / `accZ` | g |
| 角速度 | `gyroX` / `gyroY` / `gyroZ` | °/s |
| 角度 | `angleX` / `angleY` / `angleZ` | ° |
| 磁场 | `magX` / `magY` / `magZ` | — |
| 四元数 | `q1` / `q2` / `q3` / `q4` | — |
| 经纬度 | `lon` / `lat` | — |
| 航向角 | `Yaw` | ° |
| 地速 | `Speed` | — |

### 设备配置

```python
# ── 读取配置 ──
tVals = device.readReg(0x02, 3)    # 数据内容 / 回传速率 / 通讯速率

# ── 写入配置 ──
device.unlock()                     # 解锁寄存器
device.writeReg(0x03, 6)           # 设置回传速率 10Hz
device.writeReg(0x23, 0)           # 设置安装方向
device.save()                       # 保存配置

# ── 传感器校准 ──
device.AccelerationCalibration()    # 加计校准
device.BeginFiledCalibration()      # 开始磁场校准
device.EndFiledCalibration()        # 结束磁场校准
```

---

## 📡 ESP32 无线网关

### 功能介绍

ESP32 固件将 YJ931 传感器数据通过 **WiFi 热点** 以 Web 页面实时展示，手机/电脑连接 WiFi 即可查看，无需安装任何软件。

**核心特性：**
- 📶 创建 WiFi 热点 `YJ931-IMU` / 密码 `12345678`
- 🌐 内置 Web 服务器，响应式页面 100ms 刷新
- 📊 展示 Roll / Pitch / Yaw + 时间戳 + 温度

### 硬件接线

<table>
<tr>
<th>ESP32 引脚</th>
<th>YJ931 引脚</th>
<th>说明</th>
</tr>
<tr>
<td>GPIO 12</td>
<td>TX</td>
<td>ESP32 RX（接收数据）</td>
</tr>
<tr>
<td>GPIO 13</td>
<td>RX</td>
<td>ESP32 TX（发送指令）</td>
</tr>
<tr>
<td>3.3V</td>
<td>VCC</td>
<td>供电</td>
</tr>
<tr>
<td>GND</td>
<td>GND</td>
<td>共地</td>
</tr>
</table>

### 使用步骤

```
1. 烧录固件 → Arduino IDE 打开 main.ino，编译上传
2. 连接硬件 → 按接线表连接 ESP32 与 YJ931
3. 上电启动 → ESP32 自动创建 WiFi 热点
4. 访问页面 → 连接 WiFi 后浏览器打开 http://192.168.4.1
```

### 自定义配置

```cpp
#define WIFI_SSID       "YJ931-IMU"     // WiFi 名称
#define WIFI_PASSWORD   "12345678"      // WiFi 密码
#define YJ931_BAUD      921600          // 传感器波特率
#define YJ931_RX_PIN    12              // RX 引脚
#define YJ931_TX_PIN    13              // TX 引脚
```

---

## ⚙️ 串口配置参考

| 设备型号 | 默认波特率 | 协议 | Windows | Linux |
|:---------|:-----------|:-----|:--------|:------|
| JY901S | 115200 | 维特标准协议 | COMx | /dev/ttyUSB0 |
| JY931 | 921600 / 9600 | 维特标准协议 | COMx | /dev/ttyUSB0 |
| WT901C485 | 9600 | RS485/Modbus | COMx | /dev/ttyUSB0 |

> 💡 Windows 用户可在 **设备管理器 → 端口** 中查看 COM 口编号。

---

## 📚 参考资料

- 📖 [维特智能官方教程](https://blog.csdn.net/Fred_1986/article/details/114415548)
- 🎬 [视频教程 - Bilibili](https://www.bilibili.com/video/BV1bV411v7Bm/)
- 🏠 [维特智能官网](https://wit-motion.yuque.com/wit-motion)
- 📘 [Python SDK 快速上手](https://wit-motion.yuque.com/wumwnr/ltst03/asds5m)

---

<div align="center">

**本项目基于维特智能官方示例程序修改扩展，仅供学习和研究使用。**

</div>
