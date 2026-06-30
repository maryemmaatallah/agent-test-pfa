(function () {
    if (window.RECORDER && window.RECORDER.actif) {
        console.warn('[RECORDER] Déjà actif. Appelez window.RECORDER.stop() d\'abord.');
        return;
    }

    const BACKEND_URL = window.__REC_BACKEND || 'http://localhost:8000';

    const RECORDER = {
        actif: true,
        actions: [],
        _lastUrl: window.location.href,
        _badge: null,
        _listeners: [],

        _createBadge() {
            const old = document.getElementById('__recorder_badge');
            if (old) old.remove();
            const badge = document.createElement('div');
            badge.id = '__recorder_badge';
            badge.style.cssText = `
                position:fixed;bottom:20px;right:20px;z-index:999999;
                background:#ef4444;color:white;border-radius:12px;
                padding:10px 16px;font-family:monospace;font-size:13px;
                box-shadow:0 4px 20px rgba(0,0,0,0.4);
                display:flex;align-items:center;gap:8px;
            `;
            const style = document.createElement('style');
            style.textContent = '@keyframes blink{0%,100%{opacity:1}50%{opacity:0.3}}';
            document.head.appendChild(style);
            badge.innerHTML = `
                <span style="width:10px;height:10px;background:#fff;border-radius:50%;display:inline-block;animation:blink 1s infinite"></span>
                <span id="__rec_count">0 actions</span>
                <button id="__rec_assert_btn" style="background:#f59e0b;color:#000;border:none;border-radius:6px;padding:2px 8px;cursor:pointer;font-weight:bold;font-size:12px">✓ Vérifier</button>
                <button id="__rec_stop_btn" style="background:#fff;color:#ef4444;border:none;border-radius:6px;padding:2px 8px;cursor:pointer;font-weight:bold;font-size:12px">STOP</button>
            `;
            document.body.appendChild(badge);

            document.getElementById('__rec_stop_btn').addEventListener('click', () => window.RECORDER.stop());

            document.getElementById('__rec_assert_btn').addEventListener('click', () => {
                const lignes = document.body.innerText
                    .split('\n')
                    .map(l => l.trim())
                    .filter(l => l.length > 2 && l.length < 50);
                const suggestion = lignes[0] || '';
                const mot = prompt('Quel texte vérifier sur cette page ?', suggestion);
                if (!mot) return;
                window.RECORDER._push({
                    type: 'ASSERT',
                    text: mot.trim(),
                    displayValue: mot.trim()
                });
                console.log(`%c[REC] ASSERT "${mot.trim()}"`, 'color:#f59e0b;font-weight:bold');
            });

            this._badge = badge;
            console.log('%c[RECORDER] ✅ Badge créé — faites vos actions !', 'color:#22c55e;font-weight:bold;font-size:14px');
        },

        _updateBadge() {
            const el = document.getElementById('__rec_count');
            if (el) el.textContent = `${this.actions.length} action${this.actions.length > 1 ? 's' : ''}`;
        },

        _getSelector(el) {
            if (!el || el === document.body) return 'body';
            if (el.id) return '#' + el.id;
            if (el.getAttribute('data-testid')) return `[data-testid="${el.getAttribute('data-testid')}"]`;
            if (el.name) return `[name="${el.name}"]`;

            const tag = el.tagName.toLowerCase();

            if (['button', 'a'].includes(tag)) {
                const txt = (el.innerText || el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 40);
                if (txt) return `${tag}:has-text("${txt}")`;
            }

            if (tag === 'input') {
                if (el.placeholder) return `input[placeholder="${el.placeholder}"]`;
                if (el.type && el.type !== 'text') return `input[type="${el.type}"]`;
            }

            let path = '';
            let node = el;
            let depth = 0;
            while (node && node !== document.body && depth < 4) {
                let seg = node.tagName.toLowerCase();
                if (node.id) { seg = '#' + node.id; path = seg; break; }
                const siblings = Array.from(node.parentNode?.children || []);
                const sameTags = siblings.filter(s => s.tagName === node.tagName);
                if (sameTags.length > 1) seg += `:nth-child(${siblings.indexOf(node) + 1})`;
                path = seg + (path ? ' > ' + path : '');
                node = node.parentNode;
                depth++;
            }
            return path || tag;
        },

        _push(action) {
            if (action.type === 'GOTO' && this.actions.length > 0) {
                const last = this.actions[this.actions.length - 1];
                if (last.type === 'GOTO' && last.url === action.url) return;
            }
            this.actions.push({ ...action, timestamp: Date.now() });
            this._updateBadge();
            const display = action.type === 'FILL'
                ? `FILL ${action.selector} = ${action.displayValue}`
                : action.type === 'GOTO' ? `GOTO ${action.url}`
                : action.type === 'ASSERT' ? `ASSERT "${action.text}"`
                : `CLICK ${action.selector}`;
            console.log(`%c[REC] ${display}`, 'color:#38bdf8');
        },

        _addListener(target, event, fn, capture) {
            target.addEventListener(event, fn, capture);
            this._listeners.push({ target, event, fn, capture });
        },

        _setupListeners() {
            const self = this;

            // ── 1. Navigation SPA ──
            const origPush = history.pushState.bind(history);
            const origReplace = history.replaceState.bind(history);

            history.pushState = function (...args) {
                origPush(...args);
                setTimeout(() => self._push({ type: 'GOTO', url: window.location.href }), 50);
            };
            history.replaceState = function (...args) {
                origReplace(...args);
                setTimeout(() => self._push({ type: 'GOTO', url: window.location.href }), 50);
            };

            window.addEventListener('popstate', () => {
                setTimeout(() => self._push({ type: 'GOTO', url: window.location.href }), 50);
            });

            setInterval(() => {
                if (window.location.href !== self._lastUrl) {
                    self._lastUrl = window.location.href;
                    self._push({ type: 'GOTO', url: window.location.href });
                }
            }, 500);

            let fillTimers = {};

            // ── 2. Saisie dans les champs (focusout) ──
            // ── NIVEAU 2 : on capture aussi htmlType pour la détection précise ──
            this._addListener(document, 'focusout', function(e) {
                const el = e.target;
                if (!['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName)) return;
                if (!el.value) return;
                const sel = self._getSelector(el);
                clearTimeout(fillTimers[sel]);
                delete fillTimers[sel];
                const last = self.actions[self.actions.length - 1];
                if (last && last.type === 'FILL' && last.selector === sel && last.value === el.value) return;
                self._push({
                    type: 'FILL',
                    selector: sel,
                    value: el.value,
                    displayValue: el.type === 'password' ? '●●●●●●' : el.value,
                    htmlType: el.type || 'text',          // ← TYPE HTML RÉEL
                    htmlMin: el.min || null,               // ← min si défini
                    htmlMax: el.max || null,               // ← max si défini
                    htmlMaxLength: el.maxLength > 0 ? el.maxLength : null,  // ← maxlength si défini
                    htmlRequired: el.required || false     // ← required si défini
                });
            }, true);

        // ── 3. Clics ──
this._addListener(document, 'click', function(e) {
    if (e.target.closest('#__recorder_badge')) return;
    const tag = e.target.tagName?.toLowerCase();
    if (['input', 'textarea'].includes(tag)) return;

    // On capture UNIQUEMENT l'élément qui a le focus actif au moment du clic
    // (pas un scan de tout le document, pour éviter de capturer des champs
    // d'un autre écran qui apparaît/disparaît pendant une transition SPA)
    const actif = document.activeElement;
    if (actif && ['INPUT', 'TEXTAREA', 'SELECT'].includes(actif.tagName) && actif.value) {
        const sel = self._getSelector(actif);
        const dejaCapture = self.actions.some(a =>
            a.type === 'FILL' && a.selector === sel && a.value === actif.value
        );
        if (!dejaCapture) {
            self._push({
                type: 'FILL',
                selector: sel,
                value: actif.value,
                displayValue: actif.type === 'password' ? '●●●●●●' : actif.value,
                htmlType: actif.type || 'text',
                htmlMin: actif.min || null,
                htmlMax: actif.max || null,
                htmlMaxLength: actif.maxLength > 0 ? actif.maxLength : null,
                htmlRequired: actif.required || false
            });
        }
    }

    let el = e.target;
    while (el && el !== document.body) {
        const t = el.tagName?.toLowerCase();
        if (['a', 'button', 'input', 'select', 'textarea', 'label'].includes(t)) break;
        if (el.getAttribute('role') === 'button') break;
        if (el.onclick || el.getAttribute('onclick')) break;
        el = el.parentElement;
    }
    el = el || e.target;

    const sel = self._getSelector(el);
    const txt = (el.innerText || el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 60);
    self._push({ type: 'CLICK', selector: sel, text: txt });
}, true);
            // ── 4. Select / checkbox ──
            this._addListener(document, 'change', function(e) {
                const el = e.target;
                if (el.tagName === 'SELECT') {
                    self._push({
                        type: 'FILL',
                        selector: self._getSelector(el),
                        value: el.value,
                        displayValue: el.value,
                        htmlType: 'select'
                    });
                }
            }, true);
        },

        async stop() {
            if (!this.actif) return;
            this.actif = false;

            const badge = document.getElementById('__recorder_badge');
            if (badge) badge.remove();

            this._listeners.forEach(({ target, event, fn, capture }) => {
                try { target.removeEventListener(event, fn, capture); } catch(e) {}
            });

            console.log(`[REC] Arrêt — ${this.actions.length} actions enregistrées`);

            if (this.actions.length === 0) {
                console.warn('[REC] Aucune action à sauvegarder.');
                return;
            }

            const nom = window.__REC_NOM || prompt('Nom de cette session ?', 'Test ' + new Date().toLocaleTimeString());
            if (!nom) { console.warn('[REC] Annulé.'); return; }

            const payload = {
                nom,
                url: window.__REC_URL || this.actions.find(a => a.type === 'GOTO')?.url || window.location.href,
                actions: this.actions
            };

            try {
                const res = await fetch(`${BACKEND_URL}/api/sessions/sauvegarder`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                console.log(`✅ Session sauvegardée — ID ${data.id} — ${data.nb_actions} actions`);
                alert(`✅ Session "${nom}" sauvegardée !\n${data.nb_actions} actions enregistrées.`);
            } catch (err) {
                console.error('[REC] Erreur sauvegarde:', err);
                navigator.clipboard?.writeText(JSON.stringify(payload, null, 2));
                alert('⚠️ Backend non accessible. Actions copiées dans le presse-papiers.');
            }
        }
    };

    RECORDER._createBadge();
    RECORDER._setupListeners();
    RECORDER._push({ type: 'GOTO', url: window.location.href });

    window.RECORDER = RECORDER;
})();
