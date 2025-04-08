#!/usr/bin/env python3
# web_app.py - เว็บแอปพลิเคชันสำหรับระบบนับลูกค้าผ่านกล้องวงจรปิด
from flask import Flask, render_template, request, jsonify, Response, redirect, url_for, send_file
import threading
import time
import datetime
import logging
import os
import cv2
import base64
import json
import numpy as np
from logging.handlers import RotatingFileHandler
import sys

# นำเข้าโมดูลจากโฟลเดอร์ client
sys.path.append('client')
from config_manager import ConfigManager
from camera_counter import CameraCounter
from data_manager import DataManager
from api_client import APIClient

# ตั้งค่าการบันทึกล็อก
log_dir = 'logs'
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(
            os.path.join(log_dir, 'web_app.log'), 
            maxBytes=10485760, 
            backupCount=5
        ),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("WebApp")

# สร้างแอปพลิเคชัน Flask
app = Flask(__name__)
app.secret_key = os.urandom(24)

# สร้างโฟลเดอร์ที่จำเป็น
os.makedirs('static/snapshots', exist_ok=True)
os.makedirs('exports', exist_ok=True)
os.makedirs('cache', exist_ok=True)
os.makedirs('backups', exist_ok=True)

# ตัวแปรส่วนกลาง
config_manager = None
data_manager = None
api_client = None
camera = None
branch_id = None
branch_name = None
video_frames = {}  # เก็บเฟรมล่าสุดของกล้องแต่ละตัว

# เริ่มการทำงานของระบบ
def initialize_system(config_path='config.ini', debug_mode=False):
    global config_manager, data_manager, api_client, camera, branch_id, branch_name
    
    try:
        # โหลดการตั้งค่า
        config_manager = ConfigManager(config_path)
        
        # ตรวจสอบและตั้งค่ารหัสสาขา
        branch_id = config_manager.get('Branch', 'id', fallback=None)
        if not branch_id:
            # สร้างรหัสสาขาอัตโนมัติถ้าไม่มีการระบุ
            import uuid
            branch_id = f"branch_{uuid.uuid4().hex[:8]}"
            config_manager.set('Branch', 'id', branch_id)
            config_manager.save()
            logger.info(f"สร้างรหัสสาขาอัตโนมัติ: {branch_id}")
        
        branch_name = config_manager.get('Branch', 'name', fallback='สาขาหลัก')
        
        # สร้างอินสแตนซ์ของตัวจัดการข้อมูล
        data_manager = DataManager(config_manager, branch_id=branch_id)
        
        # สร้างอินสแตนซ์ของตัวเชื่อมต่อ API
        api_client = APIClient(config_manager, data_manager, branch_id=branch_id)
        
        # สร้างอินสแตนซ์ของตัวนับจากกล้อง
        camera = CameraCounter(
            config_manager=config_manager,
            data_manager=data_manager,
            video_source=None,
            display_video=False,  # ไม่แสดงหน้าต่าง OpenCV
            branch_id=branch_id,
            debug_mode=debug_mode
        )
        
        # เริ่มการซิงค์ข้อมูลกับเซิร์ฟเวอร์
        api_client.start_sync()
        
        # เริ่มเธรดสำหรับดึงเฟรมและอัพเดตข้อมูล
        threading.Thread(target=update_frames, daemon=True).start()
        
        logger.info("เริ่มต้นระบบสำเร็จ")
        return True
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการเริ่มต้นระบบ: {str(e)}", exc_info=True)
        return False

