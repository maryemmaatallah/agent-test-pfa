import os
from groq import Groq
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def demander_agent(instruction, contexte_page, historique):
    historique_str = "\n".join(historique) if historique else "Aucune action encore"
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": """Tu es un agent de test web. 
                Tu reçois une instruction, le contenu de la page actuelle, et l'historique des actions déjà faites.
                Tu réponds avec UNE SEULE action à la fois, rien d'autre, aucune explication.
                
                Format STRICT (une seule ligne) :
                GOTO: <url>
                CLICK: <sélecteur CSS>
                FILL: <sélecteur CSS> | <texte>
                DONE: <résultat du test>
                
                RÈGLES IMPORTANTES :
                - Ne répète JAMAIS une action déjà faite
                - Si tu es déjà sur la bonne page, passe à l'étape suivante
                - Pour chercher sur Google, utilise FILL: textarea | <texte>
                - Quand l'objectif est atteint, utilise DONE
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
    premiere_ligne = response.choices[0].message.content.strip().split("\n")[0]
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
        except:
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
        except:
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
        browser = p.chromium.launch(headless=True)
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

