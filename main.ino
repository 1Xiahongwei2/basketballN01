#include <WiFi.h>
#include <WebServer.h>

// ========== 配置 ==========
#define WIFI_SSID       "YJ931-IMU"
#define WIFI_PASSWORD   "12345678"

// UART 配置 - YJ931 默认 115200，可改为 921600
#define YJ931_UART      UART_NUM_1
#define YJ931_BAUD      921600
#define YJ931_RX_PIN    12    // ESP32-S3 GPIO16 (RX)
#define YJ931_TX_PIN    13    // ESP32-S3 GPIO17 (TX)

// Web 服务器
WebServer server(80);

// ========== 数据结构 ==========
#pragma pack(push, 1)
struct STime {
    uint8_t year;
    uint8_t month;
    uint8_t day;
    uint8_t hour;
    uint8_t minute;
    uint8_t second;
    uint16_t ms;
};

struct SAngle {
    int16_t roll;   // X轴角度 (除以32768*180得到实际角度)
    int16_t pitch;  // Y轴角度
    int16_t yaw;    // Z轴角度
    int16_t temp;   // 温度
};
#pragma pack(pop)

// 全局数据
volatile struct STime imuTime;
volatile struct SAngle imuAngle;
volatile bool dataUpdated = false;

// 串口接收缓冲区
static uint8_t rxBuffer[11];
static uint8_t rxIndex = 0;

// ========== HTML 页面 ==========
const char* HTML_PAGE = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YJ931 IMU 数据展示</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 20px;
            color: white;
        }
        .container {
            max-width: 800px;
            width: 100%;
        }
        h1 {
            text-align: center;
            margin-bottom: 30px;
            font-size: 2.5em;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .card {
            background: rgba(255,255,255,0.15);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 25px;
            margin-bottom: 20px;
            border: 1px solid rgba(255,255,255,0.2);
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
        }
        .card-title {
            font-size: 1.3em;
            margin-bottom: 15px;
            color: #ffd700;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .data-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
        }
        .data-item {
            background: rgba(255,255,255,0.1);
            padding: 15px;
            border-radius: 12px;
            text-align: center;
        }
        .data-label {
            font-size: 0.9em;
            opacity: 0.8;
            margin-bottom: 5px;
        }
        .data-value {
            font-size: 1.8em;
            font-weight: bold;
            color: #00ff88;
        }
        .data-unit {
            font-size: 0.8em;
            opacity: 0.7;
        }
        .status {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #00ff88;
            animation: pulse 1s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .update-time {
            text-align: center;
            margin-top: 20px;
            opacity: 0.7;
            font-size: 0.9em;
        }
        .euler-visual {
            display: flex;
            justify-content: space-around;
            margin-top: 15px;
            flex-wrap: wrap;
            gap: 10px;
        }
        .euler-box {
            background: rgba(0,0,0,0.2);
            padding: 20px;
            border-radius: 15px;
            min-width: 120px;
            text-align: center;
        }
        .euler-name {
            font-size: 0.9em;
            margin-bottom: 10px;
            opacity: 0.8;
        }
        .euler-value {
            font-size: 2.2em;
            font-weight: bold;
            color: #00d2ff;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎯 YJ931 姿态传感器</h1>
        
        <div class="card">
            <div class="card-title">
                <span class="status"></span>
                实时欧拉角
            </div>
            <div class="euler-visual">
                <div class="euler-box">
                    <div class="euler-name">横滚 Roll</div>
                    <div class="euler-value" id="roll">--</div>
                </div>
                <div class="euler-box">
                    <div class="euler-name">俯仰 Pitch</div>
                    <div class="euler-value" id="pitch">--</div>
                </div>
                <div class="euler-box">
                    <div class="euler-name">偏航 Yaw</div>
                    <div class="euler-value" id="yaw">--</div>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-title">⏰ 时间戳</div>
            <div class="data-grid">
                <div class="data-item">
                    <div class="data-label">日期</div>
                    <div class="data-value" id="date">--</div>
                </div>
                <div class="data-item">
                    <div class="data-label">时间</div>
                    <div class="data-value" id="time">--</div>
                </div>
                <div class="data-item">
                    <div class="data-label">毫秒</div>
                    <div class="data-value" id="ms">--</div>
                    <div class="data-unit">ms</div>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-title">🌡️ 温度</div>
            <div class="data-grid">
                <div class="data-item">
                    <div class="data-label">芯片温度</div>
                    <div class="data-value" id="temp">--</div>
                    <div class="data-unit">°C</div>
                </div>
            </div>
        </div>

        <div class="update-time">最后更新: <span id="updateTime">--</span></div>
    </div>

    <script>
        function fetchData() {
            fetch('/api/data')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('roll').textContent = data.roll.toFixed(2);
                    document.getElementById('pitch').textContent = data.pitch.toFixed(2);
                    document.getElementById('yaw').textContent = data.yaw.toFixed(2);
                    document.getElementById('date').textContent = data.date;
                    document.getElementById('time').textContent = data.time;
                    document.getElementById('ms').textContent = data.ms;
                    document.getElementById('temp').textContent = data.temp.toFixed(1);
                    document.getElementById('updateTime').textContent = new Date().toLocaleTimeString();
                })
                .catch(err => console.error('Fetch error:', err));
        }
        
        // 每100ms刷新一次
        setInterval(fetchData, 100);
        fetchData(); // 初始加载
    </script>
</body>
</html>
)rawliteral";

