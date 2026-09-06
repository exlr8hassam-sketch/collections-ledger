/**
 * WhatsApp Payment Reminder Agent - Mobile & Notification Engine
 * Adheres to impeccable.md craftsmanship standards: clean human copy, no emoji tropes.
 */

class NotificationManager {
  constructor() {
    this.swRegistration = null;
    this.deferredInstallPrompt = null;
    this.audioContext = null;
    this.soundEnabled = localStorage.getItem('notif_sound_enabled') !== 'false';
    this.lastOverdueCount = parseInt(localStorage.getItem('last_overdue_count') || '0', 10);
    this.init();
  }

  async init() {
    this.registerServiceWorker();
    this.setupInstallPrompt();
    this.setupAudio();
    this.bindUI();

    setTimeout(() => {
      this.checkDailyBriefing();
    }, 3000);
  }

  async registerServiceWorker() {
    if ('serviceWorker' in navigator) {
      try {
        const reg = await navigator.serviceWorker.register('/sw.js', { scope: '/' });
        this.swRegistration = reg;
        console.log('[PWA] Service Worker registered:', reg.scope);
      } catch (err) {
        console.warn('[PWA] Service Worker registration failed:', err);
      }
    }
  }

  setupAudio() {
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) {
        this.audioContext = new AudioCtx();
      }
    } catch (e) {
      console.warn('Web Audio not supported:', e);
    }
  }

  playChime(type = 'default') {
    if (!this.soundEnabled) return;
    try {
      if (!this.audioContext) {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        this.audioContext = new AudioCtx();
      }
      if (this.audioContext.state === 'suspended') {
        this.audioContext.resume();
      }

      const now = this.audioContext.currentTime;
      const osc = this.audioContext.createOscillator();
      const gain = this.audioContext.createGain();

      osc.type = 'sine';
      if (type === 'alert') {
        osc.frequency.setValueAtTime(523.25, now);
        osc.frequency.setValueAtTime(783.99, now + 0.1);
        osc.frequency.setValueAtTime(1046.50, now + 0.2);
        gain.gain.setValueAtTime(0.2, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.55);
        osc.start(now);
        osc.stop(now + 0.55);
      } else {
        osc.frequency.setValueAtTime(659.25, now);
        osc.frequency.setValueAtTime(880.00, now + 0.12);
        gain.gain.setValueAtTime(0.15, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.4);
        osc.start(now);
        osc.stop(now + 0.4);
      }

      osc.connect(gain);
      gain.connect(this.audioContext.destination);
    } catch (err) {
      console.log('Audio chime error:', err);
    }
  }

  async requestPermission() {
    if (!('Notification' in window)) {
      alert('This browser does not support native notifications.');
      return false;
    }

    if (Notification.permission === 'granted') {
      return true;
    }

    const permission = await Notification.requestPermission();
    if (permission === 'granted') {
      this.playChime('default');
      this.showNotification('Notifications Enabled', {
        body: 'You will receive invoice due dates, overdue notices, and delivery confirmations.',
        tag: 'welcome'
      });
      return true;
    }
    return false;
  }

  async showNotification(title, options = {}) {
    const defaultOptions = {
      icon: '/static/icon-192.png',
      badge: '/static/icon-192.png',
      vibrate: [200, 100, 200],
      tag: options.tag || 'general-reminder',
      renotify: true,
      body: options.body || ''
    };
    const merged = { ...defaultOptions, ...options };

    this.playChime(options.soundType || 'default');

    if (this.swRegistration && 'showNotification' in this.swRegistration) {
      try {
        await this.swRegistration.showNotification(title, merged);
        return;
      } catch (err) {
        console.warn('SW notification fallback:', err);
      }
    }

    if ('Notification' in window && Notification.permission === 'granted') {
      try {
        new Notification(title, merged);
      } catch (e) {
        console.warn('Fallback notification failed:', e);
      }
    }
  }

  async checkDailyBriefing() {
    try {
      const res = await fetch('/api/notifications/summary');
      if (!res.ok) return;
      const data = await res.json();

      const todayKey = new Date().toISOString().split('T')[0];
      const lastBriefingDate = localStorage.getItem('last_briefing_date');

      if (data.overdue_count > this.lastOverdueCount && data.overdue_count > 0) {
        this.showNotification('Overdue Invoices Require Attention', {
          body: `${data.overdue_count} invoice(s) are past due date (PKR ${Number(data.overdue_amount).toLocaleString()} outstanding).`,
          soundType: 'alert',
          tag: 'overdue-alert'
        });
        this.lastOverdueCount = data.overdue_count;
        localStorage.setItem('last_overdue_count', this.lastOverdueCount.toString());
      }

      if (lastBriefingDate !== todayKey && (data.due_today_count > 0 || data.overdue_count > 0)) {
        this.showNotification('Daily Collections Briefing', {
          body: `${data.due_today_count} invoice(s) due today, ${data.overdue_count} overdue. Pending total: PKR ${Number(data.pending_amount).toLocaleString()}.`,
          soundType: 'default',
          tag: 'daily-briefing'
        });
        localStorage.setItem('last_briefing_date', todayKey);
      }
    } catch (e) {
      console.log('Briefing check error:', e);
    }
  }

  setupInstallPrompt() {
    window.addEventListener('beforeinstallprompt', (e) => {
      e.preventDefault();
      this.deferredInstallPrompt = e;

      const banner = document.getElementById('mobile-install-banner');
      if (banner && !localStorage.getItem('install_dismissed')) {
        banner.classList.remove('hidden');
      }
    });

    window.addEventListener('appinstalled', () => {
      this.deferredInstallPrompt = null;
      const banner = document.getElementById('mobile-install-banner');
      if (banner) banner.classList.add('hidden');
      localStorage.setItem('app_installed', 'true');
      this.showNotification('Application Installed', {
        body: 'Collections Ledger is installed on your device.',
        tag: 'app-installed'
      });
    });
  }

  async triggerInstallPrompt() {
    if (!this.deferredInstallPrompt) {
      alert('To install on your phone:\n1. Tap the three dots (?) in your browser\n2. Select "Add to Home screen" or "Install app"');
      return;
    }

    this.deferredInstallPrompt.prompt();
    const { outcome } = await this.deferredInstallPrompt.userChoice;
    if (outcome === 'accepted') {
      const banner = document.getElementById('mobile-install-banner');
      if (banner) banner.classList.add('hidden');
    }
    this.deferredInstallPrompt = null;
  }

  dismissInstallBanner() {
    const banner = document.getElementById('mobile-install-banner');
    if (banner) banner.classList.add('hidden');
    localStorage.setItem('install_dismissed', 'true');
  }

  bindUI() {
    const soundToggle = document.getElementById('cfg-notif-sound');
    if (soundToggle) {
      soundToggle.checked = this.soundEnabled;
      soundToggle.addEventListener('change', (e) => {
        this.soundEnabled = e.target.checked;
        localStorage.setItem('notif_sound_enabled', this.soundEnabled);
      });
    }
  }

  async testNotification() {
    const granted = await this.requestPermission();
    if (!granted) {
      alert('Please enable notification permissions in your browser or device settings.');
      return;
    }

    this.showNotification('Test Notification Active', {
      body: 'Audible chime, banner, and vibration are working correctly.',
      soundType: 'alert',
      tag: 'test-' + Date.now()
    });
  }
}

window.notifManager = new NotificationManager();
