// ===== UPLOAD Count Files SECTION =====

function upload_files_final(contentArea) {
  contentArea.innerHTML = `
    <h1>Upload Files</h1>
    <p>อัปโหลดไฟล์ Excel สำหรับข้อมูลต่างๆ</p>
    <table class="form-table">
      <tr>
        <td>BU:</td>
        <td>
          <select id="bu">
            <option value="B2S">B2S</option>
            <option value="CHG">CHG</option>
          </select>
        </td>
        <td>STCODE:</td>
        <td><input type="text" id="stcode" placeholder="ระบุ STCODE"></td>
        <td>ATYPE:</td>
        <td>
          <select id="atype">
            <option value="3F">Full Count 3F</option>
            <option value="3Q">SPECIAL 3Q</option>
          </select>
        </td>
        <td>CNTDATE:</td>
        <td><input type="date" id="cntdate"></td>
        <td><button onclick="load_store_detail()">Search</button></td>
      </tr>
    </table>
    <table class="form-table">
      <tr>
        <td>Store Detail:</td>
        <td><input type="text" id="store_detail" readonly></td>
        <td>StocktakeID:</td>
        <td><input type="text" id="stocktakeid" readonly></td>
      </tr>
    </table>

    <table class="form-table">
    <h2>Upload Files First</h2>
    <thead>
      <tr>
        <th>File Type</th>
        <th>Action</th>
        <th>Status</th>
        <th>Details</th>
      </tr>
    </thead>
      <tr>
        <td>First STK1 File :</td>
        <td>
          <button onclick="uploadFileExcel('STK1', 'Credit')">STK1_Credit</button>
          <button onclick="uploadFileExcel('STK1', 'Consign')">STK1_Consign</button>
          <button onclick="uploadFileExcel('STK1', 'Paint')">STK1_Paint</button>
        </td>
        <td><input type="text" id="stk1_status" readonly></td>
        <td><input type="text" id="stk1_details" readonly></td>
      </tr>
      <tr>
        <td>First VAR1 File :</td>
        <td>
          <button onclick="uploadFileExcel('VAR1', 'Credit')">VAR1_Credit</button>
          <button onclick="uploadFileExcel('VAR1', 'Consign')">VAR1_Consign</button>
          <button onclick="uploadFileExcel('VAR1', 'Paint')">VAR1_Paint</button>
        </td>
        <td><input type="text" id="var1_status" readonly></td>
        <td><input type="text" id="var1_details" readonly></td>
      </tr>
    </table>
    <br><hr><br>
    <table class="form-table">
    <h2>Upload Files Final</h2>
    <thead>
      <tr>
        <th>File Type</th>
        <th>Action</th>
        <th>Status</th>
        <th>Details</th>
      </tr>
    </thead>
      <tr>
        <td>Final STK2 File :</td>
        <td>
          <button onclick="uploadFileExcel('STK2', 'Credit')">STK2_Credit</button>
          <button onclick="uploadFileExcel('STK2', 'Consign')">STK2_Consign</button>
          <button onclick="uploadFileExcel('STK2', 'Paint')">STK2_Paint</button>
        </td>
        <td><input type="text" id="stk2_status" readonly></td>
        <td><input type="text" id="stk2_details" readonly></td>
      </tr>
      <tr>
        <td>Final VAR2 File :</td>
        <td>
          <button onclick="uploadFileExcel('VAR2', 'Credit')">VAR2_Credit</button>
          <button onclick="uploadFileExcel('VAR2', 'Consign')">VAR2_Consign</button>
          <button onclick="uploadFileExcel('VAR2', 'Paint')">VAR2_Paint</button>
        </td>
        <td><input type="text" id="var2_status" readonly></td>
        <td><input type="text" id="var2_details" readonly></td>
      </tr>
      <tr>
        <td>SALE File :</td>
        <td><button onclick="upload_sale()">Upload SALE</button></td>
        <td><input type="text" id="sale_status" readonly></td>
        <td><input type="text" id="sale_details" readonly></td>
      </tr>
      <tr>
        <td>RECONCILE File :</td>
        <td><button onclick="upload_reconcile()">Upload RECONCILE</button></td>
        <td><input type="text" id="reconcile_status" readonly></td>
        <td><input type="text" id="reconcile_details" readonly></td>
      </tr>
      <tr>
        <td>BLOCK File :</td>
        <td><button onclick="upload_block()">Upload BLOCK</button></td>
        <td><input type="text" id="block_status" readonly></td>
        <td><input type="text" id="block_details" readonly></td>
      </tr>
    </table>
    
  `;
}


