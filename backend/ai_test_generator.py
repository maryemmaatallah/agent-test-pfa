"""
ai_test_generator.py — Génération de cas de test invalides via Ollama local
-----------------------------------------------------------------------------
Utilise un format ligne-par-ligne (plus robuste qu'un JSON strict pour un
modèle 8B) plutôt qu'un tableau JSON, qui est souvent mal respecté.
"""

import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.1:8b"


def generer_cas_invalides_ia(nom_champ: str, type_champ: str, valeur_originale: str = "") -> list:
    """
    Demande à Ollama de générer des cas de test invalides intelligents,
    adaptés au nom et au type réel du champ, dans un format simple à parser
    (une ligne par cas : valeur ||| contrainte ||| attendu).
    """
    prompt = f"""Tu es un expert en test de logiciels. Pour un champ de formulaire web nommé "{nom_champ}" de type "{type_champ}" (valeur exemple actuelle : "{valeur_originale}"), génère exactement 5 cas de test INVALIDES pertinents pour détecter des failles de validation.

Adapte les cas au NOM du champ et à son contexte métier probable (ex: si le nom suggère un stock ou une quantité, teste des nombres négatifs ou du texte ; si le nom suggère un nom/titre, teste vide, trop court, trop long, caractères spéciaux).

Réponds UNIQUEMENT avec 5 lignes, AUCUN autre texte, AUCUNE numérotation, AUCUNE explication. Chaque ligne doit suivre EXACTEMENT ce format avec le séparateur ||| (trois barres verticales) :
valeur||| description courte de la contrainte testée||| comportement attendu de l'application

La colonne "valeur" doit être la VALEUR LITTÉRALE EXACTE à taper dans le champ (jamais une description en mots).

Exemples corrects de lignes (le format, pas le contenu à copier) :
|||Champ vide|||Erreur de champ obligatoire
A|||Trop court (1 caractère)|||Erreur longueur minimale
@#$%^&|||Caractères spéciaux interdits|||Erreur de format

Exemples INCORRECTS à ne JAMAIS faire (descriptions au lieu de vraies valeurs) :
nom trop court|||...|||...   ← INTERDIT, ceci décrit le test au lieu de donner une vraie valeur
valeur vide|||...|||...      ← INTERDIT, écris juste ||| (rien avant le premier séparateur) pour signifier vide

Génère maintenant tes 5 lignes pour le champ "{nom_champ}", en choisissant TOI-MÊME les 5 cas les plus pertinents selon son nom et son contexte métier probable :"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False
            },
            timeout=120
        )
        response.raise_for_status()
        texte = response.json().get("response", "").strip()

        cas_valides = []
        for ligne in texte.split("\n"):
            ligne = ligne.strip()
            if "|||" not in ligne:
                continue
            parties = ligne.split("|||")
            if len(parties) < 3:
                continue
            valeur = parties[0].strip()
            contrainte = parties[1].strip()
            attendu = parties[2].strip()
            if contrainte and attendu:  # la valeur peut être vide volontairement
                cas_valides.append({
                    "valeur": valeur,
                    "contrainte": contrainte,
                    "attendu": attendu
                })

        if cas_valides:
            print(f"[IA] {len(cas_valides)} cas générés pour '{nom_champ}' ({type_champ})")
            return cas_valides[:5]  # on garde au maximum 5 cas même si plus de lignes valides

        print(f"[IA] Aucune ligne valide extraite pour '{nom_champ}' — réponse brute : {texte[:300]}")

    except Exception as e:
        print(f"[IA] Erreur génération Ollama pour '{nom_champ}': {e}")

    # Fallback si Ollama échoue complètement
    return [{"valeur": "", "contrainte": "Champ vide", "attendu": "Erreur champ obligatoire"}]