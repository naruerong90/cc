#!/usr/bin/env python3
# main.py - จุดเริ่มต้นของแอปพลิเคชันบน Mini PC
import os
import sys
import argparse
import logging
from logging.handlers import RotatingFileHandler
import time

# นำเข้าโมดูลจากโฟลเดอร์ client
sys.path.append('client')
from config_manager import ConfigManager
from camera_counter import CameraCounter
from data_manager import DataManager
from api_client import APIClient
from gui_manager import GUIManager
from user_interface import ConsoleUI

def setup_logging(debug_mode=False):
    """กำหนดค่าเริ่มต้นสำหรับการบันทึกล็อก"""
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)
    
    log_level = logging.DEBUG if debug_mode else logging.INFO
    
    # กำหนดรูปแบบและระดับการบันทึกล็อก
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            RotatingFileHandler(
                os.path.join(log_dir, 'shop_counter.log'), 
                maxBytes=10485760, 
                backupCount=5
            ),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger("ShopCounter")

def main():
    """ฟังก์ชันหลักของแอปพลิเคชัน"""
    # ตั้งค่าตัวแปรการรันคำสั่ง
    parser = argparse.ArgumentParser(description='ระบบนับลูกค้าผ่านกล้องวงจรปิดสำหรับสาขา')
    parser.add_argument('--config', type=str, default='config.ini', help='ไฟล์การตั้งค่า')
    parser.add_argument('--branch', type=str, help='รหัสสาขา')
    parser.add_argument('--video', type=str, help='แหล่งวีดีโอ (อาจเป็นตัวเลขสำหรับกล้องในเครื่อง หรือ URL หรือพาธของไฟล์)')
    parser.add_argument('--no-gui', action='store_true', help='เรียกใช้งานแบบไม่มี GUI')
    parser.add_argument('--no-display', action='store_true', help='ไม่แสดงหน้าต่างวีดีโอ')
    parser.add_argument('--debug', action='store_true', help='เปิดโหมดดีบัก')
    
    args = parser.parse_args()
    
    # ตั้งค่าระบบบันทึกล็อก
    logger = setup_logging(args.debug)
    logger.info("กำลังเริ่มระบบนับลูกค้าสำหรับสาขา...")
    
    # สร้างโฟลเดอร์ที่จำเป็น
    os.makedirs('exports', exist_ok=True)
    os.makedirs('cache', exist_ok=True)
    os.makedirs('backups', exist_ok=True)
    
    try:
        # โหลดการตั้งค่า
        config_manager = ConfigManager(args.config)
        
        # ตรวจสอบและตั้งค่ารหัสสาขา
        branch_id = args.branch or config_manager.get('Branch', 'id', fallback=None)
        if not branch_id:
            # สร้างรหัสสาขาอัตโนมัติถ้าไม่มีการระบุ
            import uuid
            branch_id = f"branch_{uuid.uuid4().hex[:8]}"
            config_manager.set('Branch', 'id', branch_id)
            config_manager.save()
            logger.info(f"สร้างรหัสสาขาอัตโนมัติ: {branch_id}")
        
        # สร้างอินสแตนซ์ของตัวจัดการข้อมูล
        data_manager = DataManager(config_manager, branch_id=branch_id)
        
        # สร้างอินสแตนซ์ของตัวเชื่อมต่อ API
        api_client = APIClient(config_manager, data_manager, branch_id=branch_id)
        
        # สร้างอินสแตนซ์ของตัวนับจากกล้อง
        camera = CameraCounter(
            config_manager=config_manager,
            data_manager=data_manager,
            video_source=args.video,
            display_video=(not args.no_display),
            branch_id=branch_id,
            debug_mode=args.debug
        )
        
        # เริ่มการทำงานของระบบ
        if args.no_gui:
            # โหมด console
            logger.info("เริ่มการทำงานในโหมด console")
            camera.start()
            
            # เริ่มการซิงค์ข้อมูลกับเซิร์ฟเวอร์
            api_client.start_sync()
            
            # เริ่มส่วนติดต่อผู้ใช้แบบคอนโซล
            console_ui = ConsoleUI(camera, data_manager, api_client)
            console_ui.run()
        else:
            # โหมด GUI
            logger.info("เริ่มการทำงานในโหมด GUI")
            gui = GUIManager(camera, data_manager, api_client, config_manager)
            gui.run()
        
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการเริ่มระบบ: {str(e)}", exc_info=True)
        return 1
    
    logger.info("ระบบหยุดการทำงานเรียบร้อย")
    return 0

if __name__ == "__main__":
    sys.exit(main())