// ========== 串口数据解析 ==========
void parseYJ931Data(uint8_t data) {
    // 等待帧头 0x55
    if (rxIndex == 0 && data != 0x55) {
        return;
    }
    
    rxBuffer[rxIndex++] = data;
    
    // 接收到完整 11 字节数据包
    if (rxIndex >= 11) {
        rxIndex = 0;
        
        // 校验和验证
        uint8_t sum = 0;
        for (int i = 0; i < 10; i++) {
            sum += rxBuffer[i];
        }
        if (sum != rxBuffer[10]) {
            return; // 校验失败
        }
        
        uint8_t type = rxBuffer[1];
        
        switch (type) {
            case 0x50: // 时间数据
                memcpy((void*)&imuTime, &rxBuffer[2], 8);
                break;
                
            case 0x53: // 角度数据(欧拉角)
                memcpy((void*)&imuAngle, &rxBuffer[2], 8);
                dataUpdated = true;
                break;
                
            // 可以添加 0x51(加速度)、0x52(角速度) 等其他数据类型的处理
        }
    }
}

// ========== UART 中断处理 ==========
void IRAM_ATTR onUartRx() {
    while (Serial1.available()) {
        uint8_t data = Serial1.read();
        parseYJ931Data(data);
    }
}

// ========== Web 服务器路由 ==========
void handleRoot() {
    server.send(200, "text/html", HTML_PAGE);
}

void handleData() {
    // 计算实际角度值: 原始值 / 32768 * 180
    float roll = (float)imuAngle.roll / 32768.0f * 180.0f;
    float pitch = (float)imuAngle.pitch / 32768.0f * 180.0f;
    float yaw = (float)imuAngle.yaw / 32768.0f * 180.0f;
    float temp = (float)imuAngle.temp / 340.0f + 36.25f;
    
    // 格式化时间
    char dateStr[16], timeStr[16];
    sprintf(dateStr, "20%02d-%02d-%02d", imuTime.year, imuTime.month, imuTime.day);
    sprintf(timeStr, "%02d:%02d:%02d", imuTime.hour, imuTime.minute, imuTime.second);
    
    String json = "{";
    json += "\"roll\":" + String(roll, 2) + ",";
    json += "\"pitch\":" + String(pitch, 2) + ",";
    json += "\"yaw\":" + String(yaw, 2) + ",";
    json += "\"temp\":" + String(temp, 1) + ",";
    json += "\"date\":\"" + String(dateStr) + "\",";
    json += "\"time\":\"" + String(timeStr) + "\",";
    json += "\"ms\":" + String(imuTime.ms);
    json += "}";
    
    server.send(200, "application/json", json);
}

// ========== 初始化 ==========
void setup() {
    Serial.begin(115200);
    delay(1000);
    Serial.println("\n=== YJ931 IMU Web Server Starting ===");
    
    // 1. 配置 UART1 连接 YJ931
    Serial1.begin(YJ931_BAUD, SERIAL_8N1, YJ931_RX_PIN, YJ931_TX_PIN);
    Serial.printf("YJ931 UART initialized: %d baud\n", YJ931_BAUD);
    
    // 2. 开启 WiFi 热点
    WiFi.softAP(WIFI_SSID, WIFI_PASSWORD);
    IPAddress IP = WiFi.softAPIP();
    Serial.printf("WiFi AP Started: %s\n", WIFI_SSID);
    Serial.printf("AP IP Address: %s\n", IP.toString().c_str());
    
    // 3. 配置 Web 服务器
    server.on("/", handleRoot);
    server.on("/api/data", handleData);
    server.begin();
    Serial.println("Web server started on port 80");
    Serial.printf("Access: http://%s\n", IP.toString().c_str());
}

// ========== 主循环 ==========
void loop() {
    // 处理串口数据
    while (Serial1.available()) {
        uint8_t data = Serial1.read();
        parseYJ931Data(data);
    }
    
    // 处理 Web 请求
    server.handleClient();
    
    // 调试输出 (可选)
    static unsigned long lastPrint = 0;
    if (millis() - lastPrint > 1000 && dataUpdated) {
        lastPrint = millis();
        float roll = (float)imuAngle.roll / 32768.0f * 180.0f;
        float pitch = (float)imuAngle.pitch / 32768.0f * 180.0f;
        float yaw = (float)imuAngle.yaw / 32768.0f * 180.0f;
        
        Serial.printf("Time: 20%02d-%02d-%02d %02d:%02d:%02d.%03d | ", 
            imuTime.year, imuTime.month, imuTime.day,
            imuTime.hour, imuTime.minute, imuTime.second, imuTime.ms);
        Serial.printf("Angle: Roll=%.2f, Pitch=%.2f, Yaw=%.2f\n", roll, pitch, yaw);
    }
}