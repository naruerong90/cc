#!/usr/bin/env python3
# data_manager.py - จัดการข้อมูลของระบบนับลูกค้าและจัดการพนักงาน
import sqlite3
import datetime
import logging
import os
import csv
import json
import shutil
import time

class DataManager:
    """คลาสสำหรับจัดการข้อมูลของระบบ"""
    
    def __init__(self, config_manager, branch_id=None):
        """กำหนดค่าเริ่มต้นสำหรับตัวจัดการข้อมูล"""
        # ตั้งค่าระบบบันทึก log
        self.logger = logging.getLogger("DataManager")
        
        # กำหนดตัวแปรเริ่มต้น
        self.config_manager = config_manager
        self.branch_id = branch_id or config_manager.get('Branch', 'id', fallback='unknown')
        
        # กำหนดพาธของฐานข้อมูล
        self.db_name = config_manager.get('Database', 'db_name', fallback='shop_tracking.db')
        
        # สร้างฐานข้อมูล
        self._setup_database()
        
        # เวลาสำรองฐานข้อมูลล่าสุด
        self.last_backup_time = time.time()
        
        # รอบเวลาสำรองฐานข้อมูล (วินาที)
        self.backup_interval = config_manager.getint('Database', 'backup_interval', fallback=86400)  # 24 ชั่วโมง
        
        # ตรวจสอบและลองนำข้อมูลจากแคชมาใช้
        self._check_cached_data()
        
        self.logger.info(f"ตัวจัดการข้อมูลถูกเริ่มต้นแล้ว สำหรับสาขา: {self.branch_id}")
        
        # สร้างโฟลเดอร์สำหรับส่งออกข้อมูล
        export_path = config_manager.get('Recording', 'export_path', fallback='exports')
        os.makedirs(export_path, exist_ok=True)
    
    def _setup_database(self):
        """สร้างฐานข้อมูลและตารางที่จำเป็น"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            # สร้างตารางพนักงาน
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                position TEXT NOT NULL,
                status TEXT DEFAULT 'available'
            )
            ''')
            
            # สร้างตารางการนัดหมาย
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                phone TEXT,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                service TEXT NOT NULL,
                employee_id INTEGER,
                status TEXT DEFAULT 'scheduled',
                notes TEXT,
                synced BOOLEAN DEFAULT 0,
                FOREIGN KEY (employee_id) REFERENCES employees (id)
            )
            ''')
            
            # สร้างตารางบันทึกจำนวนลูกค้า
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS customer_counts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                branch_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                entries INTEGER NOT NULL,
                exits INTEGER NOT NULL,
                total_in_store INTEGER NOT NULL,
                synced BOOLEAN DEFAULT 0
            )
            ''')
            
            # สร้างตารางสถิติประจำวัน
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                branch_id TEXT NOT NULL,
                date TEXT NOT NULL,
                total_entries INTEGER NOT NULL,
                total_exits INTEGER NOT NULL,
                peak_time TEXT,
                peak_count INTEGER,
                notes TEXT,
                synced BOOLEAN DEFAULT 0,
                UNIQUE(branch_id, date)
            )
            ''')
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"เตรียมฐานข้อมูล: {self.db_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการเตรียมฐานข้อมูล: {str(e)}")
            return False
    
    def record_customer_count(self, timestamp, entries, exits, total_in_store, branch_id=None):
        """บันทึกจำนวนลูกค้าลงฐานข้อมูล"""
        try:
            # ใช้ branch_id ที่ส่งมา หรือใช้ค่าเริ่มต้น
            branch_id = branch_id or self.branch_id
            
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            # บันทึกข้อมูลลงตาราง customer_counts
            cursor.execute(
                "INSERT INTO customer_counts (branch_id, timestamp, entries, exits, total_in_store, synced) VALUES (?, ?, ?, ?, ?, ?)",
                (branch_id, timestamp, entries, exits, total_in_store, 0)
            )
            
            # อัพเดตหรือเพิ่มข้อมูลลงตาราง daily_stats
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            
            # ตรวจสอบว่ามีข้อมูลของวันนี้หรือไม่
            cursor.execute("SELECT id, total_entries, total_exits, peak_count FROM daily_stats WHERE branch_id = ? AND date = ?", (branch_id, today))
            daily_record = cursor.fetchone()
            
            if daily_record:
                # อัพเดตข้อมูลที่มีอยู่
                record_id, total_entries, total_exits, peak_count = daily_record
                
                # อัพเดตยอดรวม
                cursor.execute(
                    "UPDATE daily_stats SET total_entries = ?, total_exits = ?, synced = ? WHERE id = ?",
                    (entries, exits, 0, record_id)
                )
                
                # อัพเดตช่วงเวลาที่มีลูกค้ามากที่สุด ถ้าจำนวนปัจจุบันมากกว่า
                if total_in_store > peak_count:
                    peak_time = datetime.datetime.now().strftime("%H:%M")
                    cursor.execute(
                        "UPDATE daily_stats SET peak_time = ?, peak_count = ? WHERE id = ?",
                        (peak_time, total_in_store, record_id)
                    )
            else:
                # เพิ่มข้อมูลใหม่
                peak_time = datetime.datetime.now().strftime("%H:%M")
                cursor.execute(
                    "INSERT INTO daily_stats (branch_id, date, total_entries, total_exits, peak_time, peak_count, synced) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (branch_id, today, entries, exits, peak_time, total_in_store, 0)
                )
            
            conn.commit()
            conn.close()
            
            # ตรวจสอบและสำรองฐานข้อมูลถ้าถึงเวลา
            self._check_backup()
            
            return True
            
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการบันทึกข้อมูลจำนวนลูกค้า: {str(e)}")
            # แคชข้อมูลเพื่อใช้ในกรณีที่ฐานข้อมูลมีปัญหา
            self._cache_customer_data(timestamp, entries, exits, total_in_store, branch_id)
            return False
    
    def _cache_customer_data(self, timestamp, entries, exits, total_in_store, branch_id):
        """แคชข้อมูลลูกค้าในกรณีที่ฐานข้อมูลมีปัญหา"""
        try:
            # สร้างโฟลเดอร์แคช
            cache_dir = 'cache'
            os.makedirs(cache_dir, exist_ok=True)
            
            # สร้างชื่อไฟล์
            filename = f"{cache_dir}/customer_data_{int(time.time())}.json"
            
            # เตรียมข้อมูล
            data = {
                'branch_id': branch_id or self.branch_id,
                'timestamp': timestamp,
                'entries': entries,
                'exits': exits,
                'total_in_store': total_in_store
            }
            
            # บันทึกข้อมูล
            with open(filename, 'w') as f:
                json.dump(data, f)
            
            self.logger.info(f"แคชข้อมูลลูกค้าไปยัง: {filename}")
            return True
            
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการแคชข้อมูลลูกค้า: {str(e)}")
            return False
    
    def _check_cached_data(self):
        """ตรวจสอบและนำข้อมูลจากแคชมาใช้ถ้ามี"""
        try:
            cache_dir = 'cache'
            if not os.path.exists(cache_dir):
                return
            
            # ตรวจสอบไฟล์ในโฟลเดอร์แคช
            cached_files = [f for f in os.listdir(cache_dir) if f.startswith('customer_data_') and f.endswith('.json')]
            
            if not cached_files:
                return
            
            self.logger.info(f"พบข้อมูลแคช {len(cached_files)} รายการ กำลังนำมาใช้...")
            
            # นำข้อมูลจากแคชมาใช้
            for filename in cached_files:
                try:
                    # อ่านข้อมูล
                    with open(os.path.join(cache_dir, filename), 'r') as f:
                        data = json.load(f)
                    
                    # บันทึกลงฐานข้อมูล
                    self.record_customer_count(
                        data['timestamp'],
                        data['entries'],
                        data['exits'],
                        data['total_in_store'],
                        data['branch_id']
                    )
                    
                    # ลบไฟล์แคช
                    os.remove(os.path.join(cache_dir, filename))
                    
                except Exception as e:
                    self.logger.error(f"เกิดข้อผิดพลาดในการนำข้อมูลแคชมาใช้ ({filename}): {str(e)}")
            
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการตรวจสอบข้อมูลแคช: {str(e)}")
    
    def _check_backup(self):
        """ตรวจสอบและสำรองฐานข้อมูลถ้าถึงเวลา"""
        current_time = time.time()
        if current_time - self.last_backup_time > self.backup_interval:
            self.backup_database()
            self.last_backup_time = current_time
    
    def backup_database(self):
        """สำรองฐานข้อมูล"""
        try:
            # สร้างโฟลเดอร์สำรอง
            backup_dir = 'backups'
            os.makedirs(backup_dir, exist_ok=True)
            
            # สร้างชื่อไฟล์
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"{backup_dir}/{self.branch_id}_{timestamp}.db"
            
            # สำรองฐานข้อมูล
            shutil.copy2(self.db_name, backup_file)
            
            self.logger.info(f"สำรองฐานข้อมูลไปยัง: {backup_file}")
            
            # จำกัดจำนวนไฟล์สำรอง (เก็บแค่ 10 ไฟล์ล่าสุด)
            self._cleanup_backups(backup_dir, 10)
            
            return True
            
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการสำรองฐานข้อมูล: {str(e)}")
            return False
    
    def _cleanup_backups(self, backup_dir, keep_count):
        """ลบไฟล์สำรองเก่า เหลือแค่จำนวนที่กำหนด"""
        try:
            backup_files = [os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.endswith('.db')]
            backup_files.sort(key=os.path.getmtime)  # เรียงตามเวลาแก้ไข
            
            # ลบไฟล์เก่า
            while len(backup_files) > keep_count:
                old_file = backup_files.pop(0)  # ลบไฟล์เก่าที่สุด
                os.remove(old_file)
                self.logger.info(f"ลบไฟล์สำรองเก่า: {old_file}")
                
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการลบไฟล์สำรองเก่า: {str(e)}")
    
    def get_unsync_data(self, limit=100):
        """ดึงข้อมูลที่ยังไม่ได้ซิงค์กับเซิร์ฟเวอร์"""
        try:
            conn = sqlite3.connect(self.db_name)
            conn.row_factory = sqlite3.Row  # เพื่อให้ผลลัพธ์เป็น dict
            cursor = conn.cursor()
            
            # ดึงข้อมูลลูกค้าที่ยังไม่ได้ซิงค์
            cursor.execute(
                "SELECT id, branch_id, timestamp, entries, exits, total_in_store FROM customer_counts WHERE synced = 0 ORDER BY timestamp LIMIT ?",
                (limit,)
            )
            customer_counts = [dict(row) for row in cursor.fetchall()]
            
            # ดึงข้อมูลสถิติประจำวันที่ยังไม่ได้ซิงค์
            cursor.execute(
                "SELECT id, branch_id, date, total_entries, total_exits, peak_time, peak_count, notes FROM daily_stats WHERE synced = 0 ORDER BY date LIMIT ?",
                (limit,)
            )
            daily_stats = [dict(row) for row in cursor.fetchall()]
            
            # ดึงข้อมูลการนัดหมายที่ยังไม่ได้ซิงค์
            cursor.execute(
                """
                SELECT a.id, a.customer_name, a.phone, a.date, a.time, a.service, a.employee_id, a.status, a.notes, 
                       e.name as employee_name
                FROM appointments a
                LEFT JOIN employees e ON a.employee_id = e.id
                WHERE a.synced = 0
                ORDER BY a.date, a.time
                LIMIT ?
                """,
                (limit,)
            )
            appointments = [dict(row) for row in cursor.fetchall()]
            
            conn.close()
            
            return {
                'customer_counts': customer_counts,
                'daily_stats': daily_stats,
                'appointments': appointments
            }
            
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการดึงข้อมูลที่ยังไม่ได้ซิงค์: {str(e)}")
            return {
                'customer_counts': [],
                'daily_stats': [],
                'appointments': []
            }
    
    def mark_as_synced(self, table, ids):
        """ทำเครื่องหมายว่าข้อมูลได้ซิงค์กับเซิร์ฟเวอร์แล้ว"""
        if not ids:
            return True
        
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            # สร้างพารามิเตอร์สำหรับ IN clause
            placeholders = ','.join(['?'] * len(ids))
            
            # อัพเดตสถานะซิงค์
            cursor.execute(f"UPDATE {table} SET synced = 1 WHERE id IN ({placeholders})", ids)
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"ทำเครื่องหมายข้อมูลในตาราง {table} จำนวน {len(ids)} รายการว่าซิงค์แล้ว")
            return True
            
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการทำเครื่องหมายข้อมูลว่าซิงค์แล้ว: {str(e)}")
            return False
    
    def add_employee(self, name, position):
        """เพิ่มพนักงานใหม่"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            cursor.execute("INSERT INTO employees (name, position) VALUES (?, ?)", (name, position))
            
            employee_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            self.logger.info(f"เพิ่มพนักงาน {name} (ID: {employee_id}) สำเร็จ")
            return employee_id
            
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการเพิ่มพนักงาน: {str(e)}")
            return None
    
    def update_employee(self, employee_id, name=None, position=None, status=None):
        """อัพเดตข้อมูลพนักงาน"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            # สร้างชุดคำสั่ง SQL สำหรับอัพเดต
            updates = []
            params = []
            
            if name is not None:
                updates.append("name = ?")
                params.append(name)
                
            if position is not None:
                updates.append("position = ?")
                params.append(position)
                
            if status is not None:
                updates.append("status = ?")
                params.append(status)
            
            # ถ้าไม่มีข้อมูลที่จะอัพเดต
            if not updates:
                conn.close()
                return False
            
            # เพิ่ม ID เข้าไปใน params
            params.append(employee_id)
            
           # สร้างคำสั่ง SQL
            sql = f"UPDATE employees SET {', '.join(updates)} WHERE id = ?"
            
            # ทำการอัพเดต
            cursor.execute(sql, params)
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"อัพเดตพนักงาน ID: {employee_id} สำเร็จ")
            return True
            
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการอัพเดตพนักงาน: {str(e)}")
            return False
    
    def get_employees(self):
        """ดึงรายชื่อพนักงานทั้งหมด"""
        try:
            conn = sqlite3.connect(self.db_name)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT id, name, position, status FROM employees ORDER BY name")
            employees = [dict(row) for row in cursor.fetchall()]
            
            conn.close()
            return employees
            
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการดึงรายชื่อพนักงาน: {str(e)}")
            return []
    
    def add_appointment(self, customer_name, phone, date, time, service, employee_id=None, notes=""):
        """เพิ่มการนัดหมายใหม่"""
        try:
            # ตรวจสอบรูปแบบวันที่และเวลา
            try:
                datetime.datetime.strptime(date, "%Y-%m-%d")
                datetime.datetime.strptime(time, "%H:%M")
            except ValueError:
                self.logger.error("รูปแบบวันที่หรือเวลาไม่ถูกต้อง")
                return None
            
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            # ตรวจสอบว่าพนักงานมีอยู่หรือไม่
            if employee_id:
                cursor.execute("SELECT id FROM employees WHERE id = ?", (employee_id,))
                if not cursor.fetchone():
                    conn.close()
                    self.logger.error(f"ไม่พบพนักงาน ID: {employee_id}")
                    return None
            
            # เพิ่มการนัดหมายใหม่
            cursor.execute("""
                INSERT INTO appointments (customer_name, phone, date, time, service, employee_id, notes, synced) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (customer_name, phone, date, time, service, employee_id, notes, 0))
            
            appointment_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            self.logger.info(f"เพิ่มการนัดหมาย ID: {appointment_id} สำหรับลูกค้า: {customer_name} สำเร็จ")
            return appointment_id
            
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการเพิ่มการนัดหมาย: {str(e)}")
            return None
    
    def update_appointment_status(self, appointment_id, status):
        """อัพเดตสถานะการนัดหมาย"""
        try:
            valid_statuses = ['scheduled', 'completed', 'cancelled']
            
            if status not in valid_statuses:
                self.logger.error(f"สถานะไม่ถูกต้อง: {status} กรุณาเลือกจาก {', '.join(valid_statuses)}")
                return False
            
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            # ตรวจสอบว่ามีการนัดหมายนี้หรือไม่
            cursor.execute("SELECT id FROM appointments WHERE id = ?", (appointment_id,))
            if not cursor.fetchone():
                conn.close()
                self.logger.error(f"ไม่พบการนัดหมาย ID: {appointment_id}")
                return False
            
            # อัพเดตสถานะและตั้งค่า synced = 0 เพื่อให้ซิงค์ข้อมูลใหม่
            cursor.execute("UPDATE appointments SET status = ?, synced = 0 WHERE id = ?", (status, appointment_id))
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"อัพเดตสถานะการนัดหมาย ID: {appointment_id} เป็น '{status}' สำเร็จ")
            return True
            
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการอัพเดตสถานะการนัดหมาย: {str(e)}")
            return False
    
    def get_appointments(self, date=None, employee_id=None):
        """ดึงรายการนัดหมาย"""
        try:
            conn = sqlite3.connect(self.db_name)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = """
                SELECT a.id, a.customer_name, a.phone, a.date, a.time, a.service, 
                       a.employee_id, e.name as employee_name, a.status, a.notes
                FROM appointments a
                LEFT JOIN employees e ON a.employee_id = e.id
                WHERE 1=1
            """
            params = []
            
            if date:
                query += " AND a.date = ?"
                params.append(date)
            
            if employee_id:
                query += " AND a.employee_id = ?"
                params.append(employee_id)
            
            query += " ORDER BY a.date, a.time"
            
            cursor.execute(query, params)
            appointments = [dict(row) for row in cursor.fetchall()]
            
            conn.close()
            return appointments
            
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการดึงรายการนัดหมาย: {str(e)}")
            return []
    
    def get_daily_stats(self, date=None, days=7):
        """ดึงสถิติประจำวัน"""
        try:
            conn = sqlite3.connect(self.db_name)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if date:
                # ดึงข้อมูลของวันที่ระบุ
                cursor.execute(
                    "SELECT * FROM daily_stats WHERE branch_id = ? AND date = ?",
                    (self.branch_id, date)
                )
                stats = [dict(row) for row in cursor.fetchall()]
            else:
                # ดึงข้อมูลของ x วันล่าสุด
                cursor.execute(
                    """
                    SELECT * FROM daily_stats 
                    WHERE branch_id = ? 
                    ORDER BY date DESC LIMIT ?
                    """,
                    (self.branch_id, days)
                )
                stats = [dict(row) for row in cursor.fetchall()]
            
            conn.close()
            return stats
            
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการดึงสถิติประจำวัน: {str(e)}")
            return []
    
    def export_daily_stats(self, start_date=None, end_date=None):
        """ส่งออกสถิติประจำวันเป็นไฟล์ CSV"""
        try:
            conn = sqlite3.connect(self.db_name)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = """
                SELECT branch_id, date, total_entries, total_exits, peak_time, peak_count, notes
                FROM daily_stats
                WHERE branch_id = ?
            """
            params = [self.branch_id]
            
            if start_date:
                query += " AND date >= ?"
                params.append(start_date)
            
            if end_date:
                query += " AND date <= ?"
                params.append(end_date)
            
            query += " ORDER BY date"
            
            cursor.execute(query, params)
            stats = [dict(row) for row in cursor.fetchall()]
            
            conn.close()
            
            if not stats:
                self.logger.warning("ไม่พบข้อมูลสถิติสำหรับส่งออก")
                return None
            
            # สร้างชื่อไฟล์
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            export_path = self.config_manager.get('Recording', 'export_path', fallback='exports')
            filename = f"{export_path}/daily_stats_{self.branch_id}_{timestamp}.csv"
            
            # เขียนไฟล์ CSV
            with open(filename, 'w', newline='') as csvfile:
                fieldnames = ['branch_id', 'date', 'total_entries', 'total_exits', 'peak_time', 'peak_count', 'notes']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for stat in stats:
                    writer.writerow(stat)
            
            self.logger.info(f"ส่งออกสถิติประจำวันไปยัง: {filename}")
            return filename
            
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการส่งออกสถิติประจำวัน: {str(e)}")
            return None
    
    def import_data(self, employees=None, appointments=None):
        """นำเข้าข้อมูลพนักงานและการนัดหมายจากเซิร์ฟเวอร์"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            # นำเข้าข้อมูลพนักงาน
            if employees:
                for employee in employees:
                    # ตรวจสอบว่ามีพนักงานนี้อยู่แล้วหรือไม่
                    cursor.execute("SELECT id FROM employees WHERE id = ?", (employee['id'],))
                    existing = cursor.fetchone()
                    
                    if existing:
                        # อัพเดตข้อมูลพนักงาน
                        cursor.execute(
                            "UPDATE employees SET name = ?, position = ?, status = ? WHERE id = ?",
                            (employee['name'], employee['position'], employee['status'], employee['id'])
                        )
                    else:
                        # เพิ่มพนักงานใหม่
                        cursor.execute(
                            "INSERT INTO employees (id, name, position, status) VALUES (?, ?, ?, ?)",
                            (employee['id'], employee['name'], employee['position'], employee['status'])
                        )
            
            # นำเข้าข้อมูลการนัดหมาย
            if appointments:
                for appointment in appointments:
                    # ตรวจสอบว่ามีการนัดหมายนี้อยู่แล้วหรือไม่
                    cursor.execute("SELECT id FROM appointments WHERE id = ?", (appointment['id'],))
                    existing = cursor.fetchone()
                    
                    if existing:
                        # อัพเดตข้อมูลการนัดหมาย
                        cursor.execute(
                            """
                            UPDATE appointments 
                            SET customer_name = ?, phone = ?, date = ?, time = ?, service = ?, 
                                employee_id = ?, status = ?, notes = ?, synced = 1
                            WHERE id = ?
                            """,
                            (
                                appointment['customer_name'], appointment['phone'], appointment['date'], 
                                appointment['time'], appointment['service'], appointment['employee_id'], 
                                appointment['status'], appointment['notes'], appointment['id']
                            )
                        )
                    else:
                        # เพิ่มการนัดหมายใหม่
                        cursor.execute(
                            """
                            INSERT INTO appointments 
                            (id, customer_name, phone, date, time, service, employee_id, status, notes, synced) 
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                            """,
                            (
                                appointment['id'], appointment['customer_name'], appointment['phone'], 
                                appointment['date'], appointment['time'], appointment['service'], 
                                appointment['employee_id'], appointment['status'], appointment['notes']
                            )
                        )
            
            conn.commit()
            conn.close()
            
            if employees:
                self.logger.info(f"นำเข้าข้อมูลพนักงาน {len(employees)} รายการสำเร็จ")
            
            if appointments:
                self.logger.info(f"นำเข้าข้อมูลการนัดหมาย {len(appointments)} รายการสำเร็จ")
            
            return True
            
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการนำเข้าข้อมูล: {str(e)}")
            return False