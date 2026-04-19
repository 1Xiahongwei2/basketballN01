# WitMotion Sensor Toolkit

> 维特智能（WitMotion）陀螺仪传感器 Python SDK & ESP32 固件 & 应用示例
>
> 支持 JY901S / JY931 / WT901C485 等 6/9 轴倾角传感器

---

## 目录

- [项目概览](#项目概览)
- [项目结构](#项目结构)
- [环境准备](#环境准备)
- [快速开始](#快速开始)
- [Python SDK](#python-sdk)
  - [基础数据读取](#基础数据读取)
  - [可视化应用](#可视化应用)
  - [诊断工具](#诊断工具)
  - [SDK 核心架构](#sdk-核心架构)
- [ESP32 无线网关](#esp32-无线网关)
  - [功能介绍](#功能介绍)
  - [硬件接线](#硬件接线)
  - [使用方式](#使用方式)
- [串口配置参考](#串口配置参考)
- [参考资料](#参考资料)

---

## 项目概览

本项目包含两个核心部分：

| 模块 | 语言 | 说明 |
|:-----|:-----|:-----|
| **Python-WitProtocol** | Python | 传感器串口通信 SDK、数据可视化与投篮姿势纠正系统 |
| **ESP32CODE** | C++ (Arduino) | ESP32 无线网关固件，将传感器数据通过 WiFi 热点以 Web 页面实时展示 |

---

## 项目结构

```
.
├── Python-WitProtocol/
│   └── chs/
│       ├── lib/                                    # 核心 SDK 库
│       │   ├── device_model.py                     # 设备模型（串口管理、数据读写）
│       │   ├── data_processor/roles/
│       │   │   └── jy901s_dataProcessor.py         # JY901S 数据处理器
│       │   ├── protocol_resolver/roles/
│       │   │   ├── wit_protocol_resolver.py        # 维特标准协议解析器
│       │   │   └── protocol_485_resolver.py        # RS485/Modbus 协议解析器
│       │   └── utils/
│       │       └── byte_array_converter.py         # 字节数组转换工具
│       ├── JY901S.py                               # JY901S 传感器基础示例
│       ├── WT901C485.py                            # WT901C485 (RS485) 传感器示例
│       ├── test_jy931.py                           # JY931 测试脚本
│       ├── jy931_visualizer.py                     # JY931 3D 可视化程序
│       ├── shooting_posture_corrector.py           # 投篮姿势纠正系统
│       ├── diagnose.py                             # 串口原始数据诊断脚本
│       └── test_raw.py                             # 串口原始数据测试脚本
│
├── ESP32CODE/
│   └── main.ino                                    # ESP32 WiFi 网关固件
│
└── README.md
```

---

## 环境准备

### Python 环境

| 依赖 | 版本要求 | 安装命令 |
|:-----|:---------|:---------|
| Python | >= 3.6 | — |
| pyserial | 最新 | `python -m pip install pyserial` |

> **提示**：多 Python 版本共存时，请使用 `python -m pip install` 而非 `pip install`，确保安装到正确的 Python 环境。

### ESP32 环境

- Arduino IDE + ESP32 开发板支持
- 依赖库：`WiFi.h`、`WebServer.h`（ESP32 自带）

---

## 快速开始

```bash
# 1. 安装 Python 依赖
python -m pip install pyserial

# 2. 进入项目目录
cd Python-WitProtocol/chs

# 3. 选择一个示例运行
python JY901S.py                  # JY901S 基础数据读取
python test_jy931.py              # JY931 多波特率自动测试
python jy931_visualizer.py        # JY931 3D 可视化界面
python shooting_posture_corrector.py  # 投篮姿势纠正系统
```

---

## Python SDK

### 基础数据读取

以 JY901S 为例，最小化代码连接传感器并读取欧拉角：

```python
import lib.device_model as deviceModel
from lib.data_processor.roles.jy901s_dataProcessor import JY901SDataProcessor
from lib.protocol_resolver.roles.wit_protocol_resolver import WitProtocolResolver

# 初始化设备
device = deviceModel.DeviceModel(
    "JY901S", WitProtocolResolver(), JY901SDataProcessor(), "51_0"
)
device.serialConfig.portName = "COM3"
device.serialConfig.baud = 115200
device.openDevice()

# 数据更新回调
def onUpdate(dm):
    print(f"Roll={dm.getDeviceData('angleX'):.1f}°  "
          f"Pitch={dm.getDeviceData('angleY'):.1f}°  "
          f"Yaw={dm.getDeviceData('angleZ'):.1f}°")

device.dataProcessor.onVarChanged.append(onUpdate)
input()  # 按 Enter 退出
device.closeDevice()
```

### 可视化应用

#### JY931 3D 可视化 — `jy931_visualizer.py`

基于 tkinter 的实时 3D 姿态可视化程序：

- 3D 立方体随传感器姿态实时旋转
- 欧拉角（Roll / Pitch / Yaw）数值与进度条
- 实时帧率 + 平均帧率统计
- 帧类型计数（时间包 0x50 / 角度包 0x53）
- 角度变化历史曲线（三轴同屏）

#### 投篮姿势纠正系统 — `shooting_posture_corrector.py`

基于 JY931 陀螺仪 + 震动模块的实时投篮姿势纠正：

- **姿态检测** — 翻滚角（Roll）和俯仰角（Pitch）实时监测
- **阈值纠正** — 超过 ±15°（可调）时触发对应方向震动
- **四方向震动** — 上 / 下 / 左 / 右模块可视化
- **手臂俯视图** — 偏离点 + 方向箭头 + 阈值圆环
- **统计面板** — 正确次数、纠正次数、正确率
- **历史曲线** — Roll / Pitch 角度变化趋势

### 诊断工具

遇到传感器连接问题时，可使用以下工具排查：

| 脚本 | 用途 |
|:-----|:-----|
| `diagnose.py` | 分析串口原始数据帧，验证 0x55 帧头协议的帧完整性 |
| `test_raw.py` | 直接读取串口原始数据，支持 Modbus CRC16 校验，自动扫描多个设备地址 |

### SDK 核心架构

#### 核心模块

```
┌─────────────────────────────────────────────┐
│                 DeviceModel                  │
│          串口管理 · 数据收发 · 寄存器读写       │
├──────────────────┬──────────────────────────┤
│ WitProtocolResolver │ Protocol485Resolver    │
│  维特标准协议        │  RS485/Modbus 协议     │
├──────────────────┴──────────────────────────┤
│           JY901SDataProcessor               │
│   加速度 · 角速度 · 角度 · 磁场 · 四元数      │
└─────────────────────────────────────────────┘
```

#### 传感器数据 Key 对照表

| 类别 | Key | 单位 |
|:-----|:----|:-----|
| 芯片时间 | `Chiptime` | — |
| 温度 | `temperature` | °C |
| 加速度 | `accX` / `accY` / `accZ` | g |
| 角速度 | `gyroX` / `gyroY` / `gyroZ` | °/s |
| 角度 | `angleX` / `angleY` / `angleZ` | ° |
| 磁场 | `magX` / `magY` / `magZ` | — |
| 四元数 | `q1` / `q2` / `q3` / `q4` | — |
| 经度 / 纬度 | `lon` / `lat` | — |
| 航向角 | `Yaw` | ° |
| 地速 | `Speed` | — |

#### 设备配置操作

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

## ESP32 无线网关

### 功能介绍

`ESP32CODE/main.ino` 是一个运行在 ESP32 上的 Arduino 固件，将 YJ931 传感器数据通过 **WiFi 热点** 以 Web 页面实时展示，无需安装任何软件，手机 / 电脑连接 WiFi 即可查看。

**核心功能：**

- ESP32 创建 WiFi 热点（SSID: `YJ931-IMU`，密码: `12345678`）
- 通过 UART1 读取 YJ931 传感器数据
- 解析维特协议帧（0x55 帧头，校验和验证）
- 内置 Web 服务器，提供实时数据 API（`/api/data`）
- 精美响应式 Web 页面，100ms 自动刷新

**Web 页面展示内容：**

- 实时欧拉角（Roll / Pitch / Yaw）
- 传感器时间戳（日期 + 时间 + 毫秒）
- 芯片温度

### 硬件接线

| ESP32 引脚 | YJ931 引脚 | 说明 |
|:-----------|:-----------|:-----|
| GPIO 12 | TX | ESP32 RX（接收传感器数据） |
| GPIO 13 | RX | ESP32 TX（发送指令） |
| 3.3V | VCC | 供电 |
| GND | GND | 共地 |

### 使用方式

1. **烧录固件** — 使用 Arduino IDE 打开 `ESP32CODE/main.ino`，选择对应的 ESP32 开发板，编译并上传
2. **连接硬件** — 按上方接线表连接 ESP32 与 YJ931
3. **上电启动** — ESP32 自动创建 WiFi 热点 `YJ931-IMU`
4. **访问页面** — 手机或电脑连接该 WiFi，浏览器打开 `http://192.168.4.1`

> **自定义配置**：修改 `main.ino` 顶部的宏定义可调整 WiFi 名称、密码、波特率及引脚：
>
> ```cpp
> #define WIFI_SSID       "YJ931-IMU"     // WiFi 名称
> #define WIFI_PASSWORD   "12345678"      // WiFi 密码
> #define YJ931_BAUD      921600          // 传感器波特率
> #define YJ931_RX_PIN    12              // RX 引脚
> #define YJ931_TX_PIN    13              // TX 引脚
> ```

---

## 串口配置参考

| 设备型号 | 默认波特率 | 协议 | Windows 串口 | Linux 串口 |
|:---------|:-----------|:-----|:-------------|:-----------|
| JY901S | 115200 | 维特标准协议 | COMx | /dev/ttyUSB0 |
| JY931 | 921600 / 9600 | 维特标准协议 | COMx | /dev/ttyUSB0 |
| WT901C485 | 9600 | RS485/Modbus | COMx | /dev/ttyUSB0 |

> 请根据实际连接情况修改代码中的端口号和波特率。Windows 用户可在 **设备管理器 → 端口** 中查看 COM 口编号。

---

## 参考资料

- [维特智能官方教程](https://blog.csdn.net/Fred_1986/article/details/114415548)
- [视频教程 - Bilibili](https://www.bilibili.com/video/BV1bV411v7Bm/)
- [维特智能官网](https://wit-motion.yuque.com/wit-motion)
- [Python SDK 快速上手](https://wit-motion.yuque.com/wumwnr/ltst03/asds5m)

---

## 许可证

本项目基于维特智能官方示例程序修改扩展，仅供学习和研究使用。
