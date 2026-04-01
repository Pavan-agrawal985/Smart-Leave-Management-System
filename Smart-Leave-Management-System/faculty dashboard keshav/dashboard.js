/* ===== SLMS Faculty Dashboard — dashboard.js ===== */

// Live date in topbar
(function() {
  const el = document.getElementById('dateDisp');
  if (el) {
    el.textContent = new Date().toLocaleDateString('en-IN', {
      weekday: 'short', day: '2-digit', month: 'short', year: 'numeric'
    });
  }
})();

// Auto-hide flash messages after 4 seconds
setTimeout(() => {
  document.querySelectorAll('.flash-success,.flash-error').forEach(el => {
    el.style.transition = 'opacity .4s';
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 400);
  });
}, 4000);

// Global search — filter table rows
const gs = document.getElementById('globalSearch');
if (gs) {
  gs.addEventListener('input', function() {
    const v = this.value.toLowerCase();
    document.querySelectorAll('.tbl tbody tr').forEach(row => {
      row.style.display = row.textContent.toLowerCase().includes(v) ? '' : 'none';
    });
  });
}

// Toast helper
function showToast(msg, warn = false) {
  let t = document.getElementById('toast');
  if (!t) return;
  t.textContent = msg;
  t.style.background = warn ? '#d97706' : '#1e293b';
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 3500);
}

// Modal helpers (overridden per page if needed)
function openModal() {}
function closeModal() {
  const m = document.getElementById('reviewModal');
  if (m) m.style.display = 'none';
}