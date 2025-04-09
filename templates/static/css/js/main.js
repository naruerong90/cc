// JavaScript หลักสำหรับระบบนับลูกค้าผ่านกล้องวงจรปิด

// อัพเดตเวลาปัจจุบัน
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
    document.getElementById('currentTime').textContent = now.toLocaleString('th-TH', options);
}

// แสดงข้อความแจ้งเตือน
function showAlert(message, type = 'info') {
    const alertContainer = document.getElementById('alertContainer');
    
    if (!alertContainer) {
        console.error('ไม่พบ alert container');
        return;
    }
    
    const alertHTML = `
        <div class="alert alert-${type} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    `;
    
    alertContainer.innerHTML = alertHTML;
    
    // ซ่อนแจ้งเตือนหลังจาก 5 วินาที
    setTimeout(() => {
        const alert = document.querySelector('.alert');
        if (alert) {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }
    }, 5000);
}

// แสดง loading spinner
function showLoading() {
    const loadingSpinner = document.getElementById('loadingSpinner');
    if (loadingSpinner) {
        loadingSpinner.style.display = 'block';
    }
}

// ซ่อน loading spinner
function hideLoading() {
    const loadingSpinner = document.getElementById('loadingSpinner');
    if (loadingSpinner) {
        loadingSpinner.style.display = 'none';
    }
}

// ฟังก์ชั่นสำหรับการเรียก API
async function callApi(url, method = 'GET', data = null) {
    showLoading();
    
    try {
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json'
            }
        };
        
        if (data) {
            options.body = JSON.stringify(data);
        }
        
        const response = await fetch(url, options);
        const result = await response.json();
        
        hideLoading();
        return result;
    } catch (error) {
        hideLoading();
        console.error('API error:', error);
        showAlert('เกิดข้อผิดพลาดในการเรียก API: ' + error.message, 'danger');
        throw error;
    }
}

// จัดการฟอร์ม
function handleFormSubmit(formId, submitUrl, successCallback = null, errorCallback = null) {
    const form = document.getElementById(formId);
    
    if (!form) {
        console.error(`ไม่พบฟอร์ม: ${formId}`);
        return;
    }
    
    form.addEventListener('submit', async function(event) {
        event.preventDefault();
        
        showLoading();
        
        // รวบรวมข้อมูลจากฟอร์ม
        const formData = new FormData(form);
        const data = {};
        
        for (let [key, value] of formData.entries()) {