// ===== B2S SECTION =====

function loadB2SSection(contentArea) {
  contentArea.innerHTML = `
    <h1>B2S - Book to Stationery</h1>


    <table class="form-table-full">
      <tr>
        <td>CNTNUM:</td>
        <td><input type="text" id="cntnum" placeholder="CNTNUM" /></td>
        <td><button onclick="searchCNTNUM()" class="searching">Search</button></td>
      </tr>
    </table>

    <div class="button-group">
      <button onclick="window.location.href='/create_cntnumber'">New Create Count Number</button>
      <button onclick="addLocation()">Add Location</button>
      <button onclick="closeLocation()" class="danger">Close Location</button>
      <button onclick="importSalePOS()" class="danger">Import File Sale POS</button>
      <button onclick="add_block_vendor()" class="danger">Import File BLOCK Vendor</button>
      <button onclick="add_block_sku()" class="danger">Import File BLOCK SKU</button>
      <button onclick="createMaster()" class="success">Create Master</button>
      <button onclick="downloadMasterDB()" class="success">Download Master.db</button>
    </div>

    <table class="form-table">
      <tr>
        <td>STCODE:</td>
        <td><input type="text" id="stcode" readonly /></td>
        <td>STNAME:</td>
        <td><input type="text" id="stname" readonly /></td>
        <td>Count DATE:</td>
        <td><input type="text" id="DATE" readonly /></td>
        <td>Count Step:</td>
        <td><input type="text" id="countStep" readonly /></td>
      </tr>
      <tr>
        <td>Status:</td>
        <td><input type="text" id="status" readonly /></td>
        <td>BLOCK (Vendor):</td>
        <td><input type="text" id="blockVendor" readonly /></td>
        <td>BLOCK (SKU):</td>
        <td><input type="text" id="blockSku" readonly /></td>
        <td>SOH Update:</td>
        <td><input type="text" id="soh_update_date" readonly /></td>
      </tr>
    </table>
    <table class="form-table">
      <tr>
        <td>Location All:</td>
        <td><input type="number" id="locationAll" readonly /></td>
        <td>Location Closed:</td>
        <td><input type="number" id="locationClosed" readonly /></td>
        <td>Location Over:</td>
        <td><input type="number" id="locationOver" readonly /></td>
        <td>Location Counted:</td>
        <td><input type="number" id="locationCounted" readonly /></td>
      </tr>
      <tr>
        <td>Location Remaining:</td>
        <td><input type="number" id="locationRemaining" readonly /></td>
        <td>Progress:</td>
        <td><input type="text" id="progress" readonly /></td>
        <td></td>
        <td><button onclick="monitorByLocation()">Monitor by Location</button></td>
        <td></td>
        <td><button onclick="monitorByType()">Monitor by Type</button></td>
      </tr>
    </table>
    
    <div class="button-group">
      <table class="form-table">
        <td>
          <button onclick="updateSOH()">Update SOH</button>
          <button onclick="ImportEditcount1()" class="danger">Import Edit Count 1</button>
          <button onclick="ImportEditcount4()" class="danger">Import Edit Count 4</button>
          <button onclick="countClose()" class="danger">Count Close</button>
          <button onclick="exportData()" class="success">Export Data</button>
        </td>

      </table>
    </div>
  `;
}

// ===== DATE DISPLAY =====
function updateDateDisplay() {
  const dateInput = document.getElementById('countDateCreate');
  const dateDisplay = document.getElementById('dateDisplayCreate');
  
  if (dateInput && dateInput.value && dateDisplay) {
    const date = new Date(dateInput.value);
    const options = { 
      weekday: 'long', 
      year: 'numeric', 
      month: 'long', 
      day: 'numeric' 
    };
    dateDisplay.textContent = date.toLocaleDateString('th-TH', options);
  }
}

