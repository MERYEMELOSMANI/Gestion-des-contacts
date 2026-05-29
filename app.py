import csv
import hashlib
import os
import re
import sqlite3
from functools import wraps

from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = "gestion-contacts-secret-key-2024"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "address_book.db")
CSV_PATH = os.path.join(BASE_DIR, "export_contacts.csv")

_CONTACT_SELECT = """
    SELECT id, nom, email, telephone,
           CASE WHEN entreprise = 'N/A' THEN '' ELSE IFNULL(entreprise, '') END AS entreprise
    FROM contacts
"""

# ── Helpers ──────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def validate_format(nom, email, telephone):
    errors = []
    if len(nom.strip()) < 3:
        errors.append("Le nom doit contenir au moins 3 caractères.")
    if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        errors.append("Format email invalide.")
    if telephone and not (telephone.startswith("+") and len(telephone) >= 10):
        errors.append("Le téléphone doit commencer par + et comporter au moins 10 caractères (ex : +33612345678).")
    return errors


def check_uniqueness(conn, nom, email, telephone, exclude_id=None):
    cond = " AND id != ?" if exclude_id else ""
    ex   = (exclude_id,) if exclude_id else ()
    errors = []

    if conn.execute(f"SELECT 1 FROM contacts WHERE nom = ?{cond}", (nom,) + ex).fetchone():
        errors.append(f"Le nom « {nom} » est déjà utilisé par un autre contact.")

    if email:
        row = conn.execute(f"SELECT nom FROM contacts WHERE email = ?{cond}", (email,) + ex).fetchone()
        if row:
            errors.append(f"L'email « {email} » est déjà utilisé par le contact « {row['nom']} ».")

    if telephone:
        row = conn.execute(f"SELECT nom FROM contacts WHERE telephone = ?{cond}", (telephone,) + ex).fetchone()
        if row:
            errors.append(f"Le téléphone « {telephone} » est déjà utilisé par le contact « {row['nom']} ».")

    return errors


def sync_csv():
    rows = get_db().execute(
        "SELECT nom, email, telephone, IFNULL(entreprise,'') AS entreprise FROM contacts ORDER BY nom"
    ).fetchall()
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Nom", "Email", "Téléphone", "Entreprise"])
        for r in rows:
            w.writerow([r["nom"], r["email"], r["telephone"], r["entreprise"] or "Non renseigné"])


# ── Authentification ──────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user" in session:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        hashed   = hashlib.sha256(password.encode()).hexdigest()
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT id FROM admins WHERE username = ? AND password = ?", (username, hashed)
            ).fetchone()
        finally:
            conn.close()
        if row:
            session["user"] = username
            flash(f"Bienvenue, {username} !", "success")
            return redirect(url_for("index"))
        flash("Identifiant ou mot de passe incorrect.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Vous avez été déconnecté.", "success")
    return redirect(url_for("login"))


# ── Contacts ──────────────────────────────────────────────────────────────────

@app.route("/")
@login_required
def index():
    q    = request.args.get("q", "").strip()
    conn = get_db()
    try:
        if q:
            p = f"%{q}%"
            contacts = conn.execute(
                _CONTACT_SELECT + "WHERE nom LIKE ? OR email LIKE ? OR telephone LIKE ? OR entreprise LIKE ? ORDER BY nom",
                (p, p, p, p)
            ).fetchall()
        else:
            contacts = conn.execute(_CONTACT_SELECT + "ORDER BY nom").fetchall()
    finally:
        conn.close()
    return render_template("index.html", contacts=contacts, q=q)