# อัพเดตเฟรมและข้อมูลในพื้นหลัง
def update_frames():
    global video_frames
    
    while True:
        try:
            if camera and camera.camera_running:
                # ดึงเฟรมล่าสุดจากกล้องทุกตัว
                for cam in camera.cameras:
                    if cam['running'] and 'current_frame' in cam and cam['current_frame'] is not None:
                        # แปลงเฟรมเป็น base64 สำหรับส่งไปยัง HTML
                        _, buffer = cv2.imencode('.jpg', cam['current_frame'], [cv2.IMWRITE_JPEG_QUALITY, 80])
                        base64_frame = base64.b64encode(buffer).decode('utf-8')
                        video_frames[cam['id']] = base64_frame
            
            # รอก่อนอัพเดตครั้งต่อไป (0.1 วินาที หรือ 10 fps)
            time.sleep(0.1)
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการอัพเดตเฟรม: {str(e)}")
            time.sleep(1.0)  # รอนานขึ้นในกรณีเกิดข้อผิดพลาด

# เส้นทาง (Route) สำหรับหน้าหลัก
@app.route('/')
def index():
    # ตรวจสอบว่าเริ่มต้นระบบแล้วหรือไม่
    if camera is None:
        # ยังไม่ได้เริ่มต้นระบบ
        if initialize_system():
            return redirect(url_for('dashboard'))
        else:
            return render_template('error.html', message="ไม่สามารถเริ่มต้นระบบได้")
    
    return redirect(url_for('dashboard'))

# เส้นทางสำหรับ Dashboard
@app.route('/dashboard')
def dashboard():
    status = camera.get_status() if camera else {}
    return render_template('dashboard.html', 
                          branch_id=branch_id,
                          branch_name=branch_name,
                          status=status,
                          camera_list=camera.get_camera_list() if camera else [])

# เส้นทางสำหรับการจัดการกล้อง
@app.route('/cameras')
def cameras():
    return render_template('cameras.html', 
                          cameras=camera.get_camera_list() if camera else [],
                          branch_id=branch_id)

# เส้นทางสำหรับสถิติ
@app.route('/stats')
def stats():
    stats = data_manager.get_daily_stats(days=7) if data_manager else []
    return render_template('stats.html', stats=stats, branch_id=branch_id)

# เส้นทางสำหรับการตั้งค่า
@app.route('/settings')
def settings():
    config_dict = {}
    if config_manager:
        for section in config_manager.sections():
            config_dict[section] = {}
            for key in config_manager.options(section):
                config_dict[section][key] = config_manager.get(section, key)
    
    return render_template('settings.html', 
                          branch_id=branch_id,
                          config=config_dict)

# API สำหรับดึงเฟรมปัจจุบันของกล้อง
@app.route('/api/frame/<int:camera_id>')
def get_frame(camera_id):
    if camera_id in video_frames:
        return jsonify({'frame': video_frames[camera_id]})
    return jsonify({'error': 'ไม่พบเฟรมสำหรับกล้องนี้'}), 404

# API สำหรับเริ่มการทำงานของกล้อง
@app.route('/api/camera/start', methods=['POST'])
def start_camera():
    if camera:
        success = camera.start()
        return jsonify({'success': success, 'message': 'เริ่มการทำงานของกล้องสำเร็จ' if success else 'ไม่สามารถเริ่มการทำงานของกล้องได้'})
    return jsonify({'success': False, 'message': 'ไม่พบอินสแตนซ์ของกล้อง'}), 500

# API สำหรับหยุดการทำงานของกล้อง
@app.route('/api/camera/stop', methods=['POST'])
def stop_camera():
    if camera:
        success = camera.stop()
        return jsonify({'success': success, 'message': 'หยุดการทำงานของกล้องสำเร็จ' if success else 'ไม่สามารถหยุดการทำงานของกล้องได้'})
    return jsonify({'success': False, 'message': 'ไม่พบอินสแตนซ์ของกล้อง'}), 500

# API สำหรับรีเซ็ตตัวนับ
@app.route('/api/camera/reset', methods=['POST'])
def reset_counters():
    if camera:
        camera.reset_counters()
        return jsonify({'success': True, 'message': 'รีเซ็ตตัวนับสำเร็จ'})
    return jsonify({'success': False, 'message': 'ไม่พบอินสแตนซ์ของกล้อง'}), 500

