import csv
import datetime
import io
import hashlib
import json
import os
import re
import smtplib
import sqlite3
import urllib.parse
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import wraps

from flask import (Flask, flash, jsonify, redirect,
                   render_template, request, send_file, session, url_for)

app = Flask(__name__)
app.jinja_env.filters['ord'] = ord
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

# Partie 9 — Google Gemini (IA générative)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL     = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent"

_CONTACT_SELECT = """
    SELECT id, nom, email, telephone,
           CASE WHEN entreprise = 'N/A' THEN '' ELSE IFNULL(entreprise, '') END AS entreprise,
           IFNULL(categorie, 'Client') AS categorie,
           IFNULL(adresse,   '')       AS adresse,
           IFNULL(fonction,  '')       AS fonction,
           IFNULL(is_favorite, 0)      AS is_favorite
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


def get_config(cle, default=""):
    try:
        conn = get_db()
        row = conn.execute("SELECT valeur FROM config WHERE cle = ?", (cle,)).fetchone()
        conn.close()
        return row["valeur"] if row else default
    except Exception:
        return default


def set_config(cle, valeur):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO config (cle, valeur) VALUES (?, ?)", (cle, valeur))
    conn.commit()
    conn.close()


@app.context_processor
def inject_get_config():
    return dict(get_config=get_config)


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
    # utf-8-sig ajoute le BOM pour qu'Excel détecte correctement l'UTF-8
    with open(CSV_PATH, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Nom", "Email", "Telephone", "Entreprise", "Categorie", "Adresse", "Fonction"])
        for r in rows:
            w.writerow([r["nom"], r["email"] or "", r["telephone"] or "",
                        r["entreprise"] or "", r["categorie"] or "",
                        r["adresse"] or "", r["fonction"] or ""])


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
        # Stats globales (non filtrées)
        total    = conn.execute("SELECT COUNT(*) AS n FROM contacts").fetchone()["n"]
        cat_rows = conn.execute(
            "SELECT IFNULL(categorie,'Autre') AS cat, COUNT(*) AS n FROM contacts GROUP BY cat"
        ).fetchall()
        stats = {"total": total, "cats": {r["cat"]: r["n"] for r in cat_rows}}

        # Contacts filtrés
        base_sql   = _CONTACT_SELECT
        params     = []
        conditions = []
        if q:
            p = f"%{q}%"
            conditions.append(
                "(nom LIKE ? OR email LIKE ? OR telephone LIKE ? "
                "OR entreprise LIKE ? OR adresse LIKE ? OR fonction LIKE ?)"
            )
            params.extend([p, p, p, p, p, p])
        if cat_filter:
            if cat_filter == 'Favoris':
                conditions.append("is_favorite = 1")
            else:
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
                           categories=CATEGORIES, cat_filter=cat_filter,
                           stats=stats)


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


# ── Favoris ───────────────────────────────────────────────────────────────────

@app.route("/toggle_favorite/<int:contact_id>", methods=["POST"])
@login_required
def toggle_favorite(contact_id):
    conn = get_db()
    try:
        contact = conn.execute("SELECT nom, IFNULL(is_favorite, 0) as is_favorite FROM contacts WHERE id = ?", (contact_id,)).fetchone()
        if contact:
            new_status = 0 if contact["is_favorite"] else 1
            conn.execute("UPDATE contacts SET is_favorite = ? WHERE id = ?", (new_status, contact_id))
            conn.commit()
            status_text = "ajouté aux favoris" if new_status else "retiré des favoris"
            flash(f"Contact « {contact['nom']} » {status_text}.", "success")
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

        # Lire les credentials depuis la DB (priorité) ou les variables d'env
        smtp_email    = get_config("smtp_email")    or SMTP_EMAIL
        smtp_password = get_config("smtp_password") or SMTP_PASSWORD

        if not smtp_email or smtp_email == "votre.email@gmail.com":
            flash("Configurez votre email SMTP dans les Paramètres avant d'envoyer.", "error")
            return render_template("send_email.html", contact=contact)

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = sujet
            msg["From"]    = smtp_email
            msg["To"]      = contact["email"]

            corps_html = corps.replace("\n", "<br>")
            msg.attach(MIMEText(corps, "plain", "utf-8"))
            msg.attach(MIMEText(f"<p>{corps_html}</p>", "html", "utf-8"))

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(smtp_email, smtp_password)
                server.sendmail(smtp_email, contact["email"], msg.as_string())

            # Log to history
            try:
                conn = get_db()
                conn.execute(
                    "INSERT INTO historique_messages (contact_id, type_msg, contenu) VALUES (?, ?, ?)",
                    (contact_id, 'email', f"Sujet: {sujet}\n\n{corps}")
                )
                conn.commit()
            finally:
                conn.close()

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

    numero  = contact["telephone"].replace("+", "").replace(" ", "")
    message = f"Bonjour {contact['nom']},"
    wa_url  = f"https://wa.me/{numero}?text={urllib.parse.quote(message)}"

    # Log to history
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO historique_messages (contact_id, type_msg, contenu) VALUES (?, ?, ?)",
            (contact_id, 'whatsapp', message)
        )
        conn.commit()
    finally:
        conn.close()

    return redirect(wa_url)


@app.route("/api/history/<int:contact_id>")
@login_required
def get_history(contact_id):
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT type_msg, contenu, date_envoi FROM historique_messages WHERE contact_id = ? ORDER BY date_envoi DESC", 
            (contact_id,)
        ).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()

@app.route("/api/history/add", methods=["POST"])
@login_required
def add_history():
    data = request.get_json()
    contact_id = data.get("contact_id")
    type_msg = data.get("type", "whatsapp")
    msg = data.get("msg", "")
    
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO historique_messages (contact_id, type_msg, contenu) VALUES (?, ?, ?)",
            (contact_id, type_msg, msg)
        )
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()

@app.route("/api/contact/<int:contact_id>")
@login_required
def get_contact_api(contact_id):
    conn = get_db()
    try:
        contact = conn.execute(_CONTACT_SELECT + "WHERE id = ?", (contact_id,)).fetchone()
        if contact:
            return jsonify(dict(contact))
        return jsonify({"error": "Introuvable"}), 404
    finally:
        conn.close()

@app.route("/api/contact/save", methods=["POST"])
@login_required
def save_contact_api():
    data = request.get_json()
    contact_id = data.get("id")
    nom = data.get("nom", "").strip()
    email = data.get("email", "").strip()
    telephone = data.get("telephone", "").strip()
    entreprise = data.get("entreprise", "").strip()
    categorie = data.get("categorie", "Client").strip()
    adresse = data.get("adresse", "").strip()
    fonction = data.get("fonction", "").strip()
    
    errors = validate_format(nom, email, telephone)
    if errors:
        return jsonify({"error": "\n".join(errors)}), 400
        
    conn = get_db()
    try:
        errors = check_uniqueness(conn, nom, email, telephone, exclude_id=contact_id)
        if errors:
            return jsonify({"error": "\n".join(errors)}), 400
            
        if contact_id:
            conn.execute(
                "UPDATE contacts SET nom=?, email=?, telephone=?, entreprise=?, categorie=?, adresse=?, fonction=? WHERE id=?",
                (nom, email, telephone, entreprise, categorie, adresse, fonction, contact_id)
            )
        else:
            conn.execute(
                "INSERT INTO contacts (nom, email, telephone, entreprise, categorie, adresse, fonction) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (nom, email, telephone, entreprise, categorie, adresse, fonction)
            )
        conn.commit()
        sync_csv()
        return jsonify({"success": True})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Ce nom est déjà utilisé."}), 400
    finally:
        conn.close()

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


# ── Partie 9 : Génération de message par IA (Google Gemini) ──────────────────

@app.route("/api/generate-message", methods=["POST"])
@login_required
def generate_message():
    data       = request.get_json(silent=True) or {}
    contact_id = data.get("contact_id")
    msg_type   = data.get("type", "email")      # "email" ou "whatsapp"
    context    = data.get("context", "").strip()

    conn = get_db()
    try:
        contact = conn.execute(_CONTACT_SELECT + "WHERE id = ?", (contact_id,)).fetchone()
        if not contact:
            return jsonify({"error": "Contact introuvable"}), 404
    finally:
        conn.close()

    nom        = contact["nom"]
    categorie  = contact["categorie"] or ""
    entreprise = contact["entreprise"] or ""
    ctx_line   = context or "prise de contact générale"

    if msg_type == "whatsapp":
        prompt = (
            f"Rédige un message WhatsApp professionnel et chaleureux en français pour ce contact :\n"
            f"Nom : {nom}\nCatégorie : {categorie}\nEntreprise : {entreprise}\n"
            f"Contexte : {ctx_line}\n\n"
            f"Le message doit être court (3-4 lignes), commencer par 'Bonjour {nom},' "
            f"et être adapté à WhatsApp. Ne retourne que le texte du message, sans titres ni explications."
        )
    else:
        prompt = (
            f"Rédige un email professionnel en français pour ce contact :\n"
            f"Nom : {nom}\nCatégorie : {categorie}\nEntreprise : {entreprise}\n"
            f"Contexte : {ctx_line}\n\n"
            f"Retourne UNIQUEMENT un objet JSON valide avec deux champs :\n"
            f"- \"sujet\" : objet de l'email (max 60 caractères)\n"
            f"- \"corps\" : corps du message (3-5 paragraphes, professionnel, commence par 'Bonjour {nom},')\n"
            f"Ne mets rien en dehors du JSON."
        )

    try:
        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 600}
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{GEMINI_URL}?key={GEMINI_API_KEY}",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        text = result["candidates"][0]["content"]["parts"][0]["text"].strip()

        if msg_type == "email":
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                try:
                    parsed = json.loads(json_match.group())
                    return jsonify({"sujet": parsed.get("sujet", ""), "corps": parsed.get("corps", text)})
                except json.JSONDecodeError:
                    pass
            return jsonify({"sujet": f"Message pour {nom}", "corps": text})
        else:
            return jsonify({"message": text})

    except (urllib.error.HTTPError, urllib.error.URLError, Exception):
        return _fallback_message(nom, categorie, entreprise, ctx_line, msg_type)


def _fallback_message(nom, categorie, entreprise, contexte, msg_type):
    """Génère un message professionnel localement selon le contexte et la catégorie."""
    ctx = contexte.lower()
    cat = (categorie or "").lower()
    ent = f" ({entreprise})" if entreprise else ""

    # Détection du sujet selon les mots-clés du contexte
    if any(w in ctx for w in ["rdv", "rendez-vous", "rendez", "réunion", "rencontre"]):
        theme = "rdv"
    elif any(w in ctx for w in ["résultat", "analyse", "rapport", "bilan", "examen"]):
        theme = "resultats"
    elif any(w in ctx for w in ["facture", "paiement", "devis", "commande", "livraison"]):
        theme = "commercial"
    elif any(w in ctx for w in ["relance", "suivi", "rappel", "urgent"]):
        theme = "relance"
    elif any(w in ctx for w in ["information", "info", "mise à jour", "actualité"]):
        theme = "info"
    else:
        theme = "general"

    # Templates email selon catégorie + thème
    templates_email = {
        ("patient", "rdv"): (
            f"Confirmation de votre rendez-vous",
            f"Bonjour {nom},\n\nNous vous confirmons votre rendez-vous à la date convenue.\n\n"
            f"Merci de vous présenter 10 minutes avant l'heure prévue et d'apporter votre carnet de santé "
            f"ainsi que votre carte d'assurance maladie.\n\n"
            f"En cas d'empêchement, nous vous prions de nous prévenir au plus tôt afin de libérer le créneau "
            f"pour un autre patient.\n\nNous restons à votre disposition pour toute question.\n\nCordialement"
        ),
        ("patient", "resultats"): (
            f"Vos résultats d'analyses sont disponibles",
            f"Bonjour {nom},\n\nNous avons le plaisir de vous informer que vos résultats d'analyses "
            f"sont désormais disponibles.\n\nNous vous invitons à prendre contact avec notre cabinet "
            f"afin de convenir d'un rendez-vous pour en discuter avec le praticien.\n\n"
            f"Votre suivi médical est notre priorité et nous restons disponibles pour répondre "
            f"à toutes vos questions.\n\nCordialement"
        ),
        ("client", "rdv"): (
            f"Confirmation de notre rendez-vous",
            f"Bonjour {nom},\n\nJe me permets de vous écrire afin de confirmer notre rendez-vous "
            f"{'concernant ' + contexte if contexte else 'prévu prochainement'}.\n\n"
            f"Ce sera l'occasion de faire le point ensemble et d'avancer sur nos projets communs.\n\n"
            f"N'hésitez pas à me contacter si vous souhaitez modifier l'horaire ou si vous avez "
            f"des questions en amont.\n\nDans l'attente de notre rencontre, je vous adresse "
            f"mes cordiales salutations."
        ),
        ("fournisseur", "commercial"): (
            f"Suivi de notre collaboration{ent}",
            f"Bonjour {nom},\n\nJe me permets de vous contacter concernant {contexte if contexte else 'notre collaboration en cours'}.\n\n"
            f"Après examen de notre dossier, je souhaiterais faire le point avec vous sur l'avancement "
            f"et m'assurer que tout se déroule conformément à nos engagements respectifs.\n\n"
            f"Pourriez-vous me confirmer les prochaines étapes et les délais prévisionnels ?\n\n"
            f"Je reste disponible pour en discuter à votre convenance.\n\nCordialement"
        ),
        ("laboratoire", "resultats"): (
            f"Demande de résultats — {nom}{ent}",
            f"Bonjour {nom},\n\nNous nous permettons de vous relancer concernant "
            f"{'les ' + contexte if contexte else 'les résultats en attente'}.\n\n"
            f"Ces éléments sont nécessaires pour assurer la continuité du suivi de nos patients "
            f"et nous vous saurions gré de bien vouloir nous les faire parvenir dans les meilleurs délais.\n\n"
            f"Nous vous remercions pour votre collaboration habituelle.\n\nCordialement"
        ),
    }

    # Chercher le template le plus adapté
    key = (cat, theme)
    if key in templates_email:
        sujet, corps = templates_email[key]
    else:
        # Template générique enrichi
        intro_par_cat = {
            "patient":      "Dans le cadre de votre suivi médical",
            "client":       "Dans le cadre de notre collaboration",
            "fournisseur":  "Dans le cadre de notre partenariat commercial",
            "laboratoire":  "Dans le cadre de nos échanges professionnels",
            "partenaire":   "Dans le cadre de notre partenariat",
        }
        intro = intro_par_cat.get(cat, "Suite à nos échanges")
        sujet = f"{'Re: ' if theme == 'relance' else ''}{contexte.capitalize() if contexte else 'Message important'} — {nom}"
        corps = (
            f"Bonjour {nom},\n\n"
            f"{intro}, je me permets de vous adresser ce message "
            f"{'concernant : ' + contexte + '.' if contexte else 'pour maintenir le contact avec vous.'}\n\n"
            f"{'Je souhaite attirer votre attention sur ce point qui nécessite votre intervention dans les meilleurs délais.' if theme == 'relance' else 'Nous accordons la plus grande importance à votre satisfaction et restons attentifs à vos besoins.'}\n\n"
            f"{'Notre équipe est à votre entière disposition' if cat in ('client','patient') else 'Je reste disponible'} "
            f"pour tout renseignement complémentaire ou pour convenir d'un rendez-vous à votre convenance.\n\n"
            f"Dans l'attente de votre retour, veuillez agréer, {nom.split('.')[0].capitalize()}, "
            f"l'expression de mes salutations distinguées.\n\nCordialement"
        )

    if msg_type == "whatsapp":
        # Version WhatsApp courte et naturelle
        wa_templates = {
            "rdv":       f"Bonjour {nom} 👋\nJe vous contacte pour {'confirmer notre RDV' if not contexte else contexte}.\nPourriez-vous confirmer votre disponibilité ? Merci 🙏",
            "resultats": f"Bonjour {nom} 👋\nVos résultats sont disponibles. Merci de nous contacter pour convenir d'un rendez-vous. À bientôt 😊",
            "commercial": f"Bonjour {nom} 👋\nSuite à {'notre échange' if not contexte else contexte}, pourriez-vous me revenir rapidement ? Merci d'avance 🙏",
            "relance":   f"Bonjour {nom} 👋\nJe me permets de vous relancer concernant {contexte if contexte else 'notre dossier en attente'}. Merci de bien vouloir me recontacter 🙏",
            "general":   f"Bonjour {nom} 👋\n{'Concernant ' + contexte + ', je' if contexte else 'Je'} souhaitais vous contacter. Seriez-vous disponible pour en discuter ? Merci 😊",
        }
        msg = wa_templates.get(theme, wa_templates["general"])
        return jsonify({"message": msg, "fallback": True})

    return jsonify({"sujet": sujet, "corps": corps, "fallback": True})


# ── Agenda (Google Calendar UI) ───────────────────────────────────────────────

@app.route("/agenda")
@login_required
def agenda():
    conn = get_db()
    try:
        contacts = conn.execute("SELECT id, nom FROM contacts ORDER BY nom").fetchall()
    finally:
        conn.close()
    return render_template("agenda.html", contacts=contacts)


@app.route("/api/agenda", methods=["GET"])
@login_required
def get_agenda():
    conn = get_db()
    try:
        rows = conn.execute('''
            SELECT r.id, r.contact_id, r.date_rdv, r.heure_rdv, r.motif, c.nom 
            FROM rendez_vous r
            JOIN contacts c ON c.id = r.contact_id
        ''').fetchall()
        events = []
        for r in rows:
            events.append({
                "id": r["id"],
                "contact_id": r["contact_id"],
                "nom": r["nom"],
                "date": r["date_rdv"],
                "heure": r["heure_rdv"],
                "motif": r["motif"]
            })
        return jsonify(events)
    finally:
        conn.close()


@app.route("/api/agenda", methods=["POST"])
@login_required
def add_agenda():
    data = request.get_json()
    contact_id = data.get("contact_id")
    date_rdv = data.get("date_rdv")
    heure_rdv = data.get("heure_rdv")
    motif = data.get("motif", "")
    
    if not contact_id or not date_rdv or not heure_rdv:
        return jsonify({"error": "Champs manquants"}), 400
        
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO rendez_vous (contact_id, date_rdv, heure_rdv, motif)
            VALUES (?, ?, ?, ?)
        ''', (contact_id, date_rdv, heure_rdv, motif))
        conn.commit()
        return jsonify({"success": True, "id": cur.lastrowid})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Un rendez-vous existe déjà à cette date et heure."}), 400
    finally:
        conn.close()


@app.route("/api/agenda/<int:rdv_id>", methods=["DELETE"])
@login_required
def delete_agenda(rdv_id):
    conn = get_db()
    try:
        conn.execute("DELETE FROM rendez_vous WHERE id = ?", (rdv_id,))
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()


# ── Paramètres SMTP ──────────────────────────────────────────────────────────

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        smtp_email    = request.form.get("smtp_email",    "").strip()
        smtp_password = request.form.get("smtp_password", "").strip()
        if not smtp_email or "@" not in smtp_email:
            flash("Adresse email invalide.", "error")
        else:
            set_config("smtp_email", smtp_email)
            if smtp_password:
                set_config("smtp_password", smtp_password)
            flash("Paramètres SMTP enregistrés.", "success")
        return redirect(url_for("settings"))

    current_email = get_config("smtp_email")
    configured    = bool(current_email)
    return render_template("settings.html",
                           current_email=current_email,
                           configured=configured)


# ── Export CSV ────────────────────────────────────────────────────────────────

@app.route("/export-csv")
@login_required
def export_csv():
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT nom, email, telephone, IFNULL(entreprise,'') AS entreprise, "
            "IFNULL(categorie,'') AS categorie, IFNULL(adresse,'') AS adresse, "
            "IFNULL(fonction,'') AS fonction FROM contacts ORDER BY nom"
        ).fetchall()
    finally:
        conn.close()

    def text_cell(val):
        # Préfixe tab : force Excel à traiter comme texte (évite conversion en nombre)
        return "\t" + val if val else ""

    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_ALL)
    w.writerow(["Nom", "Email", "Telephone", "Entreprise", "Categorie", "Adresse", "Fonction"])
    for r in rows:
        w.writerow([r["nom"], r["email"] or "", text_cell(r["telephone"]),
                    r["entreprise"] or "", r["categorie"] or "",
                    r["adresse"] or "", r["fonction"] or ""])

    # BOM UTF-8 pour ouverture correcte dans Excel avec les accents
    out = io.BytesIO()
    out.write(buf.getvalue().encode("utf-8-sig"))
    out.seek(0)
    return send_file(out, mimetype="text/csv; charset=utf-8",
                     as_attachment=True, download_name="contacts.csv")


# ── Chatbot Agenda ────────────────────────────────────────────────────────────

@app.route("/api/agenda/chat", methods=["POST"])
@login_required
def agenda_chat():
    data = request.get_json(silent=True) or {}
    question = data.get("question", "").strip()
    reset    = data.get("reset", False)

    if reset:
        session.pop("chat_history", None)
        session.modified = True

    if not question or question == "__reset__":
        return jsonify({"reply": "ok"}), 200

    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT r.date_rdv, r.heure_rdv, r.motif, c.nom, c.categorie
            FROM rendez_vous r
            JOIN contacts c ON c.id = r.contact_id
            ORDER BY r.date_rdv, r.heure_rdv
        """).fetchall()
    finally:
        conn.close()

    today = datetime.date.today().isoformat()
    def _nom_affichable(nom):
        # "karim.elidrissi" → "Karim Elidrissi"
        return " ".join(p.capitalize() for p in re.split(r"[\s.\-_]+", nom))

    agenda_lines = "\n".join(
        f"- {r['date_rdv']} à {r['heure_rdv']} : {_nom_affichable(r['nom'])} ({r['categorie'] or 'N/A'}) — {r['motif'] or 'motif non précisé'}"
        for r in rows
    ) if rows else "Aucun rendez-vous planifié pour l'instant."

    system_text = (
        f"Tu es un assistant conversationnel intelligent pour la gestion d'agenda et de contacts. "
        f"Aujourd'hui : {today}.\n\n"
        f"Voici TOUS les rendez-vous planifiés (utilise ces données pour répondre) :\n{agenda_lines}\n\n"
        f"Règles importantes :\n"
        f"- Réponds toujours en français.\n"
        f"- Si l'utilisateur mentionne un prénom ou un nom (ex : 'Karim', 'Dr Martin'), "
        f"cherche dans la liste ci-dessus les RDV avec ce contact et donne la date, l'heure et le motif.\n"
        f"- Si plusieurs RDV existent avec ce contact, liste-les tous.\n"
        f"- Si aucun RDV ne correspond au nom mentionné, dis-le clairement.\n"
        f"- Sois naturel et conversationnel. Réponds à toutes les questions, pas uniquement sur l'agenda."
    )

    history = session.get("chat_history", [])

    # Construire la conversation multi-tour pour Gemini
    contents = [
        {"role": "user",  "parts": [{"text": system_text}]},
        {"role": "model", "parts": [{"text": "Bonjour ! Je suis votre assistant agenda. Comment puis-je vous aider ?"}]},
    ]
    for h in history[-8:]:  # 4 derniers échanges
        contents.append({"role": "user",  "parts": [{"text": h["q"]}]})
        contents.append({"role": "model", "parts": [{"text": h["a"]}]})
    contents.append({"role": "user", "parts": [{"text": question}]})

    try:
        payload = json.dumps({
            "contents": contents,
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 500}
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{GEMINI_URL}?key={GEMINI_API_KEY}",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
        history.append({"q": question, "a": text})
        session["chat_history"] = history[-10:]
        session.modified = True
        return jsonify({"reply": text})
    except Exception:
        reply = _agenda_chat_fallback(question, rows, today)
        history.append({"q": question, "a": reply})
        session["chat_history"] = history[-10:]
        session.modified = True
        return jsonify({"reply": reply})


def _agenda_chat_fallback(question, rows, today):
    q     = question.lower()
    total = len(rows)
    futurs = [r for r in rows if r["date_rdv"] >= today]

    # Recherche par nom de contact (prioritaire)
    # Découpe sur espaces, points et tirets pour gérer "karim.elidrissi", "jean-marc", etc.
    matched = []
    for r in rows:
        nom_parts = re.split(r"[\s.\-_]+", r["nom"].lower())
        if any(part in q for part in nom_parts if len(part) >= 3):
            matched.append(r)
    if matched:
        nom_affiche = " ".join(p.capitalize() for p in re.split(r"[\s.\-_]+", matched[0]["nom"]))
        if len(matched) == 1:
            r = matched[0]
            statut = "à venir" if r["date_rdv"] >= today else "passé"
            return (
                f"Vous avez un rendez-vous {statut} avec {nom_affiche} "
                f"le {r['date_rdv']} à {r['heure_rdv']}"
                + (f" — {r['motif']}" if r['motif'] else "") + "."
            )
        else:
            lignes = "; ".join(
                f"le {r['date_rdv']} à {r['heure_rdv']}" + (f" ({r['motif']})" if r['motif'] else "")
                for r in matched
            )
            return f"Vous avez {len(matched)} rendez-vous avec {nom_affiche} : {lignes}."

    if any(w in q for w in ["combien", "nombre", "total", "count"]):
        return f"Il y a actuellement {total} rendez-vous planifié(s) dans votre agenda."

    if any(w in q for w in ["prochain", "suivant", "procha"]):
        if futurs:
            r = futurs[0]
            return f"Votre prochain RDV est le {r['date_rdv']} à {r['heure_rdv']} avec {r['nom']} — {r['motif'] or 'motif non précisé'}."
        return "Vous n'avez aucun rendez-vous à venir dans l'agenda."

    if any(w in q for w in ["aujourd'hui", "aujourd hui", "ce soir", "ce matin"]):
        du_jour = [r for r in rows if r["date_rdv"] == today]
        if du_jour:
            resume = "; ".join(f"{r['heure_rdv']} — {r['nom']}" for r in du_jour)
            return f"Aujourd'hui vous avez {len(du_jour)} RDV : {resume}."
        return "Vous n'avez aucun rendez-vous aujourd'hui."

    if "demain" in q:
        tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        demain = [r for r in rows if r["date_rdv"] == tomorrow]
        if demain:
            resume = "; ".join(f"{r['heure_rdv']} — {r['nom']}" for r in demain)
            return f"Demain vous avez {len(demain)} RDV : {resume}."
        return "Vous n'avez aucun rendez-vous demain."

    if any(w in q for w in ["cette semaine", "semaine"]):
        start = datetime.date.today()
        end   = start + datetime.timedelta(days=7)
        semaine = [r for r in rows if start.isoformat() <= r["date_rdv"] <= end.isoformat()]
        if semaine:
            resume = "; ".join(f"{r['date_rdv']} {r['heure_rdv']} — {r['nom']}" for r in semaine[:5])
            return f"Cette semaine vous avez {len(semaine)} RDV : {resume}."
        return "Aucun rendez-vous prévu cette semaine."

    if any(w in q for w in ["liste", "tous", "tout", "affiche", "montre", "voir", "quels"]):
        if not rows:
            return "Votre agenda est vide pour l'instant."
        resume = "; ".join(f"{r['date_rdv']} {r['heure_rdv']} — {r['nom']}" for r in rows[:5])
        suffix = f" (et {total - 5} autres)" if total > 5 else ""
        return f"Voici vos RDV : {resume}{suffix}."

    if any(w in q for w in ["dernier", "passé", "précédent"]):
        passes = [r for r in rows if r["date_rdv"] < today]
        if passes:
            r = passes[-1]
            return f"Votre dernier RDV passé était le {r['date_rdv']} à {r['heure_rdv']} avec {r['nom']}."
        return "Aucun rendez-vous passé trouvé dans l'agenda."

    if any(w in q for w in ["bonjour", "salut", "bonsoir", "hello"]):
        return "Bonjour ! Je suis votre assistant agenda. Vous pouvez me demander votre prochain RDV, la liste de vos rendez-vous, ceux d'aujourd'hui, de demain, etc."

    if any(w in q for w in ["merci", "super", "parfait", "ok", "d'accord"]):
        return "De rien ! N'hésitez pas si vous avez d'autres questions sur votre agenda."

    if total == 0:
        return "Votre agenda est vide. Commencez par ajouter un rendez-vous depuis la page Planification."

    return (
        f"Votre agenda contient {total} rendez-vous ({len(futurs)} à venir). "
        f"Je peux vous dire : le prochain RDV, les RDV d'aujourd'hui ou de demain, "
        f"ceux de la semaine, la liste complète ou le nombre total."
    )


if __name__ == "__main__":
    app.run(debug=True)