#!/usr/bin/env python3
# config_manager.py - จัดการการตั้งค่าระบบ
import os
import configparser
import logging
import json

class ConfigManager:
    """จัดการการตั้งค่าของระบบจากไฟล์ config.ini"""
    
    def __init__(self, config_file="config.ini"):
        """กำหนดค่าเริ่มต้นสำหรับตัวจัดการการตั้งค่า"""
        self.logger = logging.getLogger("ConfigManager")
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        
        # โหลดหรือสร้างไฟล์การตั้งค่า
        self._load_or_create_config()
    
    def _load_or_create_config(self):
        """โหลดไฟล์การตั้งค่าที่มีอยู่หรือสร้างไฟล์ใหม่ถ้าไม่มี"""
        if os.path.exists(self.config_file):
            try:
                self.config.read(self.config_file, encoding='utf-8')
                self.logger.info(f"โหลดไฟล์การตั้งค่า: {self.config_file}")
            except Exception as e:
                self.logger.error(f"เกิดข้อผิดพลาดในการโหลดไฟล์การตั้งค่า: {str(e)}")
                # สร้างไฟล์การตั้งค่าใหม่
                self._create_default_config()
        else:
            self._create_default_config()
    
    def _create_default_config(self):
        """สร้างไฟล์การตั้งค่าเริ่มต้น"""
        # ส่วนของสาขา
        self.config['Branch'] = {
            'id': '',  # จะถูกสร้างอัตโนมัติหากไม่ได้ระบุ
            'name': 'สาขาหลัก',
            'location': 'ไม่ระบุ'
        }
        
        # ส่วนของกล้อง
        self.config['Camera'] = {
            'source': '0',  # 0 หมายถึงกล้องเริ่มต้น
            'width': '640',
            'height': '480',
            'fps': '30',
            'detection_line': '240'  # ตำแหน่งเส้นตรวจจับตามแนวตั้ง (กลางภาพ)
        }
        
        # ส่วนของการตรวจจับ
        self.config['Detection'] = {
            'min_area': '500',  # พื้นที่ขั้นต่ำสำหรับตรวจจับการเคลื่อนไหว
            'threshold': '20',  # ค่า threshold สำหรับตรวจจับการเคลื่อนไหว
            'blur_size': '21',  # ขนาดของการ blur
            'direction_threshold': '10'  # ระยะทางขั้นต่ำที่จะถือว่ามีการเคลื่อนที่
        }
        
        # ส่วนของฐานข้อมูล
        self.config['Database'] = {
            'db_name': 'shop_tracking.db',
            'backup_interval': '86400'  # สำรองฐานข้อมูลทุก 24 ชั่วโมง (หน่วยเป็นวินาที)
        }
        
        # ส่วนของการบันทึกข้อมูล
        self.config['Recording'] = {
            'interval_seconds': '300',  # บันทึกข้อมูลทุก 5 นาที
            'export_path': 'exports/',  # ตำแหน่งสำหรับส่งออกรายงาน
            'save_snapshots': 'true'    # บันทึกภาพถ่าย
        }
        
        # ส่วนของการเชื่อมต่อ API
        self.config['API'] = {
            'server_url': 'http://localhost:5000',  # URL ของเซิร์ฟเวอร์หลัก
            'api_key': '',  # API key สำหรับการยืนยันตัวตน
            'sync_interval': '900',  # ซิงค์ข้อมูลทุก 15 นาที (หน่วยเป็นวินาที)
            'retry_interval': '60',  # ลองซิงค์ใหม่ทุก 1 นาที หากไม่สำเร็จ
            'timeout': '30'  # หมดเวลาการเชื่อมต่อหลัง 30 วินาที
        }
        
        # บันทึกไฟล์การตั้งค่า
        self.save()
        self.logger.info(f"สร้างไฟล์การตั้งค่าเริ่มต้น: {self.config_file}")
    
    def get(self, section, option, fallback=None):
        """ดึงค่าจากไฟล์การตั้งค่า"""
        return self.config.get(section, option, fallback=fallback)
    
    def getint(self, section, option, fallback=None):
        """ดึงค่าเป็นจำนวนเต็มจากไฟล์การตั้งค่า"""
        return self.config.getint(section, option, fallback=fallback)
    
    def getfloat(self, section, option, fallback=None):
        """ดึงค่าเป็นจำนวนจริงจากไฟล์การตั้งค่า"""
        return self.config.getfloat(section, option, fallback=fallback)
    
    def getboolean(self, section, option, fallback=None):
        """ดึงค่าเป็นตรรกะจากไฟล์การตั้งค่า"""
        return self.config.getboolean(section, option, fallback=fallback)
    
    def set(self, section, option, value):
        """ตั้งค่าในไฟล์การตั้งค่า"""
        if section not in self.config:
            self.config[section] = {}
        
        self.config[section][option] = str(value)
    
    def has_section(self, section):
        """ตรวจสอบว่ามีส่วนนี้หรือไม่"""
        return self.config.has_section(section)
    
    def has_option(self, section, option):
        """ตรวจสอบว่ามีตัวเลือกนี้หรือไม่"""
        return self.config.has_option(section, option)
    
    def add_section(self, section):
        """เพิ่มส่วนใหม่"""
        if not self.has_section(section):
            self.config.add_section(section)
    
    def remove_section(self, section):
        """ลบส่วน"""
        return self.config.remove_section(section)
    
    def remove_option(self, section, option):
        """ลบตัวเลือก"""
        return self.config.remove_option(section, option)
    
    def sections(self):
        """ดึงรายชื่อส่วนทั้งหมด"""
        return self.config.sections()
    
    def options(self, section):
        """ดึงรายชื่อตัวเลือกในส่วนที่ระบุ"""
        return self.config.options(section)
    
    def save(self):
        """บันทึกการตั้งค่าลงไฟล์"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as configfile:
                self.config.write(configfile)
            self.logger.info(f"บันทึกไฟล์การตั้งค่า: {self.config_file}")
            return True
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการบันทึกไฟล์การตั้งค่า: {str(e)}")
            return False
    
    def export_as_json(self):
        """ส่งออกการตั้งค่าในรูปแบบ JSON"""
        config_dict = {}
        for section in self.config.sections():
            config_dict[section] = {}
            for key, value in self.config[section].items():
                config_dict[section][key] = value
        
        return json.dumps(config_dict, indent=4, ensure_ascii=False)
    
    def import_from_json(self, json_str):
        """นำเข้าการตั้งค่าจาก JSON"""
        try:
            config_dict = json.loads(json_str)
            for section, options in config_dict.items():
                if section not in self.config:
                    self.config[section] = {}
                
                for key, value in options.items():
                    self.config[section][key] = str(value)
            
            self.save()
            self.logger.info("นำเข้าการตั้งค่าจาก JSON สำเร็จ")
            return True
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการนำเข้าการตั้งค่าจาก JSON: {str(e)}")
            return False