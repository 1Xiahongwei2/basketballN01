# Python-WitProtocol

维特智能（WitMotion）陀螺仪传感器 Python SDK 与应用示例，支持 JY901S、JY931、WT901C485 等型号的 6/9 轴倾角传感器，提供串口通信、协议解析、数据可视化及投篮姿势纠正等功能。

## 项目结构

```
Python-WitProtocol/
└── chs/
    ├── lib/                              # 核心 SDK 库
    │   ├── device_model.py               # 设备模型（串口管理、数据读写）
    │   ├── data_processor/
    │   │   └── roles/
    │   │       └── jy901s_dataProcessor.py   # JY901S 数据处理器
    │   ├── protocol_resolver/
    │   │   └── roles/
    │   │       ├── wit_protocol_resolver.py  # 维特标准协议解析器
    │   │       └── protocol_485_resolver.py  # RS485/Modbus 协议解析器
    │   └── utils/
    │       └── byte_array_converter.py       # 字节数组转换工具
    ├── JY901S.py                         # JY901S 传感器基础示例
    ├── WT901C485.py                      # WT901C485 (RS485) 传感器示例
    ├── test_jy931.py                     # JY931 测试脚本（多配置自动尝试）
    ├── jy931_visualizer.py               # JY931 陀螺仪 3D 可视化程序
    ├── shooting_posture_corrector.py      # 投篮姿势纠正系统
    ├── diagnose.py                       # 串口原始数据诊断脚本
    └── test_raw.py                       # 串口原始数据测试脚本
```

## 环境要求

- Python 3.6+
- pyserial

## 安装

```bash
# 安装依赖（多 Python 版本环境建议使用 python -m pip）
python -m pip install pyserial
```

## 快速开始

### 1. 基础数据读取

以 JY901S 为例，连接传感器并读取数据：

```python
import lib.device_model as deviceModel
from lib.data_processor.roles.jy901s_dataProcessor import JY901SDataProcessor
from lib.protocol_resolver.roles.wit_protocol_resolver import WitProtocolResolver

# 初始化设备
device = deviceModel.DeviceModel(
    "JY901S",
    WitProtocolResolver(),
    JY901SDataProcessor(),
    "51_0"
)

# 配置串口
device.serialConfig.portName = "COM3"   # Windows 串口号
device.serialConfig.baud = 115200       # 波特率

# 打开设备
device.openDevice()

# 注册数据更新回调
def onUpdate(deviceModel):
    print(f"角度: X={deviceModel.getDeviceData('angleX')}, "
          f"Y={deviceModel.getDeviceData('angleY')}, "
          f"Z={deviceModel.getDeviceData('angleZ')}")

device.dataProcessor.onVarChanged.append(onUpdate)

# 保持运行
input()
device.closeDevice()
```

### 2. 运行示例程序

```bash
cd Python-WitProtocol/chs

# JY901S 基础示例
python JY901S.py

# WT901C485 (RS485) 示例
python WT901C485.py

# JY931 测试（自动尝试多种波特率）
python test_jy931.py

# JY931 3D 可视化
python jy931_visualizer.py

# 投篮姿势纠正系统
python shooting_posture_corrector.py
```

## 应用程序说明

### JY931 3D 可视化（jy931_visualizer.py）

基于 tkinter 的实时 3D 姿态可视化程序：
- 3D 立方体姿态显示
- 欧拉角（Roll/Pitch/Yaw）实时数据
- 帧率统计与帧类型计数
- 角度变化历史曲线

### 投篮姿势纠正系统（shooting_posture_corrector.py）

基于 JY931 陀螺仪的投篮姿势实时纠正系统：
- 检测翻滚角（Roll）和俯仰角（Pitch）偏离
- 超过 ±15° 可调阈值时触发对应方向震动纠正
- 四方向震动模块可视化（上/下/左/右）
- 手臂姿态俯视图实时显示
- 角度变化历史曲线
- 姿势正确率统计

### 诊断工具

- **diagnose.py** — 分析串口原始数据帧，验证维特协议帧完整性
- **test_raw.py** — 直接读取串口原始数据，支持 Modbus CRC16 校验，用于排查连接问题

## SDK 架构

### 核心模块

| 模块 | 说明 |
|------|------|
| `DeviceModel` | 设备模型，管理串口连接、数据收发和寄存器读写 |
| `WitProtocolResolver` | 维特标准协议解析器（0x55 帧头协议） |
| `Protocol485Resolver` | RS485/Modbus 协议解析器 |
| `JY901SDataProcessor` | 数据处理器，解析加速度、角速度、角度、磁场等数据 |

### 支持的传感器数据

| 数据项 | Key | 说明 |
|--------|-----|------|
| 芯片时间 | `Chiptime` | 传感器内部时间 |
| 温度 | `temperature` | °C |
| 加速度 | `accX` / `accY` / `accZ` | 单位：g |
| 角速度 | `gyroX` / `gyroY` / `gyroZ` | 单位：°/s |
| 角度 | `angleX` / `angleY` / `angleZ` | 单位：° |
| 磁场 | `magX` / `magY` / `magZ` | — |
| 四元数 | `q1` / `q2` / `q3` / `q4` | — |
| 经度 | `lon` | — |
| 纬度 | `lat` | — |
| 航向角 | `Yaw` | — |
| 地速 | `Speed` | — |

### 设备配置操作

```python
# 读取配置
tVals = device.readReg(0x02, 3)   # 读取数据内容、回传速率、通讯速率

# 设置配置
device.unlock()                    # 解锁寄存器
device.writeReg(0x03, 6)          # 设置回传速率
device.writeReg(0x23, 0)          # 设置安装方向
device.save()                      # 保存配置

# 校准
device.AccelerationCalibration()   # 加计校准
device.BeginFiledCalibration()     # 开始磁场校准
device.EndFiledCalibration()       # 结束磁场校准
```

## 串口配置参考

| 设备型号 | 默认波特率 | 协议 | 串口（Windows） | 串口（Linux） |
|---------|-----------|------|----------------|---------------|
| JY901S | 115200 | 维特标准协议 | COMx | /dev/ttyUSB0 |
| JY931 | 921600 / 9600 | 维特标准协议 | COMx | /dev/ttyUSB0 |
| WT901C485 | 9600 | RS485/Modbus | COMx | /dev/ttyUSB0 |

> 请根据实际连接情况修改代码中的端口号和波特率。可在 Windows 设备管理器中查看 COM 口编号。

## 参考资料

- 维特智能官方教程：https://blog.csdn.net/Fred_1986/article/details/114415548
- 视频教程：https://www.bilibili.com/video/BV1bV411v7Bm/
- 维特智能官网：https://wit-motion.yuque.com/wit-motion

## 许可证

本项目基于维特智能官方示例程序修改扩展，仅供学习和研究使用。
