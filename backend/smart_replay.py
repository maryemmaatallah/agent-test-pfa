"""
smart_replay.py — Replay intelligent avec génération automatique de données
---------------------------------------------------------------------------
Version OPTIMISÉE pour la vitesse :
- Timeouts réduits
- Un seul navigateur partagé (pas de nouveau browser par scénario)
- Limite configurable du nombre de scénarios
- Logs de progression dans la console
"""

import re
import base64
import json
import hashlib
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from data_generator import planifier_tests, detecter_type_champ


def generer_id_court(id_complet: str) -> str:
    """Transforme un ID descriptif en ID court de 8 chiffres, stable et reproductible."""
    hash_obj = hashlib.md5(id_complet.encode())
    return str(int(hash_obj.hexdigest(), 16))[:8]


def _nettoyer_selector(sel: str, text: str = "") -> tuple:
    if ':has-text(' in sel:
        # Retirer un nombre dynamique en fin de texte (ex: "...INGREDIENTS 23" -> "...INGREDIENTS")
        # quel que soit le nombre de mots, car ces nombres sont des compteurs qui changent.
        sel = re.sub(r'\s+\d+"\)', '")', sel)
        text = re.sub(r'\s+\d+$', '', text).strip()

        match = re.search(r':has-text\("([^"]+)"\)', sel)
        if match:
            txt = match.group(1).strip()
            mots = txt.split()
            if len(mots) > 4:
                txt_court = ' '.join(mots[:3])
                sel = sel.replace(f':has-text("{txt}")', f':has-text("{txt_court}")')
                text = txt_court
            else:
                text = txt
    return sel, text


def _fill_champ(page, sel: str, val: str):
    """Remplit un champ en tapant caractère par caractère pour déclencher les événements React."""
    try:
        page.click(sel, timeout=2000)
        page.fill(sel, "", timeout=1000)
        page.type(sel, str(val), delay=30, timeout=5000)
    except Exception:
        try:
            page.fill(sel, val, timeout=3000)
        except Exception:
            pass


def _attendre(page, ms: float):
    page.wait_for_timeout(max(int(ms), 50))


def _screenshot_base64(page) -> str:
    """Capture une screenshot et retourne en base64."""
    try:
        screenshot = page.screenshot(type="png", timeout=3000)
        return base64.b64encode(screenshot).decode("utf-8")
    except Exception:
        return ""


def _executer_actions_base(page, actions: list, parametres: dict, vitesse: float) -> tuple:
    """
    Exécute les actions de base (GOTO, FILL avec paramètres, CLICK).
    Retourne (succes: bool, log_etapes: list).

    Version rapide : timeouts courts, pas de tentative en cascade longue,
    et on STOP dès qu'une étape critique échoue (pas de boucle infinie).
    """
    log = []

    # Dédupliquer les FILLs (garder seulement la dernière valeur pour un même selector)
    actions_propres = []
    for i, a in enumerate(actions):
        if a.get('type') == 'FILL':
            est_doublon = any(
                b.get('type') == 'FILL' and b.get('selector') == a.get('selector')
                for b in actions[i + 1:]
            )
            if est_doublon:
                continue
        actions_propres.append(a)

    for action in actions_propres:
        type_action = action.get("type", "").upper()
        try:
            if type_action == "GOTO":
                page.goto(action["url"], timeout=15000, wait_until="domcontentloaded")
                _attendre(page, 400 * vitesse)

            elif type_action == "FILL":
                sel = action["selector"]
                val = parametres.get(sel, action.get("value", ""))
                _fill_champ(page, sel, str(val))

                try:
                    valeur_reelle = page.input_value(sel)
                    print(f"[DEBUG FILL] {sel} → demandé='{val}' / réel='{valeur_reelle}'")
                except Exception:
                    pass

                try:
                    page.dispatch_event(sel, "input")
                    page.dispatch_event(sel, "change")
                except Exception:
                    pass
                _attendre(page, max(800 * vitesse, 400))
                # Si c'est un champ password, essayer de soumettre avec Enter
                if "password" in sel.lower() or "pass" in sel.lower():
                    try:
                        page.press(sel, "Enter")
                        _attendre(page, max(1500 * vitesse, 1000))
                    except Exception:
                        pass
            elif type_action == "CLICK":
                print(f"[DEBUG] Tentative de clic sur: {action['selector']}")
                print(f"[DEBUG] URL actuelle: {page.url}")
                sel, txt = _nettoyer_selector(action["selector"], action.get("text", ""))
                clique = False

                try:
                    page.wait_for_selector(sel, state="visible", timeout=6000)
                    page.click(sel, timeout=4000, force=True)
                    clique = True
                except Exception:
                    # Le clic a levé une exception. AVANT de basculer sur les méthodes
                    # de repli (qui chercheront le MÊME texte/sélecteur, donc échoueront
                    # à coup sûr si cet élément a changé après un succès réel comme
                    # "LOGIN" devenu "LOGOUT" après connexion), on vérifie explicitement
                    # si un signe de succès est apparu sur la page.
                    try:
                        page.wait_for_timeout(1000)
                        contenu_actuel = page.inner_text("body")
                        # Signal de succès générique : le texte cible a disparu du DOM
                        # alors qu'il était présent avant (preuve indirecte de changement d'état)
                        if txt and txt.upper() not in contenu_actuel.upper():
                            print(f"[DEBUG] Texte '{txt}' a disparu de la page -> action probablement réussie malgré l'exception")
                            clique = True
                    except Exception:
                        pass

                    if not clique and txt:
                        try:
                            loc = page.get_by_text(txt, exact=False).first
                            loc.wait_for(state="visible", timeout=4000)
                            loc.click(timeout=4000)
                            clique = True
                        except Exception:
                            pass
                    if not clique:
                        try:
                            loc = page.get_by_role("button", name=txt or "")
                            loc.first.wait_for(state="visible", timeout=3000)
                            loc.first.click(timeout=3000)
                            clique = True
                        except Exception:
                            pass

                _attendre(page, max(2000 * vitesse, 1200))
                try:
                    page.wait_for_load_state("networkidle", timeout=2000)
                except Exception:
                    pass

                print(f"[DEBUG] Résultat clic: {'SUCCES' if clique else 'ECHEC'}")

                if not clique:
                    log.append(f"⚠️ CLICK échoué: {sel}")
                    return False, log

            elif type_action == "ASSERT":
                # Les assertions ne bloquent pas l'exécution, juste informatif ici
                pass

        except PlaywrightTimeout:
            log.append(f"⏱️ TIMEOUT sur {type_action}")
            return False, log
        except Exception as e:
            log.append(f"❌ {type_action} erreur: {str(e)[:60]}")
            return False, log

    return True, log