# API สำหรับถ่ายภาพ
@app.route('/api/camera/snapshot', methods=['POST'])
def take_snapshot():
    if camera:
        camera_id = request.json.get('camera_id', None)
        try:
            camera_id = int(camera_id) if camera_id is not None else None
        except ValueError:
            return jsonify({'success': False, 'message': 'รหัสกล้องไม่ถูกต้อง'}), 400
            
        frame = camera.take_snapshot(camera_id)
        
        if frame is not None:
            # บันทึกภาพ
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"static/snapshots/{branch_id}_{timestamp}.jpg"
            cv2.imwrite(filename, frame)
            
            # ส่งภาพไปยังเซิร์ฟเวอร์ (ในเธรดแยก)
            threading.Thread(target=lambda: api_client.upload_snapshot(frame, {
                'people_in_store': camera.people_in_store,
                'branch_id': branch_id
            })).start()
            
            return jsonify({
                'success': True, 
                'message': 'ถ่ายภาพสำเร็จ',
                'filename': filename,
                'url': url_for('static', filename=f'snapshots/{branch_id}_{timestamp}.jpg')
            })
        else:
            return jsonify({'success': False, 'message': 'ไม่สามารถถ่ายภาพได้'}), 500
    return jsonify({'success': False, 'message': 'ไม่พบอินสแตนซ์ของกล้อง'}), 500

# API สำหรับดึงข้อมูลสถานะ
@app.route('/api/status')
def get_status():
    if camera:
        status = camera.get_status()
        
        # เพิ่มข้อมูลการซิงค์
        if api_client:
            sync_status = api_client.get_sync_status()
            status['sync'] = sync_status
        
        return jsonify(status)
    return jsonify({'error': 'ไม่พบอินสแตนซ์ของกล้อง'}), 500

# API สำหรับส่งออกรายงาน
@app.route('/api/stats/export', methods=['POST'])
def export_stats():
    if data_manager:
        start_date = request.json.get('start_date')
        end_date = request.json.get('end_date')
        
        filename = data_manager.export_daily_stats(start_date, end_date)
        
        if filename:
            return jsonify({
                'success': True,
                'message': 'ส่งออกรายงานสำเร็จ',
                'filename': filename
            })
        else:
            return jsonify({'success': False, 'message': 'ไม่สามารถส่งออกรายงานได้'}), 500
    return jsonify({'success': False, 'message': 'ไม่พบอินสแตนซ์ของตัวจัดการข้อมูล'}), 500

# API สำหรับดาวน์โหลดไฟล์
@app.route('/api/download/<path:filename>')
def download_file(filename):
    return send_file(filename, as_attachment=True)

