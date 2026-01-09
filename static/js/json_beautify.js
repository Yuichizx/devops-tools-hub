/* static/js/json_beautify.js */

document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Elements ---
    const $ = s => document.querySelector(s);
    const input = $('#input'),
          output = $('#output'),
          indentEl = $('#indent'),
          sortKeysEl = $('#sortKeys'),
          endlineEl = $('#endline'),
          statusEl = $('#status'),
          inSize = $('#inSize'),
          outSize = $('#outSize'),
          inLn = $('#inLn'),
          outLn = $('#outLn'),
          inLnPane = $('#inLnPane'),
          outLnPane = $('#outLnPane');

    // --- Helpers ---
    const units = ['B','KB','MB','GB'];
    const bytes = n => {
        if (!n) return '0 B';
        const idx = Math.floor(Math.log(n) / Math.log(1024));
        const size = (n / Math.pow(1024, idx)).toFixed(1);
        return size + ' ' + units[idx];
    };
    
    const updateSizes = () => { 
        inSize.textContent = bytes(new Blob([input.value || '']).size); 
        outSize.textContent = bytes(new Blob([output.textContent || '']).size); 
    }
    
    const setStatus = (m, t) => { 
        statusEl.className = 'status' + (t ? ' ' + t : ''); 
        statusEl.textContent = m; 
    }

    const ensureEndline = t => {
        if (!endlineEl.checked) {
            return t;
        }
        return t.endsWith('\n') ? t : t + '\n';
    };

    // --- Logic Inti ---
    const stripLineComment = line => {
      for (let i = 0; i < line.length - 1; i++) {
        if (line[i] === '/' && line[i + 1] === '/') {
          const prev = i > 0 ? line[i - 1] : '';
          if (i === 0 || prev !== ':') {
            return line.slice(0, i);
          }
        }
      }
      return line;
    };

    const parseJSON = r => {
      try {
        const cleaned = r
          .replace(/,\s*([}\]])/g, '$1') // hapus trailing comma
          .split(/\r?\n/)
          .map(stripLineComment)
          .join('\n');
        return { ok: true, data: JSON.parse(cleaned) };
      } catch (e) {
        return { ok: false, error: e.message };
      }
    };

    const sortKeysRec = o => {
      if (Array.isArray(o)) {
        return o.map(sortKeysRec);
      }
      if (o && typeof o === 'object') {
        return Object.keys(o).sort().reduce((acc, key) => {
          acc[key] = sortKeysRec(o[key]);
          return acc;
        }, {});
      }
      return o;
    };

    const renderOutput = t => {
      output.textContent = t;
      toggleLn(outLnPane, t.length > 0);
      updateLn(outLn, t);
      updateSizes();
    };

    const beautify = () => {
      const raw = input.value.trim();
      if (!raw) return setStatus('Masukkan JSON terlebih dulu.','warn');
      const p = parseJSON(raw);
      if (!p.ok) return setStatus('JSON tidak valid: ' + p.error, 'err');
      const indent = Math.min(Math.max(+indentEl.value || 2, 0), 12);
      const d = sortKeysEl.checked ? sortKeysRec(p.data) : p.data;
      renderOutput(ensureEndline(JSON.stringify(d, null, indent)));
      setStatus('Berhasil diformat.','ok');
    };

    const minify = () => {
      const raw = input.value.trim();
      if (!raw) return setStatus('Masukkan JSON terlebih dulu.','warn');
      const p = parseJSON(raw);
      if (!p.ok) return setStatus('JSON tidak valid: ' + p.error, 'err');
      renderOutput(ensureEndline(JSON.stringify(sortKeysEl.checked ? sortKeysRec(p.data) : p.data)));
      setStatus('Berhasil diminify.','ok');
    };

    const validate = () => {
      const raw = input.value.trim();
      if (!raw) return setStatus('Masukkan JSON terlebih dulu.','warn');
      const p = parseJSON(raw);
      setStatus(p.ok ? 'JSON valid. ✔' : 'JSON tidak valid: ' + p.error, p.ok ? 'ok' : 'err');
    };

    // --- Line Numbers & Scroll ---
    const updateLn = (el, t) => {
      const lines = (t || '').split('\n').length;
      el.textContent = Array.from({ length: lines }, (_, i) => i + 1).join('\n');
    };

    const toggleLn = (p, show) => p.classList.toggle('hidden', !show);

    const bindSyncScroll = (s, l) => {
      let lock = false;
      s.addEventListener('scroll', () => {
        if (lock) {
          return;
        }
        lock = true;
        l.scrollTop = s.scrollTop;
        lock = false;
      });
      l.addEventListener('scroll', () => {
        if (lock) {
          return;
        }
        lock = true;
        s.scrollTop = l.scrollTop;
        lock = false;
      });
    };
    bindSyncScroll(input, inLnPane);
    bindSyncScroll(output, outLnPane); // Untuk output (pre), scroll mungkin perlu penanganan div pembungkus

    // Karena elemen <pre> kadang sulit discroll jika overflow, pastikan parent div (.codewrap) yang discroll
    // Atau textarea di input. Di sini kita biarkan default dulu.

    input.addEventListener('input', () => {
      const v = input.value;
      toggleLn(inLnPane, v.length > 0);
      updateLn(inLn, v);
      updateSizes();
    });

    // --- Event Listeners Buttons ---
    document.getElementById('btnBeautify').onclick = beautify;
    document.getElementById('btnMinify').onclick = minify;
    document.getElementById('btnValidate').onclick = validate;

    document.getElementById('btnCopy').onclick = async () => {
      if (!output.textContent) return setStatus('Tidak ada output untuk disalin.','warn');
      try { await navigator.clipboard.writeText(output.textContent); setStatus('Output disalin.','ok'); }
      catch { setStatus('Gagal menyalin.','err'); }
    };

    document.getElementById('btnDownload').onclick = () => {
      const t = output.textContent || input.value || '';
      if (!t) return setStatus('Tidak ada konten untuk diunduh.','warn');
      const blob = new Blob([t], { type:'application/json' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'data.json';
      a.click();
      URL.revokeObjectURL(a.href);
      setStatus('Berhasil diunduh.','ok');
    };

    document.getElementById('btnClear').onclick = () => {
      output.textContent = '';
      toggleLn(outLnPane, false);
      outLn.textContent = '';
      setStatus('Output dibersihkan.','warn');
      updateSizes();
    };

    // --- Drag & Drop ---
    const inEditor = document.getElementById('inEditor');
    ['dragenter','dragover'].forEach(e =>
      inEditor.addEventListener(e, ev => { ev.preventDefault(); ev.dataTransfer.dropEffect = 'copy'; })
    );
    inEditor.addEventListener('drop', e => {
      e.preventDefault();
      const dt = e.dataTransfer;
      const f = dt && dt.files && dt.files[0];
      if (!f) return;
      if (!(/\.json$|application\/json/.test(f.name + f.type)))
        return setStatus('Hanya file .json yang didukung.','warn');
      const r = new FileReader();
      r.onload = () => { input.value = r.result || ''; input.dispatchEvent(new Event('input')); setStatus('File dimuat. Klik Beautify/Minify.','ok'); };
      r.onerror = () => setStatus('Gagal membaca file.','err');
      r.readAsText(f);
    });

    // --- Shortcut ---
    document.addEventListener('keydown', e => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); beautify(); }
    });

    // --- Init ---
    input.value = '';
    toggleLn(inLnPane, false);
    toggleLn(outLnPane, false);
    updateSizes();
});