//=====Search Store Detail =====
async function load_store_detail() {
  const bu = document.getElementById('bu').value;
  const stcode = document.getElementById('stcode').value.trim();
  const cntdate = document.getElementById('cntdate').value;
  const atype = document.getElementById('atype').value.trim();

  if (!bu || !stcode || !cntdate || !atype) {
    showError('ข้อผิดพลาด', 'กรุณาระบุ ข้อมูลให้ครบถ้วน');
    return;
  }
  showLoading('กำลังโหลด');

    try {
    const data = await fetchAPI('/api/upload_files_final/store_detail', {
      method: 'POST',
      body: JSON.stringify({ bu, stcode, cntdate, atype }),
      headers: { 'Content-Type': 'application/json' }
    });
    
    Swal.close();
    
    // Update to fields
    document.getElementById('store_detail').value = data.store_detail || '';
    document.getElementById('stocktakeid').value = data.stocktakeid || '';
    
    showSuccess('ค้นหาข้อมูลสำเร็จ');
  } catch (error) {
    showError(error.message || 'ไม่พบข้อมูล ตาม Annual Plan ที่ระบุ');
  }
}


// ===== FILE UPLOAD HELPER =====
async function uploadFileExcel(rpname,skutype, successMessage = 'Upload สำเร็จ', requireStocktakeid = true) {
  let stocktakeid = null;
  const apiEndpoint = `/api/upload_files_final/upload/${rpname}/${skutype}`;
  
  if (requireStocktakeid) {
    stocktakeid = document.getElementById('stocktakeid')?.value.trim();
    if (!stocktakeid) {
      showError('กรุณากรอก ข้อมูลให้ครบถ้วน และกดปุ่ม Search ก่อนอัปโหลดไฟล์');
      return;
    }
  }
  
  const input = document.createElement('input');
  const bu = document.getElementById('bu')?.value;
  const stcode = document.getElementById('stcode')?.value;
  const atype = document.getElementById('atype')?.value;
  const cntdate = document.getElementById('cntdate')?.value;
  const rpnameValue = rpname;
  const skutypeValue = skutype;
  
  input.type = 'file';
  input.accept = '.xlsx,.xls';
  
  input.onchange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('bu', bu);
    formData.append('stcode', stcode);
    formData.append('atype', atype);
    formData.append('cntdate', cntdate);
    formData.append('stocktakeid', stocktakeid);
    formData.append('rpname', rpnameValue);
    formData.append('skutype', skutypeValue);

    
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
      
      if (data.error) {
        showError(data.error);
      } else {
        showSuccess(data.message || successMessage);
      }
    } catch (error) {
      showError(error.message || 'เกิดข้อผิดพลาดในการอัปโหลด');
    }
  };
  
  input.click();
}


// ===== Upload Files SALE, RECONCILE, BLOCK Final OPERATIONS =====
function upload_sale() {
  uploadFileExcel(
    '/api/upload_files_final/upload_sale',
    'Upload สำเร็จ'
  );
}
function upload_reconcile() {
  uploadFileExcel(
    '/api/upload_files_final/upload_reconcile',
    'Upload สำเร็จ'
  );
}
function upload_block() {
  uploadFileExcel(
    '/api/upload_files_final/upload_block',
    'Upload สำเร็จ'
  );
}