# API สำหรับการเพิ่มกล้อง
@app.route('/api/camera/add', methods=['POST'])
def add_camera():
    if config_manager:
        try:
            data = request.json
            
            # นับจำนวนกล้องปัจจุบัน
            camera_count = len(camera.get_camera_list())
            
            # กำหนด camera_id ใหม่
            new_camera_id = camera_count + 1
            
            # สร้างส่วน Camera_X ในไฟล์ config
            camera_section = f"Camera_{new_camera_id}"
            
            # ตั้งค่า MultiCameras ถ้ายังไม่มี
            if not config_manager.has_section('MultiCameras'):
                config_manager.add_section('MultiCameras')
                config_manager.set('MultiCameras', 'enabled', 'true')
                config_manager.set('MultiCameras', 'camera_count', '1')
            else:
                current_count = config_manager.getint('MultiCameras', 'camera_count', fallback=0)
                config_manager.set('MultiCameras', 'camera_count', str(current_count + 1))
                config_manager.set('MultiCameras', 'enabled', 'true')
            
            # สร้างส่วน Camera_X
            if not config_manager.has_section(camera_section):
                config_manager.add_section(camera_section)
            
            # บันทึกข้อมูลกล้อง
            config_manager.set(camera_section, 'name', data.get('name', f'Camera {new_camera_id}'))
            config_manager.set(camera_section, 'type', data.get('type', 'dahua'))
            
            if data.get('connection_mode') == 'direct':
                # บันทึก URL โดยตรง
                config_manager.set(camera_section, 'source', data.get('source', ''))
            else:
                # บันทึกพารามิเตอร์การเชื่อมต่อ
                config_manager.set(camera_section, 'host', data.get('host', ''))
                config_manager.set(camera_section, 'port', data.get('port', '554'))
                config_manager.set(camera_section, 'username', data.get('username', 'admin'))
                config_manager.set(camera_section, 'password', data.get('password', ''))
                config_manager.set(camera_section, 'channel', data.get('channel', '1'))
                
                if data.get('path') and data.get('type') == "generic":
                    config_manager.set(camera_section, 'path', data.get('path', ''))
            
            # บันทึกการตั้งค่าตรวจจับ
            config_manager.set(camera_section, 'detection_line', data.get('detection_line', '240'))
            config_manager.set(camera_section, 'min_area', data.get('min_area', '500'))
            config_manager.set(camera_section, 'detection_angle', data.get('detection_angle', '90'))
            
            # บันทึกการตั้งค่า
            config_manager.save()
            
            # รีเซ็ต camera_counter เพื่อโหลดกล้องใหม่
            camera._setup_multiple_cameras()
            
            return jsonify({
                'success': True,
                'message': f"เพิ่มกล้อง '{data.get('name', f'Camera {new_camera_id}')}' สำเร็จ",
                'camera_id': new_camera_id
            })
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการเพิ่มกล้อง: {str(e)}")
            return jsonify({'success': False, 'message': f"เกิดข้อผิดพลาด: {str(e)}"}), 500
    
    return jsonify({'success': False, 'message': 'ไม่พบอินสแตนซ์ของตัวจัดการการตั้งค่า'}), 500

# API สำหรับการแก้ไขกล้อง
@app.route('/api/camera/edit/<int:camera_id>', methods=['POST'])
def edit_camera(camera_id):
    if config_manager:
        try:
            data = request.json
            
            # ตรวจสอบว่ามีกล้องนี้หรือไม่
            camera_section = f"Camera_{camera_id}" if camera_id > 0 else "Camera"
            if not config_manager.has_section(camera_section):
                return jsonify({'success': False, 'message': 'ไม่พบกล้องนี้'}), 404
            
            # บันทึกข้อมูลกล้อง
            config_manager.set(camera_section, 'name', data.get('name', f'Camera {camera_id}'))
            config_manager.set(camera_section, 'type', data.get('type', 'dahua'))
            
            # ลบค่าเดิมที่อาจมีอยู่
            if config_manager.has_option(camera_section, 'source'):
                config_manager.remove_option(camera_section, 'source')
            
            if config_manager.has_option(camera_section, 'host'):
                config_manager.remove_option(camera_section, 'host')
                config_manager.remove_option(camera_section, 'port')
                config_manager.remove_option(camera_section, 'username')
                config_manager.remove_option(camera_section, 'password')
                config_manager.remove_option(camera_section, 'channel')
                config_manager.remove_option(camera_section, 'path')
            
            if data.get('connection_mode') == 'direct':
                # บันทึก URL โดยตรง
                config_manager.set(camera_section, 'source', data.get('source', ''))
            else:
                # บันทึกพารามิเตอร์การเชื่อมต่อ
                config_manager.set(camera_section, 'host', data.get('host', ''))
                config_manager.set(camera_section, 'port', data.get('port', '554'))
                config_manager.set(camera_section, 'username', data.get('username', 'admin'))
                config_manager.set(camera_section, 'password', data.get('password', ''))
                config_manager.set(camera_section, 'channel', data.get('channel', '1'))
                
                if data.get('path') and data.get('type') == "generic":
                    config_manager.set(camera_section, 'path', data.get('path', ''))
            
            # บันทึกการตั้งค่าตรวจจับ
            config_manager.set(camera_section, 'detection_line', data.get('detection_line', '240'))
            config_manager.set(camera_section, 'min_area', data.get('min_area', '500'))
            config_manager.set(camera_section, 'detection_angle', data.get('detection_angle', '90'))
            
            # บันทึกการตั้งค่า
            config_manager.save()
            
            # รีเซ็ต camera_counter เพื่อโหลดกล้องใหม่
            camera._setup_multiple_cameras()
            
            return jsonify({
                'success': True,
                'message': f"แก้ไขกล้อง '{data.get('name', f'Camera {camera_id}')}' สำเร็จ"
            })
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการแก้ไขกล้อง: {str(e)}")
            return jsonify({'success': False, 'message': f"เกิดข้อผิดพลาด: {str(e)}"}), 500
    
    return jsonify({'success': False, 'message': 'ไม่พบอินสแตนซ์ของตัวจัดการการตั้งค่า'}), 500

