"""
migrer_db.py — Script de migration à exécuter UNE SEULE FOIS
Ajoute la colonne nom_application à la table sessions_enregistrees
sans perdre les données existantes.
"""

import sqlite3
import os

DB_PATH = os.path.join("instance", "tests.db")

if not os.path.exists(DB_PATH):
    print(f"❌ Base de données introuvable à {DB_PATH}")
    exit(1)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Vérifier si la colonne existe déjà (évite une erreur si on relance par erreur)
cursor.execute("PRAGMA table_info(sessions_enregistrees)")
colonnes = [col[1] for col in cursor.fetchall()]

if "nom_application" in colonnes:
    print("✅ La colonne 'nom_application' existe déjà, rien à faire.")
else:
    cursor.execute(
        "ALTER TABLE sessions_enregistrees ADD COLUMN nom_application VARCHAR(200) DEFAULT 'Sans nom'"
    )
    conn.commit()
    print("✅ Colonne 'nom_application' ajoutée avec succès.")

    # Mettre à jour les sessions existantes avec un nom par défaut basé sur l'URL
    cursor.execute("SELECT id, url_depart FROM sessions_enregistrees")
    sessions = cursor.fetchall()
    for session_id, url in sessions:
        # Donne un nom par défaut simple basé sur le domaine, modifiable ensuite
        nom_defaut = "SmartRestaurant" if "localhost:3000" in url else "Application inconnue"
        cursor.execute(
            "UPDATE sessions_enregistrees SET nom_application = ? WHERE id = ?",
            (nom_defaut, session_id)
        )
    conn.commit()
    print(f"✅ {len(sessions)} sessions existantes mises à jour avec un nom d'application par défaut.")

conn.close()
print("🎉 Migration terminée.")