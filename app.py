import csv
import hashlib
import os
import re
import smtplib
import sqlite3
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import wraps

from flask import (Flask, flash, jsonify, redirect,
                   render_template, request, session, url_for)

app = Flask(__name__)
app.secret_key = "gestion-contacts-secret-key-2024"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "address_book.db")
CSV_PATH = os.path.join(BASE_DIR, "export_contacts.csv")

# Partie 7 — Configuration SMTP (Gmail)
# Créez un "mot de passe d'application" sur votre compte Google :
# https://myaccount.google.com/apppasswords
SMTP_EMAIL    = os.environ.get("SMTP_EMAIL",    "votre.email@gmail.com")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "votre_mot_de_passe_app")

# Partie 8 — Catégories disponibles
CATEGORIES = ["Client", "Fournisseur", "Patient", "Laboratoire", "Partenaire", "Autre"]

_CONTACT_SELECT = """
    SELECT id, nom, email, telephone,
           CASE WHEN entreprise = 'N/A' THEN '' ELSE IFNULL(entreprise, '') END AS entreprise,
           IFNULL(categorie, 'Client') AS categorie,
           IFNULL(adresse,   '')       AS adresse,
           IFNULL(fonction,  '')       AS fonction
    FROM contacts
"""

# ── Helpers ───────────────────────────────────────────────────────────────────

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
        errors.append("Le téléphone doit commencer par + et comporter au moins 10 chiffres.")
    return errors


def check_uniqueness(conn, nom, email, telephone, exclude_id=None):
    cond = " AND id != ?" if exclude_id else ""
    ex   = (exclude_id,) if exclude_id else ()
    errors = []
    if conn.execute(f"SELECT 1 FROM contacts WHERE nom = ?{cond}", (nom,) + ex).fetchone():
        errors.append(f"Le nom « {nom} » est déjà utilisé.")
    if email:
        row = conn.execute(f"SELECT nom FROM contacts WHERE email = ?{cond}", (email,) + ex).fetchone()
        if row:
            errors.append(f"L'email « {email} » est déjà utilisé par « {row['nom']} ».")
    if telephone:
        row = conn.execute(f"SELECT nom FROM contacts WHERE telephone = ?{cond}", (telephone,) + ex).fetchone()
        if row:
            errors.append(f"Le téléphone « {telephone} » est déjà utilisé par « {row['nom']} ».")
    return errors


def sync_csv():
    rows = get_db().execute(
        "SELECT nom, email, telephone, IFNULL(entreprise,'') AS entreprise, "
        "IFNULL(categorie,'') AS categorie, IFNULL(adresse,'') AS adresse, "
        "IFNULL(fonction,'') AS fonction FROM contacts ORDER BY nom"
    ).fetchall()
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Nom", "Email", "Téléphone", "Entreprise", "Catégorie", "Adresse", "Fonction"])
        for r in rows:
            w.writerow([r["nom"], r["email"], r["telephone"],
                        r["entreprise"] or "—", r["categorie"] or "—",
                        r["adresse"] or "—", r["fonction"] or "—"])


def _extract_form():
    """Extrait tous les champs du formulaire (Parties 8)."""
    return (
        request.form.get("nom",        "").strip(),
        request.form.get("email",      "").strip(),
        request.form.get("telephone",  "").strip(),
        request.form.get("entreprise", "").strip(),
        request.form.get("categorie",  "Client").strip(),
        request.form.get("adresse",    "").strip(),
        request.form.get("fonction",   "").strip(),
    )


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
                "SELECT id FROM admins WHERE username = ? AND password = ?",
                (username, hashed)
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
    q          = request.args.get("q",        "").strip()
    cat_filter = request.args.get("categorie", "").strip()
    conn = get_db()
    try:
        base_sql = _CONTACT_SELECT
        params   = []

        conditions = []
        if q:
            p = f"%{q}%"
            conditions.append(
                "(nom LIKE ? OR email LIKE ? OR telephone LIKE ? "
                "OR entreprise LIKE ? OR adresse LIKE ? OR fonction LIKE ?)"
            )
            params.extend([p, p, p, p, p, p])
        if cat_filter:
            conditions.append("categorie = ?")
            params.append(cat_filter)

        if conditions:
            base_sql += " WHERE " + " AND ".join(conditions)
        base_sql += " ORDER BY nom"

        contacts = conn.execute(base_sql, params).fetchall()
    finally:
        conn.close()
    return render_template("index.html",
                           contacts=contacts, q=q,
                           categories=CATEGORIES, cat_filter=cat_filter)


