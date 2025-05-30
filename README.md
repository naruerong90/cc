# ระบบนับลูกค้าผ่านกล้องวงจรปิด (Web Application)

ระบบนับลูกค้าผ่านกล้องวงจรปิดแบบเว็บแอปพลิเคชัน ที่สามารถเข้าถึงได้ผ่านเว็บเบราว์เซอร์ ช่วยให้ผู้ใช้สามารถนับจำนวนลูกค้าที่เข้า-ออกร้านได้แบบอัตโนมัติผ่านกล้องวงจรปิด

## คุณสมบัติ

- แสดงภาพจากกล้องวงจรปิดแบบเรียลไทม์ผ่านเว็บเบราว์เซอร์
- ตรวจจับและนับจำนวนลูกค้าที่เข้า-ออกร้านอัตโนมัติ
- รองรับกล้องหลายตัว (Dahua, Hikvision และกล้องทั่วไป)
- แสดงสถิติและสร้างรายงานการเข้า-ออกของลูกค้า
- ส่งออกรายงานเป็นไฟล์ CSV
- ถ่ายภาพและบันทึกเหตุการณ์
- ซิงค์ข้อมูลกับเซิร์ฟเวอร์กลาง
- ทำงานแบบออฟไลน์ได้เมื่อไม่มีการเชื่อมต่ออินเทอร์เน็ต

## ข้อกำหนดของระบบ

### ฮาร์ดแวร์ขั้นต่ำ
- CPU: Intel Core i3 หรือเทียบเท่า
- RAM: 4GB หรือมากกว่า
- พื้นที่ว่าง: 1GB หรือมากกว่า
- กล้องเว็บแคมหรือกล้องวงจรปิดที่รองรับ RTSP

### ซอฟต์แวร์ที่จำเป็น
- Python 3.8 หรือสูงกว่า
- เว็บเบราว์เซอร์ทันสมัย (Chrome, Firefox, Edge)

## การติดตั้ง

### วิธีที่ 1: ติดตั้งด้วยสคริปต์อัตโนมัติ

1. ดาวน์โหลดโค้ดหรือโคลนจาก repository:
   ```bash
   git clone https://github.com/yourusername/shop-counter-webapp.git
   cd shop-counter-webapp
   ```

2. ให้สิทธิ์การรันสคริปต์ติดตั้ง:
   ```bash
   chmod +x setup.sh
   ```

3. รันสคริปต์ติดตั้ง:
   ```bash
   ./setup.sh
   ```

### วิธีที่ 2: ติดตั้งด้วยตนเอง

1. ดาวน์โหลดโค้ดหรือโคลนจาก repository:
   ```bash
   git clone https://github.com/yourusername/shop-counter-webapp.git
   cd shop-counter-webapp
   ```

2. ติดตั้ง dependencies:
   ```bash
   pip install -r requirements_webapp.txt
   ```

3. สร้างโฟลเดอร์ที่จำเป็น:
   ```bash
   mkdir -p logs static/snapshots exports cache backups templates
   ```

4. ให้สิทธิ์การรันสคริปต์:
   ```bash
   chmod +x run_webapp.sh
   ```

## การเริ่มใช้งาน

1. เริ่มเว็บแอปพลิเคชัน:
   ```bash
   ./run_webapp.sh
   ```

2. เปิดเว็บเบราว์เซอร์และเข้าสู่:
   ```
   http://localhost:8080
   ```

3. หากต้องการกำหนดพอร์ตอื่น สามารถระบุได้:
   ```bash
   python web_app.py --host 0.0.0.0 --port 5000
   ```

## การใช้งาน

### หน้าหลัก (Dashboard)
- แสดงภาพจากกล้องแบบเรียลไทม์
- แสดงจำนวนลูกค้าในร้าน, จำนวนลูกค้าเข้าร้าน, จำนวนลูกค้าออกจากร้าน
- ปุ่มเริ่มกล้อง, หยุดกล้อง, รีเซ็ตตัวนับ, ถ่ายภาพ

### หน้าจัดการกล้อง (Cameras)
- แสดงรายการกล้องทั้งหมด
- สามารถเพิ่ม แก้ไข ลบกล้อง
- แสดงรายละเอียดของกล้องที่เลือก
- ทดสอบการเชื่อมต่อกับกล้อง

### หน้าสถิติและรายงาน (Stats)
- แสดงกราฟแนวโน้มลูกค้า
- แสดงสถิติลูกค้าประจำวัน
- ส่งออกรายงานเป็นไฟล์ CSV

### หน้าตั้งค่า (Settings)
- ตั้งค่าข้อมูลสาขา
- ตั้งค่ากล้องทั่วไป
- ตั้งค่าการตรวจจับ
- ตั้งค่าการเชื่อมต่อ API

## การตั้งค่ากล้อง RTSP

### สำหรับกล้อง Dahua
```
ประเภท: dahua
Host: IP ของกล้อง (เช่น 192.168.1.100)
Port: 554
Username: admin
Password: รหัสผ่านของกล้อง
Channel: 1
```

### สำหรับกล้อง Hikvision
```
ประเภท: hikvision
Host: IP ของกล้อง (เช่น 192.168.1.101)
Port: 554
Username: admin
Password: รหัสผ่านของกล้อง
Channel: 1
```

### การระบุ URL โดยตรง
```
rtsp://username:password@ip-address:port/path
```

## การแก้ไขปัญหา

### ไม่สามารถเชื่อมต่อกับกล้อง
- ตรวจสอบว่า IP, พอร์ต, ชื่อผู้ใช้ และรหัสผ่านถูกต้อง
- ตรวจสอบว่าสามารถ ping ไปยัง IP ของกล้องได้
- ลองใช้ VLC Media Player ทดสอบ URL RTSP
- ตรวจสอบว่าพอร์ต RTSP (554) เปิดในไฟร์วอลล์

### วิธีดูล็อกของระบบ
ระบบจะบันทึกล็อกไว้ในโฟลเดอร์ `logs/`:
- `webapp_YYYYMMDDHHMMSS.log`: ล็อกของเว็บแอปพลิเคชัน
- `camera_counter.log`: ล็อกเกี่ยวกับการทำงานของกล้อง

## License

[MIT License](LICENSE)

## ผู้พัฒนา

พัฒนาโดย [Your Name](https://github.com/yourusername)