#include <WiFi.h>
#include <WiFiUdp.h>

// ========== 配置区 ==========
const char* ssid = "worldshaper";
const char* password = "31415926";
const char* pc_ip = "192.168.110.9

4";      // 电脑IP
const int pc_port = 8888;                   // 统一接收端口

const int localPort = 9992;                 // 本机UDP端口（FOREARM=9992）
const String node_id = "FOREARM";           // 节点标识

// ★ 参考实测：ESP32-S3 用 Serial1, 921600波特率, GPIO12/13
#define YJ931_BAUD      921600
#define YJ931_RX_PIN    12
#define YJ931_TX_PIN    13

WiFiUDP udp;

// YJ931 数据解析缓冲区
static uint8_t rxBuffer[11];
static uint8_t rxIndex = 0;

struct Angle {
  float pitch;
  float roll;
  float yaw;
} angle;

unsigned long lastHeartbeat = 0;

// ========== 初始化 ==========
void setup() {
  Serial.begin(115200);
  delay(500);
  
  // ★ ESP32-S3 必须显式指定引脚和波特率
  Serial1.begin(YJ931_BAUD, SERIAL_8N1, YJ931_RX_PIN, YJ931_TX_PIN);
  Serial.printf("[%s] YJ931 UART1 initialized: %d baud, RX=%d, TX=%d\n", 
    node_id.c_str(), YJ931_BAUD, YJ931_RX_PIN, YJ931_TX_PIN);
  
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500); Serial.print(".");
  }
  Serial.printf("\n[%s] WiFi Connected: %s\n", node_id.c_str(), WiFi.localIP().toString().c_str());
  
  udp.begin(localPort);
  Serial.printf("[%s] UDP ready, sending to %s:%d\n", node_id.c_str(), pc_ip, pc_port);
}

// ========== YJ931 协议解析（参考实测代码，含校验和） ==========
void parseYJ931(uint8_t data) {
  if (rxIndex == 0 && data != 0x55) return;
  rxBuffer[rxIndex++] = data;
  
  if (rxIndex >= 11) {
    rxIndex = 0;
    
    // ★ 校验和验证
    uint8_t sum = 0;
    for (int i = 0; i < 10; i++) sum += rxBuffer[i];
    if (sum != rxBuffer[10]) return;  // 校验失败丢弃
    
    if (rxBuffer[1] == 0x53) {  // 角度输出帧
      int16_t roll_raw  = (rxBuffer[3] << 8) | rxBuffer[2];
      int16_t pitch_raw = (rxBuffer[5] << 8) | rxBuffer[4];
      int16_t yaw_raw   = (rxBuffer[7] << 8) | rxBuffer[6];
      
      angle.roll  = roll_raw  / 32768.0 * 180.0;
      angle.pitch = pitch_raw / 32768.0 * 180.0;
      angle.yaw   = yaw_raw   / 32768.0 * 180.0;
      
      Serial.printf("[%s] IMU → p=%.1f r=%.1f y=%.1f\n", 
        node_id.c_str(), angle.pitch, angle.roll, angle.yaw);
      sendPacket();
    }
  }
  if (rxIndex > 11) rxIndex = 0;
}

// ========== UDP 发送 ==========
void sendPacket() {
  char json[128];
  snprintf(json, sizeof(json), 
    "{\"id\":\"%s\",\"p\":%.2f,\"r\":%.2f,\"y\":%.2f}", 
    node_id.c_str(), angle.pitch, angle.roll, angle.yaw);
  
  udp.beginPacket(pc_ip, pc_port);
  udp.write((uint8_t*)json, strlen(json));
  udp.endPacket();
}

// ========== 心跳包 ==========
void sendHeartbeat() {
  char json[128];
  snprintf(json, sizeof(json), 
    "{\"id\":\"%s\",\"p\":0.00,\"r\":0.00,\"y\":0.00}", 
    node_id.c_str());
  udp.beginPacket(pc_ip, pc_port);
  udp.write((uint8_t*)json, strlen(json));
  udp.endPacket();
  Serial.printf("[%s] heartbeat sent\n", node_id.c_str());
}

void loop() {
  while (Serial1.available()) {
    uint8_t data = Serial1.read();
    parseYJ931(data);
  }
  
  // 心跳：IMU无数据时也每2秒发一次，方便排查
  if (millis() - lastHeartbeat > 2000) {
    lastHeartbeat = millis();
    sendHeartbeat();
  }
  
  delay(2);
}
