#!/usr/bin/env python3
# gui_manager.py - จัดการส่วนติดต่อผู้ใช้แบบกราฟิก
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import logging
import threading
import time
import datetime
import cv2
import PIL.Image, PIL.ImageTk
import numpy as np
import os
import urllib.parse

class GUIManager:
    """คลาสสำหรับจัดการส่วนติดต่อผู้ใช้แบบกราฟิก"""
    
    def __init__(self, camera, data_manager, api_client, config_manager):
        """กำหนดค่าเริ่มต้นสำหรับส่วนติดต่อผู้ใช้"""
        # ตั้งค่าระบบบันทึกล็อก
        self.logger = logging.getLogger("GUIManager")
        
        # กำหนดตัวแปรเริ่มต้น
        self.camera = camera
        self.data_manager = data_manager
        self.api_client = api_client
        self.config_manager = config_manager
        
        # ข้อมูลสาขา
        self.branch_id = camera.branch_id
        self.branch_name = config_manager.get('Branch', 'name', fallback='สาขาหลัก')
        
        # ตัวแปรสำหรับการแสดงผลวีดีโอ
        self.video_running = False
        self.video_thread = None
        self.current_frame = None
        self.selected_camera_id = None
        
        # ตั้งค่าหน้าต่างหลัก
        self.root = tk.Tk()
        self.root.title(f"ระบบนับลูกค้า - {self.branch_name} ({self.branch_id})")
        self.root.geometry("1280x800")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # สร้างส่วนประกอบของ GUI
        self._create_widgets()
        
        self.logger.info("ส่วนติดต่อผู้ใช้แบบกราฟิกถูกเริ่มต้นแล้ว")
    
    def _create_widgets(self):
        """สร้างส่วนประกอบของ GUI"""
        # สร้าง notebook สำหรับแยกหน้า
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # สร้างหน้าต่างๆ
        self.main_tab = ttk.Frame(self.notebook)
        self.cameras_tab = ttk.Frame(self.notebook)
        self.stats_tab = ttk.Frame(self.notebook)
        self.settings_tab = ttk.Frame(self.notebook)
        
        self.notebook.add(self.main_tab, text="หน้าหลัก")
        self.notebook.add(self.cameras_tab, text="จัดการกล้อง")
        self.notebook.add(self.stats_tab, text="สถิติและรายงาน")
        self.notebook.add(self.settings_tab, text="ตั้งค่า")
        
        # สร้างส่วนประกอบของแต่ละหน้า
        self._create_main_tab()
        self._create_cameras_tab()
        self._create_stats_tab()
        self._create_settings_tab()
        
        # สร้างแถบสถานะ
        self.status_bar = ttk.Frame(self.root)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=2)
        
        self.status_label = ttk.Label(self.status_bar, text="พร้อมใช้งาน")
        self.status_label.pack(side=tk.LEFT)
        
        self.sync_status_label = ttk.Label(self.status_bar, text="การซิงค์: ไม่ทำงาน")
        self.sync_status_label.pack(side=tk.RIGHT)
        
        # เริ่มอัพเดตสถานะ
        self._update_status()
    
    def _create_main_tab(self):
        """สร้างส่วนประกอบของหน้าหลัก"""
        # กรอบด้านซ้ายสำหรับแสดงวีดีโอ
        left_frame = ttk.Frame(self.main_tab)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # สร้างแคนวาสสำหรับแสดงวีดีโอ
        self.video_canvas = tk.Canvas(left_frame, bg="black")
        self.video_canvas.pack(fill=tk.BOTH, expand=True)
        
        # กรอบควบคุมด้านล่างของวีดีโอ
        video_control_frame = ttk.Frame(left_frame)
        video_control_frame.pack(fill=tk.X, pady=5)
        
        # เลือกกล้อง
        ttk.Label(video_control_frame, text="เลือกกล้อง:").pack(side=tk.LEFT, padx=5)
        self.camera_selector = ttk.Combobox(video_control_frame)
        self.camera_selector.pack(side=tk.LEFT, padx=5)
        self.camera_selector.bind("<<ComboboxSelected>>", self.on_camera_selected)
        
        # อัพเดตรายการกล้อง
        self._update_camera_list()
        
        self.start_button = ttk.Button(video_control_frame, text="เริ่มกล้อง", command=self.start_camera)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(video_control_frame, text="หยุดกล้อง", command=self.stop_camera)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        self.reset_button = ttk.Button(video_control_frame, text="รีเซ็ตตัวนับ", command=self.reset_counters)
        self.reset_button.pack(side=tk.LEFT, padx=5)
        
        self.snapshot_button = ttk.Button(video_control_frame, text="ถ่ายภาพ", command=self.take_snapshot)
        self.snapshot_button.pack(side=tk.LEFT, padx=5)
        
        # กรอบด้านขวาสำหรับแสดงข้อมูล
        right_frame = ttk.Frame(self.main_tab)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=5, pady=5, ipadx=10, ipady=10)
        
        # ข้อมูลสาขา
        branch_frame = ttk.LabelFrame(right_frame, text="ข้อมูลสาขา")
        branch_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(branch_frame, text=f"รหัสสาขา: {self.branch_id}").pack(anchor=tk.W, padx=5, pady=2)
        ttk.Label(branch_frame, text=f"ชื่อสาขา: {self.branch_name}").pack(anchor=tk.W, padx=5, pady=2)
        
        # ข้อมูลการนับ
        count_frame = ttk.LabelFrame(right_frame, text="ข้อมูลการนับลูกค้า")
        count_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(count_frame, text="จำนวนลูกค้าในร้าน:").pack(anchor=tk.W, padx=5, pady=2)
        self.current_count_label = ttk.Label(count_frame, text="0", font=("Helvetica", 24, "bold"))
        self.current_count_label.pack(anchor=tk.W, padx=5, pady=2)
        
        ttk.Label(count_frame, text="จำนวนลูกค้าเข้าร้านทั้งหมด:").pack(anchor=tk.W, padx=5, pady=2)
        self.entry_count_label = ttk.Label(count_frame, text="0")
        self.entry_count_label.pack(anchor=tk.W, padx=5, pady=2)
        
        ttk.Label(count_frame, text="จำนวนลูกค้าออกจากร้านทั้งหมด:").pack(anchor=tk.W, padx=5, pady=2)
        self.exit_count_label = ttk.Label(count_frame, text="0")
        self.exit_count_label.pack(anchor=tk.W, padx=5, pady=2)
        
        # ข้อมูลกล้องที่เลือก
        camera_info_frame = ttk.LabelFrame(right_frame, text="ข้อมูลกล้องที่เลือก")
        camera_info_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(camera_info_frame, text="กล้อง:").pack(anchor=tk.W, padx=5, pady=2)
        self.camera_name_label = ttk.Label(camera_info_frame, text="-")
        self.camera_name_label.pack(anchor=tk.W, padx=5, pady=2)
        
        ttk.Label(camera_info_frame, text="สถานะ:").pack(anchor=tk.W, padx=5, pady=2)
        self.camera_status_label = ttk.Label(camera_info_frame, text="-")
        self.camera_status_label.pack(anchor=tk.W, padx=5, pady=2)
        
        # เวลาปัจจุบัน
        time_frame = ttk.LabelFrame(right_frame, text="เวลาปัจจุบัน")
        time_frame.pack(fill=tk.X, pady=5)
        
        self.current_time_label = ttk.Label(time_frame, text="", font=("Helvetica", 14))
        self.current_time_label.pack(anchor=tk.W, padx=5, pady=2)
        
        # อัพเดตเวลาทุกวินาที
        self._update_time()
    
    def _create_cameras_tab(self):
        """สร้างส่วนประกอบของหน้าจัดการกล้อง"""
        # กรอบด้านซ้ายสำหรับแสดงรายการกล้อง
        left_frame = ttk.Frame(self.cameras_tab)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # ตาราง
        columns = ("id", "name", "status")
        self.cameras_table = ttk.Treeview(left_frame, columns=columns, show="headings")
        
        # กำหนดหัวตาราง
        self.cameras_table.heading("id", text="ID")
        self.cameras_table.heading("name", text="ชื่อกล้อง")
        self.cameras_table.heading("status", text="สถานะ")
        
        # กำหนดความกว้างของคอลัมน์
        self.cameras_table.column("id", width=50)
        self.cameras_table.column("name", width=150)
        self.cameras_table.column("status", width=100)
        
        # สร้าง scrollbar
        scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.cameras_table.yview)
        self.cameras_table.configure(yscroll=scrollbar.set)
        
        # จัดวาง
        self.cameras_table.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # เหตุการณ์เมื่อเลือกกล้อง
        self.cameras_table.bind("<<TreeviewSelect>>", self.on_camera_table_select)
        
        # กรอบควบคุม
        control_frame = ttk.Frame(left_frame)
        control_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(control_frame, text="เพิ่มกล้อง", command=self.add_camera).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="แก้ไขกล้อง", command=self.edit_camera).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="ลบกล้อง", command=self.delete_camera).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="รีเฟรช", command=self.refresh_cameras).pack(side=tk.LEFT, padx=5)
        
        # กรอบด้านขวาสำหรับแสดงรายละเอียดกล้อง
        right_frame = ttk.LabelFrame(self.cameras_tab, text="รายละเอียดกล้อง")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # สร้างฟอร์มสำหรับแสดงรายละเอียดกล้อง
        ttk.Label(right_frame, text="ชื่อกล้อง:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.camera_detail_name = ttk.Label(right_frame, text="-")
        self.camera_detail_name.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(right_frame, text="ประเภท:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.camera_detail_type = ttk.Label(right_frame, text="-")
        self.camera_detail_type.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(right_frame, text="แหล่งที่มา:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.camera_detail_source = ttk.Label(right_frame, text="-")
        self.camera_detail_source.grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(right_frame, text="ตำแหน่งเส้นตรวจจับ:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)
        self.camera_detail_line = ttk.Label(right_frame, text="-")
        self.camera_detail_line.grid(row=3, column=1, sticky=tk.W, padx=5, pady=2)
        
        # เพิ่มข้อมูลมุมเส้นตรวจจับ
        ttk.Label(right_frame, text="มุมเส้นตรวจจับ:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=2)
        self.camera_detail_angle = ttk.Label(right_frame, text="-")
        self.camera_detail_angle.grid(row=4, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(right_frame, text="สถานะ:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=2)
        self.camera_detail_status = ttk.Label(right_frame, text="-")
        self.camera_detail_status.grid(row=5, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(right_frame, text="จำนวนคนในร้าน:").grid(row=6, column=0, sticky=tk.W, padx=5, pady=2)
        self.camera_detail_count = ttk.Label(right_frame, text="-")
        self.camera_detail_count.grid(row=6, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(right_frame, text="จำนวนคนเข้าร้าน:").grid(row=7, column=0, sticky=tk.W, padx=5, pady=2)
        self.camera_detail_entry = ttk.Label(right_frame, text="-")
        self.camera_detail_entry.grid(row=7, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(right_frame, text="จำนวนคนออกจากร้าน:").grid(row=8, column=0, sticky=tk.W, padx=5, pady=2)
        self.camera_detail_exit = ttk.Label(right_frame, text="-")
        self.camera_detail_exit.grid(row=8, column=1, sticky=tk.W, padx=5, pady=2)
        
        # เพิ่มตัวควบคุมสำหรับปรับมุมเส้นตรวจจับ
        adjustment_frame = ttk.LabelFrame(right_frame, text="ปรับแต่งการตรวจจับ")
        adjustment_frame.grid(row=9, column=0, columnspan=2, sticky=tk.W+tk.E, padx=5, pady=10)
        
        ttk.Label(adjustment_frame, text="มุมเส้นตรวจจับ:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.angle_var = tk.StringVar(value="90")
        angle_entry = ttk.Entry(adjustment_frame, textvariable=self.angle_var, width=8)
        angle_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        
        # ปุ่มปรับมุม
        def adjust_angle():
            if self.cameras_table.selection():
                item = self.cameras_table.item(self.cameras_table.selection()[0])
                camera_id = int(item['values'][0])
                try:
                    angle = int(self.angle_var.get())
                    self.camera.adjust_line_angle(angle, camera_id)
                    messagebox.showinfo("สำเร็จ", f"ปรับมุมเส้นตรวจจับเป็น {angle} องศา")
                    self._update_camera_details(camera_id)
                except ValueError:
                    messagebox.showerror("ข้อผิดพลาด", "โปรดระบุมุมเป็นตัวเลข")
        
        ttk.Button(adjustment_frame, text="ตั้งค่ามุม", command=adjust_angle).grid(row=0, column=2, padx=5, pady=2)
        
        # โหลดข้อมูลเริ่มต้น
        self.refresh_cameras()
    
    def _create_stats_tab(self):
        """สร้างส่วนประกอบของหน้าสถิติและรายงาน"""
        # กรอบด้านบนสำหรับแสดงสถิติประจำวัน
        top_frame = ttk.LabelFrame(self.stats_tab, text="สถิติลูกค้าประจำวัน")
        top_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # ตาราง
        columns = ("date", "total_entries", "total_exits", "peak_time", "peak_count")
        self.stats_table = ttk.Treeview(top_frame, columns=columns, show="headings")
        
        # กำหนดหัวตาราง
        self.stats_table.heading("date", text="วันที่")
        self.stats_table.heading("total_entries", text="ลูกค้าเข้าร้าน")
        self.stats_table.heading("total_exits", text="ลูกค้าออกจากร้าน")
        self.stats_table.heading("peak_time", text="เวลาที่มีลูกค้ามากที่สุด")
        self.stats_table.heading("peak_count", text="จำนวนสูงสุด")
        
        # กำหนดความกว้างของคอลัมน์
        self.stats_table.column("date", width=100)
        self.stats_table.column("total_entries", width=100)
        self.stats_table.column("total_exits", width=100)
        self.stats_table.column("peak_time", width=150)
        self.stats_table.column("peak_count", width=100)
        
        # สร้าง scrollbar
        scrollbar = ttk.Scrollbar(top_frame, orient=tk.VERTICAL, command=self.stats_table.yview)
        self.stats_table.configure(yscroll=scrollbar.set)
        
        # จัดวาง
        self.stats_table.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # กรอบควบคุม
        control_frame = ttk.Frame(self.stats_tab)
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(control_frame, text="รีเฟรชข้อมูล", command=self.refresh_stats).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="ส่งออกรายงาน (CSV)", command=self.export_stats).pack(side=tk.LEFT, padx=5)
        
        # โหลดข้อมูลเริ่มต้น
        self.refresh_stats()
    
    def _create_settings_tab(self):
        """สร้างส่วนประกอบของหน้าตั้งค่า"""
        # กรอบด้านซ้ายสำหรับตั้งค่าทั่วไป
        left_frame = ttk.Frame(self.settings_tab)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # ตั้งค่าสาขา
        branch_frame = ttk.LabelFrame(left_frame, text="ตั้งค่าสาขา")
        branch_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(branch_frame, text="รหัสสาขา:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.branch_id_var = tk.StringVar(value=self.branch_id)
        ttk.Entry(branch_frame, textvariable=self.branch_id_var, state="readonly").grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(branch_frame, text="ชื่อสาขา:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.branch_name_var = tk.StringVar(value=self.branch_name)
        ttk.Entry(branch_frame, textvariable=self.branch_name_var).grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(branch_frame, text="สถานที่:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.branch_location_var = tk.StringVar(value=self.config_manager.get('Branch', 'location', fallback='ไม่ระบุ'))
        ttk.Entry(branch_frame, textvariable=self.branch_location_var).grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)
        
        # ตั้งค่ากล้อง (สำหรับกล้องทั้งหมด)
        camera_frame = ttk.LabelFrame(left_frame, text="ตั้งค่ากล้อง (ทั่วไป)")
        camera_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(camera_frame, text="ความกว้าง:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.camera_width_var = tk.StringVar(value=self.config_manager.get('Camera', 'width', fallback='640'))
        ttk.Entry(camera_frame, textvariable=self.camera_width_var).grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(camera_frame, text="ความสูง:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.camera_height_var = tk.StringVar(value=self.config_manager.get('Camera', 'height', fallback='480'))
        ttk.Entry(camera_frame, textvariable=self.camera_height_var).grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(camera_frame, text="FPS:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.camera_fps_var = tk.StringVar(value=self.config_manager.get('Camera', 'fps', fallback='30'))
        ttk.Entry(camera_frame, textvariable=self.camera_fps_var).grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)
        
        # กรอบด้านขวาสำหรับตั้งค่าการตรวจจับและการเชื่อมต่อ
        right_frame = ttk.Frame(self.settings_tab)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # ตั้งค่าการตรวจจับ
        detection_frame = ttk.LabelFrame(right_frame, text="ตั้งค่าการตรวจจับ")
        detection_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(detection_frame, text="พื้นที่ขั้นต่ำ:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.min_area_var = tk.StringVar(value=self.config_manager.get('Detection', 'min_area', fallback='500'))
        ttk.Entry(detection_frame, textvariable=self.min_area_var).grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(detection_frame, text="ค่า Threshold:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.threshold_var = tk.StringVar(value=self.config_manager.get('Detection', 'threshold', fallback='20'))
        ttk.Entry(detection_frame, textvariable=self.threshold_var).grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(detection_frame, text="ขนาด Blur:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.blur_size_var = tk.StringVar(value=self.config_manager.get('Detection', 'blur_size', fallback='21'))
        ttk.Entry(detection_frame, textvariable=self.blur_size_var).grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(detection_frame, text="ระยะทางขั้นต่ำ:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)
        self.direction_threshold_var = tk.StringVar(value=self.config_manager.get('Detection', 'direction_threshold', fallback='10'))
        ttk.Entry(detection_frame, textvariable=self.direction_threshold_var).grid(row=3, column=1, sticky=tk.W, padx=5, pady=2)
        
        # เพิ่มตัวควบคุมสำหรับปรับมุม (angle)
        ttk.Label(detection_frame, text="มุมของเส้นตรวจจับ:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=2)
        self.detection_angle_var = tk.StringVar(value=self.config_manager.get('Camera', 'detection_angle', fallback='90'))
        ttk.Entry(detection_frame, textvariable=self.detection_angle_var).grid(row=4, column=1, sticky=tk.W, padx=5, pady=2)
        
        # ตั้งค่าการเชื่อมต่อ API
        api_frame = ttk.LabelFrame(right_frame, text="ตั้งค่าการเชื่อมต่อ API")
        api_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(api_frame, text="URL เซิร์ฟเวอร์:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.server_url_var = tk.StringVar(value=self.config_manager.get('API', 'server_url', fallback='http://localhost:5000'))
        ttk.Entry(api_frame, textvariable=self.server_url_var).grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(api_frame, text="API Key:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.api_key_var = tk.StringVar(value=self.config_manager.get('API', 'api_key', fallback=''))
        ttk.Entry(api_frame, textvariable=self.api_key_var, show="*").grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(api_frame, text="รอบเวลาซิงค์ (วินาที):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.sync_interval_var = tk.StringVar(value=self.config_manager.get('API', 'sync_interval', fallback='900'))
        ttk.Entry(api_frame, textvariable=self.sync_interval_var).grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)
        
        # ปุ่มบันทึกการตั้งค่า
        save_button = ttk.Button(self.settings_tab, text="บันทึกการตั้งค่า", command=self.save_settings)
        save_button.pack(pady=10)

        def run(self):
         # เริ่มการแสดงวีดีโอ
         self.start_camera()
    
        # เริ่มการซิงค์ข้อมูล (ถ้า api_client มีอยู่)
        if self.api_client:
            self.api_client.start_sync()
        
        # เริ่มรับอีเวนต์จากผู้ใช้
        self.root.mainloop()

    
    def on_close(self):
        """เมื่อปิดหน้าต่าง"""
        # ยืนยันการปิดโปรแกรม
        if messagebox.askokcancel("ยืนยันการปิดโปรแกรม", "คุณต้องการปิดโปรแกรมหรือไม่?"):
            # หยุดการแสดงวีดีโอ
            self.stop_camera()
            
            # หยุดการซิงค์ข้อมูล
            self.api_client.stop_sync()
            
            # ปิดหน้าต่าง
            self.root.destroy()
    
    def _update_camera_list(self):
        """อัพเดตรายการกล้องในตัวเลือก"""
        cameras = self.camera.get_camera_list()
        
        # อัพเดตคอมโบบ็อกซ์
        self.camera_selector['values'] = [f"{cam['id']}: {cam['name']}" for cam in cameras]
        
        # เลือกกล้องแรกถ้ายังไม่ได้เลือก
        if self.selected_camera_id is None and cameras:
            self.camera_selector.current(0)
            self.selected_camera_id = cameras[0]['id']
    
    def on_camera_selected(self, event):
        """เมื่อเลือกกล้องในคอมโบบ็อกซ์"""
        selection = self.camera_selector.get()
        if selection:
            camera_id = int(selection.split(':')[0])
            self.selected_camera_id = camera_id
            
            # อัพเดตข้อมูลกล้องที่เลือก
            self._update_selected_camera_info()
    
    def _update_selected_camera_info(self):
        """อัพเดตข้อมูลของกล้องที่เลือก"""
        cameras = self.camera.get_camera_list()
        selected_camera = next((cam for cam in cameras if cam['id'] == self.selected_camera_id), None)
        
        if selected_camera:
            self.camera_name_label.config(text=selected_camera['name'])
            self.camera_status_label.config(text="ทำงาน" if selected_camera['running'] else "ไม่ทำงาน")
    
    def on_camera_table_select(self, event):
        """เมื่อเลือกกล้องในตาราง"""
        selection = self.cameras_table.selection()
        if selection:
            item = self.cameras_table.item(selection[0])
            camera_id = int(item['values'][0])
            
            # อัพเดตรายละเอียดกล้อง
            self._update_camera_details(camera_id)
    
    def _update_camera_details(self, camera_id):
        """อัพเดตรายละเอียดของกล้องที่เลือก"""
        cameras = self.camera.get_camera_list()
        selected_camera = next((cam for cam in cameras if cam['id'] == camera_id), None)
        
        if selected_camera:
            # ดึงรายละเอียดเพิ่มเติมจาก config.ini
            camera_section = f"Camera_{camera_id}" if camera_id > 0 else "Camera"
            camera_type = self.config_manager.get(camera_section, 'type', fallback='generic')
            
            # อัพเดตข้อมูล
            self.camera_detail_name.config(text=selected_camera['name'])
            self.camera_detail_type.config(text=camera_type)
            self.camera_detail_source.config(text=str(selected_camera['source']))
            
            # ดึงตำแหน่งเส้นตรวจจับ
            detection_line = self.config_manager.getint(camera_section, 'detection_line', fallback=240)
            self.camera_detail_line.config(text=str(detection_line))
            
            # ดึงค่ามุมเส้นตรวจจับ
            detection_angle = self.config_manager.getint(camera_section, 'detection_angle', fallback=90)
            self.camera_detail_angle.config(text=str(detection_angle))
            
            # สถานะ
            self.camera_detail_status.config(text="ทำงาน" if selected_camera['running'] else "ไม่ทำงาน")
            
            # จำนวนคน
            self.camera_detail_count.config(text=str(selected_camera['people_in_store']))
            self.camera_detail_entry.config(text=str(selected_camera['entry_count']))
            self.camera_detail_exit.config(text=str(selected_camera['exit_count']))
    
    def refresh_cameras(self):
        """รีเฟรชรายการกล้อง"""
        # อัพเดตรายการกล้องในคอมโบบ็อกซ์
        self._update_camera_list()
        
        # อัพเดตข้อมูลกล้องที่เลือก
        self._update_selected_camera_info()
        
        # อัพเดตตารางกล้อง
        cameras = self.camera.get_camera_list()
        
        # ล้างข้อมูลในตาราง
        for item in self.cameras_table.get_children():
            self.cameras_table.delete(item)
        
        # เพิ่มข้อมูลลงในตาราง
        for cam in cameras:
            self.cameras_table.insert("", tk.END, values=(
                cam['id'],
                cam['name'],
                "ทำงาน" if cam['running'] else "ไม่ทำงาน"
            ))
    
    def add_camera(self):
        """เพิ่มกล้องใหม่"""
        # สร้างหน้าต่างใหม่
        add_window = tk.Toplevel(self.root)
        add_window.title("เพิ่มกล้องใหม่")
        add_window.geometry("500x600")  # เพิ่มความสูงเพื่อรองรับฟิลด์เพิ่มเติม
        add_window.resizable(False, False)
        
        # สร้างฟอร์ม
        ttk.Label(add_window, text="ชื่อกล้อง:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        name_var = tk.StringVar()
        ttk.Entry(add_window, textvariable=name_var, width=30).grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(add_window, text="ประเภทกล้อง:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        type_var = tk.StringVar(value="dahua")
        type_combo = ttk.Combobox(add_window, textvariable=type_var, width=28)
        type_combo['values'] = ["dahua", "hikvision", "generic"]
        type_combo.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        # สร้าง LabelFrame สำหรับแยกการตั้งค่าตามประเภทการกำหนดค่า
        connection_frame = ttk.LabelFrame(add_window, text="การเชื่อมต่อ")
        connection_frame.grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W+tk.E)
        
        # วิธีการเชื่อมต่อ
        connection_mode = tk.StringVar(value="params")
        ttk.Radiobutton(connection_frame, text="ระบุพารามิเตอร์ (Host, Port, ...)", variable=connection_mode, value="params").grid(row=0, column=0, columnspan=2, sticky=tk.W, padx=5, pady=2)
        ttk.Radiobutton(connection_frame, text="ระบุ URL โดยตรง", variable=connection_mode, value="direct").grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=5, pady=2)
        
        # กรอบสำหรับพารามิเตอร์
        params_frame = ttk.Frame(connection_frame)
        params_frame.grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W+tk.E)
        
        ttk.Label(params_frame, text="Host:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        host_var = tk.StringVar()
        ttk.Entry(params_frame, textvariable=host_var, width=30).grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(params_frame, text="Port:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        port_var = tk.StringVar(value="554")
        ttk.Entry(params_frame, textvariable=port_var, width=30).grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(params_frame, text="Username:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        username_var = tk.StringVar(value="admin")
        ttk.Entry(params_frame, textvariable=username_var, width=30).grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(params_frame, text="Password:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)
        password_var = tk.StringVar()
        ttk.Entry(params_frame, textvariable=password_var, width=30, show="*").grid(row=3, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(params_frame, text="Channel:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=2)
        channel_var = tk.StringVar(value="1")
        ttk.Entry(params_frame, textvariable=channel_var, width=30).grid(row=4, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(params_frame, text="Path (สำหรับ generic):").grid(row=5, column=0, sticky=tk.W, padx=5, pady=2)
        path_var = tk.StringVar()
        ttk.Entry(params_frame, textvariable=path_var, width=30).grid(row=5, column=1, sticky=tk.W, padx=5, pady=2)
        
        # กรอบสำหรับ URL โดยตรง
        direct_frame = ttk.Frame(connection_frame)
        direct_frame.grid(row=3, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W+tk.E)
        direct_frame.grid_remove()  # ซ่อนตอนเริ่มต้น
        
        ttk.Label(direct_frame, text="RTSP URL:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        source_var = tk.StringVar()
        ttk.Entry(direct_frame, textvariable=source_var, width=50).grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        
        # สลับการแสดงผลระหว่าง params_frame และ direct_frame
        def toggle_frame(*args):
            if connection_mode.get() == "params":
                params_frame.grid()
                direct_frame.grid_remove()
            else:
                params_frame.grid_remove()
                direct_frame.grid()
        
        connection_mode.trace("w", toggle_frame)
        
        # ตั้งค่าตรวจจับ
        detection_frame = ttk.LabelFrame(add_window, text="การตรวจจับ")
        detection_frame.grid(row=3, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W+tk.E)
        
        ttk.Label(detection_frame, text="ตำแหน่งเส้นตรวจจับ:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        line_var = tk.StringVar(value="240")
        ttk.Entry(detection_frame, textvariable=line_var, width=10).grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(detection_frame, text="พื้นที่ขั้นต่ำ:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        area_var = tk.StringVar(value="500")
        ttk.Entry(detection_frame, textvariable=area_var, width=10).grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)

        # เพิ่มตัวควบคุมมุมเส้นตรวจจับ    
        ttk.Label(detection_frame, text="มุมเส้นตรวจจับ:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        angle_var = tk.StringVar(value="90")
        ttk.Entry(detection_frame, textvariable=angle_var, width=10).grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)
        
        # ปุ่มทดสอบการเชื่อมต่อ
        test_button = ttk.Button(add_window, text="ทดสอบการเชื่อมต่อ", 
                                command=lambda: self._test_camera_connection(
                                    connection_mode.get(), source_var.get(), 
                                    host_var.get(), port_var.get(), username_var.get(), 
                                    password_var.get(), channel_var.get(), path_var.get(), 
                                    type_var.get()
                                ))
        test_button.grid(row=4, column=0, columnspan=2, pady=10)
        
        # ปุ่มบันทึก
        def save_camera():
            # ตรวจสอบข้อมูลที่จำเป็น
            if not name_var.get():
                messagebox.showerror("ข้อผิดพลาด", "โปรดระบุชื่อกล้อง")
                return
            
            # นับจำนวนกล้องปัจจุบัน
            camera_count = len(self.camera.get_camera_list())
            
            # กำหนด camera_id ใหม่
            new_camera_id = camera_count + 1
            
            # สร้างส่วน Camera_X ในไฟล์ config
            camera_section = f"Camera_{new_camera_id}"
            
            # ตั้งค่า MultiCameras ถ้ายังไม่มี
            if not self.config_manager.has_section('MultiCameras'):
                self.config_manager.add_section('MultiCameras')
                self.config_manager.set('MultiCameras', 'enabled', 'true')
                self.config_manager.set('MultiCameras', 'camera_count', '1')
            else:
                current_count = self.config_manager.getint('MultiCameras', 'camera_count', fallback=0)
                self.config_manager.set('MultiCameras', 'camera_count', str(current_count + 1))
                self.config_manager.set('MultiCameras', 'enabled', 'true')
            
            # สร้างส่วน Camera_X
            if not self.config_manager.has_section(camera_section):
                self.config_manager.add_section(camera_section)
            
            # บันทึกข้อมูลกล้อง
            self.config_manager.set(camera_section, 'name', name_var.get())
            self.config_manager.set(camera_section, 'type', type_var.get())
            
            if connection_mode.get() == "params":
                # บันทึกพารามิเตอร์การเชื่อมต่อ
                self.config_manager.set(camera_section, 'host', host_var.get())
                self.config_manager.set(camera_section, 'port', port_var.get())
                self.config_manager.set(camera_section, 'username', username_var.get())
                self.config_manager.set(camera_section, 'password', password_var.get())
                self.config_manager.set(camera_section, 'channel', channel_var.get())
                
                if path_var.get() and type_var.get() == "generic":
                    self.config_manager.set(camera_section, 'path', path_var.get())
            else:
                # บันทึก URL โดยตรง
                self.config_manager.set(camera_section, 'source', source_var.get())
            
            # บันทึกการตั้งค่าตรวจจับ
            self.config_manager.set(camera_section, 'detection_line', line_var.get())
            self.config_manager.set(camera_section, 'min_area', area_var.get())
            self.config_manager.set(camera_section, 'detection_angle', angle_var.get())
            
            # บันทึกการตั้งค่า
            self.config_manager.save()
            
            # รีเซ็ต camera_counter เพื่อโหลดกล้องใหม่
            self.camera._setup_multiple_cameras()
            
            # รีเฟรชรายการกล้อง
            self.refresh_cameras()
            
            # ปิดหน้าต่าง
            add_window.destroy()
            
            messagebox.showinfo("สำเร็จ", f"เพิ่มกล้อง '{name_var.get()}' สำเร็จ")
        
        save_button = ttk.Button(add_window, text="บันทึก", command=save_camera)
        save_button.grid(row=5, column=0, columnspan=2, pady=10)
        
        # จัดกึ่งกลาง
        add_window.update_idletasks()
        width = add_window.winfo_width()
        height = add_window.winfo_height()
        x = (add_window.winfo_screenwidth() // 2) - (width // 2)
        y = (add_window.winfo_screenheight() // 2) - (height // 2)
        add_window.geometry('{}x{}+{}+{}'.format(width, height, x, y))
        
    def _test_camera_connection(self, mode, source, host, port, username, password, channel, path, camera_type):
        """ทดสอบการเชื่อมต่อกับกล้อง"""
        try:
            # สร้าง URL
            if mode == "direct":
                url = source
            else:
                # เข้ารหัสรหัสผ่าน
                encoded_password = urllib.parse.quote(password, safe='')
                
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
            self.logger.info(f"ทดสอบการเชื่อมต่อกับกล้อง: {url}")
            
            # ทดสอบการเชื่อมต่อ
            cap = cv2.VideoCapture(url)
            
            if cap.isOpened():
                # ลองอ่านเฟรม
                ret, frame = cap.read()
                
                if ret:
                    # ปิดการเชื่อมต่อ
                    cap.release()
                    
                    # แสดงข้อความสำเร็จ
                    messagebox.showinfo("ทดสอบการเชื่อมต่อ", "เชื่อมต่อกับกล้องสำเร็จ")
                    return True
            
            # ปิดการเชื่อมต่อ
            cap.release()
            
            # แสดงข้อความล้มเหลว
            messagebox.showerror("ทดสอบการเชื่อมต่อ", "ไม่สามารถเชื่อมต่อกับกล้องได้")
            return False
            
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการทดสอบการเชื่อมต่อกับกล้อง: {str(e)}")
            messagebox.showerror("ข้อผิดพลาด", f"เกิดข้อผิดพลาด: {str(e)}")
            return False
    
    def edit_camera(self):
        """แก้ไขกล้องที่เลือก"""
        # ตรวจสอบว่ามีการเลือกกล้องหรือไม่
        selection = self.cameras_table.selection()
        if not selection:
            messagebox.showwarning("คำเตือน", "โปรดเลือกกล้องที่ต้องการแก้ไข")
            return
        
        # ดึงข้อมูลกล้องที่เลือก
        item = self.cameras_table.item(selection[0])
        camera_id = int(item['values'][0])
        
        # ดึงการตั้งค่าจาก config
        camera_section = f"Camera_{camera_id}" if camera_id > 0 else "Camera"
        
        # สร้างหน้าต่างใหม่
        edit_window = tk.Toplevel(self.root)
        edit_window.title(f"แก้ไขกล้อง {item['values'][1]}")
        edit_window.geometry("500x600")  # เพิ่มความสูงเพื่อรองรับฟิลด์เพิ่มเติม
        edit_window.resizable(False, False)
        
        # สร้างฟอร์ม
        ttk.Label(edit_window, text="ชื่อกล้อง:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        name_var = tk.StringVar(value=self.config_manager.get(camera_section, 'name', fallback=f"Camera {camera_id}"))
        ttk.Entry(edit_window, textvariable=name_var, width=30).grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(edit_window, text="ประเภทกล้อง:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        type_var = tk.StringVar(value=self.config_manager.get(camera_section, 'type', fallback="dahua"))
        type_combo = ttk.Combobox(edit_window, textvariable=type_var, width=28)
        type_combo['values'] = ["dahua", "hikvision", "generic"]
        type_combo.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)

        # สร้าง LabelFrame สำหรับแยกการตั้งค่าตามประเภทการกำหนดค่า
        connection_frame = ttk.LabelFrame(edit_window, text="การเชื่อมต่อ")
        connection_frame.grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W+tk.E)
        
        # ตรวจสอบว่ามีการตั้งค่า source โดยตรงหรือไม่
        has_direct_source = self.config_manager.get(camera_section, 'source', fallback=None) is not None
        
        # วิธีการเชื่อมต่อ
        connection_mode = tk.StringVar(value="direct" if has_direct_source else "params")
        ttk.Radiobutton(connection_frame, text="ระบุพารามิเตอร์ (Host, Port, ...)", variable=connection_mode, value="params").grid(row=0, column=0, columnspan=2, sticky=tk.W, padx=5, pady=2)
        ttk.Radiobutton(connection_frame, text="ระบุ URL โดยตรง", variable=connection_mode, value="direct").grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=5, pady=2)
        
        # กรอบสำหรับพารามิเตอร์
        params_frame = ttk.Frame(connection_frame)
        params_frame.grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W+tk.E)
        
        ttk.Label(params_frame, text="Host:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        host_var = tk.StringVar(value=self.config_manager.get(camera_section, 'host', fallback=''))
        ttk.Entry(params_frame, textvariable=host_var, width=30).grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(params_frame, text="Port:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        port_var = tk.StringVar(value=self.config_manager.get(camera_section, 'port', fallback='554'))
        ttk.Entry(params_frame, textvariable=port_var, width=30).grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(params_frame, text="Username:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        username_var = tk.StringVar(value=self.config_manager.get(camera_section, 'username', fallback=self.config_manager.get('MultiCameras', 'username', fallback='admin')))
        ttk.Entry(params_frame, textvariable=username_var, width=30).grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(params_frame, text="Password:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)
        password_var = tk.StringVar(value=self.config_manager.get(camera_section, 'password', fallback=self.config_manager.get('MultiCameras', 'password', fallback='')))
        ttk.Entry(params_frame, textvariable=password_var, width=30, show="*").grid(row=3, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(params_frame, text="Channel:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=2)
        channel_var = tk.StringVar(value=self.config_manager.get(camera_section, 'channel', fallback='1'))
        ttk.Entry(params_frame, textvariable=channel_var, width=30).grid(row=4, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(params_frame, text="Path (สำหรับ generic):").grid(row=5, column=0, sticky=tk.W, padx=5, pady=2)
        path_var = tk.StringVar(value=self.config_manager.get(camera_section, 'path', fallback=''))
        ttk.Entry(params_frame, textvariable=path_var, width=30).grid(row=5, column=1, sticky=tk.W, padx=5, pady=2)
        
        # กรอบสำหรับ URL โดยตรง
        direct_frame = ttk.Frame(connection_frame)
        direct_frame.grid(row=3, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W+tk.E)
        
        ttk.Label(direct_frame, text="RTSP URL:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        source_var = tk.StringVar(value=self.config_manager.get(camera_section, 'source', fallback=''))
        ttk.Entry(direct_frame, textvariable=source_var, width=50).grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        
        # แสดงกรอบที่ถูกต้องตามการตั้งค่า
        if has_direct_source:
            params_frame.grid_remove()
        else:
            direct_frame.grid_remove()
        
        # สลับการแสดงผลระหว่าง params_frame และ direct_frame
        def toggle_frame(*args):
            if connection_mode.get() == "params":
                params_frame.grid()
                direct_frame.grid_remove()
            else:
                params_frame.grid_remove()
                direct_frame.grid()
        
        connection_mode.trace("w", toggle_frame)
        
        # ตั้งค่าตรวจจับ
        detection_frame = ttk.LabelFrame(edit_window, text="การตรวจจับ")
        detection_frame.grid(row=3, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W+tk.E)
        
        ttk.Label(detection_frame, text="ตำแหน่งเส้นตรวจจับ:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        line_var = tk.StringVar(value=self.config_manager.get(camera_section, 'detection_line', fallback='240'))
        ttk.Entry(detection_frame, textvariable=line_var, width=10).grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(detection_frame, text="พื้นที่ขั้นต่ำ:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        area_var = tk.StringVar(value=self.config_manager.get(camera_section, 'min_area', fallback='500'))
        ttk.Entry(detection_frame, textvariable=area_var, width=10).grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)

        # เพิ่มตัวควบคุมมุมเส้นตรวจจับ
        ttk.Label(detection_frame, text="มุมเส้นตรวจจับ:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        angle_var = tk.StringVar(value=self.config_manager.get(camera_section, 'detection_angle', fallback='90'))
        ttk.Entry(detection_frame, textvariable=angle_var, width=10).grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)
        
        # ปุ่มทดสอบการเชื่อมต่อ
        test_button = ttk.Button(edit_window, text="ทดสอบการเชื่อมต่อ", 
                                command=lambda: self._test_camera_connection(
                                    connection_mode.get(), source_var.get(), 
                                    host_var.get(), port_var.get(), username_var.get(), 
                                    password_var.get(), channel_var.get(), path_var.get(), 
                                    type_var.get()
                                ))
        test_button.grid(row=4, column=0, columnspan=2, pady=10)
        
        # สลับการแสดงผลระหว่าง params_frame และ direct_frame
        def toggle_frame(*args):
            if connection_mode.get() == "params":
                params_frame.grid()
                direct_frame.grid_remove()
            else:
                params_frame.grid_remove()
                direct_frame.grid()
        
        connection_mode.trace("w", toggle_frame)
        
        # ตั้งค่าตรวจจับ
        detection_frame = ttk.LabelFrame(edit_window, text="การตรวจจับ")
        detection_frame.grid(row=3, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W+tk.E)
        
        ttk.Label(detection_frame, text="ตำแหน่งเส้นตรวจจับ:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        line_var = tk.StringVar(value=self.config_manager.get(camera_section, 'detection_line', fallback='240'))
        ttk.Entry(detection_frame, textvariable=line_var, width=10).grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(detection_frame, text="พื้นที่ขั้นต่ำ:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        area_var = tk.StringVar(value=self.config_manager.get(camera_section, 'min_area', fallback='500'))
        ttk.Entry(detection_frame, textvariable=area_var, width=10).grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        
        # ปุ่มทดสอบการเชื่อมต่อ
        test_button = ttk.Button(edit_window, text="ทดสอบการเชื่อมต่อ", 
                                 command=lambda: self._test_camera_connection(
                                     connection_mode.get(), source_var.get(), 
                                     host_var.get(), port_var.get(), username_var.get(), 
                                     password_var.get(), channel_var.get(), path_var.get(), 
                                     type_var.get()
                                 ))
        test_button.grid(row=4, column=0, columnspan=2, pady=10)
        
        # ปุ่มบันทึก
        def save_camera():
            # ตรวจสอบข้อมูลที่จำเป็น
            if not name_var.get():
                messagebox.showerror("ข้อผิดพลาด", "โปรดระบุชื่อกล้อง")
                return
            
            # บันทึกข้อมูลกล้อง
            self.config_manager.set(camera_section, 'name', name_var.get())
            self.config_manager.set(camera_section, 'type', type_var.get())
            
            # ลบค่าเดิมที่อาจมีอยู่
            if self.config_manager.has_option(camera_section, 'source'):
                self.config_manager.remove_option(camera_section, 'source')
            
            if self.config_manager.has_option(camera_section, 'host'):
                self.config_manager.remove_option(camera_section, 'host')
                self.config_manager.remove_option(camera_section, 'port')
                self.config_manager.remove_option(camera_section, 'username')
                self.config_manager.remove_option(camera_section, 'password')
                self.config_manager.remove_option(camera_section, 'channel')
                self.config_manager.remove_option(camera_section, 'path')
            
            if connection_mode.get() == "params":
                # บันทึกพารามิเตอร์การเชื่อมต่อ
                self.config_manager.set(camera_section, 'host', host_var.get())
                self.config_manager.set(camera_section, 'port', port_var.get())
                self.config_manager.set(camera_section, 'username', username_var.get())
                self.config_manager.set(camera_section, 'password', password_var.get())
                self.config_manager.set(camera_section, 'channel', channel_var.get())
                
                if path_var.get() and type_var.get() == "generic":
                    self.config_manager.set(camera_section, 'path', path_var.get())
            else:
                # บันทึก URL โดยตรง
                self.config_manager.set(camera_section, 'source', source_var.get())
            
            # บันทึกการตั้งค่าตรวจจับ
            self.config_manager.set(camera_section, 'detection_line', line_var.get())
            self.config_manager.set(camera_section, 'min_area', area_var.get())
            self.config_manager.set(camera_section, 'detection_angle', angle_var.get())
            
            # บันทึกการตั้งค่า
            self.config_manager.save()
            
            # รีเซ็ต camera_counter เพื่อโหลดกล้องใหม่
            self.camera._setup_multiple_cameras()
            
            # รีเฟรชรายการกล้อง
            self.refresh_cameras()
            
            # ปิดหน้าต่าง
            edit_window.destroy()
            
            messagebox.showinfo("สำเร็จ", f"แก้ไขกล้อง '{name_var.get()}' สำเร็จ")
        
        save_button = ttk.Button(edit_window, text="บันทึก", command=save_camera)
        save_button.grid(row=5, column=0, columnspan=2, pady=10)
        
        # จัดกึ่งกลาง
        edit_window.update_idletasks()
        width = edit_window.winfo_width()
        height = edit_window.winfo_height()
        x = (edit_window.winfo_screenwidth() // 2) - (width // 2)
        y = (edit_window.winfo_screenheight() // 2) - (height // 2)
        edit_window.geometry('{}x{}+{}+{}'.format(width, height, x, y))
    
    def delete_camera(self):
        """ลบกล้องที่เลือก"""
        # ตรวจสอบว่ามีการเลือกกล้องหรือไม่
        selection = self.cameras_table.selection()
        if not selection:
            messagebox.showwarning("คำเตือน", "โปรดเลือกกล้องที่ต้องการลบ")
            return
        
        # ดึงข้อมูลกล้องที่เลือก
        item = self.cameras_table.item(selection[0])
        camera_id = int(item['values'][0])
        camera_name = item['values'][1]
        
        # ยืนยันการลบ
        if not messagebox.askyesno("ยืนยันการลบ", f"คุณต้องการลบกล้อง '{camera_name}' หรือไม่?"):
            return
        
        # ไม่อนุญาตให้ลบกล้องเริ่มต้น (ID = 0)
        if camera_id == 0:
            messagebox.showerror("ข้อผิดพลาด", "ไม่สามารถลบกล้องเริ่มต้นได้")
            return
        
        # ลบส่วนการตั้งค่าของกล้อง
        camera_section = f"Camera_{camera_id}"
        if self.config_manager.has_section(camera_section):
            self.config_manager.remove_section(camera_section)
        
        # ปรับปรุงจำนวนกล้อง
        camera_count = self.config_manager.getint('MultiCameras', 'camera_count', fallback=0)
        self.config_manager.set('MultiCameras', 'camera_count', str(camera_count - 1))
        
        # บันทึกการตั้งค่า
        self.config_manager.save()
        
        # รีเซ็ต camera_counter เพื่อโหลดกล้องใหม่
        self.camera._setup_multiple_cameras()
        
        # รีเฟรชรายการกล้อง
        self.refresh_cameras()
        
        messagebox.showinfo("สำเร็จ", f"ลบกล้อง '{camera_name}' สำเร็จ")
    
    def start_camera(self):
        """เริ่มการทำงานของกล้อง"""
        # เริ่มกล้องถ้ายังไม่ได้เริ่ม
        if not self.camera.camera_running:
            if self.camera.start():
                # ปิดหน้าต่าง messagebox โดยอัตโนมัติ
                self.root.update()
                for window in self.root.winfo_children():
                    if isinstance(window, tk.Toplevel):
                        window.destroy()
                
                self.logger.info("เริ่มการทำงานของกล้องสำเร็จ")
                self.status_label.config(text="กล้องกำลังทำงาน")
                self.start_button.config(state=tk.DISABLED)
                self.stop_button.config(state=tk.NORMAL)
            else:
                messagebox.showerror("ข้อผิดพลาด", "ไม่สามารถเริ่มการทำงานของกล้องได้")
                return
        
        # เริ่มการแสดงวีดีโอ
        if not self.video_running:
            self.video_running = True
            self.video_thread = threading.Thread(target=self._update_video)
            self.video_thread.daemon = True
            self.video_thread.start()
        
    def stop_camera(self):
        """หยุดการทำงานของกล้อง"""
        # หยุดการแสดงวีดีโอ
        self.video_running = False
        if self.video_thread:
            self.video_thread.join(timeout=1.0)
        
        # หยุดกล้อง
        if self.camera.camera_running:
            if self.camera.stop():
                self.logger.info("หยุดการทำงานของกล้องสำเร็จ")
                self.status_label.config(text="พร้อมใช้งาน")
                self.start_button.config(state=tk.NORMAL)
                self.stop_button.config(state=tk.DISABLED)
            else:
                messagebox.showerror("ข้อผิดพลาด", "ไม่สามารถหยุดการทำงานของกล้องได้")
    
    def reset_counters(self):
        """รีเซ็ตตัวนับ"""
        # ยืนยันการรีเซ็ต
        if messagebox.askyesno("ยืนยันการรีเซ็ต", "คุณต้องการรีเซ็ตตัวนับทั้งหมดหรือไม่?"):
            self.camera.reset_counters()
            self.logger.info("รีเซ็ตตัวนับสำเร็จ")
            self._update_count_labels()
    
    def take_snapshot(self):
        """ถ่ายภาพปัจจุบัน"""
        if not self.camera.camera_running:
            messagebox.showwarning("คำเตือน", "กล้องไม่ได้ทำงานอยู่")
            return
        
        # ถ่ายภาพจากกล้องที่เลือก
        frame = self.camera.take_snapshot(self.selected_camera_id)
        
        if frame is None:
            messagebox.showerror("ข้อผิดพลาด", "ไม่สามารถถ่ายภาพได้")
            return
        
        # บันทึกภาพ
        try:
            # สร้างโฟลเดอร์ snapshots ถ้ายังไม่มี
            snapshots_dir = os.path.join(self.config_manager.get('Recording', 'export_path', fallback='exports'), 'snapshots')
            os.makedirs(snapshots_dir, exist_ok=True)
            
            # สร้างชื่อไฟล์
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{snapshots_dir}/{self.branch_id}_{timestamp}.jpg"
            
            # บันทึกภาพ
            cv2.imwrite(filename, frame)
            
            # ส่งภาพไปยังเซิร์ฟเวอร์
            threading.Thread(target=self._upload_snapshot, args=(frame,)).start()
            
            self.logger.info(f"บันทึกภาพ: {filename}")
            messagebox.showinfo("สำเร็จ", f"บันทึกภาพไปยัง:\n{filename}")
            
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการบันทึกภาพ: {str(e)}")
            messagebox.showerror("ข้อผิดพลาด", f"ไม่สามารถบันทึกภาพได้: {str(e)}")
    
    def _upload_snapshot(self, frame):
        """ส่งภาพไปยังเซิร์ฟเวอร์ (เรียกจากเธรดแยก)"""
        # ข้อมูลเพิ่มเติม
        metadata = {
            'people_in_store': self.camera.people_in_store,
            'entry_count': self.camera.entry_count,
            'exit_count': self.camera.exit_count,
            'branch_id': self.branch_id
        }
        
        # ส่งภาพ
        self.api_client.upload_snapshot(frame, metadata)
    
    def refresh_stats(self):
        """รีเฟรชข้อมูลสถิติ"""
        # ล้างข้อมูลในตาราง
        for item in self.stats_table.get_children():
            self.stats_table.delete(item)
        
        # ดึงข้อมูลสถิติ 7 วันล่าสุด
        stats = self.data_manager.get_daily_stats(days=7)
        
        if not stats:
            self.logger.warning("ไม่พบข้อมูลสถิติ")
            return
        
        # เพิ่มข้อมูลลงในตาราง
        for stat in stats:
            self.stats_table.insert("", tk.END, values=(
                stat["date"],
                stat["total_entries"],
                stat["total_exits"],
                stat["peak_time"],
                stat["peak_count"]
            ))
        
        self.logger.info(f"รีเฟรชข้อมูลสถิติสำเร็จ ({len(stats)} รายการ)")
    
    def export_stats(self):
        """ส่งออกรายงานสถิติ"""
        # ถามว่าต้องการส่งออกข้อมูลช่วงเวลาใด
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # สร้างหน้าต่างเพื่อระบุช่วงเวลา
        export_window = tk.Toplevel(self.root)
        export_window.title("ส่งออกรายงาน")
        export_window.geometry("300x150")
        export_window.resizable(False, False)
        
        ttk.Label(export_window, text="วันที่เริ่มต้น:").grid(row=0, column=0, padx=5, pady=5)
        start_date_var = tk.StringVar(value=current_date)
        ttk.Entry(export_window, textvariable=start_date_var).grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(export_window, text="วันที่สิ้นสุด:").grid(row=1, column=0, padx=5, pady=5)
        end_date_var = tk.StringVar(value=current_date)
        ttk.Entry(export_window, textvariable=end_date_var).grid(row=1, column=1, padx=5, pady=5)
        
        # ฟังก์ชันสำหรับส่งออกรายงาน
        def do_export():
            start_date = start_date_var.get()
            end_date = end_date_var.get()
            
            # ตรวจสอบรูปแบบวันที่
            try:
                datetime.datetime.strptime(start_date, "%Y-%m-%d")
                datetime.datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("ข้อผิดพลาด", "รูปแบบวันที่ไม่ถูกต้อง (YYYY-MM-DD)")
                return
            
            # ส่งออกรายงาน
            filename = self.data_manager.export_daily_stats(start_date, end_date)
            
            if filename:
                messagebox.showinfo("สำเร็จ", f"ส่งออกรายงานไปยัง:\n{filename}")
            else:
                messagebox.showerror("ข้อผิดพลาด", "ไม่สามารถส่งออกรายงานได้")
            
            export_window.destroy()
        
        ttk.Button(export_window, text="ส่งออก", command=do_export).grid(row=2, column=0, columnspan=2, pady=10)
    
    def save_settings(self):
        """บันทึกการตั้งค่า"""
        try:
            # บันทึกการตั้งค่าสาขา
            self.config_manager.set('Branch', 'name', self.branch_name_var.get())
            self.config_manager.set('Branch', 'location', self.branch_location_var.get())
            
            # บันทึกการตั้งค่ากล้อง
            self.config_manager.set('Camera', 'width', self.camera_width_var.get())
            self.config_manager.set('Camera', 'height', self.camera_height_var.get())
            self.config_manager.set('Camera', 'fps', self.camera_fps_var.get())
            
            # บันทึกมุมของเส้นตรวจจับ
            self.config_manager.set('Camera', 'detection_angle', self.detection_angle_var.get())
            
            # บันทึกการตั้งค่าการตรวจจับ
            self.config_manager.set('Detection', 'min_area', self.min_area_var.get())
            self.config_manager.set('Detection', 'threshold', self.threshold_var.get())
            self.config_manager.set('Detection', 'blur_size', self.blur_size_var.get())
            self.config_manager.set('Detection', 'direction_threshold', self.direction_threshold_var.get())
            
            # บันทึกการตั้งค่า API
            self.config_manager.set('API', 'server_url', self.server_url_var.get())
            self.config_manager.set('API', 'api_key', self.api_key_var.get())
            self.config_manager.set('API', 'sync_interval', self.sync_interval_var.get())
            
            # บันทึกการตั้งค่า
            if self.config_manager.save():
                self.logger.info("บันทึกการตั้งค่าสำเร็จ")
                messagebox.showinfo("สำเร็จ", "บันทึกการตั้งค่าสำเร็จ\nการตั้งค่าบางอย่างอาจต้องรีสตาร์ทโปรแกรมเพื่อให้มีผล")
                
                # อัพเดตชื่อสาขาในหน้าหลัก
                self.branch_name = self.branch_name_var.get()
                self.root.title(f"ระบบนับลูกค้า - {self.branch_name} ({self.branch_id})")
                
                # ปรับมุมเส้นตรวจจับหลังจากบันทึก
                try:
                    new_angle = int(self.detection_angle_var.get())
                    self.camera.adjust_line_angle(new_angle)
                    self.logger.info(f"ปรับมุมเส้นตรวจจับเป็น {new_angle} องศา")
                except ValueError:
                    self.logger.error("ค่ามุมเส้นตรวจจับไม่ถูกต้อง")
            else:
                messagebox.showerror("ข้อผิดพลาด", "ไม่สามารถบันทึกการตั้งค่าได้")
                
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการบันทึกการตั้งค่า: {str(e)}")
            messagebox.showerror("ข้อผิดพลาด", f"ไม่สามารถบันทึกการตั้งค่าได้: {str(e)}")
    
    def _update_video(self):
        """อัพเดตภาพวีดีโอ (เรียกจากเธรดแยก)"""
        while self.video_running:
            try:
                if not self.camera.camera_running:
                    time.sleep(0.1)
                    continue
                
                # อัพเดตข้อมูลตัวนับ
                self._update_count_labels()
                
                # ดึงเฟรมปัจจุบัน (ถ้ามี)
                current_frame = None
                
                # ถ้ามีการเลือกกล้อง ใช้กล้องที่เลือก
                if self.selected_camera_id is not None:
                    # ดึงเฟรมจากกล้องที่เลือก
                    cameras = [cam for cam in self.camera.cameras if cam['id'] == self.selected_camera_id]
                    if cameras and 'current_frame' in cameras[0] and cameras[0]['current_frame'] is not None:
                        current_frame = cameras[0]['current_frame'].copy()
                
                # ถ้าไม่มีเฟรมจากกล้องที่เลือก ใช้เฟรมหลัก
                if current_frame is None and self.camera.current_frame is not None:
                    current_frame = self.camera.current_frame.copy()
                
                # ถ้าไม่มีเฟรมหลัก ใช้เฟรมจากกล้องใดก็ได้ที่มี
                if current_frame is None:
                    for cam in self.camera.cameras:
                        if 'current_frame' in cam and cam['current_frame'] is not None:
                            current_frame = cam['current_frame'].copy()
                            break
                
                if current_frame is not None:
                    # แปลงเป็นรูปแบบที่ Tkinter รองรับ
                    current_frame = cv2.cvtColor(current_frame, cv2.COLOR_BGR2RGB)
                    
                    # ปรับขนาดให้พอดีกับแคนวาส
                    canvas_width = self.video_canvas.winfo_width()
                    canvas_height = self.video_canvas.winfo_height()
                    
                    if canvas_width > 1 and canvas_height > 1:  # ตรวจสอบว่าแคนวาสมีขนาดแล้ว
                        aspect_ratio = current_frame.shape[1] / current_frame.shape[0]
                        canvas_ratio = canvas_width / canvas_height
                        
                        if aspect_ratio > canvas_ratio:  # ภาพกว้างกว่า
                            new_width = canvas_width
                            new_height = int(canvas_width / aspect_ratio)
                        else:  # ภาพสูงกว่า
                            new_height = canvas_height
                            new_width = int(canvas_height * aspect_ratio)
                        
                        current_frame = cv2.resize(current_frame, (new_width, new_height))
                    
                    # แปลงเป็น PhotoImage
                    image = PIL.Image.fromarray(current_frame)
                    photo = PIL.ImageTk.PhotoImage(image=image)
                    
                    # อัพเดตแคนวาส
                    self.video_canvas.create_image(
                        self.video_canvas.winfo_width() // 2,
                        self.video_canvas.winfo_height() // 2,
                        image=photo,
                        anchor=tk.CENTER
                    )
                    self.video_canvas.photo = photo  # เก็บอ้างอิงไว้เพื่อป้องกันการเก็บขยะ
                
                # รอ 33 มิลลิวินาที (ประมาณ 30 FPS)
                time.sleep(0.033)
                
            except Exception as e:
                self.logger.error(f"เกิดข้อผิดพลาดในการอัพเดตวีดีโอ: {str(e)}")
                time.sleep(1.0)  # รอนานขึ้นในกรณีเกิดข้อผิดพลาด
    
    def _update_count_labels(self):
        """อัพเดตข้อความแสดงจำนวนลูกค้า"""
        # ดึงข้อมูลสถานะ
        status = self.camera.get_status()
        
        # อัพเดตข้อความ
        self.current_count_label.config(text=str(status['people_in_store']))
        self.entry_count_label.config(text=str(status['entry_count']))
        self.exit_count_label.config(text=str(status['exit_count']))
        
        # อัพเดตรายละเอียดกล้องที่เลือกในหน้าจัดการกล้อง (ถ้ามีการเลือก)
        selection = self.cameras_table.selection()
        if selection:
            item = self.cameras_table.item(selection[0])
            camera_id = int(item['values'][0])
            self._update_camera_details(camera_id)
    
    def _update_time(self):
        """อัพเดตเวลาปัจจุบัน"""
        # แสดงเวลาปัจจุบัน
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.current_time_label.config(text=now)
        
        # เรียกอัพเดตอีกครั้งหลังจากผ่านไป 1 วินาที
        self.root.after(1000, self._update_time)
    
    def _update_status(self):
        try:
            # อัพเดตสถานะการซิงค์
            if self.api_client:
                sync_status = self.api_client.get_sync_status()
                
                if sync_status['running']:
                    # คำนวณเวลาถึงการซิงค์ครั้งต่อไป
                    next_sync = max(0, int(sync_status['next_sync_time'] - time.time()))
                    
                    # แสดงสถานะการซิงค์
                    self.sync_status_label.config(text=f"การซิงค์: ทำงาน (ครั้งต่อไปใน {next_sync} วินาที)")
                else:
                    self.sync_status_label.config(text="การซิงค์: ไม่ทำงาน")
            else:
                self.sync_status_label.config(text="การซิงค์: ปิดใช้งาน")
            
            # เรียกอัพเดตอีกครั้งหลังจากผ่านไป 1 วินาที
            self.root.after(1000, self._update_status)
            
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการอัพเดตสถานะ: {str(e)}")
            # เรียกอัพเดตอีกครั้งหลังจากผ่านไป 5 วินาที (กรณีเกิดข้อผิดพลาด)
            self.root.after(5000, self._update_status)