@app.route("/add", methods=["GET", "POST"])
@login_required
def add_contact():
    if request.method == "POST":
        nom, email, telephone, entreprise = _extract_form()
        form_data = dict(nom=nom, email=email, telephone=telephone, entreprise=entreprise)

        errors = validate_format(nom, email, telephone)
        if not errors:
            conn = get_db()
            try:
                errors = check_uniqueness(conn, nom, email, telephone)
                if not errors:
                    conn.execute(
                        "INSERT INTO contacts (nom, email, telephone, entreprise) VALUES (?, ?, ?, ?)",
                        (nom, email, telephone, entreprise)
                    )
                    conn.commit()
                    sync_csv()
                    flash(f"Contact « {nom} » ajouté avec succès.", "success")
                    return redirect(url_for("index"))
            except sqlite3.IntegrityError:
                errors = [f"Le nom « {nom} » existe déjà."]
            finally:
                conn.close()

        for e in errors:
            flash(e, "error")
        return render_template("form.html", action=url_for("add_contact"), contact=None, form_data=form_data)

    return render_template("form.html", action=url_for("add_contact"), contact=None, form_data={})


@app.route("/edit/<int:contact_id>", methods=["GET", "POST"])
@login_required
def edit_contact(contact_id):
    conn = get_db()
    try:
        contact = conn.execute(_CONTACT_SELECT + "WHERE id = ?", (contact_id,)).fetchone()
        if not contact:
            flash("Contact introuvable.", "error")
            return redirect(url_for("index"))

        if request.method == "POST":
            nom, email, telephone, entreprise = _extract_form()
            form_data = dict(nom=nom, email=email, telephone=telephone, entreprise=entreprise)

            errors = validate_format(nom, email, telephone)
            if not errors:
                errors = check_uniqueness(conn, nom, email, telephone, exclude_id=contact_id)
            if errors:
                for e in errors:
                    flash(e, "error")
                return render_template("form.html",
                                       action=url_for("edit_contact", contact_id=contact_id),
                                       contact=contact, form_data=form_data)
            try:
                conn.execute(
                    "UPDATE contacts SET nom=?, email=?, telephone=?, entreprise=? WHERE id=?",
                    (nom, email, telephone, entreprise, contact_id)
                )
                conn.commit()
                sync_csv()
                flash(f"Contact « {nom} » mis à jour.", "success")
                return redirect(url_for("index"))
            except sqlite3.IntegrityError:
                flash("Ce nom est déjà utilisé par un autre contact.", "error")
                return render_template("form.html",
                                       action=url_for("edit_contact", contact_id=contact_id),
                                       contact=contact, form_data=form_data)
    finally:
        conn.close()

    return render_template("form.html",
                           action=url_for("edit_contact", contact_id=contact_id),
                           contact=contact, form_data=dict(contact))


@app.route("/delete/<int:contact_id>", methods=["POST"])
@login_required
def delete_contact(contact_id):
    conn = get_db()
    try:
        row = conn.execute("SELECT nom FROM contacts WHERE id = ?", (contact_id,)).fetchone()
        if row:
            conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
            conn.commit()
            sync_csv()
            flash(f"Contact « {row['nom']} » supprimé.", "success")
        else:
            flash("Contact introuvable.", "error")
    finally:
        conn.close()
    return redirect(url_for("index"))


# ── API JSON ──────────────────────────────────────────────────────────────────

@app.route("/api/contacts")
@login_required
def api_contacts():
    q    = request.args.get("q", "").strip()
    conn = get_db()
    try:
        if q:
            p = f"%{q}%"
            rows = conn.execute(
                _CONTACT_SELECT + "WHERE nom LIKE ? OR email LIKE ? OR telephone LIKE ? OR entreprise LIKE ? ORDER BY nom",
                (p, p, p, p)
            ).fetchall()
        else:
            rows = conn.execute(_CONTACT_SELECT + "ORDER BY nom").fetchall()
    finally:
        conn.close()
    return jsonify([dict(r) for r in rows])


# ── Utilitaire interne ────────────────────────────────────────────────────────

def _extract_form():
    return (
        request.form.get("nom",        "").strip(),
        request.form.get("email",      "").strip(),
        request.form.get("telephone",  "").strip(),
        request.form.get("entreprise", "").strip(),
    )


if __name__ == "__main__":
    app.run(debug=True)
