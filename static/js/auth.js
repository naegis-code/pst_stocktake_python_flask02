// ===== AUTHENTICATION & LOGOUT =====

function initLogoutButton() {
  const logoutButton = document.getElementById('logoutButton');
  if (logoutButton) {
    logoutButton.addEventListener('click', showLogoutModal);
  }
}

function showLogoutModal() {
  const modal = document.getElementById('logoutModal');
  if (modal) {
    modal.style.display = 'block';
  }
}

function closeLogoutModal() {
  const modal = document.getElementById('logoutModal');
  if (modal) {
    modal.style.display = 'none';
  }
}

function confirmLogout() {
  const logoutUrl = window.APP_CONFIG?.logoutUrl || '/logout';
  window.location.href = logoutUrl;
}

// Close modal when clicking outside
window.addEventListener('click', function(event) {
  const modal = document.getElementById('logoutModal');
  if (event.target === modal) {
    closeLogoutModal();
  }
});

// Close modal with ESC key
window.addEventListener('keydown', function(event) {
  if (event.key === 'Escape') {
    closeLogoutModal();
  }
});