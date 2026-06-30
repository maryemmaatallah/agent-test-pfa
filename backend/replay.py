"""
replay.py — Rejeu des actions enregistrées via Playwright
----------------------------------------------------------
Prend une liste d'actions (format recorder.py) et les rejoue
dans un navigateur Playwright headless ou visible.
"""

import re
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


def _nettoyer_selector(sel: str, text: str = "") -> tuple:
    if ':has-text(' in sel:
        sel = re.sub(r'\s+\d+"\)', '")', sel)
        text = re.sub(r'\s+\d+$', '', text)
        match = re.search(r':has-text\("([^"]+)"\)', sel)
        if match:
            txt = match.group(1).strip()
            mots = txt.split()
            if len(mots) > 4:
                txt_court = ' '.join(mots[:3])
                sel = sel.replace(f':has-text("{txt}")', f':has-text("{txt_court}")')
                text = txt_court
    return sel, text


def rejouer_session(actions: list, headless: bool = True, vitesse: float = 1.0) -> dict:
    log = []
    nb_succes = 0
    nb_echecs = 0

    # Supprimer tous les FILLs en double
    actions_propres = []
    for i, a in enumerate(actions):
        if a.get('type') == 'FILL':
            est_doublon = any(
                b.get('type') == 'FILL' and
                b.get('selector') == a.get('selector') and
                b.get('value') == a.get('value')
                for b in actions[i+1:]
            )
            if est_doublon:
                continue
        actions_propres.append(a)
    actions = actions_propres

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()

        for i, action in enumerate(actions):
            type_action = action.get("type", "").upper()
            etape = f"Étape {i+1}/{len(actions)} — {type_action}"

            try:
                if type_action == "GOTO":
                    url = action["url"]
                    page.goto(url, timeout=30000, wait_until="domcontentloaded")
                    try:
                        page.wait_for_load_state("networkidle", timeout=5000)
                    except Exception:
                        pass
                    _attendre(page, 1000 * vitesse)
                    msg = f"✅ GOTO {url}"
                    log.append({"etape": etape, "statut": "ok", "message": msg})
                    nb_succes += 1
                    print(msg)

                elif type_action == "FILL":
                    sel = action["selector"]
                    val = action["value"]
                    page.wait_for_selector(sel, timeout=8000)
                    # Fallback pour input[type=number] et autres champs spéciaux
                    try:
                        page.fill(sel, val)
                    except Exception:
                        try:
                            page.click(sel)
                            page.evaluate(f"document.querySelector('{sel}').value = ''")
                            page.type(sel, str(val))
                        except Exception:
                            page.evaluate(f"document.querySelector('{sel}').value = '{val}'")
                    _attendre(page, 500 * vitesse)
                    val_log = "●●●●●●" if ("password" in sel.lower() or "pass" in sel.lower()) else val
                    msg = f"✅ FILL {sel} = {val_log}"
                    log.append({"etape": etape, "statut": "ok", "message": msg})
                    nb_succes += 1
                    print(msg)

                elif type_action == "CLICK":
                    sel, txt_action = _nettoyer_selector(action["selector"], action.get("text", ""))
                    clique = False

                    try:
                        page.click(sel, timeout=4000)
                        clique = True
                    except (PlaywrightTimeout, Exception):
                        pass

                    if not clique and ':has-text(' in sel:
                        try:
                            txt = re.search(r':has-text\("([^"]+)"\)', sel).group(1)
                            page.get_by_text(txt, exact=False).first.click(timeout=3000)
                            clique = True
                        except Exception:
                            pass

                    if not clique and txt_action:
                        try:
                            page.get_by_text(txt_action, exact=False).first.click(timeout=3000)
                            clique = True
                        except Exception:
                            pass

                    if not clique and txt_action:
                        try:
                            page.get_by_role("button", name=txt_action).first.click(timeout=3000)
                            clique = True
                        except Exception:
                            pass

                    try:
                        page.wait_for_load_state("domcontentloaded", timeout=5000)
                    except Exception:
                        pass
                    _attendre(page, 800 * vitesse)

                    if clique:
                        msg = f"✅ CLICK {sel}"
                        log.append({"etape": etape, "statut": "ok", "message": msg})
                        nb_succes += 1
                    else:
                        msg = f"⚠️ CLICK échoué: {sel}"
                        log.append({"etape": etape, "statut": "warn", "message": msg})
                        nb_echecs += 1
                    print(msg)

                elif type_action == "ASSERT":
                    texte_attendu = action.get("text", "")
                    try:
                        contenu = page.inner_text("body")
                        if texte_attendu.lower() in contenu.lower():
                            msg = f"✅ ASSERT '{texte_attendu}' — trouvé sur la page"
                            log.append({"etape": etape, "statut": "ok", "message": msg})
                            nb_succes += 1
                        else:
                            msg = f"❌ ASSERT '{texte_attendu}' — NON trouvé sur la page"
                            log.append({"etape": etape, "statut": "echec", "message": msg})
                            nb_echecs += 1
                        print(msg)
                    except Exception as e:
                        msg = f"❌ ASSERT erreur — {str(e)[:80]}"
                        log.append({"etape": etape, "statut": "echec", "message": msg})
                        nb_echecs += 1

                else:
                    log.append({"etape": etape, "statut": "skip", "message": f"Type inconnu: {type_action}"})

            except PlaywrightTimeout as e:
                msg = f"❌ TIMEOUT {type_action} — {str(e)[:80]}"
                log.append({"etape": etape, "statut": "echec", "message": msg})
                nb_echecs += 1
                print(msg)

            except Exception as e:
                msg = f"❌ ERREUR {type_action} — {str(e)[:80]}"
                log.append({"etape": etape, "statut": "echec", "message": msg})
                nb_echecs += 1
                print(msg)

        try:
            page_finale = page.inner_text("body")[:300]
        except Exception:
            page_finale = "(impossible de lire la page)"

        browser.close()

    total = nb_succes + nb_echecs
    taux = round((nb_succes / total * 100) if total > 0 else 0, 1)

    return {
        "statut": "succes" if nb_echecs == 0 else ("partiel" if nb_succes > 0 else "echec"),
        "nb_succes": nb_succes,
        "nb_echecs": nb_echecs,
        "taux_succes": taux,
        "page_finale": page_finale,
        "log": log
    }


def _attendre(page, ms: float):
    ms = max(int(ms), 100)
    page.wait_for_timeout(ms)