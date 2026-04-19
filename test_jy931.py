# coding:UTF-8
"""
    JY931陀螺仪测试脚本
    Test script for JY931 gyroscope
"""
import time
import platform
import lib.device_model as deviceModel
from lib.data_processor.roles.jy901s_dataProcessor import JY901SDataProcessor
from lib.protocol_resolver.roles.wit_protocol_resolver import WitProtocolResolver

welcome = """
============================================
  维特智能 JY931 陀螺仪测试程序
  WitMotion JY931 Gyroscope Test Program
============================================
"""

def onUpdate(deviceModel):
    """
    数据更新回调函数
    Data update callback
    """
    print("\n---------- 传感器数据 ----------")
    print(f"温度: {deviceModel.getDeviceData('temperature')} °C")
    print(f"加速度(g): X={deviceModel.getDeviceData('accX')}, Y={deviceModel.getDeviceData('accY')}, Z={deviceModel.getDeviceData('accZ')}")
    print(f"角速度(°/s): X={deviceModel.getDeviceData('gyroX')}, Y={deviceModel.getDeviceData('gyroY')}, Z={deviceModel.getDeviceData('gyroZ')}")
    print(f"角度(°): X={deviceModel.getDeviceData('angleX')}, Y={deviceModel.getDeviceData('angleY')}, Z={deviceModel.getDeviceData('angleZ')}")
    print(f"磁场: X={deviceModel.getDeviceData('magX')}, Y={deviceModel.getDeviceData('magY')}, Z={deviceModel.getDeviceData('magZ')}")
    print(f"四元数: q1={deviceModel.getDeviceData('q1')}, q2={deviceModel.getDeviceData('q2')}, q3={deviceModel.getDeviceData('q3')}, q4={deviceModel.getDeviceData('q4')}")
    print("-------------------------------")

if __name__ == '__main__':
    print(welcome)
    
    # 初始化设备模型
    device = deviceModel.DeviceModel(
        "JY931",
        WitProtocolResolver(),
        JY901SDataProcessor(),
        "51_0"
    )
    
    # 配置串口 - JY931通常使用 COM3
    device.serialConfig.portName = "COM3"
    device.serialConfig.baud = 9600  # JY931默认波特率9600
    
    print(f"正在连接串口: {device.serialConfig.portName}, 波特率: {device.serialConfig.baud}")
    
    try:
        device.openDevice()
        print("串口打开成功!")
    except Exception as e:
        print(f"串口打开失败: {e}")
        print("请检查串口连接和波特率设置")
        exit(1)
    
    # 注册数据更新回调
    device.dataProcessor.onVarChanged.append(onUpdate)
    
    print("\n开始接收数据 (按 Enter 键退出)...\n")
    
    try:
        input()  # 等待用户按回车退出
    except KeyboardInterrupt:
        pass
    
    device.closeDevice()
    print("\n测试结束，设备已关闭")