// ===== SEARCH CNTNUM =====
async function searchCNTNUM() {
  const cntnum = document.getElementById('cntnum')?.value.trim();
  
  if (!cntnum) {
    showError('กรุณากรอก CNTNUM');
    return;
  }
  
  showLoading('กำลังค้นหาข้อมูล...');
  
  try {
    const data = await fetchAPI('/api/b2s/search', {
      method: 'POST',
      body: JSON.stringify({ cntnum: cntnum })
    });
    
    Swal.close();
    
    // Update form fields
    document.getElementById('stcode').value = data.stcode || '';
    document.getElementById('stname').value = data.stname || '';
    document.getElementById('DATE').value = data.cntdate || '';
    document.getElementById('countStep').value = data.count_step || '';
    document.getElementById('status').value = data.status || '';
    document.getElementById('blockVendor').value = data.blockVendor || '0';
    document.getElementById('blockSku').value = data.blockSku || '0';
    document.getElementById('soh_update_date').value = data.soh_update_date || '';
    document.getElementById('locationAll').value = data.locationAll || '0';
    document.getElementById('locationClosed').value = data.locationClosed || '0';
    document.getElementById('locationOver').value = data.locationOver || '0';
    document.getElementById('locationCounted').value = data.locationCounted || '0';
    document.getElementById('locationRemaining').value = data.locationRemaining || '0';
    document.getElementById('progress').value = data.progress || '0.00%';
    
    showSuccess('ค้นหาข้อมูลสำเร็จ');
  } catch (error) {
    showError(error.message || 'เกิดข้อผิดพลาดในการค้นหา');
  }
}

// ===== CREATE CNTNUM =====
async function createCNTNUM() {
  const bu = document.getElementById('bu')?.value.trim();
  const stcode = document.getElementById('stcodeCreate')?.value.trim();
  const atype = document.getElementById('atype')?.value.trim();
  const cntdate = document.getElementById('countDateCreate')?.value.trim();
  
  if (!bu || !stcode || !atype || !cntdate) {
    showError('กรุณากรอกข้อมูลให้ครบถ้วน');
    return;
  }
  
  showLoading('กำลังสร้าง CNTNUM...');
  
  try {
    const data = await fetchAPI('/api/b2s/create_cntnum', {
      method: 'POST',
      body: JSON.stringify({ bu, stcode, atype, cntdate })
    });
    
    Swal.close();
    
    if (data.cntnum) {
      document.getElementById('cntnum').value = data.cntnum;
    }
    
    showSuccess(data.message || 'สร้าง CNTNUM สำเร็จ');
  } catch (error) {
    showError(error.message || 'เกิดข้อผิดพลาดในการสร้าง CNTNUM');
  }
}

// ===== CREATE MASTER =====
async function createMaster() {
  const cntnum = document.getElementById('cntnum')?.value.trim();
  
  if (!cntnum) {
    showError('กรุณากรอก CNTNUM');
    return;
  }
  
  const result = await showConfirm(
    'ยืนยันการสร้าง Master',
    'คุณต้องการสร้าง Master Database หรือไม่?'
  );
  
  if (!result.isConfirmed) return;
  
  showLoading('กำลังสร้าง Master Database...');
  
  try {
    const data = await fetchAPI('/api/b2s/create_master', {
      method:  'POST',
      body:  JSON.stringify({ cntnum })
    });
    
    Swal.close();
    showSuccess(data.message || 'สร้าง Master สำเร็จ');
  } catch (error) {
    showError(error.message || 'เกิดข้อผิดพลาดในการสร้าง Master');
  }
}

// ===== DOWNLOAD MASTER DB =====
function downloadMasterDB() {
  const cntnum = document.getElementById('cntnum')?.value.trim();
  
  if (!cntnum) {
    showError('กรุณากรอก CNTNUM');
    return;
  }
  
  showLoading('กำลังดาวน์โหลด...');
  
  // Open download link
  window.location.href = `/api/b2s/download_master/${cntnum}`;
  
  // Close loading after a short delay
  setTimeout(() => {
    Swal.close();
  }, 1000);
}

