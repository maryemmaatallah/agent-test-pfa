import sys
import os
import hashlib
import json
import threading
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, jsonify, send_from_directory
from database import db, CasDeTest, ResultatTest, SessionEnregistree, ResultatReplay, ResultatSmartTest
from agent import lancer_test
from recorder import demarrer_enregistrement
from replay import rejouer_session
app = Flask(__name__)

@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS, PUT"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Max-Age"] = "3600"
    return response

PLATFORM_USERS = {
    "admin": hashlib.md5("admin123".encode()).hexdigest(),
    "maryem": hashlib.md5("pfa2025".encode()).hexdigest()
}

app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://agent_user:admin@localhost:5432/agent_test_db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

with app.app_context():
    db.create_all()
    if CasDeTest.query.count() == 0:
        cas_defaut = [
            CasDeTest(nom="Login valide (admin)", instruction="Connecte-toi avec username=admin et password=1234, vérifie que tu arrives sur le dashboard", url="http://127.0.0.1:5000/login", categorie="Authentification"),
            CasDeTest(nom="Login invalide (mauvais mot de passe)", instruction="Connecte-toi avec username=admin et password=mauvais123, vérifie que le login est refusé", url="http://127.0.0.1:5000/login", categorie="Authentification"),
            CasDeTest(nom="Accès dashboard sans connexion", instruction="Accède directement au dashboard sans connexion, vérifie que tu es redirigé vers login", url="http://127.0.0.1:5000/dashboard", categorie="Sécurité"),
        ]
        db.session.add_all(cas_defaut)
        db.session.commit()

# ══════════════════════════════════════════════
# AUTH
# ══════════════════════════════════════════════
@app.route("/api/platform/login", methods=["POST", "OPTIONS"])
def platform_login():
    if request.method == "OPTIONS":
        return jsonify({}), 200
    data = request.json
    username = data.get("username")
    password = hashlib.md5(data.get("password", "").encode()).hexdigest()
    if username in PLATFORM_USERS and PLATFORM_USERS[username] == password:
        return jsonify({"success": True, "username": username})
    return jsonify({"success": False, "message": "Identifiants incorrects"}), 401

# ══════════════════════════════════════════════
# CAS DE TEST
# ══════════════════════════════════════════════
@app.route("/api/cas", methods=["GET"])
def get_cas():
    return jsonify([c.to_dict() for c in CasDeTest.query.all()])

@app.route("/api/cas", methods=["POST"])
def creer_cas():
    data = request.json
    cas = CasDeTest(nom=data["nom"], instruction=data["instruction"], url=data["url"], categorie=data.get("categorie", "General"))
    db.session.add(cas)
    db.session.commit()
    return jsonify(cas.to_dict()), 201

@app.route("/api/cas/<int:id>", methods=["DELETE"])
def supprimer_cas(id):
    cas = CasDeTest.query.get_or_404(id)
    db.session.delete(cas)
    db.session.commit()
    return jsonify({"message": "Supprimé"})

@app.route("/api/executer/<int:id>", methods=["POST"])
def executer_un_test(id):
    cas = CasDeTest.query.get_or_404(id)
    resultat_str = lancer_test(cas.nom, cas.instruction, cas.url)
    statut = "succes" if "succ" in resultat_str.lower() else "echec"
    resultat = ResultatTest(cas_id=cas.id, statut=statut, message=resultat_str)
    db.session.add(resultat)
    db.session.commit()
    return jsonify(resultat.to_dict())

@app.route("/api/executer-tous", methods=["POST"])
def executer_tous():
    cas_list = CasDeTest.query.all()
    resultats = []
    for cas in cas_list:
        resultat_str = lancer_test(cas.nom, cas.instruction, cas.url)
        statut = "succes" if "succ" in resultat_str.lower() else "echec"
        resultat = ResultatTest(cas_id=cas.id, statut=statut, message=resultat_str)
        db.session.add(resultat)
        resultats.append(resultat)
    db.session.commit()
    return jsonify([r.to_dict() for r in resultats])

@app.route("/api/resultats", methods=["GET"])
def get_resultats():
    return jsonify([r.to_dict() for r in ResultatTest.query.order_by(ResultatTest.date_execution.desc()).all()])

@app.route("/api/stats", methods=["GET"])
def get_stats():
    total_cas = CasDeTest.query.count()
    total_executions = ResultatTest.query.count()
    succes = ResultatTest.query.filter_by(statut="succes").count()
    echecs = ResultatTest.query.filter_by(statut="echec").count()
    return jsonify({
        "total_cas": total_cas,
        "total_executions": total_executions,
        "succes": succes,
        "echecs": echecs,
        "taux_succes": round((succes / total_executions * 100) if total_executions > 0 else 0, 1)
    })

# ══════════════════════════════════════════════
# RECORD & REPLAY
# ══════════════════════════════════════════════
_enregistrement_en_cours = {"actif": False, "actions": [], "thread": None}

