import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, jsonify
from database import db, CasDeTest, ResultatTest
from agent import lancer_test

app = Flask(__name__)

# CORS manuel sans flask-cors
@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response

@app.route("/api/<path:path>", methods=["OPTIONS"])
def options(path):
    return jsonify({}), 200

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///tests.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

with app.app_context():
    db.create_all()
    if CasDeTest.query.count() == 0:
        cas_defaut = [
            CasDeTest(
                nom="Login valide (admin)",
                instruction="Connecte-toi avec username=admin et password=1234, vérifie que tu arrives sur le dashboard",
                url="http://127.0.0.1:5000/login",
                categorie="Authentification"
            ),
            CasDeTest(
                nom="Login invalide (mauvais mot de passe)",
                instruction="Connecte-toi avec username=admin et password=mauvais123, vérifie que le login est refusé",
                url="http://127.0.0.1:5000/login",
                categorie="Authentification"
            ),
            CasDeTest(
                nom="Accès dashboard sans connexion",
                instruction="Accède directement au dashboard sans connexion, vérifie que tu es redirigé vers login",
                url="http://127.0.0.1:5000/dashboard",
                categorie="Sécurité"
            ),
        ]
        db.session.add_all(cas_defaut)
        db.session.commit()

@app.route("/api/cas", methods=["GET"])
def get_cas():
    cas = CasDeTest.query.all()
    return jsonify([c.to_dict() for c in cas])

@app.route("/api/cas", methods=["POST"])
def creer_cas():
    data = request.json
    cas = CasDeTest(
        nom=data["nom"],
        instruction=data["instruction"],
        url=data["url"],
        categorie=data.get("categorie", "General")
    )
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
    print(f"\n🚀 Exécution : {cas.nom}")
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
        print(f"\n🚀 Exécution : {cas.nom}")
        resultat_str = lancer_test(cas.nom, cas.instruction, cas.url)
        statut = "succes" if "succ" in resultat_str.lower() else "echec"
        resultat = ResultatTest(cas_id=cas.id, statut=statut, message=resultat_str)
        db.session.add(resultat)
        resultats.append(resultat)
    db.session.commit()
    return jsonify([r.to_dict() for r in resultats])

@app.route("/api/resultats", methods=["GET"])
def get_resultats():
    resultats = ResultatTest.query.order_by(ResultatTest.date_execution.desc()).all()
    return jsonify([r.to_dict() for r in resultats])

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

if __name__ == "__main__":
    app.run(debug=True, port=8000)