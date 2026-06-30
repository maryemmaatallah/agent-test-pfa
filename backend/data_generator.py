"""
data_generator.py — Génération automatique de données de test
-------------------------------------------------------------
Génère des valeurs valides et invalides pour chaque type de champ.

NIVEAU 1 — mots-clés enrichis (couvre plus de noms de champs)
NIVEAU 2 — utilise le type HTML réel (htmlType) capturé par le recorder
           en priorité absolue sur la détection par nom.
"""

import random
import string
import re
from datetime import datetime, timedelta
from ai_test_generator import generer_cas_invalides_ia


# ══════════════════════════════════════════════
# DÉTECTION DU TYPE DE CHAMP
# ══════════════════════════════════════════════

def detecter_type_champ(selector: str, valeur_originale: str = "", html_type: str = None) -> str:
    """
    Détecte le type d'un champ.
    Priorité : 1) type HTML réel  2) mots-clés du sélecteur  3) format de la valeur
    """

    # ── NIVEAU 2 : type HTML réel — priorité absolue ──
    sel = selector.lower()
    
    # PRIORITÉ ABSOLUE : certains mots-clés dans le nom ne doivent JAMAIS être interprétés comme une date
    # même si html_type suggère autre chose, car ce sont presque toujours des quantités numériques
    if any(k in sel for k in ["stock", "qty", "quantity", "quantite"]):
        return "number"
    
    if html_type:
        ht = html_type.lower()
        mapping_html = {
            "email": "email", "tel": "phone", "number": "number",
            "date": "date", "datetime-local": "date", "month": "date", "week": "date",
            "password": "password", "url": "url", "select": "text",
        }
        if ht in mapping_html:
            return mapping_html[ht]
    
        # si htmlType == "text" on continue vers la détection par nom
        # car "text" est trop générique pour être fiable seul

    # ── NIVEAU 1 : mots-clés enrichis sur le sélecteur ──
    sel = selector.lower()

    if any(k in sel for k in ["email", "mail", "courriel"]):
        return "email"

    if any(k in sel for k in ["phone", "tel", "mobile", "gsm", "fax", "whatsapp"]):
        return "phone"

    if any(k in sel for k in [
        "date", "birth", "naissance", "start", "end", "debut", "fin",
        "expiry", "expiration", "echeance", "deadline", "starts", "ends",
        "from", "to", "depart", "arrivee", "checkin", "checkout"
    ]):
        return "date"

    if any(k in sel for k in ["password", "pass", "pwd", "motdepasse", "mdp"]):
        return "password"

    if any(k in sel for k in [
        "price", "prix", "amount", "montant", "stock", "qty", "quantity",
        "number", "num", "age", "discount", "remise", "percent", "pourcentage",
        "count", "score", "rating", "note", "total", "somme", "tax", "taxe",
        "weight", "poids", "height", "hauteur", "width", "largeur",
        "duration", "duree", "capacity", "capacite", "budget", "salary", "salaire"
    ]):
        return "number"

    if any(k in sel for k in ["url", "website", "site", "link", "lien"]):
        return "url"

    # Anciennes vérifications "type=xxx" dans le nom du sélecteur (fallback)
    if "type=number" in sel:
        return "number"
    if "type=email" in sel:
        return "email"
    if "type=date" in sel:
        return "date"
    if "type=tel" in sel:
        return "phone"

    # ── NIVEAU 3 : détection depuis le format de la valeur originale ──
    if valeur_originale:
        if re.match(r'^[\w.-]+@[\w.-]+\.\w+$', valeur_originale):
            return "email"
        if re.match(r'^\d{8}$', valeur_originale):
            return "phone"
        if re.match(r'^\d{4}-\d{2}-\d{2}$', valeur_originale):
            return "date"
        if re.match(r'^\d+\.?\d*$', valeur_originale):
            return "number"

    return "text"


# ══════════════════════════════════════════════
# GÉNÉRATEURS — VALEURS VALIDES
# ══════════════════════════════════════════════

def generer_valide(type_champ: str, html_min: str = None, html_max: str = None) -> str:
    if type_champ == "email":
        noms = ["alice", "bob", "charlie", "diana", "emma", "farid", "ghassen", "hana"]
        domaines = ["gmail.com", "yahoo.fr", "outlook.com", "test.tn"]
        return f"{random.choice(noms)}{random.randint(1,999)}@{random.choice(domaines)}"

    if type_champ == "phone":
        prefixes = ["20", "21", "22", "23", "50", "51", "52", "53", "90", "91", "92", "93", "94", "95", "96", "97", "98", "99"]
        return random.choice(prefixes) + str(random.randint(100000, 999999))

    if type_champ == "date":
        debut = datetime(2000, 1, 1)
        fin = datetime(2023, 12, 31)
        delta = fin - debut
        date_alea = debut + timedelta(days=random.randint(0, delta.days))
        return date_alea.strftime("%Y-%m-%d")

    if type_champ == "number":
        # Respecter min/max HTML si capturés par le recorder
        try:
            mn = int(float(html_min)) if html_min else 1
            mx = int(float(html_max)) if html_max else 100
            if mn >= mx:
                mx = mn + 100
            return str(random.randint(mn, mx))
        except (ValueError, TypeError):
            return str(random.randint(1, 100))

    if type_champ == "password":
        chars = string.ascii_letters + string.digits + "!@#$"
        return ''.join(random.choices(chars, k=random.randint(8, 12)))

    if type_champ == "url":
        return f"https://www.test{random.randint(1,999)}.com"

    # text
    mots = ["test", "alpha", "beta", "gamma", "delta", "omega", "sigma", "lambda"]
    return random.choice(mots) + str(random.randint(1, 999))


