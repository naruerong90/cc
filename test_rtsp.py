#!/usr/bin/env python3
# test_rtsp.py - ทดสอบการเชื่อมต่อกับกล้องผ่าน RTSP

import cv2
import time
import argparse
import urllib.parse

def test_rtsp_connection(url, timeout=10):
    """
    ทดสอบการเชื่อมต่อกับกล้องผ่าน RTSP
    
    Args:
        url: RTSP URL หรือข้อมูลการเชื่อมต่อ (username, password, host, port)
        timeout: เวลาที่รอก่อนยกเลิกการเชื่อมต่อ (วินาที)
    
    Returns:
        bool: True ถ้าเชื่อมต่อสำเร็จ, False ถ้าไม่สำเร็จ
    """
    # ตรวจสอบว่าเป็น URL หรือข้อมูลแยก
    if not url.startswith('rtsp://'):
        # ถ้าไม่ใช่ URL เต็ม ให้สร้าง URL จากข้อมูลที่ให้มา
        # คาดว่าจะเป็นในรูปแบบ username:password@host:port/path
        parts = url.split('@')
        if len(parts) == 2:
            # มีทั้ง username:password และ host:port/path
            auth_part = parts[0]
            host_part = parts[1]
            
            # แยก username และ password
            auth_parts = auth_part.split(':')
            username = auth_parts[0]
            password = auth_parts[1] if len(auth_parts) > 1 else ''
            
            # แยก host, port และ path
            host_parts = host_part.split('/')
            host_port = host_parts[0]
            path = '/' + '/'.join(host_parts[1:]) if len(host_parts) > 1 else ''
            
            # แยก host และ port
            host_port_parts = host_port.split(':')
            host = host_port_parts[0]
            port = host_port_parts[1] if len(host_port_parts) > 1 else '554'
            
            # เข้ารหัส password
            encoded_password = urllib.parse.quote(password, safe='')
            
            # สร้าง URL
            url = f"rtsp://{username}:{encoded_password}@{host}:{port}{path}"
        
    print(f"ทดสอบการเชื่อมต่อกับ: {url}")
    
    # เริ่มการเชื่อมต่อ
    cap = cv2.VideoCapture(url)
    
    start_time = time.time()
    success = False
    
    # รอจนกว่าจะเชื่อมต่อสำเร็จหรือหมดเวลา
    while time.time() - start_time < timeout:
        if cap.isOpened():
            # ลองอ่านเฟรม
            ret, frame = cap.read()
            if ret:
                # อ่านเฟรมสำเร็จ
                print("เชื่อมต่อสำเร็จ! สามารถอ่านเฟรมได้")
                print(f"ขนาดเฟรม: {frame.shape[1]}x{frame.shape[0]}px")
                
                # แสดงเฟรมที่อ่านได้
                cv2.imshow("RTSP Test", frame)
                cv2.waitKey(3000)  # รอ 3 วินาที
                cv2.destroyAllWindows()
                
                success = True
                break
        
        print("กำลังพยายามเชื่อมต่อ...")
        time.sleep(1)
    
    # ปิดการเชื่อมต่อ
    cap.release()
    
    if not success:
        print(f"เชื่อมต่อไม่สำเร็จภายในเวลา {timeout} วินาที")
        
    return success

def build_dahua_url(username, password, host, port='554', channel='1'):
    """สร้าง URL สำหรับกล้อง Dahua"""
    encoded_password = urllib.parse.quote(password, safe='')
    return f"rtsp://{username}:{encoded_password}@{host}:{port}/cam/realmonitor?channel={channel}&subtype=0"

def build_hikvision_url(username, password, host, port='554', channel='1'):
    """สร้าง URL สำหรับกล้อง Hikvision"""
    encoded_password = urllib.parse.quote(password, safe='')
    return f"rtsp://{username}:{encoded_password}@{host}:{port}/Streaming/Channels/{channel}01"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='ทดสอบการเชื่อมต่อกับกล้องผ่าน RTSP')
    
    # พารามิเตอร์สำหรับการเชื่อมต่อโดยตรง
    parser.add_argument('--url', type=str, help='RTSP URL เต็มสำหรับเชื่อมต่อกล้อง')
    
    # พารามิเตอร์สำหรับสร้าง URL
    parser.add_argument('--username', type=str, help='ชื่อผู้ใช้สำหรับเข้าถึงกล้อง')
    parser.add_argument('--password', type=str, help='รหัสผ่านสำหรับเข้าถึงกล้อง')
    parser.add_argument('--host', type=str, help='ที่อยู่ IP หรือโฮสต์เนมของกล้อง')
    parser.add_argument('--port', type=str, default='554', help='พอร์ต RTSP (ค่าเริ่มต้น: 554)')
    parser.add_argument('--channel', type=str, default='1', help='ช่องสัญญาณกล้อง (ค่าเริ่มต้น: 1)')
    parser.add_argument('--type', type=str, default='dahua', help='ประเภทกล้อง (dahua, hikvision) (ค่าเริ่มต้น: dahua)')
    
    parser.add_argument('--timeout', type=int, default=10, help='เวลาที่รอก่อนยกเลิกการเชื่อมต่อ (วินาที) (ค่าเริ่มต้น: 10)')
    
    args = parser.parse_args()
    
    url = None
    
    if args.url:
        # ใช้ URL ที่ระบุโดยตรง
        url = args.url
    elif args.username and args.password and args.host:
        # สร้าง URL จากข้อมูลที่ระบุ
        if args.type.lower() == 'hikvision':
            url = build_hikvision_url(args.username, args.password, args.host, args.port, args.channel)
        else:  # dahua หรือประเภทอื่นๆ
            url = build_dahua_url(args.username, args.password, args.host, args.port, args.channel)
    else:
        # ทำการทดสอบกับตัวอย่าง URL สำหรับกล้อง Dahua
        username = input("ชื่อผู้ใช้ [admin]: ") or "admin"
        password = input("รหัสผ่าน [Admin@1234]: ") or "Admin@1234"
        host = input("ที่อยู่ IP [10.10.1.230]: ") or "10.10.1.230"
        port = input("พอร์ต [554]: ") or "554"
        channel = input("ช่องสัญญาณ [1]: ") or "1"
        camera_type = input("ประเภทกล้อง (dahua, hikvision) [dahua]: ") or "dahua"
        
        if camera_type.lower() == 'hikvision':
            url = build_hikvision_url(username, password, host, port, channel)
        else:  # dahua หรือประเภทอื่นๆ
            url = build_dahua_url(username, password, host, port, channel)
    
    success = test_rtsp_connection(url, args.timeout)
    
    if success:
        print("\nการทดสอบสำเร็จ! สามารถเชื่อมต่อกับกล้องได้")
        print(f"RTSP URL ที่ใช้: {url}")
    else:
        print("\nการทดสอบล้มเหลว! ไม่สามารถเชื่อมต่อกับกล้องได้")
        print("สาเหตุที่เป็นไปได้:")
        print("1. ข้อมูลการเชื่อมต่อไม่ถูกต้อง (username, password, host, port)")
        print("2. ไม่สามารถเข้าถึงกล้องได้ (อาจมีไฟร์วอลล์บล็อกอยู่)")
        print("3. กล้องไม่รองรับ RTSP หรือมีการตั้งค่าที่แตกต่าง")
        print("4. URL path ไม่ถูกต้องสำหรับกล้องรุ่นนี้")