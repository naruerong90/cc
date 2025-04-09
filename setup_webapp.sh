#!/bin/bash
# setup_webapp.sh - สคริปต์ติดตั้งเว็บแอปพลิเคชันสำหรับระบบนับลูกค้าผ่านกล้องวงจรปิด

echo "=== ติดตั้งเว็บแอปพลิเคชันสำหรับระบบนับลูกค้าผ่านกล้องวงจรปิด ==="

# สร้างโครงสร้างไฟล์และโฟลเดอร์
echo "กำลังสร้างโครงสร้างไฟล์และโฟลเดอร์..."
mkdir -p logs
mkdir -p static/css
mkdir -p static/js
mkdir -p static/images
mkdir -p static/snapshots
mkdir -p templates
mkdir -p exports
mkdir -p exports/snapshots
mkdir -p exports/reports
mkdir -p cache
mkdir -p backups
mkdir -p data

# ตรวจสอบและติดตั้ง dependencies
echo "กำลังตรวจสอบและติดตั้ง dependencies..."

# ตรวจสอบว่ามี pip หรือไม่
if ! command -v pip &> /dev/null; then
    echo "ไม่พบ pip กรุณาติดตั้ง Python และ pip ก่อน"
    exit 1
fi

# ตรวจสอบเวอร์ชัน Python
echo "ตรวจสอบเวอร์ชัน Python..."
python --version

# ติดตั้ง dependencies
echo "กำลังติดตั้ง dependencies..."
pip install -r requirements_webapp.txt

# ตรวจสอบว่ามีไฟล์ web_app.py หรือไม่
if [ ! -f web_app.py ]; then
    echo "ไม่พบไฟล์ web_app.py กรุณาตรวจสอบว่ามีไฟล์สคริปต์หลักครบถ้วน"
    exit 1
fi

# ตรวจสอบว่ามีไฟล์ config.ini หรือไม่
if [ ! -f config.ini ]; then
    echo "กำลังสร้างไฟล์ config.ini เริ่มต้น..."
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
detection_angle = 90

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

# ให้สิทธิ์การรันสคริปต์
chmod +x run_webapp.sh

echo "ติดตั้งเว็บแอปพลิเคชันเสร็จสมบูรณ์"
echo "คุณสามารถเริ่มใช้งานระบบได้โดยใช้คำสั่ง: ./run_webapp.sh"
echo "จากนั้นเปิดเว็บเบราว์เซอร์และเข้าสู่: http://localhost:8080"