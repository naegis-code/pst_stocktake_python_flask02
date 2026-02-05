// ===== GLOBAL VARIABLES =====
const currentUsername = window.APP_CONFIG?.username || 'Guest';

// ===== TIME UPDATE =====
function updateTime() {
  const now = new Date();
  const options = { 
    year: 'numeric', 
    month: '2-digit', 
    day: '2-digit',
    hour: '2-digit', 
    minute: '2-digit', 
    second: '2-digit',
    hour12: false 
  };
  const timeElement = document.getElementById('current-time');
  if (timeElement) {
    timeElement.textContent = now.toLocaleString('th-TH', options);
  }
}

// ===== INITIALIZE =====
document.addEventListener('DOMContentLoaded', function() {
  console.log('Application initialized');
  
  // Start time update
  updateTime();
  setInterval(updateTime, 1000);
  
  // Initialize logout button
  initLogoutButton();
  
  // Initialize menu buttons
  initMenuButtons();
});

// ===== MENU HANDLERS =====
function initMenuButtons() {
  document.querySelectorAll('.menu-btn').forEach(function(btn) {
    btn.addEventListener('click', function(e) {
      e.preventDefault();
      
      // Remove active class from all buttons
      document.querySelectorAll('.menu-btn').forEach(b => b.classList.remove('active'));
      
      // Add active class to clicked button
      this.classList.add('active');
      
      const section = this.getAttribute('data-section');
      loadSection(section);
    });
  });
}

function loadSection(section) {
  const contentArea = document.getElementById('content-area');
  
  if (!contentArea) {
    console.error('Content area not found');
    return;
  }
  
  switch(section) {
    case 'upload_countfiles':
      upload_countfiles(contentArea);
      break;
    case 'b2s':
      loadB2SSection(contentArea);
      break;
    case 'ofm': 
      contentArea.innerHTML = '<h1>OFM - Office Mate</h1><p>Content for OFM section</p>';
      break;
    case 'ssp': 
      contentArea.innerHTML = '<h1>SSP - Super Sport</h1><p>Content for SSP section</p>';
      break;
    case 'cfr':
      contentArea.innerHTML = '<h1>CFR - Central Food Retail</h1><p>Content for CFR section</p>';
      break;
    case 'pwb':
      contentArea.innerHTML = '<h1>PWB - Power Buy</h1><p>Content for PWB section</p>';
      break;
    default:
      contentArea.innerHTML = '<h1>Section not found</h1><p>Please select a valid section.</p>';
      break;
    case 'upload_files_final':
      upload_files_final(contentArea);
      break;
  }
}

// ===== UTILITY FUNCTIONS =====
function showError(message) {
  Swal.fire({
    icon: 'error',
    title: 'ข้อผิดพลาด',
    text: message,
    confirmButtonColor: '#dc3545'
  });
}

function showSuccess(message, html = null) {
  Swal.fire({
    icon: 'success',
    title: 'สำเร็จ',
    text: html ? undefined : message,
    html: html || undefined,
    confirmButtonColor: '#27ae60'
  });
}

function showLoading(title = 'กำลังประมวลผล...') {
  Swal.fire({
    title: title,
    allowOutsideClick: false,
    allowEscapeKey: false,
    didOpen: () => {
      Swal.showLoading();
    }
  });
}

function showConfirm(title, text, confirmButtonText = 'ยืนยัน', cancelButtonText = 'ยกเลิก') {
  return Swal.fire({
    title: title,
    text: text,
    icon: 'question',
    showCancelButton: true,
    confirmButtonColor: '#3498db',
    cancelButtonColor: '#6c757d',
    confirmButtonText: confirmButtonText,
    cancelButtonText: cancelButtonText
  });
}

// ===== API HELPERS =====
async function fetchAPI(url, options = {}) {
  try {
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers
      },
      ...options
    });
    
    const data = await response.json();
    
    if (!response.ok) {
      throw new Error(data.error || `HTTP error! status: ${response.status}`);
    }
    
    return data;
  } catch (error) {
    console.error('API Error:', error);
    throw error;
  }
}