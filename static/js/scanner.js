/**
 * scanner.js
 * Handles repository scanning tasks, status polling, and UI updates.
 * Refactored to reduce cognitive complexity.
 */

(() => {
  'use strict';

  /**********************
   * CONSTANTS & CONFIG *
   **********************/
  const STORAGE_KEY = 'tasks';
  const STORAGE_VERSION = 2;
  const POLLING_INTERVAL = 5000;
  const MAX_BACKOFF = 30000;

  /**********************
   * UTILITIES          *
   **********************/
  const Utils = {
    safeParse(json) {
      try { return JSON.parse(json); } catch { return null; }
    },

    escapeHtml(str) {
      if (!str && str !== 0) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    },

    unescapeHtml(str) {
      if (!str && str !== 0) return '';
      return String(str)
        .replace(/&amp;/g, '&')
        .replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>')
        .replace(/&quot;/g, '"')
        .replace(/&#039;/g, "'");
    },

    getRepoLabel(repoUrl) {
      if (!repoUrl || typeof repoUrl !== 'string') return 'unknown/repo';
      const parts = repoUrl.split('/').filter(Boolean);
      return parts.slice(-2).join('/') || repoUrl;
    },

    minimalTask(task) {
      const { log, ...rest } = task || {};
      const logMeta = log
        ? { has_log: true, log_size: String(log).length }
        : { has_log: !!task?.has_log, log_size: task?.log_size || 0 };
      return { ...rest, ...logMeta };
    }
  };

  /**********************
   * STORAGE MANAGER    *
   **********************/
  const Storage = {
    saveTimer: null,

    load() {
      const raw = localStorage.getItem(STORAGE_KEY);
      const data = Utils.safeParse(raw);

      if (!data || typeof data !== 'object') {
        return { version: STORAGE_VERSION, items: [] };
      }

      let items = [];
      if (data.version === STORAGE_VERSION) {
        items = data.items;
      } else if (Array.isArray(data)) {
        items = data;
      }

      return {
        version: STORAGE_VERSION,
        items: Array.isArray(items) ? items : []
      };
    },

    saveNow(items) {
      try {
        const trimmed = items.slice(0, 50).map(Utils.minimalTask);
        localStorage.setItem(STORAGE_KEY, JSON.stringify({ version: STORAGE_VERSION, items: trimmed }));
      } catch (e) {
        if (e && e.name === 'QuotaExceededError') {
          this.handleQuotaExceeded(items);
        } else {
          console.warn('saveTasks error:', e);
        }
      }
    },

    handleQuotaExceeded(items) {
      try {
        const shrunk = items.slice(0, Math.max(1, Math.floor(items.length * 0.7))).map(Utils.minimalTask);
        localStorage.setItem(STORAGE_KEY, JSON.stringify({ version: STORAGE_VERSION, items: shrunk }));
      } catch {
        localStorage.setItem(STORAGE_KEY, JSON.stringify({ version: STORAGE_VERSION, items: [] }));
      }
    },

    save(items, debounceMs = 150) {
      if (this.saveTimer) clearTimeout(this.saveTimer);
      this.saveTimer = setTimeout(() => this.saveNow(items), debounceMs);
    }
  };

  /**********************
   * API SERVICE        *
   **********************/
  const Api = {
    init() {
      axios.defaults.timeout = 15000;
      axios.interceptors.request.use(this.requestInterceptor.bind(this));
      axios.interceptors.response.use(r => r, this.responseInterceptor.bind(this));
    },

    getCsrfToken() {
      return document.querySelector('input[name="csrf_token"]')?.value || null;
    },

    async refreshCsrfToken() {
      try {
        const response = await axios.get('/csrf-token', {
          headers: { 'X-Requested-With': 'XMLHttpRequest' },
        });
        const token = response.data?.csrf_token;
        const input = document.querySelector('input[name="csrf_token"]');
        if (token && input) input.value = token;
        return token;
      } catch (e) {
        console.warn('refreshCsrfToken failed:', e);
        return null;
      }
    },

    requestInterceptor(config) {
      const cfg = config;
      cfg.headers = cfg.headers || {};
      cfg.headers['X-Requested-With'] = 'XMLHttpRequest';
      const token = this.getCsrfToken();
      if (token) cfg.headers['X-CSRFToken'] = token;
      return cfg;
    },

    async responseInterceptor(error) {
      const status = error?.response?.status;
      const originalRequest = error.config || {};
      const isRetriable = status === 401 || status === 403 || status === 419;

      if (!navigator.onLine || !isRetriable || originalRequest._retry) {
        return Promise.reject(error);
      }

      originalRequest._retry = true;
      const newToken = await this.refreshCsrfToken();
      if (newToken) {
        originalRequest.headers = originalRequest.headers || {};
        originalRequest.headers['X-CSRFToken'] = newToken;
        return axios(originalRequest);
      }
      return Promise.reject(error);
    },

    async ping() {
      try { await axios.get('/ping', { timeout: 8000 }); } catch { /* ignore */ }
    }
  };

  /**********************
   * UI COMPONENTS      *
   **********************/
  const UI = {
    getStatusDetails(task) {
      const status = task?.status || 'Unknown';
      const isFailed = status.startsWith('Failed');
      const isCompleted = status.startsWith('Completed');
      
      let badgeClass = 'bg-secondary';
      let iconHtml = `<div class="spinner-border spinner-border-sm text-primary" role="status" id="spinner-${task?.task_id}"></div>`;

      if (status === 'Generating Screenshot') {
        badgeClass = 'bg-info text-dark';
      } else if (isCompleted) {
        badgeClass = 'bg-success';
        iconHtml = '<i class="bi bi-check-circle-fill text-success fs-5"></i>';
      } else if (isFailed) {
        badgeClass = 'bg-danger';
        iconHtml = '<i class="bi bi-x-circle-fill text-danger fs-5"></i>';
      } else if (status === 'Not Found') {
        badgeClass = 'bg-warning text-dark';
        iconHtml = '<i class="bi bi-question-circle-fill text-warning fs-5"></i>';
      }

      return {
        status,
        badgeClass,
        iconHtml,
        logBtn: isFailed && task?.has_log ? this.renderLogBtn(task.task_id) : '',
        sonarBtn: task?.sonar_url ? `<a href="${task.sonar_url}" target="_blank" class="btn btn-sm btn-outline-primary ms-2">View Report</a>` : '',
        screenshotBtns: this.renderScreenshotBtns(task?.screenshot_info)
      };
    },

    renderLogBtn(taskId) {
      const msg = Utils.escapeHtml('Log available on server. Click to load.');
      return `<button class="btn btn-sm btn-outline-secondary ms-2" data-bs-toggle="modal" data-bs-target="#logModal" data-task-id="${taskId}" data-log-content="${msg}">View Log</button>`;
    },

    renderScreenshotBtns(info) {
      if (!info?.filename) return '';
      const downloadUrl = `/download/screenshots/${encodeURIComponent(info.filename)}`;
      return `
        <a href="${info.display_url}" target="_blank" class="btn btn-sm btn-outline-info ms-2" title="View Screenshot"><i class="bi bi-camera"></i></a>
        <a href="${downloadUrl}" class="btn btn-sm btn-outline-success ms-2" title="Download Screenshot"><i class="bi bi-download"></i></a>
      `;
    },

    createTaskCard(task) {
      const d = this.getStatusDetails(task);
      return `
        <div class="card tasks-card mb-3" id="task-${task.task_id}">
          <div class="card-body p-3">
            <div class="row align-items-center g-3">
              <div class="col-md-5">
                <div class="d-flex align-items-center mb-1">
                  <strong class="text-primary me-2">${Utils.getRepoLabel(task.repo_url)}</strong>
                  <span class="badge bg-info-subtle text-info-emphasis rounded-pill fw-normal">
                    <i class="bi bi-git me-1"></i>${task.branch_name || 'N/A'}
                  </span>
                </div>
                <small class="text-muted">Task ID: ${task.task_id}</small>
              </div>
              <div class="col-md-3">
                <span class="badge ${d.badgeClass} status" id="status-badge-${task.task_id}">${d.status}</span>
              </div>
              <div class="col-md-4 text-md-end">
                <div id="result-container-${task.task_id}" class="d-flex align-items-center justify-content-end">
                  ${d.iconHtml} ${d.sonarBtn} ${d.screenshotBtns} ${d.logBtn}
                </div>
              </div>
            </div>
          </div>
        </div>`;
    },

    updateTaskUI(taskId, data) {
      const card = document.getElementById(`task-${taskId}`);
      if (!card) return;

      const d = this.getStatusDetails(data);
      const badge = card.querySelector(`#status-badge-${taskId}`);
      if (badge) {
        badge.textContent = d.status;
        badge.className = `badge ${d.badgeClass} status`;
      }
      const container = card.querySelector(`#result-container-${taskId}`);
      if (container) {
        container.innerHTML = `${d.iconHtml} ${d.sonarBtn} ${d.screenshotBtns} ${d.logBtn}`;
      }
    },

    renderAllTasks(items) {
      const container = document.getElementById('tasksContainer');
      if (container) {
        container.innerHTML = (items || []).map(t => this.createTaskCard(t)).join('');
      }
    },

    toggleSubmitLoading(isLoading) {
      const spinner = document.getElementById('submitSpinner');
      const btn = document.getElementById('submitBtn');
      if (spinner) spinner.classList.toggle('d-none', !isLoading);
      if (btn) btn.disabled = isLoading;
    }
  };

  /**********************
   * POLLING MANAGER    *
   **********************/
  const Poller = {
    intervals: {},
    backoff: {},
    isPaused: false,

    start(taskId) {
      if (this.intervals[taskId]) return;
      this.poll(taskId);
      this.intervals[taskId] = setInterval(() => this.poll(taskId), POLLING_INTERVAL);
    },

    stop(taskId) {
      clearInterval(this.intervals[taskId]);
      delete this.intervals[taskId];
      delete this.backoff[taskId];
    },

    poll(taskId) {
      if (this.isPaused) return;

      axios.get(`/status/${taskId}`, { timeout: 12000 })
        .then(res => this.handleSuccess(taskId, res.data))
        .catch(err => this.handleError(taskId, err));
    },

    handleSuccess(taskId, data) {
      const state = Storage.load();
      const idx = state.items.findIndex(t => t.task_id === taskId);
      if (idx === -1) return;

      const merged = { ...state.items[idx], ...data };
      state.items[idx] = merged;
      
      UI.updateTaskUI(taskId, merged);
      Storage.save(state.items);

      const s = String(merged.status || '');
      if (s.startsWith('Completed') || s.startsWith('Failed') || s === 'Not Found') {
        this.stop(taskId);
      }
    },

    handleError(taskId, error) {
      if (error?.response?.status === 404) {
        this.handleNotFound(taskId);
        return;
      }
      
      console.warn(`poll ${taskId} fail:`, error?.message || error);
      this.applyBackoff(taskId);
    },

    handleNotFound(taskId) {
      this.handleSuccess(taskId, { status: 'Not Found' });
      this.stop(taskId);
    },

    applyBackoff(taskId) {
      const current = this.backoff[taskId] || POLLING_INTERVAL;
      const next = Math.min(current * 2, MAX_BACKOFF);
      this.backoff[taskId] = next;
      
      clearInterval(this.intervals[taskId]);
      this.intervals[taskId] = setInterval(() => this.poll(taskId), next);
    },

    pauseAll() {
      this.isPaused = true;
      Object.keys(this.intervals).forEach(id => {
        clearInterval(this.intervals[id]);
        delete this.intervals[id];
      });
    },

    resumeAll() {
      this.isPaused = false;
      const state = Storage.load();
      UI.renderAllTasks(state.items);
      state.items.forEach(t => {
        const s = String(t.status || '');
        if (!s.startsWith('Completed') && !s.startsWith('Failed') && s !== 'Not Found' && t.task_id) {
          this.start(t.task_id);
        }
      });
    }
  };

  /**********************
   * EVENT HANDLERS     *
   **********************/
  const Handlers = {
    init() {
      this.setupLogModal();
      this.setupInclusionExclusion();
      this.setupFormSubmit();
      this.setupClearList();
      this.setupVisibilityChange();
      this.setupNetworkStatus();
      this.setupKeepAlive();
    },

    setupLogModal() {
      const modal = document.getElementById('logModal');
      if (!modal) return;
      modal.addEventListener('show.bs.modal', (e) => {
        const btn = e.relatedTarget;
        const taskId = btn?.getAttribute('data-task-id') || '';
        const title = modal.querySelector('.modal-title');
        const content = modal.querySelector('#logModalContent');
        
        title.textContent = `Log for Task ${taskId}`;
        content.textContent = 'Loading log...';

        if (!taskId) {
          content.textContent = Utils.unescapeHtml(btn?.getAttribute('data-log-content') || 'No log content available.');
          return;
        }

        axios.get(`/status/${encodeURIComponent(taskId)}?include_log=1`, { timeout: 12000 })
          .then(res => { content.textContent = res.data?.log || 'Log not available.'; })
          .catch(err => { content.textContent = err?.response?.data?.error || 'Failed to fetch log.'; });
      });
    },

    setupInclusionExclusion() {
      const inc = document.getElementById('sonar_inclusions');
      const exc = document.getElementById('sonar_exclusions');
      if (!inc || !exc) return;
      inc.addEventListener('input', () => { if (inc.value.trim()) exc.value = ''; });
      exc.addEventListener('input', () => { if (exc.value.trim()) inc.value = ''; });
    },

    setupFormSubmit() {
      const form = document.getElementById('scanForm');
      if (!form) return;
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        UI.toggleSubmitLoading(true);

        axios.post('/repo-scan', new FormData(form))
          .then(res => {
            const data = res.data || {};
            if (data.task_id) {
              const newTask = {
                task_id: data.task_id,
                repo_url: data.repo_url,
                branch_name: document.getElementById('branch_name')?.value || 'main',
                status: 'Queued',
                sonar_url: null,
                screenshot_info: null,
                has_log: false,
                log_size: 0,
              };
              const state = Storage.load();
              state.items.unshift(newTask);
              Storage.save(state.items);
              UI.renderAllTasks(state.items);
              Poller.start(newTask.task_id);
            }
          })
          .catch(err => {
            console.error(err);
            alert(err?.response?.data?.error || 'An unexpected error occurred.');
          })
          .finally(() => UI.toggleSubmitLoading(false));
      });
    },

    setupClearList() {
      const btn = document.getElementById('clearListBtn');
      if (!btn) return;
      btn.addEventListener('click', () => {
        Poller.pauseAll();
        localStorage.removeItem(STORAGE_KEY);
        const container = document.getElementById('tasksContainer');
        if (container) container.innerHTML = '';
      });
    },

    setupVisibilityChange() {
      document.addEventListener('visibilitychange', async () => {
        if (document.hidden) {
          Poller.pauseAll();
        } else {
          await Api.refreshCsrfToken();
          await Api.ping();
          Poller.resumeAll();
        }
      });
    },

    setupNetworkStatus() {
      const getBanner = () => {
        let el = document.getElementById('net-banner');
        if (!el) {
          el = document.createElement('div');
          el.id = 'net-banner';
          el.className = 'alert alert-warning text-center m-0 rounded-0';
          el.style.display = 'none';
          el.innerHTML = '<i class="bi bi-wifi-off me-2"></i> You are offline. Waiting for connection...';
          document.body.prepend(el);
        }
        return el;
      };

      window.addEventListener('offline', () => {
        getBanner().style.display = 'block';
        Poller.pauseAll();
      });
      window.addEventListener('online', async () => {
        getBanner().style.display = 'none';
        await Api.refreshCsrfToken();
        Poller.resumeAll();
      });
    },

    setupKeepAlive() {
      setInterval(() => {
        if (!document.hidden) Api.ping();
      }, 4 * 60 * 1000);
    }
  };

  /**********************
   * INITIALIZATION     *
   **********************/
  Api.init();

  document.addEventListener('DOMContentLoaded', () => {
    // Bootstrap Popovers
    [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'))
      .map(el => new bootstrap.Popover(el));

    Handlers.init();

    const state = Storage.load();
    UI.renderAllTasks(state.items);
    
    state.items.forEach(t => {
      const s = String(t.status || '');
      if (!s.startsWith('Completed') && !s.startsWith('Failed') && s !== 'Not Found' && t.task_id) {
        Poller.start(t.task_id);
      }
    });
  });
})();
