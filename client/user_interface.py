#!/usr/bin/env python3
# user_interface.py - ส่วนติดต่อผู้ใช้แบบคอนโซล
import logging
import time
import datetime
import threading
import os
from prettytable import PrettyTable

class ConsoleUI:
    """คลาสสำหรับจัดการส่วนติดต่อผู้ใช้แบบคอนโซล"""
    
    def __init__(self, camera, data_manager, api_client=None):
        """กำหนดค่าเริ่มต้นสำหรับส่วนติดต่อผู้ใช้"""
        # ตั้งค่าระบบบันทึกล็อก
        self.logger = logging.getLogger("ConsoleUI")
        
        # กำหนดตัวแปรเริ่มต้น
        self.camera = camera
        self.data_manager = data_manager
        self.api_client = api_client
        
        # ตัวแปรสำหรับการทำงาน
        self.running = False
        self.status_thread = None
        self.last_status_time = time.time()
        
        self.logger.info("ส่วนติดต่อผู้ใช้แบบคอนโซลถูกเริ่มต้นแล้ว")
    
    def run(self):
        """เริ่มการทำงานของส่วนติดต่อผู้ใช้"""
        self.running = True
        
        # เริ่มเธรดแสดงสถานะ
        self.status_thread = threading.Thread(target=self._display_status)
        self.status_thread.daemon = True
        self.status_thread.start()
        
        # แสดงเมนูหลัก
        self._show_main_menu()
    
    def _display_status(self):
        """แสดงสถานะของระบบอย่างต่อเนื่อง (เรียกจากเธรดแยก)"""
        while self.running:
            try:
                # รอเวลาเพื่อไม่ให้แสดงผลถี่เกินไป
                time.sleep(1.0)
                
                # แสดงสถานะเฉพาะเมื่อถึงเวลา (ทุก 5 วินาที)
                current_time = time.time()
                if current_time - self.last_status_time >= 5.0:
                    self.last_status_time = current_time
                    
                    # ล้างหน้าจอ (ไม่แน่นอนว่าจะทำงานบนทุกระบบ)
                    # os.system('cls' if os.name == 'nt' else 'clear')
                    
                    # แสดงข้อมูลสถานะ
                    self._print_status()
            except Exception as e:
                self.logger.error(f"เกิดข้อผิดพลาดในการแสดงสถานะ: {str(e)}")
    
    def _print_status(self):
        """แสดงข้อมูลสถานะปัจจุบัน"""
        # แสดงเวลาปัจจุบัน
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n=== สถานะระบบ ณ {now} ===")
        
        # แสดงสถานะกล้อง
        camera_status = self.camera.get_status()
        print(f"สาขา: {self.camera.branch_id}")
        print(f"สถานะกล้อง: {'ทำงาน' if camera_status['running'] else 'ไม่ทำงาน'}")
        print(f"จำนวนลูกค้าในร้าน: {camera_status['people_in_store']}")
        print(f"จำนวนลูกค้าเข้าร้านทั้งหมด: {camera_status['entry_count']}")
        print(f"จำนวนลูกค้าออกจากร้านทั้งหมด: {camera_status['exit_count']}")
        
        # แสดงสถานะการซิงค์ (ถ้ามี)
        if self.api_client:
            sync_status = self.api_client.get_sync_status()
            print(f"สถานะการซิงค์: {'ทำงาน' if sync_status['running'] else 'ไม่ทำงาน'}")
            
            # แสดงเวลาซิงค์ล่าสุด
            last_sync_time = datetime.datetime.fromtimestamp(sync_status['last_sync_time']).strftime("%Y-%m-%d %H:%M:%S")
            print(f"ซิงค์ล่าสุด: {last_sync_time}")
            
            # แสดงเวลาซิงค์ครั้งต่อไป
            next_sync_time = datetime.datetime.fromtimestamp(sync_status['next_sync_time']).strftime("%Y-%m-%d %H:%M:%S")
            print(f"ซิงค์ครั้งต่อไป: {next_sync_time}")
        
        print()
    
    def _show_main_menu(self):
        """แสดงเมนูหลักและรับคำสั่งจากผู้ใช้"""
        while self.running:
            print("\n====== ระบบนับลูกค้าผ่านกล้องวงจรปิด ======")
            print("1. เริ่มการทำงานของกล้อง")
            print("2. หยุดการทำงานของกล้อง")
            print("3. รีเซ็ตตัวนับลูกค้า")
            print("4. แสดงสถิติประจำวัน")
            print("5. ส่งออกรายงาน")
            print("6. เริ่มการซิงค์ข้อมูล")
            print("7. หยุดการซิงค์ข้อมูล")
            print("8. ซิงค์ข้อมูลทันที")
            print("0. ออกจากโปรแกรม")
            
            try:
                choice = input("\nเลือกเมนู (0-8): ")
                
                if choice == '0':
                    self._exit_program()
                    break
                elif choice == '1':
                    self._start_camera()
                elif choice == '2':
                    self._stop_camera()
                elif choice == '3':
                    self._reset_counters()
                elif choice == '4':
                    self._show_daily_stats()
                elif choice == '5':
                    self._export_report()
                elif choice == '6':
                    self._start_sync()
                elif choice == '7':
                    self._stop_sync()
                elif choice == '8':
                    self._sync_now()
                else:
                    print("เมนูไม่ถูกต้อง กรุณาลองใหม่")
                    
            except Exception as e:
                self.logger.error(f"เกิดข้อผิดพลาดในการจัดการเมนู: {str(e)}")
                print(f"เกิดข้อผิดพลาด: {str(e)}")
    
    def _exit_program(self):
        """ออกจากโปรแกรม"""
        print("กำลังปิดโปรแกรม...")
        
        # หยุดการทำงานของกล้อง
        self._stop_camera()
        
        # หยุดการซิงค์ข้อมูล
        if self.api_client:
            self._stop_sync()
        
        # หยุดการทำงานของเธรดแสดงสถานะ
        self.running = False
        if self.status_thread:
            self.status_thread.join(timeout=1.0)
        
        print("ปิดโปรแกรมเรียบร้อย")
    
    def _start_camera(self):
        """เริ่มการทำงานของกล้อง"""
        if self.camera.camera_running:
            print("กล้องกำลังทำงานอยู่แล้ว")
            return
        
        print("กำลังเริ่มการทำงานของกล้อง...")
        if self.camera.start():
            print("เริ่มการทำงานของกล้องสำเร็จ")
        else:
            print("ไม่สามารถเริ่มการทำงานของกล้องได้")
    
    def _stop_camera(self):
        """หยุดการทำงานของกล้อง"""
        if not self.camera.camera_running:
            print("กล้องไม่ได้ทำงานอยู่")
            return
        
        print("กำลังหยุดการทำงานของกล้อง...")
        if self.camera.stop():
            print("หยุดการทำงานของกล้องสำเร็จ")
        else:
            print("ไม่สามารถหยุดการทำงานของกล้องได้")
    
    def _reset_counters(self):
        """รีเซ็ตตัวนับลูกค้า"""
        confirm = input("คุณต้องการรีเซ็ตตัวนับลูกค้าทั้งหมดหรือไม่? (y/n): ")
        if confirm.lower() == 'y':
            self.camera.reset_counters()
            print("รีเซ็ตตัวนับลูกค้าเรียบร้อย")
        else:
            print("ยกเลิกการรีเซ็ตตัวนับลูกค้า")
    
    def _show_daily_stats(self):
        """แสดงสถิติประจำวัน"""
        # ขอให้ผู้ใช้ระบุจำนวนวันที่ต้องการดู
        days_str = input("แสดงสถิติย้อนหลังกี่วัน (1-30, Enter เพื่อใช้ค่าเริ่มต้น 7 วัน): ")
        
        try:
            days = int(days_str) if days_str else 7
            days = max(1, min(30, days))  # จำกัดค่าระหว่าง 1-30
        except ValueError:
            days = 7
            print("ค่าไม่ถูกต้อง ใช้ค่าเริ่มต้น 7 วัน")
        
        # ดึงข้อมูลสถิติ
        stats = self.data_manager.get_daily_stats(days=days)
        
        if not stats:
            print("ไม่พบข้อมูลสถิติ")
            return
        
        # แสดงข้อมูลในรูปแบบตาราง
        table = PrettyTable()
        table.field_names = ["วันที่", "ลูกค้าเข้าร้าน", "ลูกค้าออกจากร้าน", "เวลาที่มีลูกค้ามากที่สุด", "จำนวนสูงสุด"]
        
        for stat in stats:
            table.add_row([
                stat["date"],
                stat["total_entries"],
                stat["total_exits"],
                stat["peak_time"],
                stat["peak_count"]
            ])
        
        print(f"\nสถิติลูกค้าย้อนหลัง {days} วัน:")
        print(table)
    
    def _export_report(self):
        """ส่งออกรายงาน"""
        # ขอให้ผู้ใช้ระบุช่วงเวลา
        print("\nส่งออกรายงานสถิติประจำวัน")
        
        # ช่วงเวลาเริ่มต้น
        start_date = input("วันที่เริ่มต้น (YYYY-MM-DD, Enter เพื่อใช้วันนี้): ")
        if not start_date:
            start_date = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # ตรวจสอบรูปแบบวันที่
        try:
            datetime.datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            print("รูปแบบวันที่ไม่ถูกต้อง ใช้วันนี้แทน")
            start_date = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # ช่วงเวลาสิ้นสุด
        end_date = input("วันที่สิ้นสุด (YYYY-MM-DD, Enter เพื่อใช้วันเดียวกับวันที่เริ่มต้น): ")
        if not end_date:
            end_date = start_date
        
        # ตรวจสอบรูปแบบวันที่
        try:
            datetime.datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            print("รูปแบบวันที่ไม่ถูกต้อง ใช้วันเดียวกับวันที่เริ่มต้นแทน")
            end_date = start_date
        
        # ส่งออกรายงาน
        filename = self.data_manager.export_daily_stats(start_date, end_date)
        
        if filename:
            print(f"ส่งออกรายงานไปยัง: {filename} สำเร็จ")
        else:
            print("ไม่สามารถส่งออกรายงานได้")
    
    def _start_sync(self):
        """เริ่มการซิงค์ข้อมูล"""
        if not self.api_client:
            print("ไม่มีตัวเชื่อมต่อ API")
            return
        
        if self.api_client.sync_running:
            print("การซิงค์ข้อมูลกำลังทำงานอยู่แล้ว")
            return
        
        print("กำลังเริ่มการซิงค์ข้อมูล...")
        if self.api_client.start_sync():
            print("เริ่มการซิงค์ข้อมูลสำเร็จ")
        else:
            print("ไม่สามารถเริ่มการซิงค์ข้อมูลได้")
    
    def _stop_sync(self):
        """หยุดการซิงค์ข้อมูล"""
        if not self.api_client:
            print("ไม่มีตัวเชื่อมต่อ API")
            return
        
        if not self.api_client.sync_running:
            print("การซิงค์ข้อมูลไม่ได้ทำงานอยู่")
            return
        
        print("กำลังหยุดการซิงค์ข้อมูล...")
        if self.api_client.stop_sync():
            print("หยุดการซิงค์ข้อมูลสำเร็จ")
        else:
            print("ไม่สามารถหยุดการซิงค์ข้อมูลได้")
    
    def _sync_now(self):
        """ซิงค์ข้อมูลทันที"""
        if not self.api_client:
            print("ไม่มีตัวเชื่อมต่อ API")
            return
        
        print("กำลังซิงค์ข้อมูล...")
        if self.api_client.sync_data():
            print("ซิงค์ข้อมูลสำเร็จ")
        else:
            print("ไม่สามารถซิงค์ข้อมูลได้")