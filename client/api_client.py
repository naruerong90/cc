# api_client.py - จัดการการเชื่อมต่อกับ API ของเซิร์ฟเวอร์
import requests
import json
import time
import threading
import logging
import os
import datetime

class APIClient:
    """คลาสสำหรับเชื่อมต่อกับ API ของเซิร์ฟเวอร์"""
    
    def __init__(self, config_manager, data_manager, branch_id=None):
        """กำหนดค่าเริ่มต้นสำหรับตัวเชื่อมต่อ API"""
        # ตั้งค่าระบบบันทึกล็อก
        self.logger = logging.getLogger("APIClient")
        
        # กำหนดตัวแปรเริ่มต้น
        self.config_manager = config_manager
        self.data_manager = data_manager
        self.branch_id = branch_id or config_manager.get('Branch', 'id', fallback='unknown')
        
        # ตั้งค่า API
        self.server_url = config_manager.get('API', 'server_url', fallback='http://localhost:5000')
        self.api_key = config_manager.get('API', 'api_key', fallback='')
        self.timeout = config_manager.getint('API', 'timeout', fallback=30)
        
        # ตั้งค่าการซิงค์ข้อมูล
        self.sync_interval = config_manager.getint('API', 'sync_interval', fallback=900)  # 15 นาที
        self.retry_interval = config_manager.getint('API', 'retry_interval', fallback=60)  # 1 นาที
        
        # ตัวแปรสำหรับควบคุมการซิงค์
        self.sync_running = False
        self.sync_thread = None
        self.last_sync_time = time.time() - self.sync_interval  # เพื่อให้ซิงค์ทันทีเมื่อเริ่มต้น
        self.last_sync_status = False
        
        self.logger.info(f"ตัวเชื่อมต่อ API ถูกเริ่มต้นแล้ว สำหรับสาขา: {self.branch_id}")
    
    def start_sync(self):
        """เริ่มการซิงค์ข้อมูลในเธรดแยก"""
        if self.sync_running:
            self.logger.warning("การซิงค์ข้อมูลกำลังทำงานอยู่แล้ว")
            return False
        
        # เริ่มเธรดสำหรับซิงค์ข้อมูล
        self.sync_running = True
        self.sync_thread = threading.Thread(target=self._sync_loop)
        self.sync_thread.daemon = True
        self.sync_thread.start()
        
        self.logger.info("เริ่มการซิงค์ข้อมูลกับเซิร์ฟเวอร์")
        return True
    
    def stop_sync(self):
        """หยุดการซิงค์ข้อมูล"""
        if not self.sync_running:
            self.logger.warning("การซิงค์ข้อมูลไม่ได้ทำงานอยู่")
            return False
        
        self.sync_running = False
        if self.sync_thread:
            self.sync_thread.join(timeout=1.0)
        
        self.logger.info("หยุดการซิงค์ข้อมูลกับเซิร์ฟเวอร์")
        return True
    
    def _sync_loop(self):
        """ลูปการซิงค์ข้อมูล (เรียกจากเธรดแยก)"""
        while self.sync_running:
            try:
                current_time = time.time()
                
                # ตรวจสอบว่าถึงเวลาซิงค์หรือไม่
                if current_time - self.last_sync_time > self.sync_interval:
                    # ทำการซิงค์ข้อมูล
                    success = self.sync_data()
                    
                    self.last_sync_time = current_time
                    self.last_sync_status = success
                    
                    # กำหนดเวลาสำหรับการซิงค์ครั้งถัดไป
                    if success:
                        # ถ้าซิงค์สำเร็จ รอตามรอบเวลาปกติ
                        sleep_time = self.sync_interval
                    else:
                        # ถ้าซิงค์ไม่สำเร็จ รอตามรอบเวลาลองใหม่
                        sleep_time = self.retry_interval
                else:
                    # ยังไม่ถึงเวลาซิงค์
                    sleep_time = min(1, self.sync_interval - (current_time - self.last_sync_time))
                
                # รอจนกว่าจะถึงเวลาซิงค์ครั้งต่อไปหรือมีการหยุดการซิงค์
                start_wait = time.time()
                while self.sync_running and (time.time() - start_wait < sleep_time):
                    time.sleep(0.1)
                    
            except Exception as e:
                self.logger.error(f"เกิดข้อผิดพลาดในลูปการซิงค์: {str(e)}")
                time.sleep(self.retry_interval)  # รอก่อนลองใหม่
    
    def sync_data(self):
        """ซิงค์ข้อมูลกับเซิร์ฟเวอร์"""
        try:
            self.logger.info("กำลังซิงค์ข้อมูลกับเซิร์ฟเวอร์...")
            
            # ตรวจสอบการเชื่อมต่อกับเซิร์ฟเวอร์
            if not self.check_connection():
                self.logger.error("ไม่สามารถเชื่อมต่อกับเซิร์ฟเวอร์ได้")
                return False
            
            # อัพเดตข้อมูลสถานะล่าสุดของสาขา
            self.update_branch_status()
            
            # ดึงข้อมูลที่ยังไม่ได้ซิงค์
            unsync_data = self.data_manager.get_unsync_data()
            
            # ซิงค์ข้อมูลลูกค้า
            if unsync_data['customer_counts']:
                if self.sync_customer_counts(unsync_data['customer_counts']):
                    # ทำเครื่องหมายว่าข้อมูลได้ซิงค์แล้ว
                    self.data_manager.mark_as_synced('customer_counts', [item['id'] for item in unsync_data['customer_counts']])
            
            # ซิงค์ข้อมูลสถิติประจำวัน
            if unsync_data['daily_stats']:
                if self.sync_daily_stats(unsync_data['daily_stats']):
                    # ทำเครื่องหมายว่าข้อมูลได้ซิงค์แล้ว
                    self.data_manager.mark_as_synced('daily_stats', [item['id'] for item in unsync_data['daily_stats']])
            
            # ซิงค์ข้อมูลการนัดหมาย
            if unsync_data['appointments']:
                if self.sync_appointments(unsync_data['appointments']):
                    # ทำเครื่องหมายว่าข้อมูลได้ซิงค์แล้ว
                    self.data_manager.mark_as_synced('appointments', [item['id'] for item in unsync_data['appointments']])
            
            # ดึงข้อมูลใหม่จากเซิร์ฟเวอร์
            self.fetch_updates()
            
            self.logger.info("ซิงค์ข้อมูลกับเซิร์ฟเวอร์สำเร็จ")
            return True
            
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการซิงค์ข้อมูล: {str(e)}")
            return False
    
    def check_connection(self):
        """ตรวจสอบการเชื่อมต่อกับเซิร์ฟเวอร์"""
        try:
            url = f"{self.server_url}/api/v1/ping"
            headers = self._get_headers()
            
            response = requests.get(url, headers=headers, timeout=self.timeout)
            
            if response.status_code == 200:
                return True
            else:
                self.logger.warning(f"การตรวจสอบการเชื่อมต่อล้มเหลว: HTTP {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการตรวจสอบการเชื่อมต่อ: {str(e)}")
            return False
    
    def update_branch_status(self):
        """อัพเดตข้อมูลสถานะล่าสุดของสาขา"""
        try:
            url = f"{self.server_url}/api/v1/branches/{self.branch_id}/status"
            headers = self._get_headers()
            
            # สร้างข้อมูลสถานะ
            data = {
                'branch_id': self.branch_id,
                'name': self.config_manager.get('Branch', 'name', fallback='ไม่ระบุ'),
                'location': self.config_manager.get('Branch', 'location', fallback='ไม่ระบุ'),
                'status': 'online',
                'last_update': datetime.datetime.now().isoformat(),
                'version': '1.0.0'  # เวอร์ชันของซอฟต์แวร์
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=self.timeout)
            
            if response.status_code in [200, 201]:
                # ตรวจสอบว่ามีการอัพเดต API key หรือไม่
                response_data = response.json()
                if 'api_key' in response_data and response_data['api_key']:
                    # อัพเดต API key ใหม่
                    self.api_key = response_data['api_key']
                    self.config_manager.set('API', 'api_key', self.api_key)
                    self.config_manager.save()
                    self.logger.info("อัพเดต API key ใหม่จากเซิร์ฟเวอร์")
                
                return True
            else:
                self.logger.warning(f"การอัพเดตสถานะสาขาล้มเหลว: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการอัพเดตสถานะสาขา: {str(e)}")
            return False
    
    def sync_customer_counts(self, customer_counts):
        """ซิงค์ข้อมูลการนับลูกค้า"""
        try:
            url = f"{self.server_url}/api/v1/customer_counts/batch"
            headers = self._get_headers()
            
            response = requests.post(url, headers=headers, json=customer_counts, timeout=self.timeout)
            
            if response.status_code in [200, 201]:
                self.logger.info(f"ซิงค์ข้อมูลการนับลูกค้า {len(customer_counts)} รายการสำเร็จ")
                return True
            else:
                self.logger.warning(f"การซิงค์ข้อมูลการนับลูกค้าล้มเหลว: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการซิงค์ข้อมูลการนับลูกค้า: {str(e)}")
            return False
    
    def sync_daily_stats(self, daily_stats):
        """ซิงค์ข้อมูลสถิติประจำวัน"""
        try:
            url = f"{self.server_url}/api/v1/daily_stats/batch"
            headers = self._get_headers()
            
            response = requests.post(url, headers=headers, json=daily_stats, timeout=self.timeout)
            
            if response.status_code in [200, 201]:
                self.logger.info(f"ซิงค์ข้อมูลสถิติประจำวัน {len(daily_stats)} รายการสำเร็จ")
                return True
            else:
                self.logger.warning(f"การซิงค์ข้อมูลสถิติประจำวันล้มเหลว: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการซิงค์ข้อมูลสถิติประจำวัน: {str(e)}")
            return False
    
    def sync_appointments(self, appointments):
        """ซิงค์ข้อมูลการนัดหมาย"""
        try:
            url = f"{self.server_url}/api/v1/appointments/batch"
            headers = self._get_headers()
            
            response = requests.post(url, headers=headers, json=appointments, timeout=self.timeout)
            
            if response.status_code in [200, 201]:
                self.logger.info(f"ซิงค์ข้อมูลการนัดหมาย {len(appointments)} รายการสำเร็จ")
                return True
            else:
                self.logger.warning(f"การซิงค์ข้อมูลการนัดหมายล้มเหลว: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการซิงค์ข้อมูลการนัดหมาย: {str(e)}")
            return False
    
    def fetch_updates(self):
        """ดึงข้อมูลอัพเดตจากเซิร์ฟเวอร์"""
        try:
            # ดึงข้อมูลพนักงาน
            employees = self.fetch_employees()
            
            # ดึงข้อมูลการนัดหมาย
            appointments = self.fetch_appointments()
            
            # นำเข้าข้อมูล
            if employees or appointments:
                self.data_manager.import_data(employees, appointments)
            
            return True
            
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการดึงข้อมูลอัพเดต: {str(e)}")
            return False
    
    def fetch_employees(self):
        """ดึงข้อมูลพนักงานจากเซิร์ฟเวอร์"""
        try:
            url = f"{self.server_url}/api/v1/branches/{self.branch_id}/employees"
            headers = self._get_headers()
            
            response = requests.get(url, headers=headers, timeout=self.timeout)
            
            if response.status_code == 200:
                employees = response.json()
                self.logger.info(f"ดึงข้อมูลพนักงาน {len(employees)} รายการสำเร็จ")
                return employees
            else:
                self.logger.warning(f"การดึงข้อมูลพนักงานล้มเหลว: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการดึงข้อมูลพนักงาน: {str(e)}")
            return None
    
    def fetch_appointments(self):
        """ดึงข้อมูลการนัดหมายจากเซิร์ฟเวอร์"""
        try:
            # ดึงการนัดหมายของวันนี้เป็นต้นไป
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            url = f"{self.server_url}/api/v1/branches/{self.branch_id}/appointments?start_date={today}"
            headers = self._get_headers()
            
            response = requests.get(url, headers=headers, timeout=self.timeout)
            
            if response.status_code == 200:
                appointments = response.json()
                self.logger.info(f"ดึงข้อมูลการนัดหมาย {len(appointments)} รายการสำเร็จ")
                return appointments
            else:
                self.logger.warning(f"การดึงข้อมูลการนัดหมายล้มเหลว: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการดึงข้อมูลการนัดหมาย: {str(e)}")
            return None
    
    def upload_snapshot(self, image_data, metadata=None):
        """อัปโหลดภาพ snapshot ไปยังเซิร์ฟเวอร์"""
        try:
            url = f"{self.server_url}/api/v1/branches/{self.branch_id}/snapshots"
            headers = self._get_headers()
            
            # เตรียมข้อมูลสำหรับส่ง
            import cv2
            import base64
            
            # แปลงภาพเป็น base64
            if isinstance(image_data, str) and os.path.exists(image_data):
                # กรณีที่เป็นพาธของไฟล์
                with open(image_data, 'rb') as img_file:
                    img_base64 = base64.b64encode(img_file.read()).decode('utf-8')
            elif isinstance(image_data, bytes):
                # กรณีที่เป็นข้อมูลไบนารี
                img_base64 = base64.b64encode(image_data).decode('utf-8')
            else:
                # กรณีที่เป็น numpy array (จาก OpenCV)
                _, buffer = cv2.imencode('.jpg', image_data, [cv2.IMWRITE_JPEG_QUALITY, 85])
                img_base64 = base64.b64encode(buffer).decode('utf-8')
            
            # เตรียม metadata
            if metadata is None:
                metadata = {}
            
            metadata.update({
                'branch_id': self.branch_id,
                'timestamp': datetime.datetime.now().isoformat()
            })
            
            # ส่งข้อมูล
            data = {
                'image': img_base64,
                'metadata': metadata
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=self.timeout * 2)  # ให้เวลามากขึ้นสำหรับการอัปโหลดรูป
            
            if response.status_code in [200, 201]:
                self.logger.info("อัปโหลดภาพ snapshot สำเร็จ")
                return True
            else:
                self.logger.warning(f"การอัปโหลดภาพ snapshot ล้มเหลว: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการอัปโหลดภาพ snapshot: {str(e)}")
            return False
    
    def get_sync_status(self):
        """ส่งคืนสถานะการซิงค์ล่าสุด"""
        return {
            'running': self.sync_running,
            'last_sync_time': self.last_sync_time,
            'last_sync_status': self.last_sync_status,
            'next_sync_time': self.last_sync_time + (self.sync_interval if self.last_sync_status else self.retry_interval),
            'server_url': self.server_url
        }
    
    def check_for_updates(self):
        """ตรวจสอบการอัพเดตซอฟต์แวร์จากเซิร์ฟเวอร์"""
        try:
            url = f"{self.server_url}/api/v1/updates/check"
            headers = self._get_headers()
            
            # เตรียมข้อมูลสำหรับส่ง
            data = {
                'branch_id': self.branch_id,
                'version': '1.0.0',  # เวอร์ชันปัจจุบันของซอฟต์แวร์
                'platform': os.name
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=self.timeout)
            
            if response.status_code == 200:
                update_info = response.json()
                
                if update_info.get('has_update', False):
                    self.logger.info(f"พบการอัพเดตเป็นเวอร์ชัน {update_info.get('version')}")
                    return update_info
                else:
                    self.logger.info("ไม่พบการอัพเดต")
                    return None
            else:
                self.logger.warning(f"การตรวจสอบการอัพเดตล้มเหลว: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการตรวจสอบการอัพเดต: {str(e)}")
            return None
    
    def download_update(self, update_url, target_path):
        """ดาวน์โหลดไฟล์อัพเดตจากเซิร์ฟเวอร์"""
        try:
            headers = self._get_headers()
            
            # สร้างโฟลเดอร์เป้าหมายถ้ายังไม่มี
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            
            # ดาวน์โหลดไฟล์
            with requests.get(update_url, headers=headers, stream=True, timeout=self.timeout * 5) as response:
                response.raise_for_status()
                
                # บันทึกไฟล์
                with open(target_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
            
            self.logger.info(f"ดาวน์โหลดไฟล์อัพเดตไปยัง: {target_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการดาวน์โหลดไฟล์อัพเดต: {str(e)}")
            return False
    
    def _get_headers(self):
        """สร้างส่วนหัวสำหรับการส่งคำขอ API"""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        
        return headers