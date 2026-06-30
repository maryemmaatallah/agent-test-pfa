from flask import Flask, request, redirect, session, render_template_string

app = Flask(__name__)
app.secret_key = "secret123"

USERS = {"admin": "1234", "maryem": "pfa2025"}
livres = [
    {"id": 1, "titre": "Python pour débutants", "auteur": "Jean Dupont"},
    {"id": 2, "titre": "Flask en pratique", "auteur": "Marie Martin"},
]
next_livre_id = 3

HOME = """<!DOCTYPE html><html><head><title>App Demo PFA</title></head>
<body>
    <h1>Bienvenue sur App Demo PFA</h1>
    <a href="/login">Se connecter</a>
</body></html>"""

LOGIN = """<!DOCTYPE html><html><head><title>Login</title></head>
<body>
    <h1>Connexion</h1>
    {% if erreur %}<p style="color:red" id="erreur">{{ erreur }}</p>{% endif %}
    <form method="POST">
        <input type="text" name="username" id="username" placeholder="Utilisateur"><br><br>
        <input type="password" name="password" id="password" placeholder="Mot de passe"><br><br>
        <button type="submit" id="btn-login">Se connecter</button>
    </form>
</body></html>"""

DASHBOARD = """<!DOCTYPE html><html><head><title>Dashboard</title></head>
<body>
    <h1>Tableau de bord</h1>
    <p>Bonjour <strong>{{ username }}</strong> ! Connexion réussie.</p>
    <a href="/livres">📚 Gérer les livres</a> |
    <a href="/logout">Se déconnecter</a>
</body></html>"""

LIVRES = """<!DOCTYPE html><html><head><title>Livres</title></head>
<body>
    <h1>Gestion des Livres</h1>
    <a href="/livres/ajouter" id="btn-ajouter-livre">➕ Ajouter un livre</a>
    <table border="1" id="table-livres">
        <tr><th>ID</th><th>Titre</th><th>Auteur</th><th>Actions</th></tr>
        {% for livre in livres %}
        <tr id="livre-{{ livre.id }}">
            <td>{{ livre.id }}</td>
            <td class="titre-{{ livre.id }}">{{ livre.titre }}</td>
            <td>{{ livre.auteur }}</td>
            <td>
                <a href="/livres/modifier/{{ livre.id }}" id="modifier-{{ livre.id }}">✏️ Modifier</a> |
                <a href="/livres/supprimer/{{ livre.id }}" id="supprimer-{{ livre.id }}">🗑️ Supprimer</a>
            </td>
        </tr>
        {% endfor %}
    </table>
    <br><a href="/dashboard">Retour</a>
</body></html>"""

AJOUTER_LIVRE = """<!DOCTYPE html><html><head><title>Ajouter Livre</title></head>
<body>
    <h1>Ajouter un Livre</h1>
    <form method="POST">
        <input type="text" name="titre" id="titre" placeholder="Titre du livre"><br><br>
        <input type="text" name="auteur" id="auteur" placeholder="Auteur"><br><br>
        <button type="submit" id="btn-ajouter">Ajouter</button>
    </form>
    <br><a href="/livres">Retour</a>
</body></html>"""

MODIFIER_LIVRE = """<!DOCTYPE html><html><head><title>Modifier Livre</title></head>
<body>
    <h1>Modifier le Livre</h1>
    <form method="POST">
        <input type="text" name="titre" id="titre" value="{{ livre.titre }}"><br><br>
        <input type="text" name="auteur" id="auteur" value="{{ livre.auteur }}"><br><br>
        <button type="submit" id="btn-modifier">Modifier</button>
    </form>
    <br><a href="/livres">Retour</a>
</body></html>"""

@app.route("/")
def home():
    return render_template_string(HOME)

@app.route("/login", methods=["GET", "POST"])
def login():
    erreur = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if username in USERS and USERS[username] == password:
            session["user"] = username
            return redirect("/dashboard")
        else:
            erreur = "Identifiants incorrects !"
    return render_template_string(LOGIN, erreur=erreur)

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")
    return render_template_string(DASHBOARD, username=session["user"])

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/livres")
def liste_livres():
    if "user" not in session:
        return redirect("/login")
    return render_template_string(LIVRES, livres=livres)

@app.route("/livres/ajouter", methods=["GET", "POST"])
def ajouter_livre():
    global next_livre_id
    if "user" not in session:
        return redirect("/login")
    if request.method == "POST":
        livres.append({"id": next_livre_id, "titre": request.form["titre"], "auteur": request.form["auteur"]})
        next_livre_id += 1
        return redirect("/livres")
    return render_template_string(AJOUTER_LIVRE)

@app.route("/livres/modifier/<int:id>", methods=["GET", "POST"])
def modifier_livre(id):
    if "user" not in session:
        return redirect("/login")
    livre = next((l for l in livres if l["id"] == id), None)
    if not livre:
        return "Livre non trouvé", 404
    if request.method == "POST":
        livre["titre"] = request.form["titre"]
        livre["auteur"] = request.form["auteur"]
        return redirect("/livres")
    return render_template_string(MODIFIER_LIVRE, livre=livre)

@app.route("/livres/supprimer/<int:id>")
def supprimer_livre(id):
    global livres
    if "user" not in session:
        return redirect("/login")
    livres = [l for l in livres if l["id"] != id]
    return redirect("/livres")

if __name__ == "__main__":
    app.run(debug=True, port=5000)