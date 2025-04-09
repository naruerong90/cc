/**
 * main.js - JavaScript หลักสำหรับระบบนับลูกค้าผ่านกล้องวงจรปิด
 * เวอร์ชัน: 1.0.0
 * ระบบนับลูกค้าผ่านกล้องวงจรปิด Web Application
 */

// =============================================
// ตัวแปรส่วนกลาง
// =============================================
let cameraRunning = false;          // สถานะการทำงานของกล้อง
let selectedCameraId = null;        // รหัสกล้องที่เลือก
let frameUpdateInterval = null;     // ตัวแปรสำหรับอัพเดตเฟรม
let statusUpdateInterval = null;    // ตัวแปรสำหรับอัพเดตสถานะ
let syncStatusInterval = null;      // ตัวแปรสำหรับอัพเดตสถานะการซิงค์
let currentPage = '';               // หน้าปัจจุบัน
let currentTheme = 'light';         // ธีมปัจจุบัน (light หรือ dark)

// สำหรับหน้า Stats
let visitorTrendChart = null;
let visitorDistributionChart = null;
let peakTimeChart = null;
let statsData = [];

// =============================================
// ฟังก์ชันพื้นฐาน
// =============================================

/**
 * แสดงหรือซ่อน Loading Spinner
 * @param {boolean} show - true เพื่อแสดง, false เพื่อซ่อน
 */
function toggleSpinner(show) {
    const spinner = document.getElementById('loadingSpinner');
    if (spinner) {
        spinner.style.display = show ? 'block' : 'none';
    }
}

/**
 * แสดงข้อความแจ้งเตือน
 * @param {string} message - ข้อความ
 * @param {string} type - ประเภท (success, info, warning, danger)
 * @param {number} duration - ระยะเวลาแสดง (มิลลิวินาที)
 */
function showAlert(message, type = 'info', duration = 5000) {
    // หา container สำหรับ alert
    let alertContainer = document.getElementById('alertContainer');
    
    // ถ้าไม่มี ให้สร้างใหม่
    if (!alertContainer) {
        alertContainer = document.createElement('div');
        alertContainer.id = 'alertContainer';
        alertContainer.style.position = 'fixed';
        alertContainer.style.top = '20px';
        alertContainer.style.right = '20px';
        alertContainer.style.zIndex = '9999';
        document.body.appendChild(alertContainer);
    }
    
    // สร้าง alert element
    const alertEl = document.createElement('div');
    alertEl.className = `alert alert-${type} alert-dismissible fade show`;
    alertEl.role = 'alert';
    alertEl.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    // เพิ่ม alert ไปยัง container
    alertContainer.appendChild(alertEl);
    
    // ใช้ Bootstrap JS เพื่อจัดการ alert
    const bsAlert = new bootstrap.Alert(alertEl);
    
    // ตั้งเวลาลบ alert
    setTimeout(() => {
        bsAlert.close();
    }, duration);
}

/**
 * อัพเดตเวลาปัจจุบัน
 */
function updateTime() {
    const now = new Date();
    const options = {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    };
    
    const timeElements = document.querySelectorAll('.current-time');
    timeElements.forEach(el => {
        el.textContent = now.toLocaleString('th-TH', options);
    });
}

/**
 * ฟอร์แมตวันที่เป็นรูปแบบ YYYY-MM-DD
 * @param {Date} date - วันที่
 * @returns {string} วันที่ในรูปแบบ YYYY-MM-DD
 */
