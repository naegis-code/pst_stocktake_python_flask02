// ===== UPLOAD Count Files SECTION =====

function upload_countfiles(contentArea) {
  contentArea.innerHTML = `
    <h1>Upload Count Files</h1>
    <button onclick="add_countfiles()">Upload Files</button>

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

// ===== FILE UPLOAD HELPER =====
async function uploadFileCsv(apiEndpoint, successMessage) {

  const input = document.createElement('input');
  input.type = 'file';
  input.accept = '.csv';
  input.multiple = true;   // ⭐ สำคัญ

  input.onchange = async (e) => {
    const files = Array.from(e.target.files);
    if (files.length === 0) return;

    showLoading(`กำลังอัปโหลด ${files.length} ไฟล์...`);

    // Upload all files in a single request
    const formData = new FormData();
    for (const file of files) {
      formData.append('file', file);
    }

    try {
      const response = await fetch(apiEndpoint, {
        method: 'POST',
        body: formData
      });

      let data = {};
      try {
        data = await response.json();
      } catch {
        Swal.close();
        throw new Error('รูปแบบข้อมูลจาก Server ไม่ถูกต้อง');
      }

      Swal.close();

      if (!response.ok) {
        throw new Error(data.error || 'เกิดข้อผิดพลาด');
      }

      // Display success message with details
      showSuccess(null, `
        <b>สรุปการอัปโหลด</b><br><br>
        ทั้งหมด: ${files.length} ไฟล์<br>
        จำนวนรายการใหม่: ${data.record_count || 0} รายการ<br>
        จำนวน DOCNUM ที่อัปโหลด: ${data.docnum_uploaded || 0}<br><br>
        ${data.docnum_not_uploaded && data.docnum_not_uploaded.length > 0 ? 
          `<div style="text-align:left;font-size:13px">
            <b>รายการ DOCNUM ที่อัปโหลดใหม่:</b><br>
            ${data.docnum_not_uploaded.slice(0, 20).join('<br>')}
            ${data.docnum_not_uploaded.length > 20 ? '<br>...' : ''}
          </div>` : ''}
      `);

    } catch (error) {
      Swal.close();
      showError('เกิดข้อผิดพลาด', error.message);
    }
  };

  input.click();
}


// ===== Upload Countfiles OPERATIONS =====
function add_countfiles() {
  uploadFileCsv(
    '/api/upload_countfiles/upload_cntfiles',
    'เพิ่ม Count Files สำเร็จ'
  );
}
