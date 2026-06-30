"""
recorder.py — Enregistrement des actions utilisateur via Playwright
--------------------------------------------------------------------
Lance un navigateur visible, injecte un script JS qui intercepte tous
les événements (click, fill, navigation) et les renvoie au backend via
un WebSocket ou une API simple.
"""

import json
import time
import threading
from datetime import datetime
from playwright.sync_api import sync_playwright


# ──────────────────────────────────────────────
# Script JS injecté dans chaque page pour capturer les events
# ──────────────────────────────────────────────
JS_RECORDER = """
(function() {
    if (window.__recorderInjected) return;
    window.__recorderInjected = true;
    window.__recordedActions = [];

    function getSelector(el) {
        if (!el) return '';
        if (el.id) return '#' + el.id;
        if (el.name) return '[name="' + el.name + '"]';
        if (el.type === 'submit' || el.tagName === 'BUTTON') {
            const txt = el.innerText.trim().slice(0, 30);
            if (txt) return el.tagName.toLowerCase() + ':has-text("' + txt + '")';
        }
        // Fallback: chemin complet
        let path = '';
        let node = el;
        while (node && node !== document.body) {
            let seg = node.tagName.toLowerCase();
            if (node.id) { seg += '#' + node.id; }
            else {
                const idx = Array.from(node.parentNode?.children || []).indexOf(node);
                if (idx >= 0) seg += ':nth-child(' + (idx+1) + ')';
            }
            path = seg + (path ? ' > ' + path : '');
            node = node.parentNode;
        }
        return path;
    }

    // Capture les clics
    document.addEventListener('click', function(e) {
        const el = e.target;
        const sel = getSelector(el);
        const action = {
            type: 'CLICK',
            selector: sel,
            text: el.innerText?.trim().slice(0, 50) || '',
            timestamp: Date.now()
        };
        window.__recordedActions.push(action);
        console.log('[REC] CLICK:', JSON.stringify(action));
    }, true);

    // Capture les saisies (debounce 800ms)
    let fillTimers = {};
    document.addEventListener('input', function(e) {
        const el = e.target;
        if (!['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName)) return;
        const sel = getSelector(el);
        clearTimeout(fillTimers[sel]);
        fillTimers[sel] = setTimeout(function() {
            const val = el.type === 'password' ? '***HIDDEN***' : el.value;
            const action = {
                type: 'FILL',
                selector: sel,
                value: el.value,       // valeur réelle pour le replay
                displayValue: val,     // valeur masquée pour l'affichage
                timestamp: Date.now()
            };
            window.__recordedActions.push(action);
            console.log('[REC] FILL:', JSON.stringify({...action, value: val}));
        }, 800);
    }, true);

    console.log('[REC] Recorder injecté sur', window.location.href);
})();
"""


def demarrer_enregistrement(url_depart: str, callback_action=None) -> list:
    """
    Ouvre un navigateur visible sur url_depart.
    L'utilisateur fait ses actions manuellement.
    Retourne la liste des actions enregistrées quand le navigateur est fermé.

    callback_action(action_dict) — appelé en temps réel à chaque action capturée (optionnel)
    """
    actions_enregistrees = []
    url_courante = [url_depart]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--start-maximized"])
        context = browser.new_context()
        page = context.new_page()

        def on_navigation(frame):
            if frame == page.main_frame:
                url = page.url
                if url != url_courante[0]:
                    action = {
                        "type": "GOTO",
                        "url": url,
                        "timestamp": int(time.time() * 1000)
                    }
                    actions_enregistrees.append(action)
                    url_courante[0] = url
                    print(f"[REC] GOTO: {url}")
                    if callback_action:
                        callback_action(action)
                # Réinjecter le recorder JS après chaque navigation
                try:
                    page.evaluate(JS_RECORDER)
                except Exception:
                    pass

        page.on("framenavigated", on_navigation)

        # Aller à l'URL de départ
        page.goto(url_depart)
        page.wait_for_timeout(1000)
        page.evaluate(JS_RECORDER)

        actions_enregistrees.append({
            "type": "GOTO",
            "url": url_depart,
            "timestamp": int(time.time() * 1000)
        })

        print(f"\n🔴 ENREGISTREMENT EN COURS sur {url_depart}")
        print("👉 Faites vos actions dans le navigateur.")
        print("👉 Fermez le navigateur quand vous avez terminé.\n")

        # Polling des actions JS captées
        last_count = 0
        try:
            while True:
                try:
                    js_actions = page.evaluate("window.__recordedActions || []")
                    new_actions = js_actions[last_count:]
                    for a in new_actions:
                        actions_enregistrees.append(a)
                        if callback_action:
                            callback_action(a)
                        print(f"[REC] {a['type']}: {a.get('selector', a.get('url', ''))}")
                    last_count = len(js_actions)
                    page.wait_for_timeout(500)
                except Exception:
                    break  # Le navigateur a été fermé
        except KeyboardInterrupt:
            pass

        try:
            browser.close()
        except Exception:
            pass

    # Dédupliquer les clics qui suivent un FILL (souvent le bouton submit est capté deux fois)
    actions_propres = _nettoyer_actions(actions_enregistrees)
    print(f"\n✅ {len(actions_propres)} actions enregistrées.")
    return actions_propres


def _nettoyer_actions(actions: list) -> list:
    """Supprime les doublons consécutifs et les GOTOs intermédiaires parasites."""
    propres = []
    for i, a in enumerate(actions):
        if i == 0:
            propres.append(a)
            continue
        prev = propres[-1]
        # Supprimer GOTO dupliqué
        if a["type"] == "GOTO" and prev["type"] == "GOTO" and a.get("url") == prev.get("url"):
            continue
        # Supprimer CLICK dupliqué immédiat (moins de 300ms d'écart)
        if a["type"] == "CLICK" and prev["type"] == "CLICK":
            if abs(a.get("timestamp", 0) - prev.get("timestamp", 0)) < 300:
                continue
        propres.append(a)
    return propres


def serialiser_session(actions: list, nom: str, url_depart: str) -> dict:
    """Transforme la liste d'actions en dict JSON sauvegardable."""
    return {
        "nom": nom,
        "url_depart": url_depart,
        "date_creation": datetime.utcnow().strftime("%d/%m/%Y %H:%M"),
        "nb_actions": len(actions),
        "actions": actions
    }