# ══════════════════════════════════════════════
# GÉNÉRATEURS — CAS INVALIDES
# ══════════════════════════════════════════════

CAS_INVALIDES = {
    "text": [
        {"valeur": "",              "contrainte": "Champ vide",           "attendu": "Erreur champ obligatoire"},
        {"valeur": "A",             "contrainte": "Trop court (1 char)",  "attendu": "Erreur longueur minimale"},
        {"valeur": "A" * 300,       "contrainte": "Trop long (300 chars)","attendu": "Erreur longueur maximale"},
        {"valeur": "12345",         "contrainte": "Nombre dans texte",    "attendu": "Erreur format"},
        {"valeur": "!@#$%^&*()",    "contrainte": "Caractères spéciaux",  "attendu": "Erreur format"},
        {"valeur": "<script>alert(1)</script>", "contrainte": "Injection XSS", "attendu": "Erreur/sanitisation"},
    ],
    "email": [
        {"valeur": "",              "contrainte": "Champ vide",           "attendu": "Erreur champ obligatoire"},
        {"valeur": "pasunmail",     "contrainte": "Sans @",               "attendu": "Erreur format email"},
        {"valeur": "test@",         "contrainte": "Sans domaine",         "attendu": "Erreur format email"},
        {"valeur": "@gmail.com",    "contrainte": "Sans nom",             "attendu": "Erreur format email"},
        {"valeur": "test@@gmail.com","contrainte": "Double @",            "attendu": "Erreur format email"},
        {"valeur": "test@gmail",    "contrainte": "Sans extension",       "attendu": "Erreur format email"},
        {"valeur": "a" * 100 + "@gmail.com", "contrainte": "Email trop long", "attendu": "Erreur longueur"},
    ],
    "phone": [
        {"valeur": "",              "contrainte": "Champ vide",           "attendu": "Erreur champ obligatoire"},
        {"valeur": "1234567",       "contrainte": "7 chiffres (trop court)","attendu": "Erreur longueur"},
        {"valeur": "123456789",     "contrainte": "9 chiffres (trop long)","attendu": "Erreur longueur"},
        {"valeur": "abcdefgh",      "contrainte": "Lettres",              "attendu": "Erreur format"},
        {"valeur": "!@#$%^&*",      "contrainte": "Caractères spéciaux",  "attendu": "Erreur format"},
        {"valeur": "00000000",      "contrainte": "Numéro invalide",      "attendu": "Erreur format"},
    ],
    "number": [
        {"valeur": "",              "contrainte": "Champ vide",           "attendu": "Erreur champ obligatoire"},
        {"valeur": "abc",           "contrainte": "Texte dans numérique", "attendu": "Erreur format"},
        {"valeur": "-1",            "contrainte": "Nombre négatif",       "attendu": "Erreur valeur minimale"},
        {"valeur": "0",             "contrainte": "Zéro",                 "attendu": "Erreur valeur minimale"},
        {"valeur": "999999",        "contrainte": "Trop grand",           "attendu": "Erreur valeur maximale"},
        {"valeur": "1.5.6",         "contrainte": "Format décimal invalide","attendu": "Erreur format"},
        {"valeur": "2024-01-01",    "contrainte": "Date dans numérique",  "attendu": "Erreur format"},
    ],
    "date": [
        {"valeur": "",              "contrainte": "Champ vide",           "attendu": "Erreur champ obligatoire"},
        {"valeur": "pasdate",       "contrainte": "Texte",                "attendu": "Erreur format date"},
        {"valeur": "32/13/2024",    "contrainte": "Format invalide",      "attendu": "Erreur format date"},
        {"valeur": "1800-01-01",    "contrainte": "Date trop ancienne",   "attendu": "Erreur plage date"},
        {"valeur": "2099-12-31",    "contrainte": "Date trop future",     "attendu": "Erreur plage date"},
        {"valeur": "12345",         "contrainte": "Nombre",               "attendu": "Erreur format date"},
    ],
    "password": [
        {"valeur": "",              "contrainte": "Champ vide",           "attendu": "Erreur champ obligatoire"},
        {"valeur": "123",           "contrainte": "Trop court",           "attendu": "Erreur longueur minimale"},
        {"valeur": "password",      "contrainte": "Sans chiffres/spéciaux","attendu": "Erreur complexité"},
        {"valeur": "12345678",      "contrainte": "Sans lettres",         "attendu": "Erreur complexité"},
        {"valeur": "A" * 300,       "contrainte": "Trop long",            "attendu": "Erreur longueur maximale"},
    ],
    "url": [
        {"valeur": "",              "contrainte": "Champ vide",           "attendu": "Erreur champ obligatoire"},
        {"valeur": "pasunurl",      "contrainte": "Sans protocole",       "attendu": "Erreur format URL"},
        {"valeur": "http://",       "contrainte": "URL incomplète",       "attendu": "Erreur format URL"},
        {"valeur": "ftp://test.com","contrainte": "Protocole invalide",   "attendu": "Erreur format URL"},
    ]
}


