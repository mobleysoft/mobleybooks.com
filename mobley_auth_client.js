/**
 * MOBLEYAUTH CLIENT
 * Drop-in premium frontend logic for Magic-Link & Stripe integration.
 * Adheres strictly to Rule 12: Glassmorphism, micro-animations, high cognitive ergonomics.
 */

class MobleyAuth {
  constructor(config = {}) {
    this.apiBase = config.apiBase || 'https://mobleyauth-gateway.hauwamusiq.workers.dev';
    this.sessionToken = new URLSearchParams(window.location.search).get('session') || localStorage.getItem('mobley_session');
    
    if (this.sessionToken) {
      localStorage.setItem('mobley_session', this.sessionToken);
      window.history.replaceState({}, document.title, window.location.pathname);
    }
    
    this.injectStyles();
  }

  injectStyles() {
    const style = document.createElement('style');
    style.textContent = `
      .mobley-auth-modal {
        position: fixed; inset: 0; display: grid; place-items: center;
        background: rgba(0, 0, 0, 0.4); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
        z-index: 9999; opacity: 0; pointer-events: none; transition: opacity 0.4s cubic-bezier(0.16, 1, 0.3, 1);
        font-family: 'Avenir Next', 'Inter', sans-serif;
      }
      .mobley-auth-modal.active { opacity: 1; pointer-events: auto; }
      .mobley-auth-card {
        background: rgba(20, 20, 22, 0.85); border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 3rem; border-radius: 24px; width: 100%; max-width: 420px;
        box-shadow: 0 32px 64px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.1);
        transform: translateY(20px) scale(0.95); transition: all 0.5s cubic-bezier(0.16, 1, 0.3, 1);
        color: #f7f2e8; text-align: center;
      }
      .mobley-auth-modal.active .mobley-auth-card { transform: translateY(0) scale(1); }
      .mobley-auth-title { font-size: 1.5rem; font-weight: 600; margin: 0 0 0.5rem; letter-spacing: -0.03em; }
      .mobley-auth-subtitle { color: #b8c8c1; font-size: 0.95rem; margin-bottom: 2rem; line-height: 1.5; }
      .mobley-auth-input {
        width: 100%; padding: 1rem 1.25rem; background: rgba(0, 0, 0, 0.3);
        border: 1px solid rgba(255, 255, 255, 0.15); border-radius: 12px;
        color: #fff; font-size: 1rem; outline: none; transition: border-color 0.3s ease;
        margin-bottom: 1.5rem; box-sizing: border-box;
      }
      .mobley-auth-input:focus { border-color: #00FFCC; }
      .mobley-auth-btn {
        width: 100%; padding: 1rem; background: #00FFCC; color: #111;
        border: none; border-radius: 12px; font-size: 1rem; font-weight: 700;
        cursor: pointer; transition: transform 0.2s ease, filter 0.2s ease;
      }
      .mobley-auth-btn:hover { transform: scale(1.02); filter: brightness(1.1); }
      .mobley-auth-btn:active { transform: scale(0.98); }
      .mobley-auth-close {
        position: absolute; top: 1.5rem; right: 1.5rem; background: transparent;
        border: none; color: #b8c8c1; cursor: pointer; font-size: 1.2rem;
      }
    `;
    document.head.appendChild(style);
  }

  createModal() {
    if (this.modal) return;
    this.modal = document.createElement('div');
    this.modal.className = 'mobley-auth-modal';
    this.modal.innerHTML = `
      <div class="mobley-auth-card">
        <button class="mobley-auth-close">&times;</button>
        <h2 class="mobley-auth-title">Access the System</h2>
        <p class="mobley-auth-subtitle">Enter your email to receive a secure magic link.</p>
        <input type="email" class="mobley-auth-input" placeholder="architect@mobleysoft.com" />
        <button class="mobley-auth-btn">Send Magic Link</button>
      </div>
    `;
    document.body.appendChild(this.modal);

    this.modal.querySelector('.mobley-auth-close').onclick = () => this.hide();
    this.modal.querySelector('.mobley-auth-btn').onclick = () => this.handleLogin();
  }

  show() {
    this.createModal();
    // Force reflow
    void this.modal.offsetWidth;
    this.modal.classList.add('active');
  }

  hide() {
    if (this.modal) this.modal.classList.remove('active');
  }

  async handleLogin() {
    const email = this.modal.querySelector('.mobley-auth-input').value;
    const btn = this.modal.querySelector('.mobley-auth-btn');
    if (!email || !email.includes('@')) return;

    btn.textContent = 'Sending...';
    btn.style.opacity = '0.7';

    try {
      const res = await fetch(`${this.apiBase}/api/auth/magic`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email })
      });
      const data = await res.json();
      
      this.modal.innerHTML = `
        <div class="mobley-auth-card">
          <button class="mobley-auth-close" onclick="document.querySelector('.mobley-auth-modal').classList.remove('active')">&times;</button>
          <h2 class="mobley-auth-title">Check your inbox</h2>
          <p class="mobley-auth-subtitle">A secure access link has been sent to ${email}</p>
          ${data._debug_link ? `<a href="${data._debug_link}" style="color:#00FFCC;font-size:0.8rem;">[DEV: Click here to verify]</a>` : ''}
        </div>
      `;
    } catch (e) {
      btn.textContent = 'Failed. Try again.';
      btn.style.opacity = '1';
    }
  }

  async upgrade(priceId = null) {
    if (!this.sessionToken) {
      this.show();
      return;
    }
    
    try {
      const res = await fetch(`${this.apiBase}/api/billing/checkout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sessionToken: this.sessionToken, priceId })
      });
      const data = await res.json();
      if (data.url) window.location.href = data.url;
    } catch (e) {
      console.error("Treasury Gateway Error:", e);
    }
  }
}

window.MobleyAuth = MobleyAuth;