@app.route("/add", methods=["GET", "POST"])
@login_required
def add_contact():
    if request.method == "POST":
        nom, email, telephone, entreprise, categorie, adresse, fonction = _extract_form()
        form_data = dict(nom=nom, email=email, telephone=telephone,
                         entreprise=entreprise, categorie=categorie,
                         adresse=adresse, fonction=fonction)
        errors = validate_format(nom, email, telephone)
        if not errors:
            conn = get_db()
            try:
                errors = check_uniqueness(conn, nom, email, telephone)
                if not errors:
                    conn.execute(
                        "INSERT INTO contacts "
                        "(nom, email, telephone, entreprise, categorie, adresse, fonction) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (nom, email, telephone, entreprise, categorie, adresse, fonction)
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
        return render_template("form.html",
                               action=url_for("add_contact"),
                               contact=None, form_data=form_data,
                               categories=CATEGORIES)

    return render_template("form.html",
                           action=url_for("add_contact"),
                           contact=None, form_data={},
                           categories=CATEGORIES)


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
            nom, email, telephone, entreprise, categorie, adresse, fonction = _extract_form()
            form_data = dict(nom=nom, email=email, telephone=telephone,
                             entreprise=entreprise, categorie=categorie,
                             adresse=adresse, fonction=fonction)
            errors = validate_format(nom, email, telephone)
            if not errors:
                errors = check_uniqueness(conn, nom, email, telephone, exclude_id=contact_id)
            if errors:
                for e in errors:
                    flash(e, "error")
                return render_template("form.html",
                                       action=url_for("edit_contact", contact_id=contact_id),
                                       contact=contact, form_data=form_data,
                                       categories=CATEGORIES)
            try:
                conn.execute(
                    "UPDATE contacts SET nom=?, email=?, telephone=?, "
                    "entreprise=?, categorie=?, adresse=?, fonction=? WHERE id=?",
                    (nom, email, telephone, entreprise, categorie, adresse, fonction, contact_id)
                )
                conn.commit()
                sync_csv()
                flash(f"Contact « {nom} » mis à jour.", "success")
                return redirect(url_for("index"))
            except sqlite3.IntegrityError:
                flash("Ce nom est déjà utilisé par un autre contact.", "error")
                return render_template("form.html",
                                       action=url_for("edit_contact", contact_id=contact_id),
                                       contact=contact, form_data=form_data,
                                       categories=CATEGORIES)
    finally:
        conn.close()

    return render_template("form.html",
                           action=url_for("edit_contact", contact_id=contact_id),
                           contact=contact, form_data=dict(contact),
                           categories=CATEGORIES)


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


# ── Partie 7 : Envoi d'email ──────────────────────────────────────────────────

@app.route("/send-email/<int:contact_id>", methods=["GET", "POST"])
@login_required
def send_email(contact_id):
    conn = get_db()
    try:
        contact = conn.execute(_CONTACT_SELECT + "WHERE id = ?", (contact_id,)).fetchone()
        if not contact:
            flash("Contact introuvable.", "error")
            return redirect(url_for("index"))
    finally:
        conn.close()

    if request.method == "POST":
        sujet  = request.form.get("sujet",  "").strip()
        corps  = request.form.get("corps",  "").strip()
        if not sujet or not corps:
            flash("Le sujet et le message sont obligatoires.", "error")
            return render_template("send_email.html", contact=contact)

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = sujet
            msg["From"]    = SMTP_EMAIL
            msg["To"]      = contact["email"]

            # Version texte + version HTML basique
            corps_html = corps.replace("\n", "<br>")
            msg.attach(MIMEText(corps, "plain", "utf-8"))
            msg.attach(MIMEText(f"<p>{corps_html}</p>", "html", "utf-8"))

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(SMTP_EMAIL, SMTP_PASSWORD)
                server.sendmail(SMTP_EMAIL, contact["email"], msg.as_string())

            flash(f"Email envoyé à {contact['nom']} ({contact['email']}).", "success")
            return redirect(url_for("index"))

        except smtplib.SMTPAuthenticationError:
            flash("Erreur d'authentification SMTP. Vérifiez SMTP_EMAIL et SMTP_PASSWORD.", "error")
        except smtplib.SMTPException as e:
            flash(f"Erreur d'envoi : {e}", "error")

    return render_template("send_email.html", contact=contact)


# ── Partie 7 : Lien WhatsApp ──────────────────────────────────────────────────

@app.route("/whatsapp/<int:contact_id>")
@login_required
def whatsapp(contact_id):
    """Redirige vers WhatsApp Web avec un message pré-rempli."""
    conn = get_db()
    try:
        contact = conn.execute(_CONTACT_SELECT + "WHERE id = ?", (contact_id,)).fetchone()
        if not contact or not contact["telephone"]:
            flash("Contact sans numéro de téléphone.", "error")
            return redirect(url_for("index"))
    finally:
        conn.close()

    # Supprime le + et les espaces pour l'URL WhatsApp
    numero = contact["telephone"].replace("+", "").replace(" ", "")
    message = f"Bonjour {contact['nom']},"
    import urllib.parse
    wa_url = f"https://wa.me/{numero}?text={urllib.parse.quote(message)}"
    return redirect(wa_url)


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
                _CONTACT_SELECT +
                "WHERE nom LIKE ? OR email LIKE ? OR telephone LIKE ? "
                "OR entreprise LIKE ? ORDER BY nom",
                (p, p, p, p)
            ).fetchall()
        else:
            rows = conn.execute(_CONTACT_SELECT + "ORDER BY nom").fetchall()
    finally:
        conn.close()
    return jsonify([dict(r) for r in rows])


if __name__ == "__main__":
    app.run(debug=True)