function formatDate(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

/**
 * สร้าง URL ที่มีพารามิเตอร์
 * @param {string} baseUrl - URL พื้นฐาน
 * @param {Object} params - พารามิเตอร์
 * @returns {string} URL พร้อมพารามิเตอร์
 */
function buildUrl(baseUrl, params) {
    const url = new URL(baseUrl, window.location.origin);
    Object.keys(params).forEach(key => {
        if (params[key] !== null && params[key] !== undefined) {
            url.searchParams.append(key, params[key]);
        }
    });
    return url.toString();
}

/**
 * เรียก API
 * @param {string} url - URL ของ API
 * @param {string} method - HTTP method (GET, POST, PUT, DELETE)
 * @param {Object|null} data - ข้อมูลที่จะส่ง (สำหรับ POST, PUT)
 * @returns {Promise} ผลลัพธ์จาก API
 */
async function callApi(url, method = 'GET', data = null) {
    toggleSpinner(true);
    
    try {
        const options = {
            method,
            headers: {}
        };
        
        if (data) {
            options.headers['Content-Type'] = 'application/json';
            options.body = JSON.stringify(data);
        }
        
        const response = await fetch(url, options);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        toggleSpinner(false);
        return result;
    } catch (error) {
        toggleSpinner(false);
        console.error('API error:', error);
        showAlert(`เกิดข้อผิดพลาดในการเรียก API: ${error.message}`, 'danger');
        throw error;
    }
}

// =============================================
// ฟังก์ชันสำหรับหน้าหลัก (Dashboard)
// =============================================

/**
 * อัพเดตเฟรมวิดีโอ
 */
function updateVideoFrame() {
    if (!cameraRunning || !selectedCameraId) return;
    
    callApi(`/api/frame/${selectedCameraId}`, 'GET')
        .then(data => {
            if (data.frame) {
                const imgElement = document.getElementById('videoFrame');
                if (imgElement) {
                    imgElement.src = 'data:image/jpeg;base64,' + data.frame;
                }
            }
        })
        .catch(error => {
            console.error('Error updating video frame:', error);
        });
}

/**
 * เริ่มอัพเดตเฟรมวิดีโอ
 */
function startFrameUpdate() {
    if (!frameUpdateInterval) {
        frameUpdateInterval = setInterval(updateVideoFrame, 100); // 10 FPS
    }
}

/**
 * หยุดอัพเดตเฟรมวิดีโอ
 */
function stopFrameUpdate() {
    if (frameUpdateInterval) {
        clearInterval(frameUpdateInterval);
        frameUpdateInterval = null;
    }
}

/**
 * อัพเดตสถานะกล้องและระบบ
 */
function updateStatus() {
    callApi('/api/status', 'GET')
        .then(data => {
            // อัพเดตตัวนับ
            document.getElementById('currentCount').textContent = data.people_in_store || '0';
            document.getElementById('entryCount').textContent = data.entry_count || '0';
            document.getElementById('exitCount').textContent = data.exit_count || '0';
            
            // อัพเดตสถานะกล้อง
            document.getElementById('cameraStatus').textContent = data.running ? 'ทำงาน' : 'ไม่ทำงาน';
            
            // อัพเดตปุ่มควบคุม
            document.getElementById('startCameraBtn').disabled = data.running;
            document.getElementById('stopCameraBtn').disabled = !data.running;
            
            // อัพเดตสถานะระบบ
            const appStatusEl = document.getElementById('appStatus');
            if (data.running) {
                appStatusEl.innerHTML = '<i class="fas fa-circle text-success me-1"></i> กล้องกำลังทำงาน';
                cameraRunning = true;
                startFrameUpdate();
            } else {
                appStatusEl.innerHTML = '<i class="fas fa-circle text-warning me-1"></i> กล้องไม่ทำงาน';
                cameraRunning = false;
                stopFrameUpdate();
            }
            
            // อัพเดตสถานะการซิงค์
            if (data.sync) {
                updateSyncStatus(data.sync);
            }
        })
        .catch(error => {
            console.error('Error updating status:', error);
            document.getElementById('appStatus').innerHTML = '<i class="fas fa-circle text-danger me-1"></i> ไม่สามารถเชื่อมต่อกับเซิร์ฟเวอร์';
        });
}

/**
 * อัพเดตสถานะการซิงค์
 * @param {Object} syncData - ข้อมูลสถานะการซิงค์
 */
function updateSyncStatus(syncData) {
    const syncStatusEl = document.getElementById('syncStatus');
    if (!syncStatusEl) return;
    
    const syncRunning = syncData.running;
    const nextSyncTime = new Date(syncData.next_sync_time * 1000);
    const now = new Date();
    const timeToNextSync = Math.max(0, Math.floor((nextSyncTime - now) / 1000));
    
    if (syncRunning) {
        syncStatusEl.innerHTML = `<i class="fas fa-sync fa-spin"></i> การซิงค์: ทำงาน (ครั้งต่อไปใน ${timeToNextSync} วินาที)`;
    } else {
        syncStatusEl.innerHTML = `<i class="fas fa-sync"></i> การซิงค์: ไม่ทำงาน`;
    }
}

/**
 * เริ่มการทำงานของกล้อง
 */
function startCamera() {
    toggleSpinner(true);
    
    callApi('/api/camera/start', 'POST')
        .then(data => {
            if (data.success) {
                showAlert('เริ่มการทำงานของกล้องสำเร็จ', 'success');
                updateStatus();
            } else {
                showAlert(`ไม่สามารถเริ่มการทำงานของกล้องได้: ${data.message}`, 'danger');
            }
        })
        .catch(error => {
            console.error('Error starting camera:', error);
            showAlert('เกิดข้อผิดพลาดในการเริ่มกล้อง', 'danger');
        });
}

/**
 * หยุดการทำงานของกล้อง
 */
function stopCamera() {
    toggleSpinner(true);
    
    callApi('/api/camera/stop', 'POST')
        .then(data => {
            if (data.success) {
                showAlert('หยุดการทำงานของกล้องสำเร็จ', 'success');
                stopFrameUpdate();
                updateStatus();
            } else {
                showAlert(`ไม่สามารถหยุดการทำงานของกล้องได้: ${data.message}`, 'danger');
            }
        })
        .catch(error => {
            console.error('Error stopping camera:', error);
            showAlert('เกิดข้อผิดพลาดในการหยุดกล้อง', 'danger');
        });
}

/**
 * รีเซ็ตตัวนับลูกค้า
 */
function resetCounters() {
    if (confirm('คุณต้องการรีเซ็ตตัวนับลูกค้าทั้งหมดหรือไม่?')) {
        toggleSpinner(true);
        
        callApi('/api/camera/reset', 'POST')
            .then(data => {
                if (data.success) {
                    showAlert('รีเซ็ตตัวนับสำเร็จ', 'success');
                    updateStatus();
                } else {
                    showAlert(`ไม่สามารถรีเซ็ตตัวนับได้: ${data.message}`, 'danger');
                }
            })
            .catch(error => {
                console.error('Error resetting counters:', error);
                showAlert('เกิดข้อผิดพลาดในการรีเซ็ตตัวนับ', 'danger');
            });
    }
}

/**
 * ถ่ายภาพจากกล้อง
 */
function takeSnapshot() {
    toggleSpinner(true);
    
    callApi('/api/camera/snapshot', 'POST', { camera_id: selectedCameraId })
        .then(data => {
            if (data.success) {
                // แสดงภาพถ่ายใน Modal
                document.getElementById('snapshotImage').src = data.url;
                document.getElementById('downloadSnapshotBtn').href = data.url;
                
                // แสดง Modal
                const snapshotModal = new bootstrap.Modal(document.getElementById('snapshotModal'));
                snapshotModal.show();
                
                showAlert('ถ่ายภาพสำเร็จ', 'success');
            } else {
                showAlert(`ไม่สามารถถ่ายภาพได้: ${data.message}`, 'danger');
            }
        })
        .catch(error => {
            console.error('Error taking snapshot:', error);
            showAlert('เกิดข้อผิดพลาดในการถ่ายภาพ', 'danger');
        });
}

/**
 * เลือกกล้อง
 * @param {number} cameraId - รหัสกล้อง
 */
function selectCamera(cameraId) {
    selectedCameraId = cameraId;
    
    // อัพเดตข้อมูลกล้องที่เลือก
    callApi(`/api/camera/${cameraId}`, 'GET')
        .then(data => {
            if (data.success) {
                const camera = data.camera;
                document.getElementById('cameraNameLabel').textContent = camera.name;
            }
        })
        .catch(error => {
            console.error('Error getting camera details:', error);
        });
}

// =============================================
// ฟังก์ชันสำหรับหน้าจัดการกล้อง (Cameras)
// =============================================

/**
 * โหลดรายละเอียดกล้อง
 * @param {number} cameraId - รหัสกล้อง
 */
function loadCameraDetails(cameraId) {
    toggleSpinner(true);
    
    callApi(`/api/camera/${cameraId}`, 'GET')
        .then(response => {
            if (response.success) {
                const camera = response.camera;
                
                // แสดงรายละเอียดกล้อง
                const detailsHtml = `
                    <div class="row">
                        <div class="col-md-6">
                            <h5>${camera.name}</h5>
                            <p><strong>ID:</strong> ${camera.id}</p>
                            <p><strong>ประเภท:</strong> ${camera.type}</p>
                            <p><strong>สถานะ:</strong> <span class="badge ${camera.running ? 'bg-success' : 'bg-danger'}">${camera.running ? 'ทำงาน' : 'ไม่ทำงาน'}</span></p>
                            <p><strong>แหล่งที่มา:</strong> ${camera.connection_mode === 'direct' ? camera.source : 'Params-based connection'}</p>
                        </div>
                        <div class="col-md-6">
                            <h5>ข้อมูลการตรวจจับ</h5>
                            <p><strong>ตำแหน่งเส้นตรวจจับ:</strong> ${camera.detection_line}</p>
                            <p><strong>มุมเส้นตรวจจับ:</strong> ${camera.detection_angle}°</p>
                            <p><strong>พื้นที่ขั้นต่ำ:</strong> ${camera.min_area}</p>
                            <p><strong>จำนวนคนในร้าน:</strong> ${camera.people_in_store}</p>
                        </div>
                    </div>
                    <div class="row mt-3">
                        <div class="col-md-12">
                            <h5>สถิติการนับ</h5>
                            <div class="row">
                                <div class="col-md-4">
                                    <div class="card bg-primary text-white">
                                        <div class="card-body">
                                            <h5 class="card-title">จำนวนคนในร้าน</h5>
                                            <p class="card-text display-6">${camera.people_in_store}</p>
                                        </div>
                                    </div>
                                </div>
                                <div class="col-md-4">
                                    <div class="card bg-success text-white">
                                        <div class="card-body">
                                            <h5 class="card-title">คนเข้าร้าน</h5>
                                            <p class="card-text display-6">${camera.entry_count}</p>
                                        </div>
                                    </div>
                                </div>
                                <div class="col-md-4">
                                    <div class="card bg-danger text-white">
                                        <div class="card-body">
                                            <h5 class="card-title">คนออกร้าน</h5>
                                            <p class="card-text display-6">${camera.exit_count}</p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
                
                document.getElementById('cameraDetailsContainer').innerHTML = detailsHtml;
            } else {
                document.getElementById('cameraDetailsContainer').innerHTML = `
                    <div class="alert alert-danger">
                        ${response.message}
                    </div>
                `;
            }
        })
        .catch(error => {
            console.error('Error loading camera details:', error);
            document.getElementById('cameraDetailsContainer').innerHTML = `
                <div class="alert alert-danger">
                    เกิดข้อผิดพลาดในการโหลดรายละเอียดกล้อง
                </div>
            `;
        })
        .finally(() => {
            toggleSpinner(false);
        });
}

/**
 * ทดสอบการเชื่อมต่อกล้อง
 * @param {boolean} isEdit - true หากกำลังแก้ไขกล้อง, false หากกำลังเพิ่มกล้อง
 */
function testCameraConnection(isEdit = false) {
    toggleSpinner(true);
    
    const formSelector = isEdit ? '#editCameraForm' : '#addCameraForm';
    const connectionModeSelector = isEdit ? 'input[name="editConnectionMode"]:checked' : 'input[name="connectionMode"]:checked';
    
    const connectionMode = document.querySelector(connectionModeSelector).value;
    
    // รวบรวมข้อมูลจากฟอร์ม
    const formData = new FormData(document.querySelector(formSelector));
    const requestData = {
        connection_mode: connectionMode,
        type: isEdit ? document.getElementById('editCameraType').value : document.getElementById('cameraType').value
    };
    
    if (connectionMode === 'direct') {
        // ใช้ URL โดยตรง
        requestData.source = isEdit ? 
            document.getElementById('editCameraSource').value : 
            document.getElementById('cameraSource').value;
    } else {
        // ใช้พารามิเตอร์
        requestData.host = isEdit ? 
            document.getElementById('editCameraHost').value : 
            document.getElementById('cameraHost').value;
        requestData.port = isEdit ? 
            document.getElementById('editCameraPort').value : 
            document.getElementById('cameraPort').value;
        requestData.username = isEdit ? 
            document.getElementById('editCameraUsername').value : 
            document.getElementById('cameraUsername').value;
        requestData.password = isEdit ? 
            document.getElementById('editCameraPassword').value : 
            document.getElementById('cameraPassword').value;
        requestData.channel = isEdit ? 
            document.getElementById('editCameraChannel').value : 
            document.getElementById('cameraChannel').value;
        requestData.path = isEdit ? 
            document.getElementById('editCameraPath').value : 
            document.getElementById('cameraPath').value;
    }
    
    // เรียก API ทดสอบการเชื่อมต่อ
    callApi('/api/camera/test_connection', 'POST', requestData)
        .then(response => {
            if (response.success) {
                showAlert('เชื่อมต่อกับกล้องสำเร็จ', 'success');
            } else {
                showAlert(`ไม่สามารถเชื่อมต่อกับกล้องได้: ${response.message}`, 'warning');
            }
        })
        .catch(error => {
            console.error('Error testing camera connection:', error);
            showAlert('เกิดข้อผิดพลาดในการทดสอบการเชื่อมต่อ', 'danger');
        });
}

/**
 * เพิ่มกล้องใหม่
 */
function addCamera() {
    toggleSpinner(true);
    
    const connectionMode = document.querySelector('input[name="connectionMode"]:checked').value;
    const formData = {
        name: document.getElementById('cameraName').value,
        type: document.getElementById('cameraType').value,
        connection_mode: connectionMode,
        detection_line: document.getElementById('detectionLine').value,
        min_area: document.getElementById('minArea').value,
        detection_angle: document.getElementById('detectionAngle').value
    };
    
    if (connectionMode === 'direct') {
        // ใช้ URL โดยตรง
        formData.source = document.getElementById('cameraSource').value;
    } else {
        // ใช้พารามิเตอร์
        formData.host = document.getElementById('cameraHost').value;
        formData.port = document.getElementById('cameraPort').value;
        formData.username = document.getElementById('cameraUsername').value;
        formData.password = document.getElementById('cameraPassword').value;
        formData.channel = document.getElementById('cameraChannel').value;
        formData.path = document.getElementById('cameraPath').value;
    }
    
    // เรียก API เพิ่มกล้อง
    callApi('/api/camera/add', 'POST', formData)
        .then(response => {
            if (response.success) {
                const addCameraModal = bootstrap.Modal.getInstance(document.getElementById('addCameraModal'));
                addCameraModal.hide();
                showAlert(response.message, 'success');
                // รีเฟรชหน้า
                setTimeout(() => {
                    window.location.reload();
                }, 1000);
            } else {
                showAlert(`ไม่สามารถเพิ่มกล้องได้: ${response.message}`, 'danger');
            }
        })
        .catch(error => {
            console.error('Error adding camera:', error);
            showAlert('เกิดข้อผิดพลาดในการเพิ่มกล้อง', 'danger');
        });
}

/**
 * โหลดข้อมูลกล้องสำหรับแก้ไข
 * @param {number} cameraId - รหัสกล้อง
 */
function loadCameraForEdit(cameraId) {
    toggleSpinner(true);
    
    callApi(`/api/camera/${cameraId}`, 'GET')
        .then(response => {
            if (response.success) {
                const camera = response.camera;
                
                // เก็บ ID สำหรับการอัพเดต
                document.getElementById('editCameraId').value = camera.id;
                
                // กรอกข้อมูลในฟอร์ม
                document.getElementById('editCameraName').value = camera.name;
                document.getElementById('editCameraType').value = camera.type;
                
                // ตั้งค่าโหมดการเชื่อมต่อ
                if (camera.connection_mode === 'direct') {
                    document.getElementById('editDirectMode').checked = true;
                    document.getElementById('editParamsForm').style.display = 'none';
                    document.getElementById('editDirectForm').style.display = 'block';
                    
                    // กรอกข้อมูล URL
                    document.getElementById('editCameraSource').value = camera.source;
                } else {
                    document.getElementById('editParamsMode').checked = true;
                    document.getElementById('editParamsForm').style.display = 'block';
                    document.getElementById('editDirectForm').style.display = 'none';
                    
                    // กรอกข้อมูลพารามิเตอร์
                    document.getElementById('editCameraHost').value = camera.host;
                    document.getElementById('editCameraPort').value = camera.port;
                    document.getElementById('editCameraUsername').value = camera.username;
                    document.getElementById('editCameraPassword').value = '';  // ไม่แสดงรหัสผ่าน
                    document.getElementById('editCameraChannel').value = camera.channel;
                    document.getElementById('editCameraPath').value = camera.path;
                }
                
                // กรอกข้อมูลการตรวจจับ
                document.getElementById('editDetectionLine').value = camera.detection_line;
                document.getElementById('editMinArea').value = camera.min_area;
                document.getElementById('editDetectionAngle').value = camera.detection_angle;
                
                // แสดง Modal
                const editCameraModal = new bootstrap.Modal(document.getElementById('editCameraModal'));
                editCameraModal.show();
            } else {
                showAlert(`ไม่สามารถโหลดข้อมูลกล้องได้: ${response.message}`, 'danger');
            }
        })
        .catch(error => {
            console.error('Error loading camera for edit:', error);
            showAlert('เกิดข้อผิดพลาดในการโหลดข้อมูลกล้อง', 'danger');
        })
        .finally(() => {
            toggleSpinner(false);
        });
}

/**
 * อัพเดตกล้อง
 */
function updateCamera() {
    toggleSpinner(true);
    
    const cameraId = document.getElementById('editCameraId').value;
    const connectionMode = document.querySelector('input[name="editConnectionMode"]:checked').value;
    const formData = {
        name: document.getElementById('editCameraName').value,
        type: document.getElementById('editCameraType').value,
        connection_mode: connectionMode,
        detection_line: document.getElementById('editDetectionLine').value,
        min_area: document.getElementById('editMinArea').value,
        detection_angle: document.getElementById('editDetectionAngle').value
    };
    
    if (connectionMode === 'direct') {
        // ใช้ URL โดยตรง
        formData.source = document.getElementById('editCameraSource').value;
    } else {
        // ใช้พารามิเตอร์
        formData.host = document.getElementById('editCameraHost').value;
        formData.port = document.getElementById('editCameraPort').value;
        formData.username = document.getElementById('editCameraUsername').value;
        formData.password = document.getElementById('editCameraPassword').value || null;  // ส่ง null ถ้าไม่ได้กรอก
        formData.channel = document.getElementById('editCameraChannel').value;
        formData.path = document.getElementById('editCameraPath').value;
    }
    
    // เรียก API แก้ไขกล้อง
    callApi(`/api/camera/edit/${cameraId}`, 'POST', formData)
        .then(response => {
            if (response.success) {
                const editCameraModal = bootstrap.Modal.getInstance(document.getElementById('editCameraModal'));
                editCameraModal.hide();
                showAlert(response.message, 'success');
                // รีเฟรชหน้า
                setTimeout(() => {
                    window.location.reload();
                }, 1000);
            } else {
                showAlert(`ไม่สามารถแก้ไขกล้องได้: ${response.message}`, 'danger');
            }
        })
        .catch(error => {
            console.error('Error updating camera:', error);
            showAlert('เกิดข้อผิดพลาดในการแก้ไขกล้อง', 'danger');
        });
}

/**
 * แสดง Modal ยืนยันการลบกล้อง
 * @param {number} cameraId - รหัสกล้อง
 * @param {string} cameraName - ชื่อกล้อง
 */
function showDeleteConfirmation(cameraId, cameraName) {
    document.getElementById('deleteCameraId').value = cameraId;
    document.getElementById('deleteModalCameraName').textContent = cameraName;
    const deleteCameraModal = new bootstrap.Modal(document.getElementById('deleteCameraModal'));
    deleteCameraModal.show();
}

/**
 * ลบกล้อง
 */
function deleteCamera() {
    toggleSpinner(true);
    
    const cameraId = document.getElementById('deleteCameraId').value;
    
    // เรียก API ลบกล้อง
    callApi(`/api/camera/delete/${cameraId}`, 'POST')
        .then(response => {
            if (response.success) {
                const deleteCameraModal = bootstrap.Modal.getInstance(document.getElementById('deleteCameraModal'));
                deleteCameraModal.hide();
                showAlert(response.message, 'success');
                // รีเฟรชหน้า
                setTimeout(() => {
                    window.location.reload();
                }, 1000);
            } else {
                showAlert(`ไม่สามารถลบกล้องได้: ${response.message}`, 'danger');
            }
        })
        .catch(error => {
            console.error('Error deleting camera:', error);
            showAlert('เกิดข้อผิดพลาดในการลบกล้อง', 'danger');
        });
}

// =============================================
// ฟังก์ชันสำหรับหน้าสถิติและรายงาน (Stats)
// =============================================

/**
 * โหลดข้อมูลสถิติ
 * @param {number} days - จำนวนวันย้อนหลัง
 * @param {string} startDate - วันที่เริ่มต้น (YYYY-MM-DD)
 * @param {string} endDate - วันที่สิ้นสุด (YYYY-MM-DD)
 */
function loadStats(days = 7, startDate = null, endDate = null) {
    toggleSpinner(true);
    
    let url = '/api/stats/data';
    let params = {};
    
    if (startDate && endDate) {
        params.start_date = startDate;
        params.end_date = endDate;
    } else {
        params.days = days;
    }
    
    // สร้าง query string
    url = buildUrl(url, params);
    
    callApi(url, 'GET')
        .then(response => {
            if (response.success) {
                statsData = response.data;
                updateStatsView();
                updateChartsAndTable();
            } else {
                showAlert(`ไม่สามารถโหลดข้อมูลสถิติได้: ${response.message}`, 'danger');
            }
        })
        .catch(error => {
            console.error('Error loading stats:', error);
            showAlert('เกิดข้อผิดพลาดในการโหลดข้อมูลสถิติ', 'danger');
        })
        .finally(() => {
            toggleSpinner(false);
        });
}

/**
 * อัพเดตการแสดงสถิติ
 */
function updateStatsView() {
    // ถ้าไม่มีข้อมูล
    if (!statsData || statsData.length === 0) {
        document.getElementById('totalVisitors').textContent = '0';
        document.getElementById('avgVisitors').textContent = '0';
        document.getElementById('peakVisitors').textContent = '0';
        return;
    }
    
    // คำนวณข้อมูลสรุป
    let totalEntries = 0;
    let peakCount = 0;
    
    statsData.forEach(function(stat) {
        totalEntries += stat.total_entries;
        if (stat.peak_count > peakCount) {
            peakCount = stat.peak_count;
        }
    });
    
    const avgEntries = Math.round(totalEntries / statsData.length);
    
    // แสดงผล
    document.getElementById('totalVisitors').textContent = totalEntries;
    document.getElementById('avgVisitors').textContent = avgEntries;
    document.getElementById('peakVisitors').textContent = peakCount;
}

/**
 * อัพเดตกราฟและตาราง
 */
function updateChartsAndTable() {
    updateTrendChart();
    updateDistributionChart();
    updatePeakTimeChart();
    updateStatsTable();
}

/**
 * อัพเดตกราฟแนวโน้ม
 */
function updateTrendChart() {
    // ถ้าไม่มีข้อมูล
    if (!statsData || statsData.length === 0) {
        return;
    }
    
    // เรียงข้อมูลตามวันที่
    const sortedData = [...statsData].sort((a, b) => new Date(a.date) - new Date(b.date));
    
    // เตรียมข้อมูลกราฟ
    const labels = sortedData.map(stat => stat.date);
    const entriesData = sortedData.map(stat => stat.total_entries);
    const exitsData = sortedData.map(stat => stat.total_exits);
    
    // ถ้ามีกราฟอยู่แล้ว ให้ทำลายก่อน
    if (visitorTrendChart) {
        visitorTrendChart.destroy();
    }
    
    // สร้างกราฟใหม่
    const ctx = document.getElementById('visitorTrendChart').getContext('2d');
    visitorTrendChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'ลูกค้าเข้าร้าน',
                    data: entriesData,
                    borderColor: '#2ed8b6',
                    backgroundColor: 'rgba(46, 216, 182, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3
                },
                {
                    label: 'ลูกค้าออกจากร้าน',
                    data: exitsData,
                    borderColor: '#ff5370',
                    backgroundColor: 'rgba(255, 83, 112, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                title: {
                    display: true,
                    text: 'แนวโน้มจำนวนลูกค้า'
                },
                tooltip: {
                    enabled: true
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        precision: 0
                    }
                }
            }
        }
    });
}

/**
 * อัพเดตกราฟการกระจายตัว
 */
function updateDistributionChart() {
    // ถ้าไม่มีข้อมูล
    if (!statsData || statsData.length === 0) {
        return;
    }
    
    // สมมติว่าเรามีข้อมูลการกระจายตามช่วงเวลา
    // ในกรณีจริง คุณอาจต้องดึงข้อมูลนี้จาก API
    const timeSlots = ['9:00-11:00', '11:00-13:00', '13:00-15:00', '15:00-17:00', '17:00-19:00', '19:00-21:00'];
    const distributionData = [15, 25, 20, 18, 30, 12]; // สมมติข้อมูล
    
    // ถ้ามีกราฟอยู่แล้ว ให้ทำลายก่อน
    if (visitorDistributionChart) {
        visitorDistributionChart.destroy();
    }
    
    // สร้างกราฟใหม่
    const ctx = document.getElementById('visitorDistributionChart').getContext('2d');
    visitorDistributionChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: timeSlots,
            datasets: [{
                data: distributionData,
                backgroundColor: [
                    '#4099ff',
                    '#2ed8b6',
                    '#ffb64d',
                    '#ff5370',
                    '#7759de',
                    '#FF9800'
                ],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: 'การกระจายตัวของลูกค้าตามช่วงเวลา'
                },
                legend: {
                    position: 'right',
                }
            }
        }
    });
}

/**
 * อัพเดตกราฟช่วงเวลาที่มีลูกค้ามากที่สุด
 */
function updatePeakTimeChart() {
    // ถ้าไม่มีข้อมูล
    if (!statsData || statsData.length === 0) {
        return;
    }
    
    // สมมติว่าเรามีข้อมูลช่วงเวลาที่มีลูกค้ามากที่สุด
    // ในกรณีจริง คุณอาจต้องดึงข้อมูลนี้จาก API
    const hours = ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00', '18:00', '19:00', '20:00'];
    const peakData = [5, 8, 12, 15, 10, 8, 12, 16, 20, 18, 15, 8]; // สมมติข้อมูล
    
    // ถ้ามีกราฟอยู่แล้ว ให้ทำลายก่อน
    if (peakTimeChart) {
        peakTimeChart.destroy();
    }
    
    // สร้างกราฟใหม่
    const ctx = document.getElementById('peakTimeChart').getContext('2d');
    peakTimeChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: hours,
            datasets: [{
                label: 'จำนวนลูกค้า',
                data: peakData,
                backgroundColor: 'rgba(255, 182, 77, 0.7)',
                borderColor: '#ffb64d',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: 'จำนวนลูกค้าตามช่วงเวลา'
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        precision: 0
                    }
                }
            }
        }
    });
}

/**
 * อัพเดตตารางสถิติ
 */
function updateStatsTable() {
    // ถ้าไม่มีข้อมูล
    if (!statsData || statsData.length === 0) {
        document.getElementById('statsTableBody').innerHTML = '<tr><td colspan="5" class="text-center">ไม่พบข้อมูล</td></tr>';
        return;
    }
    
    // เรียงข้อมูลตามวันที่ (ล่าสุดอยู่บน)
    const sortedData = [...statsData].sort((a, b) => new Date(b.date) - new Date(a.date));
    
    // สร้าง HTML สำหรับตาราง
    let tableHtml = '';
    sortedData.forEach(function(stat) {
        tableHtml += `
            <tr>
                <td>${stat.date}</td>
                <td>${stat.total_entries}</td>
                <td>${stat.total_exits}</td>
                <td>${stat.peak_time || '-'}</td>
                <td>${stat.peak_count}</td>
            </tr>
        `;
    });
    
    // อัพเดตตาราง
    document.getElementById('statsTableBody').innerHTML = tableHtml;
}

/**
 * ส่งออกรายงานเป็น CSV
 * @param {string} startDate - วันที่เริ่มต้น (YYYY-MM-DD)
 * @param {string} endDate - วันที่สิ้นสุด (YYYY-MM-DD)
 */
function exportReport(startDate, endDate) {
    toggleSpinner(true);
    
    callApi('/api/stats/export', 'POST', {
        start_date: startDate,
        end_date: endDate
    })
        .then(response => {
            if (response.success) {
                // ดาวน์โหลดไฟล์
                window.location.href = `/api/download/${response.filename}`;
                const exportModal = bootstrap.Modal.getInstance(document.getElementById('exportModal'));
                exportModal.hide();
                showAlert('ส่งออกรายงานสำเร็จ', 'success');
            } else {
                showAlert(`ไม่สามารถส่งออกรายงานได้: ${response.message}`, 'danger');
            }
        })
        .catch(error => {
            console.error('Error exporting report:', error);
            showAlert('เกิดข้อผิดพลาดในการส่งออกรายงาน', 'danger');
        });
}

// =============================================
// ฟังก์ชันสำหรับหน้าตั้งค่า (Settings)
// =============================================

/**
 * บันทึกการตั้งค่า
 */
function saveSettings() {
    toggleSpinner(true);
    
    // รวบรวมข้อมูลจากฟอร์ม
    const formData = {
        branch_name: document.getElementById('branchName').value,
        branch_location: document.getElementById('branchLocation').value,
        camera_width: document.getElementById('cameraWidth').value,
        camera_height: document.getElementById('cameraHeight').value,
        camera_fps: document.getElementById('cameraFps').value,
        detection_angle: document.getElementById('detectionAngle').value,
        min_area: document.getElementById('minArea').value,
        threshold: document.getElementById('threshold').value,
        blur_size: document.getElementById('blurSize').value,
        direction_threshold: document.getElementById('directionThreshold').value,
        server_url: document.getElementById('serverUrl').value,
        api_key: document.getElementById('apiKey').value,
        sync_interval: document.getElementById('syncInterval').value
    };
    
    // เรียก API บันทึกการตั้งค่า
    callApi('/api/settings/save', 'POST', formData)
        .then(response => {
            if (response.success) {
                showAlert(response.message, 'success');
            } else {
                showAlert(`ไม่สามารถบันทึกการตั้งค่าได้: ${response.message}`, 'danger');
            }
        })
        .catch(error => {
            console.error('Error saving settings:', error);
            showAlert('เกิดข้อผิดพลาดในการบันทึกการตั้งค่า', 'danger');
        });
}

// =============================================
// ตรวจสอบเหตุการณ์ (Event Handlers)
// =============================================

/**
 * ติดตั้งตัวจัดการเหตุการณ์สำหรับหน้าหลัก (Dashboard)
 */
function setupDashboardEvents() {
    // อัพเดตตัวแปรหน้าปัจจุบัน
    currentPage = 'dashboard';
    
    // ตั้งค่า event listener สำหรับปุ่มควบคุม
    document.getElementById('startCameraBtn')?.addEventListener('click', startCamera);
    document.getElementById('stopCameraBtn')?.addEventListener('click', stopCamera);
    document.getElementById('resetCountersBtn')?.addEventListener('click', resetCounters);
    document.getElementById('snapshotBtn')?.addEventListener('click', takeSnapshot);
    
    // ตั้งค่า event listener สำหรับการเลือกกล้อง
    const cameraSelector = document.getElementById('cameraSelector');
    if (cameraSelector) {
        cameraSelector.addEventListener('change', function() {
            const selectedOption = this.options[this.selectedIndex];
            const cameraId = parseInt(selectedOption.value.split(':')[0]);
            selectCamera(cameraId);
        });
        
        // เลือกกล้องแรกโดยอัตโนมัติถ้ามี
        if (cameraSelector.options.length > 0) {
            const cameraId = parseInt(cameraSelector.options[0].value.split(':')[0]);
            selectedCameraId = cameraId;
        }
    }
    
    // เริ่มอัพเดตสถานะ
    statusUpdateInterval = setInterval(updateStatus, 2000);
    
    // อัพเดตสถานะครั้งแรก
    updateStatus();
}

/**
 * ติดตั้งตัวจัดการเหตุการณ์สำหรับหน้าจัดการกล้อง (Cameras)
 */
function setupCamerasEvents() {
    // อัพเดตตัวแปรหน้าปัจจุบัน
    currentPage = 'cameras';
    
    // สร้าง Modal objects
    const addCameraModal = new bootstrap.Modal(document.getElementById('addCameraModal'));
    const editCameraModal = new bootstrap.Modal(document.getElementById('editCameraModal'));
    const deleteCameraModal = new bootstrap.Modal(document.getElementById('deleteCameraModal'));
    
    // สลับการแสดงผลฟอร์มการเชื่อมต่อใน Modal เพิ่มกล้อง
    document.querySelectorAll('input[name="connectionMode"]').forEach(radio => {
        radio.addEventListener('change', function() {
            if (this.value === 'params') {
                document.getElementById('paramsForm').style.display = 'block';
                document.getElementById('directForm').style.display = 'none';
            } else {
                document.getElementById('paramsForm').style.display = 'none';
                document.getElementById('directForm').style.display = 'block';
            }
        });
    });
    
    // สลับการแสดงผลฟอร์มการเชื่อมต่อใน Modal แก้ไขกล้อง
    document.querySelectorAll('input[name="editConnectionMode"]').forEach(radio => {
        radio.addEventListener('change', function() {
            if (this.value === 'params') {
                document.getElementById('editParamsForm').style.display = 'block';
                document.getElementById('editDirectForm').style.display = 'none';
            } else {
                document.getElementById('editParamsForm').style.display = 'none';
                document.getElementById('editDirectForm').style.display = 'block';
            }
        });
    });
    
    // ปุ่มทดสอบการเชื่อมต่อ (Modal เพิ่มกล้อง)
    document.getElementById('testConnectionBtn')?.addEventListener('click', () => testCameraConnection(false));
    
    // ปุ่มทดสอบการเชื่อมต่อ (Modal แก้ไขกล้อง)
    document.getElementById('editTestConnectionBtn')?.addEventListener('click', () => testCameraConnection(true));
    
    // ปุ่มบันทึกกล้องใหม่
    document.getElementById('saveCameraBtn')?.addEventListener('click', addCamera);
    
    // ปุ่มอัพเดตกล้อง
    document.getElementById('updateCameraBtn')?.addEventListener('click', updateCamera);
    
    // ปุ่มยืนยันการลบกล้อง
    document.getElementById('confirmDeleteBtn')?.addEventListener('click', deleteCamera);
    
    // ปุ่มรีเฟรช
    document.getElementById('refreshBtn')?.addEventListener('click', function(e) {
        e.preventDefault();
        window.location.reload();
    });
    
    // ปุ่มดูรายละเอียดกล้อง
    document.querySelectorAll('.view-camera-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const cameraId = this.getAttribute('data-camera-id');
            loadCameraDetails(parseInt(cameraId));
        });
    });
    
    // ปุ่มแก้ไขกล้อง
    document.querySelectorAll('.edit-camera-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const cameraId = this.getAttribute('data-camera-id');
            loadCameraForEdit(parseInt(cameraId));
        });
    });
    
    // ปุ่มลบกล้อง
    document.querySelectorAll('.delete-camera-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const cameraId = this.getAttribute('data-camera-id');
            const cameraName = this.closest('tr').querySelector('td:nth-child(2)').textContent;
            showDeleteConfirmation(parseInt(cameraId), cameraName);
        });
    });
    
    // โหลดรายละเอียดกล้องแรกโดยอัตโนมัติถ้ามี
    const firstCameraRow = document.querySelector('#camerasTableBody tr:first-child');
    if (firstCameraRow) {
        const firstCameraId = firstCameraRow.getAttribute('data-camera-id');
        if (firstCameraId) {
            loadCameraDetails(parseInt(firstCameraId));
        }
    }
}

/**
 * ติดตั้งตัวจัดการเหตุการณ์สำหรับหน้าสถิติและรายงาน (Stats)
 */
function setupStatsEvents() {
    // อัพเดตตัวแปรหน้าปัจจุบัน
    currentPage = 'stats';
    
    // สร้าง Modal objects
    const exportModal = new bootstrap.Modal(document.getElementById('exportModal'));
    
    // ตั้งค่าวันที่เริ่มต้นและสิ้นสุดเป็นวันนี้
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('exportStartDate').value = today;
    document.getElementById('exportEndDate').value = today;
    document.getElementById('startDate').value = today;
    document.getElementById('endDate').value = today;
    
    // เปลี่ยนช่วงเวลา
    document.getElementById('filterPeriod')?.addEventListener('change', function() {
        const period = this.value;
        
        if (period === 'custom') {
            // แสดงตัวเลือกวันที่แบบกำหนดเอง
            document.getElementById('customDateStart').style.display = 'block';
            document.getElementById('customDateEnd').style.display = 'block';
        } else {
            // ซ่อนตัวเลือกวันที่แบบกำหนดเอง
            document.getElementById('customDateStart').style.display = 'none';
            document.getElementById('customDateEnd').style.display = 'none';
            
            // โหลดข้อมูลตามจำนวนวัน
            loadStats(parseInt(period));
        }
    });
    
    // กรองข้อมูล
    document.getElementById('applyFilter')?.addEventListener('click', function() {
        const period = document.getElementById('filterPeriod').value;
        
        if (period === 'custom') {
            // กรองตามวันที่ที่กำหนด
            const startDate = document.getElementById('startDate').value;
            const endDate = document.getElementById('endDate').value;
            
            if (!startDate || !endDate) {
                showAlert('กรุณาระบุวันที่เริ่มต้นและสิ้นสุด', 'warning');
                return;
            }
            
            // ตรวจสอบวันที่
            if (new Date(startDate) > new Date(endDate)) {
                showAlert('วันที่เริ่มต้นต้องมาก่อนวันที่สิ้นสุด', 'warning');
                return;
            }
            
            loadStats(null, startDate, endDate);
        } else {
            // กรองตามจำนวนวัน
            loadStats(parseInt(period));
        }
    });
    
    // ปุ่มแสดงข้อมูลรายวัน
    document.getElementById('viewDaily')?.addEventListener('click', function() {
        this.classList.remove('btn-outline-light');
        this.classList.add('btn-light');
        document.getElementById('viewHourly').classList.remove('btn-light');
        document.getElementById('viewHourly').classList.add('btn-outline-light');
        viewMode = 'daily';
        updateChartsAndTable();
    });
    
    // ปุ่มแสดงข้อมูลรายชั่วโมง
    document.getElementById('viewHourly')?.addEventListener('click', function() {
        this.classList.remove('btn-outline-light');
        this.classList.add('btn-light');
        document.getElementById('viewDaily').classList.remove('btn-light');
        document.getElementById('viewDaily').classList.add('btn-outline-light');
        viewMode = 'hourly';
        updateChartsAndTable();
    });
    
    // ปุ่มส่งออก CSV
    document.getElementById('exportCSV')?.addEventListener('click', function() {
        // รีเซ็ตฟอร์มและแสดง Modal
        document.getElementById('exportStartDate').value = today;
        document.getElementById('exportEndDate').value = today;
        exportModal.show();
    });
    
    // ปุ่มยืนยันการส่งออก
    document.getElementById('confirmExport')?.addEventListener('click', function() {
        const startDate = document.getElementById('exportStartDate').value;
        const endDate = document.getElementById('exportEndDate').value;
        
        if (!startDate || !endDate) {
            showAlert('กรุณาระบุวันที่เริ่มต้นและสิ้นสุด', 'warning');
            return;
        }
        
        // ตรวจสอบวันที่
        if (new Date(startDate) > new Date(endDate)) {
            showAlert('วันที่เริ่มต้นต้องมาก่อนวันที่สิ้นสุด', 'warning');
            return;
        }
        
        exportReport(startDate, endDate);
    });
    
    // โหลดข้อมูลสถิติเริ่มต้น (7 วันล่าสุด)
    loadStats(7);
}

/**
 * ติดตั้งตัวจัดการเหตุการณ์สำหรับหน้าตั้งค่า (Settings)
 */
function setupSettingsEvents() {
    // อัพเดตตัวแปรหน้าปัจจุบัน
    currentPage = 'settings';
    
    // ปุ่มบันทึกการตั้งค่า
    document.getElementById('saveSettingsBtn')?.addEventListener('click', saveSettings);
}

/**
 * ติดตั้งตัวจัดการเหตุการณ์ทั่วไป
 */
function setupCommonEvents() {
   // อัพเดตเวลาทุกวินาที
   updateTime();
   setInterval(updateTime, 1000);
   
   // อัพเดตสถานะการซิงค์ทุก 5 วินาที
   syncStatusInterval = setInterval(() => {
       callApi('/api/status', 'GET')
           .then(data => {
               if (data.sync) {
                   updateSyncStatus(data.sync);
               }
           })
           .catch(error => {
               console.error('Error updating sync status:', error);
           });
   }, 5000);
   
   // ติดตั้งตัวจัดการสำหรับการเปลี่ยนธีม
   document.getElementById('toggleThemeBtn')?.addEventListener('click', toggleTheme);
   
   // ติดตั้งการตรวจสอบเมื่อกดปุ่ม ESC เพื่อปิด Modal
   document.addEventListener('keydown', function(event) {
       if (event.key === 'Escape') {
           const modals = document.querySelectorAll('.modal.show');
           if (modals.length > 0) {
               const modalInstance = bootstrap.Modal.getInstance(modals[0]);
               if (modalInstance) {
                   modalInstance.hide();
               }
           }
       }
   });
}

/**
* สลับธีมระหว่าง light และ dark
*/
function toggleTheme() {
   if (currentTheme === 'light') {
       // เปลี่ยนเป็น dark theme
       document.body.classList.add('dark-theme');
       document.getElementById('toggleThemeBtn').innerHTML = '<i class="fas fa-sun"></i>';
       currentTheme = 'dark';
       localStorage.setItem('theme', 'dark');
   } else {
       // เปลี่ยนเป็น light theme
       document.body.classList.remove('dark-theme');
       document.getElementById('toggleThemeBtn').innerHTML = '<i class="fas fa-moon"></i>';
       currentTheme = 'light';
       localStorage.setItem('theme', 'light');
   }
}

/**
* โหลดธีมจาก localStorage
*/
function loadTheme() {
   const savedTheme = localStorage.getItem('theme');
   if (savedTheme) {
       currentTheme = savedTheme;
       if (savedTheme === 'dark') {
           document.body.classList.add('dark-theme');
           const themeToggleBtn = document.getElementById('toggleThemeBtn');
           if (themeToggleBtn) {
               themeToggleBtn.innerHTML = '<i class="fas fa-sun"></i>';
           }
       }
   }
}

// =============================================
// เริ่มการทำงานของสคริปต์
// =============================================