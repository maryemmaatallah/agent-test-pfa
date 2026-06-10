from datetime import datetime

def generer_rapport(resultats):
    """Génère un rapport HTML des tests"""
    
    date = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    total = len(resultats)
    succes = sum(1 for _, r in resultats if "succ" in r.lower())
    echecs = total - succes

    lignes_tests = ""
    for nom, resultat in resultats:
        if "succ" in resultat.lower():
            statut = '<span style="color:green">✅ SUCCÈS</span>'
        else:
            statut = '<span style="color:red">❌ ÉCHEC</span>'
        lignes_tests += f"""
        <tr>
            <td>{nom}</td>
            <td>{resultat}</td>
            <td>{statut}</td>
        </tr>
        """

    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Rapport de Test - Agent IA</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        .header {{ background: #2c3e50; color: white; padding: 20px; border-radius: 8px; }}
        .stats {{ display: flex; gap: 20px; margin: 20px 0; }}
        .stat {{ background: white; padding: 20px; border-radius: 8px; text-align: center; flex: 1; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .stat h2 {{ margin: 0; font-size: 40px; }}
        .total {{ color: #2c3e50; }}
        .succes {{ color: green; }}
        .echec {{ color: red; }}
        table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        th {{ background: #2c3e50; color: white; padding: 12px; text-align: left; }}
        td {{ padding: 12px; border-bottom: 1px solid #eee; }}
        tr:hover {{ background: #f9f9f9; }}
        .footer {{ margin-top: 20px; color: #888; text-align: center; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 Rapport de Test — Agent IA</h1>
        <p>Généré le : {date}</p>
    </div>

    <div class="stats">
        <div class="stat">
            <h2 class="total">{total}</h2>
            <p>Total tests</p>
        </div>
        <div class="stat">
            <h2 class="succes">{succes}</h2>
            <p>Succès</p>
        </div>
        <div class="stat">
            <h2 class="echec">{echecs}</h2>
            <p>Échecs</p>
        </div>
    </div>

    <table>
        <thead>
            <tr>
                <th>Nom du test</th>
                <th>Résultat</th>
                <th>Statut</th>
            </tr>
        </thead>
        <tbody>
            {lignes_tests}
        </tbody>
    </table>

    <div class="footer">
        <p>Agent de test automatique — PFA 2025</p>
    </div>
</body>
</html>
"""

    nom_fichier = f"rapport_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    with open(nom_fichier, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n📄 Rapport généré : {nom_fichier}")
    return nom_fichier