# API สำหรับการลบกล้อง
@app.route('/api/camera/delete/<int:camera_id>', methods=['POST'])
def delete_camera(camera_id):
    if config_manager:
        try:
            # ไม่อนุญาตให้ลบกล้องเริ่มต้น (ID = 0)
            if camera_id == 0:
                return jsonify({'success': False, 'message': 'ไม่สามารถลบกล้องเริ่มต้นได้'}), 400
            
            # ลบส่วนการตั้งค่าของกล้อง
            camera_section = f"Camera_{camera_id}"
            if config_manager.has_section(camera_section):
                config_manager.remove_section(camera_section)
            else:
                return jsonify({'success': False, 'message': 'ไม่พบกล้องนี้'}), 404
            
            # ปรับปรุงจำนวนกล้อง
            camera_count = config_manager.getint('MultiCameras', 'camera_count', fallback=0)
            config_manager.set('MultiCameras', 'camera_count', str(camera_count - 1))
            
            # บันทึกการตั้งค่า
            config_manager.save()
            
            # รีเซ็ต camera_counter เพื่อโหลดกล้องใหม่
            camera._setup_multiple_cameras()
            
            return jsonify({
                'success': True,
                'message': f"ลบกล้องสำเร็จ"
            })
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการลบกล้อง: {str(e)}")
            return jsonify({'success': False, 'message': f"เกิดข้อผิดพลาด: {str(e)}"}), 500
    
    return jsonify({'success': False, 'message': 'ไม่พบอินสแตนซ์ของตัวจัดการการตั้งค่า'}), 500

# API สำหรับการบันทึกการตั้งค่า
@app.route('/api/settings/save', methods=['POST'])
def save_settings():
    if config_manager:
        try:
            data = request.json
            
            # บันทึกการตั้งค่าสาขา
            config_manager.set('Branch', 'name', data.get('branch_name', 'สาขาหลัก'))
            config_manager.set('Branch', 'location', data.get('branch_location', 'ไม่ระบุ'))
            
            # บันทึกการตั้งค่ากล้อง
            config_manager.set('Camera', 'width', data.get('camera_width', '640'))
            config_manager.set('Camera', 'height', data.get('camera_height', '480'))
            config_manager.set('Camera', 'fps', data.get('camera_fps', '30'))
            
            # บันทึกมุมของเส้นตรวจจับ
            config_manager.set('Camera', 'detection_angle', data.get('detection_angle', '90'))
            
            # บันทึกการตั้งค่าการตรวจจับ
            config_manager.set('Detection', 'min_area', data.get('min_area', '500'))
            config_manager.set('Detection', 'threshold', data.get('threshold', '20'))
            config_manager.set('Detection', 'blur_size', data.get('blur_size', '21'))
            config_manager.set('Detection', 'direction_threshold', data.get('direction_threshold', '10'))
            
            # บันทึกการตั้งค่า API
            config_manager.set('API', 'server_url', data.get('server_url', 'http://localhost:5000'))
            config_manager.set('API', 'api_key', data.get('api_key', ''))
            config_manager.set('API', 'sync_interval', data.get('sync_interval', '900'))
            
            # บันทึกการตั้งค่า
            if config_manager.save():
                # อัพเดตชื่อสาขา
                global branch_name
                branch_name = data.get('branch_name', 'สาขาหลัก')
                
                # ปรับมุมเส้นตรวจจับหลังจากบันทึก
                try:
                    new_angle = int(data.get('detection_angle', '90'))
                    camera.adjust_line_angle(new_angle)
                    logger.info(f"ปรับมุมเส้นตรวจจับเป็น {new_angle} องศา")
                except ValueError:
                    logger.error("ค่ามุมเส้นตรวจจับไม่ถูกต้อง")
                
                return jsonify({
                    'success': True,
                    'message': 'บันทึกการตั้งค่าสำเร็จ การตั้งค่าบางอย่างอาจต้องรีสตาร์ทโปรแกรมเพื่อให้มีผล'
                })
            else:
                return jsonify({'success': False, 'message': 'ไม่สามารถบันทึกการตั้งค่าได้'}), 500
                
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการบันทึกการตั้งค่า: {str(e)}")
            return jsonify({'success': False, 'message': f"เกิดข้อผิดพลาด: {str(e)}"}), 500
    
    return jsonify({'success': False, 'message': 'ไม่พบอินสแตนซ์ของตัวจัดการการตั้งค่า'}), 500

