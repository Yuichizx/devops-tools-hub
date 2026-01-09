// static/js/password-generator.js

// --- Toast ---
const toast = document.getElementById('toast');
const toastMsg = document.getElementById('toast-message');
let t;

function showToast(m, type = 'success') {
    clearTimeout(t);
    toastMsg.textContent = m;
    toast.className = 'fixed bottom-5 right-5 text-white px-5 py-3 rounded-lg shadow-xl transform translate-y-0 opacity-100 '
        + (type === 'error' ? 'bg-red-600' : 'bg-slate-800');
    t = setTimeout(() => {
        toast.className = 'fixed bottom-5 right-5 text-white px-5 py-3 rounded-lg shadow-xl transform translate-y-20 opacity-0';
    }, 3000);
}

// --- DOM Elements ---
const output = document.getElementById('output');
const lengthRange = document.getElementById('length');
const lengthVal = document.getElementById('lengthVal');

// Checkboxes
const optLower = document.getElementById('optLower');
const optUpper = document.getElementById('optUpper');
const optNumber = document.getElementById('optNumber');
const optGeneral = document.getElementById('optGeneral'); // Checkbox Simbol Umum
const symbolCheckboxes = document.querySelectorAll('.sym-chk'); // Checkbox Simbol Spesifik

// Meter Elements
const meterBar = document.getElementById('meterBar');
const meterLabel = document.getElementById('meterLabel');
const entropyEl = document.getElementById('entropy');

// --- Helper Functions ---
window.toggleSymbols = (state) => {
    symbolCheckboxes.forEach(cb => cb.checked = state);
    doGenerate();
};

function syncLen(v) { lengthVal.textContent = v; }
lengthRange.addEventListener('input', (e) => { syncLen(e.target.value); doGenerate(); });

// --- Core Generator ---
const CHARS = {
    lower: 'abcdefghijklmnopqrstuvwxyz',
    upper: 'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
    number: '0123456789',
    // Simbol Umum: Tidak termasuk # $ " ^ [ ] / \ % @
    general: "!&'()*+,-.:;<=>?_`{|}~"
};

function getCryptoRandom(max) {
    const cryptoApi = window.crypto || window.msCrypto;
    if (!cryptoApi || !cryptoApi.getRandomValues) {
        return null;
    }
    const arr = new Uint32Array(1);
    cryptoApi.getRandomValues(arr);
    return arr[0] % max;
}

function generate() {
    const len = parseInt(lengthRange.value);
    let pool = '';

    if (optLower.checked) pool += CHARS.lower;
    if (optUpper.checked) pool += CHARS.upper;
    if (optNumber.checked) pool += CHARS.number;

    // Tambahkan Simbol Umum jika dicentang
    if (optGeneral.checked) pool += CHARS.general;

    // Tambahkan Simbol Spesifik yang dicentang
    symbolCheckboxes.forEach(cb => {
        if (cb.checked) pool += cb.value;
    });

    if (!pool) return '';

    let password = '';
    for (let i = 0; i < len; i++) {
        const idx = getCryptoRandom(pool.length);
        if (idx === null) {
            return null;
        }
        password += pool[idx];
    }
    return password;
}

function getStrengthConfig(entropy) {
    if (entropy > 120) return { percent: 100, color: 'bg-emerald-500', text: 'Excellent' };
    if (entropy > 80) return { percent: 75, color: 'bg-green-500', text: 'Strong' };
    if (entropy > 50) return { percent: 50, color: 'bg-yellow-500', text: 'Moderate' };
    return { percent: 25, color: 'bg-red-500', text: 'Weak' };
}

// --- Strength Meter ---
function calcStrength(pw) {
    if (!pw) {
        meterBar.style.width = '0%';
        meterBar.className = 'bg-gray-300';
        meterLabel.textContent = '-';
        entropyEl.textContent = '0';
        return;
    }

    // Calculate Pool Size used
    let poolSize = 0;
    if (optLower.checked) poolSize += 26;
    if (optUpper.checked) poolSize += 26;
    if (optNumber.checked) poolSize += 10;
    if (optGeneral.checked) poolSize += CHARS.general.length;

    let symCount = 0;
    symbolCheckboxes.forEach(cb => { if (cb.checked) symCount++; });
    poolSize += symCount;

    if (poolSize === 0) poolSize = 1;

    // Entropy Formula: Length * log2(PoolSize)
    const entropy = pw.length * Math.log2(poolSize);
    entropyEl.textContent = entropy.toFixed(0);

    // Visual Meter
    const { percent, color, text } = getStrengthConfig(entropy);

    meterBar.style.width = percent + '%';
    meterBar.className = color + ' h-full block rounded-full transition-all duration-300';
    meterLabel.textContent = text;
    meterLabel.className = `font-bold ${color.replace('bg-', 'text-')}`;
}

// --- Actions ---
function doGenerate() {
    const pw = generate();
    if (pw === null) {
        output.value = '';
        showToast('Crypto API tidak tersedia di browser ini.', 'error');
        calcStrength('');
        return;
    }
    if (!pw) {
        output.value = '';
        showToast('Pilih minimal satu opsi karakter!', 'error');
        calcStrength('');
        return;
    }
    output.value = pw;
    calcStrength(pw);
}

document.getElementById('btnGenerate').onclick = () => { doGenerate(); showToast('Password baru dibuat!'); };
document.getElementById('btnRegenerate').onclick = doGenerate;

document.getElementById('btnCopy').onclick = () => {
    if (!output.value) return;
    navigator.clipboard.writeText(output.value).then(() => showToast('Password disalin!'));
};

// Auto update on settings change
[optLower, optUpper, optNumber, optGeneral, lengthRange].forEach(el => el.addEventListener('change', doGenerate));
symbolCheckboxes.forEach(el => el.addEventListener('change', doGenerate));

// Init
doGenerate();
