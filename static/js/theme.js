// theme.js

// 1. Fungsi untuk menerapkan tema
function applyTheme(theme) {
  // Kita pasang di <html> (document.documentElement) bukan body
  // karena <html> sudah ada sejak awal loading, sedangkan body belum.
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('theme', theme);
  
  // Update tombol jika elemennya sudah ada (opsional jika script ditaruh di head)
  const btn = document.getElementById('btnTheme');
  if (btn) btn.textContent = theme === 'light' ? '🌞 Light' : '🌙 Dark';
}

// 2. Baca tema tersimpan atau default ke 'light'
const savedTheme = localStorage.getItem('theme') || 'light';
applyTheme(savedTheme);

// 3. Event Listener untuk tombol (Hanya jalan setelah DOM siap)
document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('btnTheme');
  if (btn) {
    // Set text awal tombol agar sesuai status saat ini
    btn.textContent = document.documentElement.getAttribute('data-theme') === 'light' ? '🌞 Light' : '🌙 Dark';
    
    btn.onclick = () => {
      const current = document.documentElement.getAttribute('data-theme');
      const next = current === 'light' ? 'dark' : 'light';
      applyTheme(next);
    };
  }
});