# API สำหรับการทดสอบการเชื่อมต่อกับกล้อง
@app.route('/api/camera/test_connection', methods=['POST'])
def test_camera_connection():
    try:
        data = request.json
        connection_mode = data.get('connection_mode', 'params')
        
        # สร้าง URL
        if connection_mode == 'direct':
            url = data.get('source', '')
        else:
            # ดึงข้อมูลการเชื่อมต่อ
            host = data.get('host', '')
            port = data.get('port', '554')
            username = data.get('username', 'admin')
            password = data.get('password', '')
            channel = data.get('channel', '1')
            path = data.get('path', '')
            camera_type = data.get('type', 'dahua')
            
            # เข้ารหัสรหัสผ่าน
            import urllib.parse
            encoded_password = urllib.parse.quote(password)
            
            if camera_type == "hikvision":
                url = f"rtsp://{username}:{encoded_password}@{host}:{port}/Streaming/Channels/{channel}01"
            elif camera_type == "dahua":
                url = f"rtsp://{username}:{encoded_password}@{host}:{port}/cam/realmonitor?channel={channel}&subtype=0"
            else:  # generic
                url = f"rtsp://{username}:{encoded_password}@{host}:{port}"
                if path:
                    if not path.startswith('/'):
                        url += f"/{path}"
                    else:
                        url += path
        
        # แสดง URL ที่ใช้
        logger.info(f"ทดสอบการเชื่อมต่อกับกล้อง: {url}")
        
        # ทดสอบการเชื่อมต่อ
        cap = cv2.VideoCapture(url)
        
        if cap.isOpened():
            # ลองอ่านเฟรม
            ret, frame = cap.read()
            
            # ปิดการเชื่อมต่อ
            cap.release()
            
            if ret:
                return jsonify({'success': True, 'message': 'เชื่อมต่อกับกล้องสำเร็จ'})
            else:
                return jsonify({'success': False, 'message': 'เปิดการเชื่อมต่อได้ แต่ไม่สามารถอ่านเฟรมได้'})
        
        return jsonify({'success': False, 'message': 'ไม่สามารถเชื่อมต่อกับกล้องได้'})
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการทดสอบการเชื่อมต่อกับกล้อง: {str(e)}")
        return jsonify({'success': False, 'message': f"เกิดข้อผิดพลาด: {str(e)}"}), 500