@app.route("/api/sessions", methods=["GET"])
def get_sessions():
    sessions = SessionEnregistree.query.order_by(SessionEnregistree.date_creation.desc()).all()
    return jsonify([s.to_dict_light() for s in sessions])

@app.route("/api/sessions/<int:id>", methods=["GET"])
def get_session(id):
    return jsonify(SessionEnregistree.query.get_or_404(id).to_dict())

@app.route("/api/sessions/<int:id>", methods=["DELETE"])
def supprimer_session(id):
    session = SessionEnregistree.query.get_or_404(id)
    db.session.delete(session)
    db.session.commit()
    return jsonify({"message": "Session supprimée"})

@app.route("/api/sessions/enregistrer", methods=["POST"])
def demarrer_record():
    if _enregistrement_en_cours["actif"]:
        return jsonify({"error": "Un enregistrement est déjà en cours"}), 409
    data = request.json
    nom = data.get("nom", f"Session {len(SessionEnregistree.query.all()) + 1}")
    url = data.get("url", "http://127.0.0.1:5000")
    nom_application = data.get("nom_application", "Sans nom")
    _enregistrement_en_cours["actif"] = True
    _enregistrement_en_cours["actions"] = []

    def run():
        def on_action(action):
            _enregistrement_en_cours["actions"].append(action)
        actions = demarrer_enregistrement(url, callback_action=on_action)
        with app.app_context():
            session = SessionEnregistree(nom=nom, url_depart=url, nom_application=nom_application)
            session.actions = actions
            db.session.add(session)
            db.session.commit()
        _enregistrement_en_cours["actif"] = False

    t = threading.Thread(target=run, daemon=True)
    t.start()
    _enregistrement_en_cours["thread"] = t
    return jsonify({"message": f"Enregistrement démarré sur {url}.", "nom": nom, "url": url})
@app.route("/api/sessions/statut", methods=["GET"])
def statut_enregistrement():
    return jsonify({
        "actif": _enregistrement_en_cours["actif"],
        "nb_actions_capturees": len(_enregistrement_en_cours["actions"])
    })

@app.route("/recorder_browser.js")
def serve_recorder():
    return send_from_directory("static", "recorder_browser.js")

@app.route("/api/sessions/<int:id>/parametres", methods=["GET"])
def get_parametres_session(id):
    session = SessionEnregistree.query.get_or_404(id)
    actions = session.actions
    parametres = []
    vus = set()
    for a in actions:
        if a.get("type") == "FILL":
            sel = a.get("selector", "")
            val = a.get("value", "")
            # Exclure password ET username (credentials non modifiables)
            est_credential = (
                "password" in sel.lower() or
                "pass" in sel.lower() or
                sel in ["#username", "#email", "[name='username']", "input[type='email']"]
            )
            if sel not in vus and not est_credential:
                parametres.append({
                    "selector": sel,
                    "valeur_originale": val,
                    "label": sel.replace("#", "").replace("[", "").replace("]", "").replace('"', "").replace("placeholder=", "")
                })
                vus.add(sel)
    return jsonify(parametres)

@app.route("/api/sessions/<int:id>/replay", methods=["POST"])
def replay_session(id):
    """
    Rejoue une session.
    Body JSON : {
        "headless": false,
        "vitesse": 1.0,
        "parametres": {"#ingredientName": "mangue", "#ingredientStock": "5"}  ← optionnel
    }
    """
    session = SessionEnregistree.query.get_or_404(id)
    data = request.json or {}
    headless = data.get("headless", False)
    vitesse = float(data.get("vitesse", 1.0))
    parametres = data.get("parametres", {})  # {selector: nouvelle_valeur}

    # Appliquer les paramètres sur une copie des actions
    actions = session.actions
    if parametres:
        actions_modifiees = []
        for a in actions:
            a_copie = dict(a)
            if a_copie.get("type") == "FILL" and a_copie.get("selector") in parametres:
                nouvelle_val = parametres[a_copie["selector"]]
                a_copie["value"] = nouvelle_val
                a_copie["displayValue"] = nouvelle_val
            # Mettre à jour les assertions si elles référencent une ancienne valeur
            if a_copie.get("type") == "ASSERT":
                for sel, nouvelle_val in parametres.items():
                    ancienne_val = next((x.get("value","") for x in actions if x.get("selector") == sel and x.get("type") == "FILL"), None)
                    if ancienne_val and ancienne_val.lower() in a_copie.get("text","").lower():
                        a_copie["text"] = a_copie["text"].replace(ancienne_val, nouvelle_val)
            actions_modifiees.append(a_copie)
        actions = actions_modifiees

    print(f"\n▶️  Replay de '{session.nom}' — {len(actions)} actions")
    resultat = rejouer_session(actions, headless=headless, vitesse=vitesse)

    replay = ResultatReplay(
        session_id=session.id,
        statut=resultat["statut"],
        nb_succes=resultat["nb_succes"],
        nb_echecs=resultat["nb_echecs"],
        taux_succes=resultat["taux_succes"],
        log_json=json.dumps(resultat["log"], ensure_ascii=False)
    )
    db.session.add(replay)
    db.session.commit()
    return jsonify({**replay.to_dict(), "page_finale": resultat.get("page_finale", "")})