// ===== FILE UPLOAD HELPER =====
async function uploadFile(apiEndpoint, successMessage, requireCntnum = false) {
  let cntnum = null;
  
  if (requireCntnum) {
    cntnum = document.getElementById('cntnum')?.value.trim();
    if (!cntnum) {
      showError('กรุณากรอก CNTNUM');
      return;
    }
  }
  
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = '.xlsx,.xls';
  
  input.onchange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    
    if (cntnum) {
      formData.append('cntnum', cntnum);
    }
    
    showLoading('กำลังอัปโหลดไฟล์...');
    
    try {
      const response = await fetch(apiEndpoint, {
        method: 'POST',
        body: formData
      });
      
      const data = await response.json();
      
      if (! response.ok) {
        throw new Error(data.error || 'เกิดข้อผิดพลาด');
      }
      
      Swal.close();
      
      if (data.total_count !== undefined) {
        showSuccess(null, `
          ${data.message}<br><br>
          <b>สรุป:</b><br>
          ทั้งหมด: ${data.total_count} รายการ<br>
          เพิ่มใหม่: ${data.new_count} รายการ<br>
          มีอยู่แล้ว: ${data.existing_count} รายการ
        `);
      } else {
        showSuccess(data.message || successMessage);
      }
    } catch (error) {
      showError(error.message || 'เกิดข้อผิดพลาดในการอัปโหลด');
    }
  };
  
  input.click();
}

// ===== B2S OPERATIONS =====
function addLocation() {
  uploadFile('/api/b2s/add_location', 'เพิ่ม Location สำเร็จ', true);
}

function closeLocation() {
  uploadFile('/api/b2s/close_location', 'ปิด Location สำเร็จ', true);
}

function add_block_vendor() {
  uploadFile('/api/b2s/add_block_vendor', 'เพิ่ม BLOCK Vendor สำเร็จ', true);
}

function add_block_sku() {
  uploadFile('/api/b2s/add_block_sku', 'เพิ่ม BLOCK SKU สำเร็จ', true);
}

function updateSOH() {
  uploadFile('/api/b2s/update_soh', 'อัปเดท SOH สำเร็จ', true);
}

function importSalePOS() {
  uploadFile('/api/b2s/import_sale_pos', 'นำเข้าไฟล์ Sale POS สำเร็จ', true);
}

function monitorByLocation() {
  showError('ฟังก์ชันนี้ยังไม่พร้อมใช้งาน ให้ใช้ใน MS ACCESS ก่อน');
}

function monitorByType() {
  showError('ฟังก์ชันนี้ยังไม่พร้อมใช้งาน ให้ใช้ใน MS ACCESS ก่อน');
}

function exportData() {
  showError('ฟังก์ชันนี้ยังไม่พร้อมใช้งาน ให้ใช้ใน MS ACCESS ก่อน');
}

function ImportEditcount1() {
  showError('ฟังก์ชันนี้ยังไม่พร้อมใช้งาน ให้ใช้ใน MS ACCESS ก่อน')
}

function ImportEditcount4() {
  showError('ฟังก์ชันนี้ยังไม่พร้อมใช้งาน ให้ใช้ใน MS ACCESS ก่อน')
}

async function countClose() {
  const cntnum = document.getElementById('cntnum')?.value.trim();
  if (!cntnum) {
    showError('กรุณากรอก CNTNUM');
    return;
  }

  const result = await showConfirm(
    'ยืนยันการปิด Count 1',
    `คุณต้องการปิด Count 1 สำหรับ CNTNUM: ${cntnum} หรือไม่?`
  );

  if (!result.isConfirmed) return;

  showLoading('กำลังปิด Count 1...');

  try {
    const data = await fetchAPI('/api/b2s/countclose01to04', {
      method: 'POST',
      body: JSON.stringify({ cntnum })
    });

    Swal.close();
    showSuccess(data.message || 'ปิด Count 1 สำเร็จ');
  } catch (error) {
    showError(error.message || 'เกิดข้อผิดพลาดในการปิด Count 1');
  }
}