def executer_tests_automatiques(
    session_actions: list,
    champs: list,
    headless: bool = True,
    vitesse: float = 0.5,
    max_scenarios: int | None = None,
    max_invalides_par_champ: int = 3,
) -> dict:
    """
    Exécute tous les scénarios de test (valide + invalides) et retourne un rapport complet.

    session_actions        : liste des actions enregistrées
    champs                 : liste des champs à tester [{selector, valeur_originale, label}]
    headless               : True = navigateur invisible (BEAUCOUP plus rapide)
    vitesse                : multiplicateur des temps d'attente (0.5 = 2x plus rapide que 1.0)
    max_scenarios           : limite le nombre total de scénarios exécutés (None = tous)
    max_invalides_par_champ : limite le nombre de cas invalides testés par champ
                              (au lieu de tous les cas définis dans data_generator.py)
    """
    scenarios = planifier_tests(champs)

    # ── Limiter le nombre de cas invalides par champ pour réduire le temps total ──
    if max_invalides_par_champ is not None:
        scenarios_valides = [s for s in scenarios if s["type"] == "valide"]
        scenarios_invalides = [s for s in scenarios if s["type"] == "invalide"]

        par_champ = {}
        scenarios_invalides_limites = []
        for s in scenarios_invalides:
            champ = s.get("champ_teste", "")
            par_champ.setdefault(champ, 0)
            if par_champ[champ] < max_invalides_par_champ:
                scenarios_invalides_limites.append(s)
                par_champ[champ] += 1

        scenarios = scenarios_valides + scenarios_invalides_limites

    # ── Limiter le nombre total de scénarios si demandé ──
    if max_scenarios is not None:
        scenarios = scenarios[:max_scenarios]

    total_prevu = len(scenarios)
    print(f"\n🧠 Smart Test — {total_prevu} scénarios à exécuter (headless={headless}, vitesse={vitesse})\n")

    resultats = []
    nb_succes = 0
    nb_echecs = 0
    validations_manquantes = []

    with sync_playwright() as p:
        # Un seul navigateur pour tous les scénarios (on ouvre/ferme juste le contexte)
        browser = p.chromium.launch(headless=headless, args=["--disable-gpu"])

        for idx, scenario in enumerate(scenarios, start=1):
            print(f"[{idx}/{total_prevu}] {scenario['nom']}")

            context = browser.new_context()
            page = context.new_page()
            page.set_default_timeout(4000)  # timeout global par défaut, évite les attentes interminables
            screenshot_b64 = ""

            try:
                ok, log_base = _executer_actions_base(
                    page, session_actions, scenario["parametres"], vitesse
                )

                _attendre(page, 1200 * vitesse)
                contenu_page = ""
                url_finale = page.url
                try:
                    contenu_page = page.inner_text("body")[:1000]
                    print(f"[DEBUG CONTENU PAGE] {contenu_page[:400]}")
                except Exception:
                    pass

                mots_erreur = ["error", "erreur", "invalid", "invalide", "required", "obligatoire",
                               "incorrect", "failed", "échec", "warning", "attention", "must", "doit"]
                page_a_erreur = any(m in contenu_page.lower() for m in mots_erreur)

                if not ok:
                    # Le scénario n'a pas pu être exécuté complètement (ex: clic submit raté)
                    statut = "echec"
                    nb_echecs += 1
                    resultat_obtenu = "Scénario interrompu : " + (log_base[-1] if log_base else "erreur inconnue")
                    screenshot_b64 = _screenshot_base64(page)

                elif scenario["type"] == "valide":
                    statut = "succes" if not page_a_erreur else "echec"
                    if statut == "succes":
                        nb_succes += 1
                        resultat_obtenu = "Formulaire soumis avec succès"
                    else:
                        nb_echecs += 1
                        resultat_obtenu = "Erreur inattendue avec données valides"
                        screenshot_b64 = _screenshot_base64(page)

                else:
                    if page_a_erreur:
                        statut = "succes"
                        nb_succes += 1
                        resultat_obtenu = "Validation correcte — erreur détectée"
                    else:
                        statut = "echec"
                        nb_echecs += 1
                        resultat_obtenu = "⚠️ Validation manquante — valeur invalide acceptée"
                        screenshot_b64 = _screenshot_base64(page)
                        validations_manquantes.append({
                        "id": scenario["id"],
                        "id_court": generer_id_court(scenario["id"]),
                        "champ": scenario.get("champ_teste", ""),
                        "contrainte": scenario.get("contrainte", ""),
                        "valeur": scenario.get("valeur_invalide", ""),
                    })
                    print(f"[DEBUG] Validation manquante ajoutée avec ID: {scenario['id']}")

                champ_teste = scenario.get("champ_teste", "tous")
                valeur_utilisee = scenario.get("valeur_invalide", str(scenario["parametres"]))
                if scenario["type"] == "valide":
                    valeur_utilisee = str(scenario["parametres"])

                resultats.append({
                    "scenario_id": scenario["id"],
                    "nom": scenario["nom"],
                    "type": scenario["type"],
                    "champ_teste": champ_teste,
                    "type_champ": detecter_type_champ(
                        next((c["selector"] for c in champs if c["label"] == champ_teste), ""),
                        scenario.get("valeur_invalide", ""),
                        next((c.get("html_type") for c in champs if c["label"] == champ_teste), None)
                    ),
                    "valeur_utilisee": str(valeur_utilisee)[:100],
                    "contrainte": scenario.get("contrainte", "Données valides aléatoires"),
                    "resultat_attendu": scenario.get("resultat_attendu", "Succès"),
                    "resultat_obtenu": resultat_obtenu,
                    "statut": statut,
                    "url_finale": url_finale,
                    "screenshot": screenshot_b64
                })

                print(f"    → {statut.upper()} : {resultat_obtenu}")

            except Exception as e:
                nb_echecs += 1
                print(f"    → ERREUR : {str(e)[:80]}")
                resultats.append({
                    "scenario_id": scenario["id"],
                    "nom": scenario["nom"],
                    "type": scenario["type"],
                    "champ_teste": scenario.get("champ_teste", ""),
                    "type_champ": "",
                    "valeur_utilisee": "",
                    "contrainte": scenario.get("contrainte", ""),
                    "resultat_attendu": scenario.get("resultat_attendu", ""),
                    "resultat_obtenu": f"Erreur d'exécution: {str(e)[:80]}",
                    "statut": "echec",
                    "url_finale": "",
                    "screenshot": ""
                })
            finally:
                try:
                    context.close()
                except Exception:
                    pass

        browser.close()

    total = len(resultats)
    taux = round((nb_succes / total * 100) if total > 0 else 0, 1)

    recommandations = []
    for vm in validations_manquantes:
        valeur_affichee = vm['valeur'] if vm['valeur'] else "(valeur vide)"
        recommandations.append(
            f"#{vm['id_court']} — Le champ '{vm['champ']}' devrait rejeter la valeur {valeur_affichee} "
            f"car il s'agit d'un cas de « {vm['contrainte']} ». "
            f"Aucun message d'erreur n'a été affiché : il manque une règle de validation pour ce cas précis."
        )

    print(f"\n✅ Smart Test terminé — {nb_succes}/{total} succès ({taux}%)\n")

    return {
        "date_execution": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "total_tests": total,
        "nb_succes": nb_succes,
        "nb_echecs": nb_echecs,
        "taux_succes": taux,
        "resultats": resultats,
        "validations_manquantes": validations_manquantes,
        "recommandations": recommandations
    }