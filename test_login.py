import os
from groq import Groq
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
from reporter import generer_rapport

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
                Tu réponds avec UNE SEULE action à la fois, rien d'autre.
                
                Format STRICT (une seule ligne) :
                GOTO: <url>
                CLICK: <sélecteur CSS>
                FILL: <sélecteur CSS> | <texte>
                DONE: <résultat du test>
                
                RÈGLES :
                - Ne répète jamais une action déjà faite
                - Si tu vois "Bonjour" ou "Tableau de bord" ou "Connexion réussie" -> DONE: succès - connecté au dashboard
                - Si tu vois "Identifiants incorrects" -> DONE: succès - login refusé comme attendu
                - Si tu es redirigé vers /login depuis /dashboard -> DONE: succès - accès refusé comme attendu
                - Si les champs sont vides et formulaire toujours visible -> DONE: succès - champs vides refusés comme attendu
                - Si après déconnexion tu vois la page d'accueil ou login -> DONE: succès - déconnexion réussie
                - Pour remplir un champ utilise son id: FILL: #username | valeur
                - Pour cliquer sur un lien texte utilise: CLICK: a[href='/logout']
                """
            },
            {
                "role": "user",
                "content": f"""Instruction: {instruction}

Actions déjà effectuées:
{historique_str}

Contenu actuel de la page:
{contexte_page}

Prochaine action (UNE SEULE ligne) :"""
            }
        ]
    )
    return response.choices[0].message.content.strip().split("\n")[0]

def executer_action(page, action):
    action = action.strip()
    print(f"🤖 Agent décide : {action}")

    if action.startswith("GOTO:"):
        url = action.replace("GOTO:", "").strip()
        page.goto(url)
        page.wait_for_timeout(1000)
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
    print(f"\n{'='*50}")
    print(f"🧪 TEST : {nom_test}")
    print(f"📋 {instruction}")
    print(f"{'='*50}")

    historique = []
    resultat_final = "non terminé"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url_depart)
        page.wait_for_timeout(1000)
        historique.append(f"GOTO: {url_depart} -> succès")

        for etape in range(10):
            print(f"\n--- Étape {etape + 1} ---")
            contenu = page.inner_text("body")[:800]
            action = demander_agent(instruction, contenu, historique)
            termine, resultat = executer_action(page, action)
            historique.append(f"{action} -> exécuté")
            if termine:
                resultat_final = resultat
                break
            page.wait_for_timeout(1000)

        browser.close()

    return resultat_final

# =============================
# TOUS LES TESTS
# =============================
resultats = []
print("\n🚀 Démarrage de la suite de tests...")

r = lancer_test(
    nom_test="Login valide (admin)",
    instruction="Connecte-toi avec username=admin et password=1234, vérifie que tu arrives sur le dashboard",
    url_depart="http://127.0.0.1:5000/login"
)
resultats.append(("Login valide (admin)", r))

r = lancer_test(
    nom_test="Login valide (maryem)",
    instruction="Connecte-toi avec username=maryem et password=pfa2025, vérifie que tu arrives sur le dashboard",
    url_depart="http://127.0.0.1:5000/login"
)
resultats.append(("Login valide (maryem)", r))

r = lancer_test(
    nom_test="Login invalide (mauvais mot de passe)",
    instruction="Connecte-toi avec username=admin et password=mauvais123, vérifie que le login est refusé avec un message d'erreur",
    url_depart="http://127.0.0.1:5000/login"
)
resultats.append(("Login invalide (mauvais mot de passe)", r))

r = lancer_test(
    nom_test="Login invalide (utilisateur inexistant)",
    instruction="Connecte-toi avec username=hacker et password=test123, vérifie que le login est refusé",
    url_depart="http://127.0.0.1:5000/login"
)
resultats.append(("Login invalide (utilisateur inexistant)", r))

r = lancer_test(
    nom_test="Login champs vides",
    instruction="Clique sur le bouton login sans remplir les champs, vérifie que c'est refusé",
    url_depart="http://127.0.0.1:5000/login"
)
resultats.append(("Login champs vides", r))

r = lancer_test(
    nom_test="Accès dashboard sans connexion",
    instruction="Accède directement au dashboard sans connexion, vérifie que tu es redirigé vers login",
    url_depart="http://127.0.0.1:5000/dashboard"
)
resultats.append(("Accès dashboard sans connexion", r))

r = lancer_test(
    nom_test="Déconnexion",
    instruction="Connecte-toi avec username=admin et password=1234, puis clique sur le lien Se déconnecter, vérifie que tu reviens à la page d'accueil",
    url_depart="http://127.0.0.1:5000/login"
)
resultats.append(("Déconnexion", r))

# =============================
# RÉSUMÉ + RAPPORT
# =============================
print(f"\n{'='*50}")
print("📊 RÉSUMÉ DES TESTS")
print(f"{'='*50}")
for nom, res in resultats:
    emoji = "✅" if "succ" in res.lower() else "❌"
    print(f"{emoji} {nom} : {res}")

generer_rapport(resultats)
