from flask import Flask, request, redirect, url_for, session, render_template_string

app = Flask(__name__)
app.secret_key = "secret123"

USERS = {"admin": "1234", "maryem": "pfa2025"}

HOME = """
<!DOCTYPE html>
<html>
<head><title>App Demo PFA</title></head>
<body>
    <h1>Bienvenue sur App Demo</h1>
    <p>Connectez-vous pour accéder au tableau de bord.</p>
    <a href="/login">Se connecter</a>
</body>
</html>
"""

LOGIN = """
<!DOCTYPE html>
<html>
<head><title>Login</title></head>
<body>
    <h1>Connexion</h1>
    {% if erreur %}
        <p style="color:red">{{ erreur }}</p>
    {% endif %}
    <form method="POST">
        <label>Nom d'utilisateur:</label><br>
        <input type="text" name="username" id="username"><br><br>
        <label>Mot de passe:</label><br>
        <input type="password" name="password" id="password"><br><br>
        <button type="submit" id="btn-login">Se connecter</button>
    </form>
</body>
</html>
"""

DASHBOARD = """
<!DOCTYPE html>
<html>
<head><title>Dashboard</title></head>
<body>
    <h1>Tableau de bord</h1>
    <p>Bonjour <strong>{{ username }}</strong> !</p>
    <p id="message">Connexion réussie.</p>
    <a href="/logout">Se déconnecter</a>
</body>
</html>
"""

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

if __name__ == "__main__":
    app.run(debug=True, port=5000)