def get_cas_invalides(type_champ: str) -> list:
    return CAS_INVALIDES.get(type_champ, CAS_INVALIDES["text"])


def _ajouter_cas_html_constraints(cas_base: list, html_max_length=None, html_required=None) -> list:
    """
    Ajoute des cas invalides supplémentaires basés sur les contraintes HTML
    réelles capturées par le recorder (maxlength, required).
    """
    cas = list(cas_base)

    if html_max_length:
        try:
            ml = int(html_max_length)
            cas.append({
                "valeur": "X" * (ml + 10),
                "contrainte": f"Dépasse maxlength HTML ({ml})",
                "attendu": "Le navigateur devrait tronquer ou l'app doit rejeter"
            })
        except (ValueError, TypeError):
            pass

    return cas


# ══════════════════════════════════════════════
# PLANIFICATEUR DE TESTS
# ══════════════════════════════════════════════

def planifier_tests(champs: list) -> list:
    """
    Prend une liste de champs FILL et génère un plan de tests complet.

    champs = [{
        "selector": "#name",
        "valeur_originale": "fraise",
        "label": "name",
        "html_type": "text",       # optionnel — capturé par le recorder
        "html_min": None,          # optionnel
        "html_max": None,          # optionnel
        "html_max_length": None,   # optionnel
        "html_required": False    # optionnel
    }, ...]
    """
    scenarios = []

    def _type_de(champ):
        return detecter_type_champ(
            champ["selector"],
            champ.get("valeur_originale", ""),
            champ.get("html_type")
        )

    # ── Scénario 1 : données valides aléatoires ──
# ── Scénario 1 : données valides ──
    # Pour les champs de login (email/password), on réutilise la vraie valeur
    # enregistrée car le compte doit exister en base — un email aléatoire échouerait toujours.
    valeurs_valides = {}
    for champ in champs:
        t = _type_de(champ)
        sel_lower = champ["selector"].lower()
        label_lower = champ.get("label", "").lower()

        est_champ_login = (
            "login" in sel_lower or "login" in label_lower
            or "signin" in sel_lower or "signin" in label_lower
        )

        if est_champ_login and champ.get("valeur_originale"):
            valeur = champ["valeur_originale"]
        else:
            valeur = generer_valide(t, champ.get("html_min"), champ.get("html_max"))

        valeurs_valides[champ["selector"]] = {
            "valeur": valeur,
            "type": t,
            "label": champ["label"]
        }
    scenarios.append({
        "id": "valid_random",
        "nom": "✅ Test valide — données aléatoires",
        "type": "valide",
        "parametres": {sel: v["valeur"] for sel, v in valeurs_valides.items()},
        "details": valeurs_valides
    })

    # ── Scénarios 2+ : cas invalides par champ ──
    for champ in champs:
        sel = champ["selector"]
        label = champ["label"]
        t = _type_de(champ)
        print(f"[DEBUG TYPE] champ={label}, html_type_recu={champ.get('html_type')}, type_detecte={t}")
        cas = generer_cas_invalides_ia(label, t, champ.get("valeur_originale", ""))
        if not cas:  # sécurité si l'IA échoue complètement
           cas = get_cas_invalides(t)
        cas = _ajouter_cas_html_constraints(
            cas,
            html_max_length=champ.get("html_max_length"),
            html_required=champ.get("html_required")
        )

        for cas_invalide in cas:
            params = {}
            for c in champs:
                if c["selector"] == sel:
                    params[sel] = cas_invalide["valeur"]
                else:
                    sel_lower2 = c["selector"].lower()
                    label_lower2 = c.get("label", "").lower()
                    est_login2 = (
                        "login" in sel_lower2 or "login" in label_lower2
                        or "signin" in sel_lower2 or "signin" in label_lower2
                    )
                    if est_login2 and c.get("valeur_originale"):
                        params[c["selector"]] = c["valeur_originale"]
                    else:
                        t2 = _type_de(c)
                        params[c["selector"]] = generer_valide(t2, c.get("html_min"), c.get("html_max"))

            scenarios.append({
                "id": f"invalid_{label}_{cas_invalide['contrainte'].replace(' ', '_')}",
                "nom": f"❌ {label} — {cas_invalide['contrainte']}",
                "type": "invalide",
                "champ_teste": label,
                "contrainte": cas_invalide["contrainte"],
                "valeur_invalide": cas_invalide["valeur"],
                "resultat_attendu": cas_invalide["attendu"],
                "parametres": params
            })

    return scenarios