import os
import ollama
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

# Nom du modèle local installé via "ollama pull llama3.2:3b"
MODELE_LOCAL = "llama3.1:8b"


def demander_agent(instruction, contexte_page, historique):
    historique_str = "\n".join(historique) if historique else "Aucune action encore"

    response = ollama.chat(
        model=MODELE_LOCAL,
        messages=[
            {
                "role": "system",
                "content": """Tu es un agent de test web.
Tu réponds avec UNE SEULE action à la fois, rien d'autre.

Format STRICT (une seule ligne) :
GOTO: <url>
CLICK: <sélecteur CSS>
FILL: <sélecteur CSS> | <texte>
DONE: <résultat du test>

RÈGLES :
- Ne répète jamais une action déjà faite
- Pour remplir username utilise: FILL: #username | valeur
- Pour remplir password utilise: FILL: #password | valeur
- Pour soumettre le formulaire utilise: CLICK: #btn-login
- Pour se déconnecter utilise: CLICK: a[href='/logout']
- Si tu vois "Bonjour" ou "Tableau de bord" -> DONE: succès - connecté au dashboard
- Si tu vois "Identifiants incorrects" -> DONE: succès - login refusé comme attendu
- Si redirigé vers /login depuis /dashboard -> DONE: succès - accès refusé comme attendu
- Si formulaire vide soumis et toujours visible -> DONE: succès - champs vides refusés
- Si après déconnexion tu vois page accueil -> DONE: succès - déconnexion réussie
"""
            },
            {
                "role": "user",
                "content": f"""Instruction globale: {instruction}

Actions déjà effectuées:
{historique_str}

Contenu actuel de la page:
{contexte_page}

Quelle est la prochaine action à faire ? (UNE SEULE ligne)"""
            }
        ]
    )
    # Structure de réponse Ollama différente de Groq :
    # response["message"]["content"] au lieu de response.choices[0].message.content
    premiere_ligne = response["message"]["content"].strip().split("\n")[0]
    return premiere_ligne


def executer_action(page, action):
    action = action.strip()
    print(f"🤖 Agent décide : {action}")

    if action.startswith("GOTO:"):
        url = action.replace("GOTO:", "").strip()
        page.goto(url)
        page.wait_for_timeout(2000)
        print(f"✅ Navigation vers : {url}")

    elif action.startswith("CLICK:"):
        selecteur = action.replace("CLICK:", "").strip()
        try:
            page.click(selecteur, timeout=5000)
            page.wait_for_timeout(1000)
            print(f"✅ Clic sur : {selecteur}")
        except Exception:
            print(f"⚠️ Clic échoué sur : {selecteur}")

    elif action.startswith("FILL:"):
        parties = action.replace("FILL:", "").strip().split("|")
        selecteur = parties[0].strip()
        texte = parties[1].strip()
        try:
            page.fill(selecteur, texte)
            page.wait_for_timeout(500)
            print(f"✅ Remplissage : {selecteur} = {texte}")
            if "password" in selecteur or "pass" in selecteur.lower():
                page.keyboard.press("Enter")
                page.wait_for_timeout(1000)
                print(f"✅ Entrée appuyée")
        except Exception:
            print(f"⚠️ Remplissage échoué : {selecteur}")

    elif action.startswith("DONE:"):
        resultat = action.replace("DONE:", "").strip()
        print(f"\n🏁 Résultat : {resultat}")
        return True, resultat

    return False, None


def lancer_test(nom_test, instruction, url_depart):
    print(f"\n🚀 Lancement : {nom_test}")
    print(f"📋 Instruction : {instruction}")
    print(f"🌐 URL : {url_depart}\n")

    historique = []
    resultat_final = "non terminé"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(url_depart)
        page.wait_for_timeout(2000)
        historique.append(f"GOTO: {url_depart} -> succès")

        for etape in range(8):
            print(f"\n--- Étape {etape + 1} ---")
            contenu = page.inner_text("body")[:800]
            action = demander_agent(instruction, contenu, historique)
            termine, resultat = executer_action(page, action)
            historique.append(f"{action} -> exécuté")
            if termine:
                resultat_final = resultat
                break
            page.wait_for_timeout(1500)

        browser.close()

    return resultat_final