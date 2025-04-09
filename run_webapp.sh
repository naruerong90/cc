#!/bin/bash
# run_webapp.sh - สคริปต์เริ่มเว็บแอปพลิเคชันสำหรับระบบนับลูกค้าผ่านกล้องวงจรปิด

# ไม่บัฟเฟอร์ stdout และ stderr
export PYTHONUNBUFFERED=1

# สร้างโฟลเดอร์ที่จำเป็น
mkdir -p logs
mkdir -p static/snapshots
mkdir -p exports
mkdir -p cache
mkdir -p backups
mkdir -p templates

# ตรวจสอบการเชื่อมต่ออินเทอร์เน็ต
echo "กำลังตรวจสอบการเชื่อมต่ออินเทอร์เน็ต..."
ping -c 1 google.com > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "ไม่สามารถเชื่อมต่ออินเทอร์เน็ตได้ แต่จะเริ่มแอปพลิเคชันในโหมดออฟไลน์"
fi

# ตรวจสอบว่ามีไฟล์ config.ini หรือไม่
if [ ! -f config.ini ]; then
    echo "ไม่พบไฟล์ config.ini กำลังสร้างไฟล์ตั้งค่าเริ่มต้น..."
    cp config.ini.backup config.ini 2>/dev/null || cat > config.ini << EOL
[Branch]
id = branch_shop_1
name = สาขาหลัก
location = ไม่ระบุ

[Camera]
source = 0
width = 640
height = 480
fps = 30
detection_line = 240

[Detection]
min_area = 500
threshold = 20
blur_size = 21
direction_threshold = 10

[Database]
db_name = shop_tracking.db
backup_interval = 86400

[Recording]
interval_seconds = 300
export_path = exports/
save_snapshots = true

[API]
server_url = http://localhost:5000
api_key = 
sync_interval = 900
retry_interval = 60
timeout = 30

[MultiCameras]
enabled = false
camera_count = 0
EOL
fi

# ตรวจสอบว่ามีไฟล์เทมเพลตหรือไม่
if [ ! -d "templates" ] || [ ! -f "templates/dashboard.html" ]; then
    echo "ไม่พบไฟล์เทมเพลต กรุณาตรวจสอบว่ามีไฟล์เทมเพลตครบถ้วน"
fi

# ตรวจสอบ Python และติดตั้ง dependencies
echo "กำลังตรวจสอบ Python และติดตั้ง dependencies..."
python -c "import sys; print(f'Python version: {sys.version}')"

# ติดตั้ง dependencies ที่จำเป็น
echo "กำลังติดตั้ง dependencies..."
pip install flask opencv-python numpy pillow requests

# เริ่มเว็บแอปพลิเคชัน
echo "กำลังเริ่มเว็บแอปพลิเคชัน..."
python web_app.py --host 0.0.0.0 --port 8080 > logs/webapp_$(date +%Y%m%d%H%M%S).log 2>&1