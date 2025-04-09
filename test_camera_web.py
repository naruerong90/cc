#!/usr/bin/env python3
# test_camera_web.py - ทดสอบการเชื่อมต่อกับกล้องสำหรับเว็บแอป

import cv2
import argparse
import urllib.parse
import time
import sys
import json
import os
from flask import Flask, Response, render_template, request, jsonify

app = Flask(__name__, template_folder='.')

# ตัวแปรส่วนกลาง
camera = None
current_frame = None
connected = False
frame_count = 0

# HTML สำหรับหน้าทดสอบ
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ทดสอบการเชื่อมต่อกล้อง</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        body { font-family: 'Sarabun', sans-serif; padding: 20px; }
        .camera-container { 
            border: 1px solid #ccc; 
            border-radius: 10px; 
            padding: 10px; 
            margin-bottom: 20px;
            background-color: #f8f9fa;
        }
        .video-container {
            width: 100%;
            height: 480px;
            background-color: #000;
            margin-bottom: 20px;
            border-radius: 5px;
            overflow: hidden;
            position: relative;
        }
        .control-panel {
            margin-top: 20px;
            padding: 15px;
            border-radius: 5px;
            background-color: #f5f5f5;
        }
        .status {
            padding: 10px;
            margin-bottom: 15px;
            border-radius: 5px;
        }
        .status-success { background-color: #d4edda; color: #155724; }
        .status-warning { background-color: #fff3cd; color: #856404; }
        .status-danger { background-color: #f8d7da; color: #721c24; }
        #connectionForm .row { margin-bottom: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h1 class="mb-4"><i class="fas fa-camera me-2"></i>ทดสอบการเชื่อมต่อกล้อง</h1>
        
        <div class="row">
            <div class="col-md-8">
                <div class="camera-container">
                    <h4>ภาพจากกล้อง</h4>
                    <div class="video-container">
                        <img id="cameraFeed" src="/video_feed" style="width: 100%; height: 100%; object-fit: contain;">
                    </div>
                    <div id="statusInfo" class="status status-warning">
                        <i class="fas fa-circle-info me-2"></i>กรุณากรอกข้อมูลและเชื่อมต่อกับกล้อง
                    </div>
                </div>
            </div>
            
            <div class="col-md-4">
                <div class="control-panel">
                    <h4 class="mb-3">ข้อมูลการเชื่อมต่อ</h4>
                    
                    <form id="connectionForm">
                        <div class="mb-3">
                            <label class="form-label">ประเภทการเชื่อมต่อ:</label>
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="connectionType" id="typeParams" value="params" checked>
                                <label class="form-check-label" for="typeParams">
                                    พารามิเตอร์ (Host, Username, ...)
                                </label>
                            </div>
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="connectionType" id="typeUrl" value="url">
                                <label class="form-check-label" for="typeUrl">
                                    URL โดยตรง
                                </label>
                            </div>
                        </div>
                        
                        <div id="paramsForm">
                            <div class="row">
                                <div class="col">
                                    <label for="cameraType" class="form-label">ประเภทกล้อง:</label>
                                    <select class="form-select" id="cameraType">
                                        <option value="dahua">Dahua</option>
                                        <option value="hikvision">Hikvision</option>
                                        <option value="generic">Generic</option>
                                    </select>
                                </div>
                            </div>
                            <div class="row">
                                <div class="col">
                                    <label for="host" class="form-label">Host:</label>
                                    <input type="text" class="form-control" id="host" placeholder="192.168.1.100">
                                </div>
                                <div class="col">
                                    <label for="port" class="form-label">Port:</label>
                                    <input type="text" class="form-control" id="port" value="554">
                                </div>
                            </div>
                            <div class="row">
                                <div class="col">
                                    <label for="username" class="form-label">Username:</label>
                                    <input type="text" class="form-control" id="username" value="admin">
                                </div>
                                <div class="col">
                                    <label for="password" class="form-label">Password:</label>
                                    <input type="password" class="form-control" id="password">
                                </div>
                            </div>
                            <div class="row">
                                <div class="col">
                                    <label for="channel" class="form-label">Channel:</label>
                                    <input type="text" class="form-control" id="channel" value="1">
                                </div>
                                <div class="col">
                                    <label for="path" class="form-label">Path (สำหรับ generic):</label>
                                    <input type="text" class="form-control" id="path" placeholder="/stream">
                                </div>
                            </div>
                        </div>
                        
                        <div id="urlForm" style="display:none;">
                            <div class="mb-3">
                                <label for="rtspUrl" class="form-label">RTSP URL:</label>
                                <input type="text" class="form-control" id="rtspUrl" placeholder="rtsp://username:password@192.168.1.100:554/stream">
                            </div>
                        </div>
                        
                        <div class="d-grid gap-2 mt-3">
                            <button type="button" id="connectBtn" class="btn btn-primary">
                                <i class="fas fa-plug me-1"></i>เชื่อมต่อ
                            </button>
                            <button type="button" id="disconnectBtn" class="btn btn-danger" disabled>
                                <i class="fas fa-times-circle me-1"></i>ตัดการเชื่อมต่อ
                            </button>
                        </div>
                    </form>
                </div>
                
                <div class="card mt-3">
                    <div class="card-header">ข้อมูลกล้อง</div>
                    <div class="card-body">
                        <p><strong>สถานะ:</strong> <span id="connectionStatus">ไม่ได้เชื่อมต่อ</span></p>
                        <p><strong>RTSP URL:</strong> <span id="urlDisplay">-</span></p>
                        <p><strong>จำนวนเฟรม:</strong> <span id="frameCount">0</span></p>
                        <p><strong>ขนาดภาพ:</strong> <span id="frameSize">-</span></p>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // เลือกประเภทการเชื่อมต่อ
        $('input[name="connectionType"]').change(function() {
            if ($(this).val() === 'params') {
                $('#paramsForm').show();
                $('#urlForm').hide();
            } else {
                $('#paramsForm').hide();
                $('#urlForm').show();
            }
        });
        
        // อัพเดตสถานะทุก 1 วินาที
        function updateStatus() {
            $.getJSON('/status', function(data) {
                $('#connectionStatus').text(data.connected ? 'เชื่อมต่อแล้ว' : 'ไม่ได้เชื่อมต่อ');
                $('#frameCount').text(data.frame_count);
                $('#frameSize').text(data.frame_size || '-');
                
                // อัพเดตสถานะ
                const statusDiv = $('#statusInfo');
                statusDiv.removeClass('status-success status-warning status-danger');
                
                if (data.connected) {
                    statusDiv.addClass('status-success');
                    statusDiv.html('<i class="fas fa-check-circle me-2"></i>เชื่อมต่อกับกล้องสำเร็จ กำลังรับภาพ...');
                    $('#connectBtn').prop('disabled', true);
                    $('#disconnectBtn').prop('disabled', false);
                } else {
                    statusDiv.addClass('status-warning');
                    statusDiv.html('<i class="fas fa-circle-info me-2"></i>ไม่ได้เชื่อมต่อกับกล้อง');
                    $('#connectBtn').prop('disabled', false);
                    $('#disconnectBtn').prop('disabled', true);
                }
            });
        }
        
        // เริ่มอัพเดตสถานะ
        setInterval(updateStatus, 1000);
        
        // เชื่อมต่อกับกล้อง
        $('#connectBtn').click(function() {
            const connectionType = $('input[name="connectionType"]:checked').val();
            let data = {};
            
            if (connectionType === 'params') {
                data = {
                    connection_type: 'params',
                    camera_type: $('#cameraType').val(),
                    host: $('#host').val(),
                    port: $('#port').val(),
                    username: $('#username').val(),
                    password: $('#password').val(),
                    channel: $('#channel').val(),
                    path: $('#path').val()
                };
            } else {
                data = {
                    connection_type: 'url',
                    url: $('#rtspUrl').val()
                };
            }
            
            // แสดงสถานะกำลังเชื่อมต่อ
            const statusDiv = $('#statusInfo');
            statusDiv.removeClass('status-success status-warning status-danger');
            statusDiv.addClass('status-warning');
            statusDiv.html('<i class="fas fa-circle-notch fa-spin me-2"></i>กำลังเชื่อมต่อกับกล้อง...');
            
            // ส่งคำขอเชื่อมต่อ
            $.ajax({
                url: '/connect',
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify(data),
                success: function(response) {
                    if (response.success) {
                        $('#urlDisplay').text(response.url);
                        updateStatus();
                    } else {
                        statusDiv.removeClass('status-success status-warning status-danger');
                        statusDiv.addClass('status-danger');
                        statusDiv.html('<i class="fas fa-times-circle me-2"></i>ไม่สามารถเชื่อมต่อกับกล้องได้: ' + response.message);
                    }
                },
                error: function() {
                    statusDiv.removeClass('status-success status-warning status-danger');
                    statusDiv.addClass('status-danger');
                    statusDiv.html('<i class="fas fa-times-circle me-2"></i>เกิดข้อผิดพลาดในการเชื่อมต่อ');
                }
            });
        });
        
        // ตัดการเชื่อมต่อ
        $('#disconnectBtn').click(function() {
            $.post('/disconnect', function(response) {
                if (response.success) {
                    updateStatus();
                    $('#urlDisplay').text('-');
                }
            });
        });
    </script>
</body>
</html>
"""

def build_rtsp_url(data):
    """สร้าง RTSP URL จากข้อมูลที่ได้รับ"""
    if data.get('connection_type') == 'url':
        return data.get('url', '')
    
    # สร้าง URL จากพารามิเตอร์
    camera_type = data.get('camera_type', 'generic')
    host = data.get('host', '')
    port = data.get('port', '554')
    username = data.get('username', 'admin')
    password = data.get('password', '')
    channel = data.get('channel', '1')
    path = data.get('path', '')
    
    # เข้ารหัสรหัสผ่าน
    encoded_password = urllib.parse.quote(password)
    
    # สร้าง URL ตามประเภทกล้อง
    if camera_type == 'dahua':
        return f"rtsp://{username}:{encoded_password}@{host}:{port}/cam/realmonitor?channel={channel}&subtype=0"
    elif camera_type == 'hikvision':
        return f"rtsp://{username}:{encoded_password}@{host}:{port}/Streaming/Channels/{channel}01"
    else:  # generic
        url = f"rtsp://{username}:{encoded_password}@{host}:{port}"
        if path:
            if not path.startswith('/'):
                url += f"/{path}"
            else:
                url += path
        return url

def gen_frames():
    """สร้าง generator สำหรับส่ง frame ไปยังหน้าเว็บ"""
    global current_frame, connected, frame_count
    
    while True:
        if connected and current_frame is not None:
            # แปลงเฟรมเป็น JPEG
            ret, buffer = cv2.imencode('.jpg', current_frame)
            if ret:
                frame_count += 1
                # ส่งเฟรมในรูปแบบ multipart/x-mixed-replace
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        else:
            # ถ้าไม่ได้เชื่อมต่อหรือไม่มีเฟรม ส่งภาพว่าง
            blank_image = cv2.imencode('.jpg', 
                          cv2.putText(
                              cv2.rectangle(
                                  np.zeros((480, 640, 3), np.uint8), 
                                  (0, 0), (640, 480), (50, 50, 50), -1
                              ), 
                              "No Camera Connected", (50, 240), 
                              cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2
                          ))[1].tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + blank_image + b'\r\n')
        time.sleep(0.033)  # ประมาณ 30 fps

@app.route('/')
def index():
    """หน้าหลัก"""
    return HTML_TEMPLATE

@app.route('/video_feed')
def video_feed():
    """สตรีมวิดีโอ"""
    return Response(gen_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/status')
def get_status():
    """ส่งข้อมูลสถานะกล้อง"""
    global connected, frame_count, current_frame
    
    frame_size = f"{current_frame.shape[1]}x{current_frame.shape[0]}" if connected and current_frame is not None else "-"
    
    return jsonify({
        'connected': connected,
        'frame_count': frame_count,
        'frame_size': frame_size
    })

@app.route('/connect', methods=['POST'])
def connect():
    """เชื่อมต่อกับกล้อง"""
    global camera, connected, current_frame, frame_count
    
    # รับข้อมูลการเชื่อมต่อ
    data = request.json
    
    # ตัดการเชื่อมต่อก่อนหากมีการเชื่อมต่ออยู่
    if connected and camera is not None:
        camera.release()
        connected = False
    
    try:
        # สร้าง URL
        rtsp_url = build_rtsp_url(data)
        
        if not rtsp_url:
            return jsonify({'success': False, 'message': 'ไม่สามารถสร้าง URL ได้'})
        
        # พยายามเชื่อมต่อกับกล้อง
        print(f"กำลังเชื่อมต่อกับ: {rtsp_url}")
        camera = cv2.VideoCapture(rtsp_url)
        
        # รอการเชื่อมต่อสักครู่
        time.sleep(2)
        
        # ตรวจสอบการเชื่อมต่อ
        if camera.isOpened():
            # ลองอ่านเฟรม
            ret, frame = camera.read()
            if ret:
                current_frame = frame
                connected = True
                frame_count = 0
                print("เชื่อมต่อกับกล้องสำเร็จ!")
                
                # เริ่มเธรดสำหรับอ่านเฟรม
                threading.Thread(target=read_frames, daemon=True).start()
                
                return jsonify({
                    'success': True,
                    'message': 'เชื่อมต่อกับกล้องสำเร็จ',
                    'url': rtsp_url
                })
        
        # ถ้าไม่สามารถอ่านเฟรมได้
        camera.release()
        return jsonify({'success': False, 'message': 'ไม่สามารถอ่านเฟรมจากกล้องได้'})
        
    except Exception as e:
        if camera:
            camera.release()
        print(f"เกิดข้อผิดพลาด: {str(e)}")
        return jsonify({'success': False, 'message': f'เกิดข้อผิดพลาด: {str(e)}'})

@app.route('/disconnect', methods=['POST'])
def disconnect():
    """ตัดการเชื่อมต่อกับกล้อง"""
    global camera, connected
    
    if connected and camera is not None:
        camera.release()
        connected = False
        print("ตัดการเชื่อมต่อกับกล้อง")
    
    return jsonify({'success': True, 'message': 'ตัดการเชื่อมต่อกับกล้องสำเร็จ'})

def read_frames():
    """อ่านเฟรมจากกล้องในเธรดแยก"""
    global camera, current_frame, connected
    
    while connected and camera is not None:
        try:
            ret, frame = camera.read()
            if ret:
                current_frame = frame
            else:
                print("ไม่สามารถอ่านเฟรมได้")
                time.sleep(0.5)
                
                # ถ้าอ่านไม่ได้หลายครั้ง ให้ตัดการเชื่อมต่อ
                retry_count = 0
                while not ret and retry_count < 5:
                    ret, frame = camera.read()
                    retry_count += 1
                    time.sleep(0.5)
                
                if not ret:
                    print("ไม่สามารถอ่านเฟรมได้หลายครั้ง ตัดการเชื่อมต่อ")
                    connected = False
                    camera.release()
                    break
        except Exception as e:
            print(f"เกิดข้อผิดพลาดในการอ่านเฟรม: {str(e)}")
            connected = False
            if camera:
                camera.release()
            break
        
        time.sleep(0.01)  # หน่วงเวลาเล็กน้อย

if __name__ == '__main__':
    import numpy as np
    
    # สร้างตัวแปร current_frame เป็นภาพว่าง
    current_frame = np.zeros((480, 640, 3), np.uint8)
    cv2.putText(current_frame, "No Camera Connected", (50, 240), 
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    
    parser = argparse.ArgumentParser(description='ทดสอบการเชื่อมต่อกับกล้องสำหรับเว็บแอป')
    parser.add_argument('--host', type=str, default='127.0.0.1', help='Host (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=8081, help='Port (default: 8081)')
    parser.add_argument('--debug', action='store_true', help='เปิดโหมดดีบัก')
    
    args = parser.parse_args()
    
    print(f"เริ่มเว็บเซิร์ฟเวอร์ที่ http://{args.host}:{args.port}")
    print("เปิดเบราว์เซอร์และเข้าสู่ URL ข้างต้นเพื่อเริ่มทดสอบการเชื่อมต่อกับกล้อง")
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)