@app.route("/api/sessions/<int:id>/replays", methods=["GET"])
def get_replays_session(id):
    replays = ResultatReplay.query.filter_by(session_id=id).order_by(ResultatReplay.date_execution.desc()).all()
    return jsonify([r.to_dict() for r in replays])

@app.route("/api/sessions/sauvegarder", methods=["POST"])
def sauvegarder_actions_manuelles():
    data = request.json
    nom = data.get("nom", "Session sans nom")
    url = data.get("url", "")
    actions = data.get("actions", [])
    if not actions:
        return jsonify({"error": "Aucune action fournie"}), 400
    session = SessionEnregistree(nom=nom, url_depart=url)
    session.actions = actions
    db.session.add(session)
    db.session.commit()
    return jsonify(session.to_dict_light()), 201
import threading
_smart_test_resultats = {}

@app.route("/api/smart-test/<int:id>", methods=["POST", "OPTIONS"])
def smart_test(id):
    if request.method == "OPTIONS":
        response = jsonify({})
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return response, 200

    try:
        from smart_replay import executer_tests_automatiques
        import json

        session = SessionEnregistree.query.get_or_404(id)
        actions = json.loads(session.actions_json)

        champs = []
        for a in actions:
            if a.get("type") == "FILL":
                sel = a.get("selector", "")
                val = a.get("value", "")
                est_credential = "password" in sel.lower() or "pass" in sel.lower() or sel in ["#username", "#email"]
                if not est_credential:
                    label = sel.replace("#", "").replace("[", "").replace("]", "").replace('"', "").split("=")[-1]
                    champs.append({
                        "selector": sel,
                        "valeur_originale": val,
                        "label": label,
                        "html_type": a.get("htmlType"),
                        "html_min": a.get("htmlMin"),
                        "html_max": a.get("htmlMax"),
                        "html_max_length": a.get("htmlMaxLength"),
                        "html_required": a.get("htmlRequired")
                    })

        if not champs:
            resp = jsonify({"erreur": "Aucun champ FILL trouvé"})
            resp.headers["Access-Control-Allow-Origin"] = "*"
            return resp, 400

        # Lancer en arrière-plan
        _smart_test_resultats[id] = {"statut": "en_cours"}

        def run():
            with app.app_context():
                try:
                    resultats = executer_tests_automatiques(actions, champs, headless=False)
                    _smart_test_resultats[id] = {"statut": "termine", **resultats}

                    # ── Persistance en base de données ──
                    session_obj = SessionEnregistree.query.get(id)
                    enregistrement = ResultatSmartTest(
                        session_id=id,
                        nom_session=session_obj.nom if session_obj else "",
                        total_tests=resultats.get("total_tests", 0),
                        nb_succes=resultats.get("nb_succes", 0),
                        nb_echecs=resultats.get("nb_echecs", 0),
                        taux_succes=resultats.get("taux_succes", 0.0),
                        resultats_json=json.dumps(resultats.get("resultats", []), ensure_ascii=False),
                        validations_manquantes_json=json.dumps(resultats.get("validations_manquantes", []), ensure_ascii=False),
                        recommandations_json=json.dumps(resultats.get("recommandations", []), ensure_ascii=False),
                    )
                    db.session.add(enregistrement)
                    db.session.commit()

                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    _smart_test_resultats[id] = {"statut": "erreur", "erreur": str(e)}

        t = threading.Thread(target=run, daemon=True)
        t.start()

        resp = jsonify({"statut": "en_cours", "message": "Tests démarrés"})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    except Exception as e:
        import traceback
        traceback.print_exc()
        resp = jsonify({"erreur": str(e)})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp, 500


@app.route("/api/smart-test/<int:id>/statut", methods=["GET"])
def smart_test_statut(id):
    resultat = _smart_test_resultats.get(id, {"statut": "inconnu"})
    resp = jsonify(resultat)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp

@app.route("/api/smart-test/historique", methods=["GET"])
def smart_test_historique():
    """Liste tous les rapports Smart Test déjà générés, peu importe quand"""
    resultats = ResultatSmartTest.query.order_by(ResultatSmartTest.date_execution.desc()).all()
    resp = jsonify([r.to_dict() for r in resultats])
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


@app.route("/api/smart-test/historique/<int:id>", methods=["GET"])
def smart_test_historique_detail(id):
    """Récupère un rapport Smart Test précis depuis la base, par son ID de rapport"""
    resultat = ResultatSmartTest.query.get_or_404(id)
    resp = jsonify(resultat.to_dict())
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp

@app.route("/api/smart-test/historique/<int:id>", methods=["DELETE"])
def supprimer_smart_test_historique(id):
    resultat = ResultatSmartTest.query.get_or_404(id)
    db.session.delete(resultat)
    db.session.commit()
    resp = jsonify({"message": "Rapport supprimé"})
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp

if __name__ == "__main__":
    app.run(debug=True, port=8000)