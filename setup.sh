#!/bin/bash
# setup.sh - สคริปต์ติดตั้งระบบนับลูกค้าผ่านกล้องวงจรปิด

echo "=== ติดตั้งระบบนับลูกค้าผ่านกล้องวงจรปิด ==="

# สร้างโครงสร้างไฟล์และโฟลเดอร์
echo "กำลังสร้างโครงสร้างไฟล์และโฟลเดอร์..."

mkdir -p client
mkdir -p logs
mkdir -p exports
mkdir -p exports/snapshots
mkdir -p exports/reports
mkdir -p backups
mkdir -p cache
mkdir -p data

# สร้างไฟล์ __init__.py ในโฟลเดอร์ client
touch client/__init__.py

# ตรวจสอบและติดตั้ง dependencies
echo "กำลังตรวจสอบและติดตั้ง dependencies..."

# ตรวจสอบว่ามี pip หรือไม่
if ! command -v pip &> /dev/null; then
    echo "ไม่พบ pip กรุณาติดตั้ง Python และ pip ก่อน"
    exit 1
fi

# ติดตั้ง requirements
pip install opencv-python numpy Pillow requests prettytable python-dateutil

# สร้างไฟล์ config.ini ถ้ายังไม่มี
if [ ! -f config.ini ]; then
    echo "กำลังสร้างไฟล์ config.ini เริ่มต้น..."
    cat > config.ini << EOL
[Branch]
id = branch_shop_1
name = สาขาหลัก
location = กรุงเทพฯ

[Camera]
# กรณีใช้กล้องเดี่ยว
source = 0
width = 640
height = 480
fps = 30
detection_line = 320
detection_angle = 90

[Detection]
# พื้นที่ขั้นต่ำสำหรับตรวจจับการเคลื่อนไหว
min_area = 500
# ค่าขีดแบ่งสำหรับการตรวจจับการเคลื่อนไหว
threshold = 20
# ขนาดของการ blur (ต้องเป็นเลขคี่)
blur_size = 21
# ระยะทางขั้นต่ำที่จะถือว่ามีการเคลื่อนที่
direction_threshold = 10

[Database]
db_name = shop_tracking.db
backup_interval = 86400

[Recording]
interval_seconds = 300
export_path = exports/
save_snapshots = true

[API]
enabled = false
server_url = http://localhost:5000
api_key = 
sync_interval = 900
retry_interval = 60
timeout = 30

[MultiCameras]
enabled = false
camera_count = 0
username = admin
password = admin

# ตัวอย่างการตั้งค่ากล้องเพิ่มเติม - ลบ # ออกและแก้ไขค่าตามต้องการ
# [Camera_1]
# name = ประตูหน้า
# type = dahua
# host = 10.10.1.230
# port = 554
# channel = 1
# detection_line = 320
# detection_angle = 90
# min_area = 500

# [Camera_2]
# name = ประตูหลัง
# type = dahua
# host = 10.10.1.230
# port = 554
# channel = 2
# detection_line = 320
# detection_angle = 90
# min_area = 550
EOL
fi

# สร้างไฟล์ run.sh
echo "กำลังสร้างไฟล์ run.sh..."
cat > run.sh << EOL
#!/bin/bash
# run.sh - สคริปต์เริ่มการทำงานของระบบนับลูกค้า

# ไม่บัฟเฟอร์ stdout และ stderr
export PYTHONUNBUFFERED=1

# คำสั่งเริ่มการทำงาน
python main.py \$@
EOL

# ให้สิทธิ์การรันไฟล์ run.sh
chmod +x run.sh
chmod +x setup.sh

echo "การติดตั้งเสร็จสมบูรณ์"
echo "คุณสามารถเริ่มใช้งานระบบได้โดยใช้คำสั่ง: ./run.sh"
echo "หรือเริ่มในโหมดคอนโซล: ./run.sh --no-gui"
echo ""
echo "หากต้องการใช้งานกล้องหลายตัว กรุณาแก้ไขไฟล์ config.ini ดังนี้:"
echo "1. กำหนด [MultiCameras] enabled = true"
echo "2. กำหนด [MultiCameras] camera_count = จำนวนกล้อง"
echo "3. เปิดการใช้งานและแก้ไขการตั้งค่าในส่วน [Camera_1], [Camera_2], ..."