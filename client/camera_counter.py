#!/usr/bin/env python3
# camera_counter.py - นับลูกค้าผ่านกล้องวงจรปิด
import cv2
import numpy as np
import time
import datetime
import threading
import logging
import os
import urllib.parse
import PIL.Image, PIL.ImageDraw, PIL.ImageFont
import math

class CameraCounter:
    """คลาสสำหรับนับลูกค้าผ่านกล้องวงจรปิด"""
    
    def __init__(self, config_manager, data_manager=None, video_source=None, display_video=True, branch_id=None, debug_mode=False):
        """กำหนดค่าเริ่มต้นสำหรับตัวนับลูกค้า"""
        # ตั้งค่าระบบบันทึก log
        self.logger = logging.getLogger("CameraCounter")
        if debug_mode:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)
        
        handler = logging.FileHandler("logs/camera_counter.log", encoding='utf-8')
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        
        # กำหนดตัวแปรเริ่มต้น
        self.config_manager = config_manager
        self.data_manager = data_manager
        self.display_video = display_video
        self.debug_mode = debug_mode
        self.branch_id = branch_id or config_manager.get('Branch', 'id', fallback='unknown')
        
        # โหลดฟอนต์ที่รองรับภาษาไทย
        self.font = self._load_thai_font(20)
        self.small_font = self._load_thai_font(16)
        
        # ตัวแปรสำหรับการติดตามการเคลื่อนไหว
        self.fgbg = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=16, detectShadows=False)
        
        # ตัวแปรสำหรับการทำงาน
        self.camera_running = False
        
        # ตัวแปรสำหรับบันทึกข้อมูล
        self.recording_interval = config_manager.getint('Recording', 'interval_seconds', fallback=300)
        self.last_record_time = time.time()
        
        # ตรวจสอบการตั้งค่ากล้องหลายตัว
        self.multi_cameras_enabled = config_manager.getboolean('MultiCameras', 'enabled', fallback=False)
        self.cameras = []
        
        # ข้อมูลสรุปรวมจากทุกกล้อง
        self.people_in_store = 0
        self.entry_count = 0
        self.exit_count = 0
        self.current_frame = None
        
        # ตั้งค่ากล้อง
        if self.multi_cameras_enabled:
            self._setup_multiple_cameras(video_source)
        else:
            self._setup_single_camera(video_source)
            
        self.logger.info(f"ตัวนับลูกค้าจากกล้องถูกเริ่มต้นแล้ว สำหรับสาขา: {self.branch_id}")
    
    def _load_thai_font(self, size):
        """โหลดฟอนต์ที่รองรับภาษาไทย"""
        try:
            # ลองโหลดฟอนต์ Tahoma (รองรับภาษาไทย)
            font_path = r"C:\Windows\Fonts\tahoma.ttf"
            if not os.path.exists(font_path):
                # ถ้าไม่พบ tahoma ลองใช้ฟอนต์อื่น
                for font_name in ['arial.ttf', 'thsarabun.ttf', 'cordia.ttf', 'cour.ttf']:
                    alt_path = os.path.join(r"C:\Windows\Fonts", font_name)
                    if os.path.exists(alt_path):
                        font_path = alt_path
                        break
            
            return PIL.ImageFont.truetype(font_path, size)
        except Exception as e:
            self.logger.warning(f"ไม่สามารถโหลดฟอนต์ภาษาไทยได้: {str(e)}")
            return PIL.ImageFont.load_default()
    
    def _setup_multiple_cameras(self, video_source=None):
        """ตั้งค่ากล้องหลายตัว"""
        camera_count = self.config_manager.getint('MultiCameras', 'camera_count', fallback=1)
        
        # รหัสผู้ใช้และรหัสผ่านส่วนกลางที่ใช้ร่วมกัน
        common_username = self.config_manager.get('MultiCameras', 'username', fallback='admin')
        common_password = self.config_manager.get('MultiCameras', 'password', fallback='admin')
        
        for i in range(1, camera_count + 1):
            camera_section = f'Camera_{i}'
            
            if self.config_manager.has_section(camera_section):
                # ใช้การตั้งค่าเฉพาะของกล้องแต่ละตัว ถ้ามี
                cam_name = self.config_manager.get(camera_section, 'name', fallback=f'Camera {i}')
                cam_host = self.config_manager.get(camera_section, 'host', fallback=None)
                cam_port = self.config_manager.get(camera_section, 'port', fallback='554')
                cam_path = self.config_manager.get(camera_section, 'path', fallback='')
                cam_channel = self.config_manager.get(camera_section, 'channel', fallback=str(i))
                
                # ใช้ username/password จากการตั้งค่าเฉพาะของกล้องหรือใช้ค่าร่วม
                cam_username = self.config_manager.get(camera_section, 'username', fallback=common_username)
                cam_password = self.config_manager.get(camera_section, 'password', fallback=common_password)
                
                # สำหรับ "source" โดยตรง (ใช้กรณีไม่ได้ใช้รูปแบบ host/username/password)
                direct_source = self.config_manager.get(camera_section, 'source', fallback=None)
                
                # ถ้ามีการระบุ host ให้สร้าง RTSP URL
                if cam_host:
                    # เข้ารหัสรหัสผ่านเพื่อจัดการกับอักขระพิเศษ
                    encoded_password = urllib.parse.quote(cam_password)
                    rtsp_url = f"rtsp://{cam_username}:{encoded_password}@{cam_host}:{cam_port}"
                    
                    # เพิ่ม path ถ้ามี
                    if cam_path:
                        # ตรวจสอบว่า path เริ่มต้นด้วย / หรือไม่
                        if not cam_path.startswith('/'):
                            rtsp_url += f"/{cam_path}"
                        else:
                            rtsp_url += cam_path
                    
                    # สำหรับกล้อง Hikvision
                    if "hikvision" in self.config_manager.get(camera_section, 'type', fallback='').lower():
                        rtsp_url = f"rtsp://{cam_username}:{encoded_password}@{cam_host}:{cam_port}/Streaming/Channels/{cam_channel}01"
                    
                    # สำหรับกล้อง Dahua
                    elif "dahua" in self.config_manager.get(camera_section, 'type', fallback='').lower():
                        rtsp_url = f"rtsp://{cam_username}:{encoded_password}@{cam_host}:{cam_port}/cam/realmonitor?channel={cam_channel}&subtype=1"
                    
                    cam_source = rtsp_url
                elif direct_source:
                    cam_source = direct_source
                else:
                    # ถ้าไม่มีทั้ง host และ direct_source ให้ข้ามกล้องนี้
                    self.logger.warning(f"ข้ามกล้อง {cam_name} เนื่องจากไม่มีข้อมูลแหล่งที่มา")
                    continue
                
                width = self.config_manager.getint(camera_section, 'width', fallback=640)
                height = self.config_manager.getint(camera_section, 'height', fallback=480)
                detection_line = self.config_manager.getint(camera_section, 'detection_line', fallback=height // 2)
                
                self.cameras.append({
                    'id': i,
                    'name': cam_name,
                    'source': cam_source,
                    'width': width,
                    'height': height,
                    'detection_line': detection_line,
                    'detection_angle': self.config_manager.getint(camera_section, 'detection_angle', fallback=0),
                    'min_area': self.config_manager.getint(camera_section, 'min_area', 
                                                      fallback=self.config_manager.getint('Detection', 'min_area', fallback=500)),
                    'cap': None,
                    'running': False,
                    'thread': None,
                    'people_in_store': 0,
                    'entry_count': 0,
                    'exit_count': 0,
                    'previous_centers': [],
                    'last_record_time': time.time(),
                    'current_frame': None
                })
        
        # ถ้าไม่มีกล้องที่ตั้งค่าไว้ ให้ใช้กล้องเริ่มต้น
        if not self.cameras:
            self.logger.warning("ไม่พบการตั้งค่ากล้อง ใช้กล้องเริ่มต้น")
            self._setup_single_camera(video_source)
    
    def _setup_single_camera(self, video_source=None):
        """ตั้งค่ากล้องเดี่ยว"""
        # กำหนดค่าแหล่งวีดีโอ
        if video_source is not None:
            source = video_source
        else:
            source = self.config_manager.get('Camera', 'source', fallback='0')
            # แปลงเป็นตัวเลขถ้าเป็นตัวเลข
            if isinstance(source, str) and source.isdigit():
                source = int(source)
        
        width = self.config_manager.getint('Camera', 'width', fallback=640)
        height = self.config_manager.getint('Camera', 'height', fallback=480)
        detection_line = self.config_manager.getint('Camera', 'detection_line', fallback=height // 2)
        
        self.cameras.append({
            'id': 0,
            'name': 'Default Camera',
            'source': source,
            'width': width,
            'height': height,
            'detection_line': detection_line,
            'detection_angle': self.config_manager.getint('Camera', 'detection_angle', fallback=0),
            'min_area': self.config_manager.getint('Detection', 'min_area', fallback=500),
            'cap': None,
            'running': False,
            'thread': None,
            'people_in_store': 0,
            'entry_count': 0,
            'exit_count': 0,
            'previous_centers': [],
            'last_record_time': time.time(),
            'current_frame': None
        })
    
def start(self):
    try:
        logger.info("กำลังเริ่มกล้อง...")
        if self.video_source is None:
            # ถ้าใช้หลายกล้อง ให้เริ่มกล้องทุกตัว
            if self.use_multiple_cameras:
                logger.info(f"เริ่มกล้องหลายตัว จำนวน {len(self.cameras)} ตัว")
                for cam in self.cameras:
                    cam_id = cam['id']
                    logger.info(f"กำลังเริ่มกล้อง {cam_id}: {cam['name']}")
                    
                    # ตรวจสอบว่ามี URL หรือไม่
                    if 'url' not in cam or not cam['url']:
                        logger.error(f"ไม่พบ URL สำหรับกล้อง {cam_id}")
                        continue
                        
                    # ทดสอบการเปิดกล้อง
                    logger.info(f"ทดสอบเปิดกล้อง {cam_id} ด้วย URL: {cam['url']}")
                    test_cap = cv2.VideoCapture(cam['url'])
                    if test_cap.isOpened():
                        ret, frame = test_cap.read()
                        test_cap.release()
                        if ret:
                            logger.info(f"เปิดกล้อง {cam_id} และอ่านเฟรมสำเร็จ")
                        else:
                            logger.error(f"เปิดกล้อง {cam_id} ได้ แต่ไม่สามารถอ่านเฟรมได้")
                    else:
                        logger.error(f"ไม่สามารถเปิดกล้อง {cam_id} ได้")
        
        # เรียกฟังก์ชันเดิม
        self.camera_running = True
        return True
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการเริ่มกล้อง: {str(e)}", exc_info=True)
        return False
    
    def stop(self):
        """หยุดการทำงานของกล้อง"""
        if not self.camera_running:
            self.logger.warning("กล้องไม่ได้ทำงานอยู่")
            return False
        
        for camera in self.cameras:
            if not camera['running']:
                continue
            
            try:
                # หยุดเธรด
                camera['running'] = False
                if camera['thread']:
                    camera['thread'].join(timeout=1.0)
                
                # ปิดกล้อง
                if camera['cap'] and camera['cap'].isOpened():
                    camera['cap'].release()
                
                self.logger.info(f"หยุดการทำงานของกล้อง {camera['name']} สำเร็จ")
                
            except Exception as e:
                self.logger.error(f"เกิดข้อผิดพลาดในการหยุดกล้อง {camera['name']}: {str(e)}")
        
        # ล้างข้อมูลเฟรมปัจจุบัน
        self.current_frame = None
        
        # อัพเดตสถานะการทำงาน
        self.camera_running = False
        
        # ปิดหน้าต่างแสดงผล
        if self.display_video:
            cv2.destroyAllWindows()
        
        self.logger.info("หยุดการทำงานของทุกกล้องเรียบร้อย")
        return True
    
    def reset_counters(self):
        """รีเซ็ตตัวนับทั้งหมด"""
        for camera in self.cameras:
            camera['people_in_store'] = 0
            camera['entry_count'] = 0
            camera['exit_count'] = 0
        
        # รีเซ็ตตัวนับรวม
        self.people_in_store = 0
        self.entry_count = 0
        self.exit_count = 0
        
        self.logger.info("รีเซ็ตตัวนับลูกค้าทั้งหมด")
    
    def get_status(self):
        """ส่งคืนสถานะปัจจุบันของตัวนับ"""
        # อัพเดตสถานะรวมจากทุกกล้อง
        self._update_total_counts()
        
        return {
            'branch_id': self.branch_id,
            'running': self.camera_running,
            'people_in_store': self.people_in_store,
            'entry_count': self.entry_count,
            'exit_count': self.exit_count,
            'last_count_time': self.last_record_time,
            'timestamp': datetime.datetime.now().isoformat(),
            'cameras': [{
                'id': cam['id'],
                'name': cam['name'],
                'running': cam['running'],
                'people_in_store': cam['people_in_store'],
                'entry_count': cam['entry_count'],
                'exit_count': cam['exit_count']
            } for cam in self.cameras]
        }
    
    def _update_total_counts(self):
        """อัพเดตตัวนับรวมจากทุกกล้อง"""
        self.people_in_store = sum(cam['people_in_store'] for cam in self.cameras)
        self.entry_count = sum(cam['entry_count'] for cam in self.cameras)
        self.exit_count = sum(cam['exit_count'] for cam in self.cameras)
    
    def _process_camera(self, camera):
        """ประมวลผลภาพจากกล้อง (เรียกจากเธรดแยก)"""
        self.logger.info(f"เริ่มการประมวลผลภาพจากกล้อง {camera['name']}")
        
        # สร้าง background subtractor สำหรับกล้องนี้
        fgbg = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=16, detectShadows=False)
        
        while camera['running'] and camera['cap'] and camera['cap'].isOpened():
            try:
                # อ่านเฟรมจากกล้อง
                ret, frame = camera['cap'].read()
                if not ret or frame is None:
                    self.logger.error(f"ไม่สามารถอ่านเฟรมจากกล้อง {camera['name']}")
                    time.sleep(0.5)  # หน่วงเวลาเพื่อไม่ให้ทำงานซ้ำเร็วเกินไป
                    continue
                
                # ประมวลผลภาพเพื่อนับจำนวนลูกค้า
                self._process_frame(camera, frame, fgbg)
                
                # เก็บเฟรมปัจจุบัน
                camera['current_frame'] = frame.copy()
                
                # เก็บเฟรมปัจจุบันของกล้องแรกเป็นเฟรมหลักสำหรับแสดงผล
                if camera['id'] == self.cameras[0]['id']:
                    self.current_frame = frame.copy()
                
                # แสดงภาพ (ถ้าเปิดใช้งาน)
                if self.display_video:
                    # เพิ่มข้อมูลกล้องลงในภาพโดยใช้ PIL
                    pil_img = PIL.Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                    draw = PIL.ImageDraw.Draw(pil_img)
                    
                    # วาดข้อความด้วยฟอนต์ภาษาไทย
                    draw.text((10, 30), f"จำนวนคนในร้าน: {camera['people_in_store']}", font=self.font, fill=(255, 0, 0))
                    draw.text((10, 60), f"จำนวนคนเข้าร้านทั้งหมด: {camera['entry_count']}", font=self.font, fill=(255, 0, 0))
                    draw.text((10, 90), f"จำนวนคนออกจากร้านทั้งหมด: {camera['exit_count']}", font=self.font, fill=(255, 0, 0))
                    draw.text((10, 120), f"กล้อง: {camera['name']}", font=self.font, fill=(255, 0, 0))
                    
                    # เพิ่มเวลาปัจจุบัน
                    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    draw.text((frame.shape[1] - 200, 20), now, font=self.small_font, fill=(255, 255, 255))
                    
                    # แปลงกลับเป็นเฟรม OpenCV
                    frame = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
                    
                    # วาดเส้นตรวจจับ (ไม่ต้องใช้ PIL สำหรับการวาดเส้น)
                    # cv2.line(frame, (0, camera['detection_line']), (frame.shape[1], camera['detection_line']), (0, 255, 0), 2)
                    
                    cv2.imshow(f"Camera {camera['name']}", frame)
                    
                    # รอคีย์ 'q' เพื่อหยุด
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        camera['running'] = False
                        break
                
                # บันทึกข้อมูลลงฐานข้อมูลตามรอบเวลา
                current_time = time.time()
                if current_time - camera['last_record_time'] > self.recording_interval:
                    self._record_customer_count(camera)
                    camera['last_record_time'] = current_time
                    
            except Exception as e:
                self.logger.error(f"เกิดข้อผิดพลาดในการประมวลผลกล้อง {camera['name']}: {str(e)}")
                time.sleep(1)  # หน่วงเวลาเพื่อไม่ให้ทำงานซ้ำเร็วเกินไป
        
        # ปิดหน้าต่างแสดงผลเฉพาะกล้องนี้
        if self.display_video:
            cv2.destroyWindow(f"Camera {camera['name']}")
        
        self.logger.info(f"หยุดการประมวลผลภาพจากกล้อง {camera['name']}")
    
    def _process_frame(self, camera, frame, fgbg):
        """ประมวลผลเฟรมเพื่อตรวจจับและนับลูกค้า"""
        try:
            # แปลงเป็นสีเทา
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # ทำ Gaussian blur เพื่อลดสัญญาณรบกวน
            blur_size = self.config_manager.getint('Detection', 'blur_size', fallback=21)
            if blur_size % 2 == 0:  # ต้องเป็นเลขคี่
                blur_size += 1
            gray = cv2.GaussianBlur(gray, (blur_size, blur_size), 0)
            
            # ใช้ Background Subtraction เพื่อตรวจจับวัตถุเคลื่อนไหว
            fgmask = fgbg.apply(gray)
            
            # กรองสัญญาณรบกวน
            thresh = cv2.threshold(fgmask, self.config_manager.getint('Detection', 'threshold', fallback=20), 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)
            
            # หา contours ของวัตถุ
            contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # วาดเส้นตรวจจับตามแนวตั้ง (แบบปรับมุมได้)
            height, width = frame.shape[:2]
            
            # สำหรับแนวตั้ง ใช้จุดกลางตามแนวนอน
            center_x = camera.get('detection_line', width // 2)  # ใช้ค่า detection_line เป็นตำแหน่ง x
            center_y = height // 2
            
            # ดึงมุมจากการตั้งค่า (หรือใช้ค่าเริ่มต้น 90 องศาสำหรับเส้นตรงแนวตั้ง)
            angle = camera.get('detection_angle', 90)
            
            # คำนวณความยาวของเส้นให้ครอบคลุมทั้งภาพ
            line_length = max(width, height) * 2
            
            # คำนวณจุดปลายของเส้นโดยใช้มุม
            import math
            angle_rad = math.radians(angle)
            cos_angle = math.cos(angle_rad)
            sin_angle = math.sin(angle_rad)
            
            # คำนวณจุดปลายของเส้น
            x1 = int(center_x - line_length * cos_angle)
            y1 = int(center_y - line_length * sin_angle)
            x2 = int(center_x + line_length * cos_angle)
            y2 = int(center_y + line_length * sin_angle)
            
            # วาดเส้น
            cv2.line(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            # เพิ่มฟังก์ชันตรวจสอบจุดอยู่ด้านไหนของเส้น
            def is_left_of_line(point_x, point_y, line_x1, line_y1, line_x2, line_y2):
                # ค่าเป็นบวกถ้าจุดอยู่ทางซ้ายของเส้น ลบถ้าอยู่ทางขวา
                return (line_y2 - line_y1) * point_x + (line_x1 - line_x2) * point_y + (line_x2 * line_y1 - line_x1 * line_y2) > 0
            
            # ตรวจสอบแต่ละ contour
            centers = []
            for contour in contours:
                # คำนวณพื้นที่ของ contour
                area = cv2.contourArea(contour)
                
                # ตรวจสอบว่าพื้นที่มากกว่าค่าขั้นต่ำหรือไม่
                if area > camera['min_area']:
                    # หากมีขนาดใหญ่พอ จะถือว่าเป็นคน
                    (x, y, w, h) = cv2.boundingRect(contour)
                    
                    # วาดกรอบรอบตัวคน
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    
                    # คำนวณจุดศูนย์กลาง
                    center_x_point = x + w // 2
                    center_y_point = y + h // 2
                    centers.append((center_x_point, center_y_point))
                    
                    # วาดจุดที่จุดศูนย์กลาง
                    cv2.circle(frame, (center_x_point, center_y_point), 4, (0, 0, 255), -1)
                    
                    # ตรวจสอบการเคลื่อนที่ผ่านเส้น
                    direction_threshold = self.config_manager.getint('Detection', 'direction_threshold', fallback=10)
                    
                    for prev_center in camera['previous_centers']:
                        prev_x, prev_y = prev_center
                        
                        # คำนวณระยะทางระหว่างจุดศูนย์กลางปัจจุบันและก่อนหน้า
                        distance = np.sqrt((center_x_point - prev_x) ** 2 + (center_y_point - prev_y) ** 2)
                        
                        # ตรวจสอบว่าเป็นวัตถุเดียวกันหรือไม่
                        if distance < 50:  # ระยะห่างสำหรับพิจารณาว่าเป็นวัตถุเดียวกัน
                            # ตรวจสอบการเคลื่อนที่ผ่านเส้น
                            prev_is_left = is_left_of_line(prev_x, prev_y, x1, y1, x2, y2)
                            curr_is_left = is_left_of_line(center_x_point, center_y_point, x1, y1, x2, y2)
                            
                            # ถ้ามีการเคลื่อนที่ข้ามเส้น และระยะทางมากกว่าค่า threshold
                            if prev_is_left != curr_is_left and distance > direction_threshold:
                                if prev_is_left and not curr_is_left:
                                    # เคลื่อนที่จากซ้ายไปขวา (คนเดินเข้า)
                                    camera['entry_count'] += 1
                                    camera['people_in_store'] += 1
                                    self.logger.info(f"กล้อง {camera['name']} ตรวจพบคนเข้า (ซ้ายไปขวา) - คนในร้าน: {camera['people_in_store']}")
                                    
                                    # อัพเดตตัวนับรวม
                                    self._update_total_counts()
                                elif not prev_is_left and curr_is_left:
                                    # เคลื่อนที่จากขวาไปซ้าย (คนเดินออก)
                                    camera['exit_count'] += 1
                                    camera['people_in_store'] = max(0, camera['people_in_store'] - 1)  # ป้องกันค่าติดลบ
                                    self.logger.info(f"กล้อง {camera['name']} ตรวจพบคนออก (ขวาไปซ้าย) - คนในร้าน: {camera['people_in_store']}")
                                    
                                    # อัพเดตตัวนับรวม
                                    self._update_total_counts()
            
            # บันทึกตำแหน่งจุดศูนย์กลางปัจจุบันสำหรับการตรวจสอบครั้งต่อไป
            camera['previous_centers'] = centers
            
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการประมวลผลเฟรมจากกล้อง {camera['name']}: {str(e)}")
    
    def _record_customer_count(self, camera=None):
        """บันทึกจำนวนลูกค้าลงฐานข้อมูล"""
        if not self.data_manager:
            return
        
        try:
            # อัพเดตตัวนับรวม
            self._update_total_counts()
            
            # บันทึกข้อมูลผ่านตัวจัดการข้อมูล
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.data_manager.record_customer_count(
                timestamp=timestamp, 
                entries=self.entry_count, 
                exits=self.exit_count, 
                total_in_store=self.people_in_store,
                branch_id=self.branch_id
            )
            
            self.logger.info(f"บันทึกข้อมูลจำนวนลูกค้ารวม: เข้า {self.entry_count}, ออก {self.exit_count}, ในร้าน {self.people_in_store}")
            
            # บันทึกเวลาล่าสุด
            self.last_record_time = time.time()
                
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการบันทึกข้อมูลจำนวนลูกค้า: {str(e)}")
    
    def adjust_line_angle(self, angle, camera_id=None):
        """ปรับมุมของเส้นตรวจจับ"""
        # ถ้าระบุ camera_id ให้ปรับแค่กล้องที่ระบุ ไม่เช่นนั้นปรับทุกกล้อง
        cameras_to_adjust = []
        if camera_id is not None:
            camera = next((cam for cam in self.cameras if cam['id'] == camera_id), None)
            if camera:
                cameras_to_adjust.append(camera)
            else:
                self.logger.error(f"ไม่พบกล้อง ID: {camera_id}")
                return False
        else:
            cameras_to_adjust = self.cameras
        
        for camera in cameras_to_adjust:
            camera['detection_angle'] = angle
            camera_section = f"Camera_{camera['id']}" if camera['id'] > 0 else "Camera"
            self.config_manager.set(camera_section, 'detection_angle', str(angle))
        
        self.config_manager.save()
        self.logger.info(f"ปรับมุมเส้นตรวจจับเป็น {angle} องศา สำหรับ {len(cameras_to_adjust)} กล้อง")
        return True
    
    def _save_snapshot(self, camera=None):
        """บันทึกภาพ snapshot จากกล้อง"""
        try:
            if camera is None:
                # ใช้กล้องแรก
                if not self.cameras:
                    self.logger.error("ไม่มีกล้องสำหรับบันทึกภาพ snapshot")
                    return
                camera = self.cameras[0]
            
            if not camera['running'] or not camera['cap'] or not camera['cap'].isOpened():
                self.logger.error(f"กล้อง {camera['name']} ไม่พร้อมสำหรับบันทึกภาพ snapshot")
                return
            
            # อ่านเฟรมจากกล้อง
            ret, frame = camera['cap'].read()
            if not ret or frame is None:
                self.logger.error(f"ไม่สามารถอ่านเฟรมจากกล้อง {camera['name']} สำหรับบันทึกภาพ snapshot")
                return
            
            # สร้างโฟลเดอร์สำหรับเก็บภาพ
            snapshots_dir = os.path.join(self.config_manager.get('Recording', 'export_path', fallback='exports'), 'snapshots')
            os.makedirs(snapshots_dir, exist_ok=True)
            
            # เพิ่มข้อมูลลงในภาพก่อนบันทึก
            pil_img = PIL.Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            draw = PIL.ImageDraw.Draw(pil_img)
            
            # วาดข้อความด้วยฟอนต์ภาษาไทย
            draw.text((10, 30), f"สาขา: {self.branch_id}", font=self.font, fill=(255, 0, 0))
            draw.text((10, 60), f"กล้อง: {camera['name']}", font=self.font, fill=(255, 0, 0))
            draw.text((10, 90), f"จำนวนคนในร้าน: {camera['people_in_store']}", font=self.font, fill=(255, 0, 0))
            
            # เพิ่มเวลาปัจจุบัน
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            draw.text((10, frame.shape[0] - 40), now, font=self.small_font, fill=(255, 255, 255))
            
            # แปลงกลับเป็นเฟรม OpenCV
            frame = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            
            # สร้างชื่อไฟล์
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{snapshots_dir}/{self.branch_id}_{camera['name']}_{timestamp}.jpg"
            
            # บันทึกภาพ
            cv2.imwrite(filename, frame)
            self.logger.info(f"บันทึกภาพ snapshot จากกล้อง {camera['name']}: {filename}")
            
            return filename
            
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการบันทึกภาพ snapshot: {str(e)}")
            return None
    
    def take_snapshot(self, camera_id=None):
        """ถ่ายภาพปัจจุบันจากกล้อง"""
        # ถ้าระบุ camera_id ให้ใช้กล้องที่ระบุ ไม่เช่นนั้นใช้กล้องแรก
        if camera_id is not None:
            camera = next((cam for cam in self.cameras if cam['id'] == camera_id), None)
            if camera is None:
                self.logger.error(f"ไม่พบกล้อง ID: {camera_id}")
                return None
        else:
            if not self.cameras:
                self.logger.error("ไม่มีกล้องสำหรับถ่ายภาพ")
                return None
            camera = self.cameras[0]
        
        # ตรวจสอบสถานะกล้อง
        if not camera['running'] or not camera['cap'] or not camera['cap'].isOpened():
            self.logger.error(f"กล้อง {camera['name']} ไม่พร้อมสำหรับถ่ายภาพ")
            return None
        
        # ดึงเฟรมปัจจุบัน (ถ้ามี)
        if camera['current_frame'] is not None:
            # ทำสำเนาก่อนเพื่อไม่ให้กระทบข้อมูลเดิม
            frame = camera['current_frame'].copy()
            
            # เพิ่มข้อมูลลงในภาพด้วย PIL
            pil_img = PIL.Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            draw = PIL.ImageDraw.Draw(pil_img)
            
            # วาดข้อความด้วยฟอนต์ภาษาไทย
            draw.text((10, 30), f"สาขา: {self.branch_id}", font=self.font, fill=(255, 0, 0))
            draw.text((10, 60), f"กล้อง: {camera['name']}", font=self.font, fill=(255, 0, 0))
            draw.text((10, 90), f"จำนวนคนในร้าน: {camera['people_in_store']}", font=self.font, fill=(255, 0, 0))
            
            # เพิ่มเวลาปัจจุบัน
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            draw.text((10, frame.shape[0] - 40), now, font=self.small_font, fill=(255, 255, 255))
            
            # แปลงกลับเป็นเฟรม OpenCV
            frame = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            
            return frame
        
        # หรือถ่ายภาพใหม่
        try:
            ret, frame = camera['cap'].read()
            if not ret or frame is None:
                self.logger.error(f"ไม่สามารถอ่านเฟรมจากกล้อง {camera['name']}")
                return None
                
            # เพิ่มข้อมูลลงในภาพด้วย PIL
            pil_img = PIL.Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            draw = PIL.ImageDraw.Draw(pil_img)
            
            # วาดข้อความด้วยฟอนต์ภาษาไทย
            draw.text((10, 30), f"สาขา: {self.branch_id}", font=self.font, fill=(255, 0, 0))
            draw.text((10, 60), f"กล้อง: {camera['name']}", font=self.font, fill=(255, 0, 0))
            draw.text((10, 90), f"จำนวนคนในร้าน: {camera['people_in_store']}", font=self.font, fill=(255, 0, 0))
            
            # เพิ่มเวลาปัจจุบัน
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            draw.text((10, frame.shape[0] - 40), now, font=self.small_font, fill=(255, 255, 255))
            
            # แปลงกลับเป็นเฟรม OpenCV
            frame = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            
            return frame
            
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการถ่ายภาพจากกล้อง {camera['name']}: {str(e)}")
            return None
    
    def get_camera_list(self):
        """ส่งคืนรายการกล้องทั้งหมด"""
        return [{
            'id': cam['id'],
            'name': cam['name'],
            'running': cam['running'],
            'source': cam['source'],
            'people_in_store': cam['people_in_store'],
            'entry_count': cam['entry_count'],
            'exit_count': cam['exit_count']
        } for cam in self.cameras]
    
    def adjust_detection_parameters(self, min_area=None, threshold=None, blur_size=None, direction_threshold=None, camera_id=None):
        """ปรับพารามิเตอร์สำหรับการตรวจจับ"""
        # ถ้าระบุ camera_id ให้ปรับแค่กล้องที่ระบุ ไม่เช่นนั้นปรับทุกกล้อง
        cameras_to_adjust = []
        if camera_id is not None:
            camera = next((cam for cam in self.cameras if cam['id'] == camera_id), None)
            if camera:
                cameras_to_adjust.append(camera)
            else:
                self.logger.error(f"ไม่พบกล้อง ID: {camera_id}")
                return False
        else:
            cameras_to_adjust = self.cameras
        
        # ปรับพารามิเตอร์
        for camera in cameras_to_adjust:
            camera_section = f"Camera_{camera['id']}" if camera['id'] > 0 else "Camera"
            
            # ปรับค่าในกล้อง
            if min_area is not None:
                camera['min_area'] = min_area
                self.config_manager.set(camera_section, 'min_area', str(min_area))
            
            # บันทึกค่าคงที่ในไฟล์การตั้งค่า
            section = 'Detection'
            if threshold is not None:
                self.config_manager.set(section, 'threshold', str(threshold))
            
            if blur_size is not None:
                # ต้องเป็นเลขคี่
                if blur_size % 2 == 0:
                    blur_size += 1
                self.config_manager.set(section, 'blur_size', str(blur_size))
            
            if direction_threshold is not None:
                self.config_manager.set(section, 'direction_threshold', str(direction_threshold))
        
        # บันทึกค่าลงไฟล์
        self.config_manager.save()
        self.logger.info(f"ปรับพารามิเตอร์การตรวจจับสำหรับ {len(cameras_to_adjust)} กล้องแล้ว")
        return True
    
    def adjust_line_position(self, position, camera_id=None):
        """ปรับตำแหน่งเส้นตรวจจับ"""
        # ถ้าระบุ camera_id ให้ปรับแค่กล้องที่ระบุ ไม่เช่นนั้นปรับทุกกล้อง
        cameras_to_adjust = []
        if camera_id is not None:
            camera = next((cam for cam in self.cameras if cam['id'] == camera_id), None)
            if camera:
                cameras_to_adjust.append(camera)
            else:
                self.logger.error(f"ไม่พบกล้อง ID: {camera_id}")
                return False
        else:
            cameras_to_adjust = self.cameras
        
        for camera in cameras_to_adjust:
            if position > 0:
                camera['detection_line'] = position
                camera_section = f"Camera_{camera['id']}" if camera['id'] > 0 else "Camera"
                self.config_manager.set(camera_section, 'detection_line', str(position))
        
        self.config_manager.save()
        self.logger.info(f"ปรับตำแหน่งเส้นตรวจจับเป็น {position} สำหรับ {len(cameras_to_adjust)} กล้องแล้ว")
        return True
    
    def adjust_line_position_horizontal(self, position, camera_id=None):
        """ปรับตำแหน่งเส้นตรวจจับตามแนวนอน (ค่า x)"""
        # ถ้าระบุ camera_id ให้ปรับแค่กล้องที่ระบุ ไม่เช่นนั้นปรับทุกกล้อง
        cameras_to_adjust = []
        if camera_id is not None:
            camera = next((cam for cam in self.cameras if cam['id'] == camera_id), None)
            if camera:
                cameras_to_adjust.append(camera)
            else:
                self.logger.error(f"ไม่พบกล้อง ID: {camera_id}")
                return False
        else:
            cameras_to_adjust = self.cameras
        
        for camera in cameras_to_adjust:
            if position > 0:
                camera['detection_line'] = position
                camera_section = f"Camera_{camera['id']}" if camera['id'] > 0 else "Camera"
                self.config_manager.set(camera_section, 'detection_line', str(position))
        
        self.config_manager.save()
        self.logger.info(f"ปรับตำแหน่งเส้นตรวจจับตามแนวนอนเป็น {position} สำหรับ {len(cameras_to_adjust)} กล้อง")
        return True