# API สำหรับดึงรายละเอียดของกล้อง
@app.route('/api/camera/<int:camera_id>')
def get_camera_details(camera_id):
    if camera and config_manager:
        try:
            # ดึงข้อมูลกล้องจาก CameraCounter
            cameras = camera.get_camera_list()
            selected_camera = next((cam for cam in cameras if cam['id'] == camera_id), None)
            
            if not selected_camera:
                return jsonify({'success': False, 'message': 'ไม่พบกล้องนี้'}), 404
            
            # ดึงรายละเอียดเพิ่มเติมจาก config.ini
            camera_section = f"Camera_{camera_id}" if camera_id > 0 else "Camera"
            
            # ตรวจสอบว่าส่วนนี้มีอยู่ใน config หรือไม่
            if not config_manager.has_section(camera_section):
                return jsonify({'success': False, 'message': 'ไม่พบข้อมูลการตั้งค่ากล้องนี้'}), 404
            
            # ดึงข้อมูลจาก config
            camera_type = config_manager.get(camera_section, 'type', fallback='generic')
            
            # ตรวจสอบว่ามีการตั้งค่าแบบ URL โดยตรงหรือไม่
            has_direct_source = config_manager.has_option(camera_section, 'source')
            source = config_manager.get(camera_section, 'source', fallback='') if has_direct_source else ''
            
            # ข้อมูลพารามิเตอร์การเชื่อมต่อ
            host = config_manager.get(camera_section, 'host', fallback='')
            port = config_manager.get(camera_section, 'port', fallback='554')
            username = config_manager.get(camera_section, 'username', fallback=config_manager.get('MultiCameras', 'username', fallback='admin'))
            password = config_manager.get(camera_section, 'password', fallback=config_manager.get('MultiCameras', 'password', fallback=''))
            channel = config_manager.get(camera_section, 'channel', fallback='1')
            path = config_manager.get(camera_section, 'path', fallback='')
            
            # ข้อมูลการตรวจจับ
            detection_line = config_manager.getint(camera_section, 'detection_line', fallback=240)
            detection_angle = config_manager.getint(camera_section, 'detection_angle', fallback=90)
            min_area = config_manager.getint(camera_section, 'min_area', fallback=500)
            
            # สร้างข้อมูลที่จะส่งกลับ
            camera_details = {
                'id': camera_id,
                'name': selected_camera['name'],
                'running': selected_camera['running'],
                'people_in_store': selected_camera['people_in_store'],
                'entry_count': selected_camera['entry_count'],
                'exit_count': selected_camera['exit_count'],
                'type': camera_type,
                'connection_mode': 'direct' if has_direct_source else 'params',
                'source': source,
                'host': host,
                'port': port,
                'username': username,
                'password': password,
                'channel': channel,
                'path': path,
                'detection_line': detection_line,
                'detection_angle': detection_angle,
                'min_area': min_area
            }
            
            return jsonify({'success': True, 'camera': camera_details})
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการดึงรายละเอียดกล้อง: {str(e)}")
            return jsonify({'success': False, 'message': f"เกิดข้อผิดพลาด: {str(e)}"}), 500
    
    return jsonify({'success': False, 'message': 'ไม่พบอินสแตนซ์ของกล้องหรือตัวจัดการการตั้งค่า'}), 500

# เริ่มต้นเซิร์ฟเวอร์
if __name__ == '__main__':
    # สร้างพาร์เซอร์สำหรับพารามิเตอร์บรรทัดคำสั่ง
    import argparse
    
    parser = argparse.ArgumentParser(description='เว็บแอปพลิเคชันสำหรับระบบนับลูกค้าผ่านกล้องวงจรปิด')
    parser.add_argument('--config', type=str, default='config.ini', help='ไฟล์การตั้งค่า')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='IP แอดเดรสสำหรับเซิร์ฟเวอร์')
    parser.add_argument('--port', type=int, default=5000, help='พอร์ตสำหรับเซิร์ฟเวอร์')
    parser.add_argument('--debug', action='store_true', help='เปิดโหมดดีบัก')
    
    args = parser.parse_args()
    
    # เริ่มต้นระบบ
    if initialize_system(args.config, args.debug):
        # เริ่มเซิร์ฟเวอร์
        app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)