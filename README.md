# Contact Manager — Flask Web Application

A full-stack contact management web application built with Python and Flask. Supports user authentication, categorized contacts, AI-powered assistance, email integration, and CSV export.

---

## Features

- **User Authentication** — Secure login with SHA-256 hashed passwords and session management
- **Contact CRUD** — Add, edit, delete, and search contacts with full validation
- **Categories** — Classify contacts as Client, Fournisseur, Patient, Laboratoire, Partenaire, or Autre
- **Favorites** — Mark and filter favorite contacts
- **Email Integration** — Send emails directly from the app using Gmail SMTP
- **AI Assistant** — Google Gemini integration for smart contact suggestions
- **CSV Export** — Export your entire contact list to CSV in one click
- **Agenda** — Built-in calendar/agenda linked to contacts
- **Settings Panel** — Configure SMTP, API keys, and preferences from the UI

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3, Flask |
| Database | SQLite (via `sqlite3`) |
| Frontend | Jinja2 templates, HTML/CSS |
| Auth | SHA-256 hashing, Flask sessions |
| AI | Google Gemini API |
| Email | smtplib, Gmail SMTP |

---

## Project Structure

```
Gestion-des-contacts/
├── app.py            # Flask routes and main application
├── auth.py           # Login window (Tkinter desktop version)
├── database.py       # SQLite database class and schema
├── contact.py        # Contact data model
├── gui.py            # Desktop GUI (Tkinter)
├── main.py           # Entry point
├── templates/
│   ├── base.html     # Base layout
│   ├── index.html    # Contact list view
│   ├── form.html     # Add/edit contact form
│   ├── login.html    # Authentication page
│   ├── agenda.html   # Agenda view
│   ├── send_email.html
│   └── settings.html
├── requirements.txt
└── address_book.db   # SQLite database (auto-created)
```

---

## Setup and Installation

**1. Clone the repository**
```bash
git clone https://github.com/MERYEMELOSMANI/Gestion-des-contacts.git
cd Gestion-des-contacts
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Configure environment variables** (optional — for email and AI features)
```bash
export SMTP_EMAIL="your.email@gmail.com"
export SMTP_PASSWORD="your_app_password"   # Gmail App Password
export GEMINI_API_KEY="your_gemini_key"
```

**4. Initialize the database and create admin account**
```bash
python database.py
```

**5. Run the application**
```bash
python app.py
```

Open `http://localhost:5000` in your browser.

Default credentials: `admin` / `admin123`

---

## Contact Fields

| Field | Description |
|---|---|
| Name | Full name (minimum 3 characters) |
| Email | Validated email address |
| Phone | International format (`+` prefix, 10+ digits) |
| Company | Organization name |
| Category | Client / Fournisseur / Patient / Laboratoire / Partenaire / Autre |
| Address | Physical address |
| Function | Job title or role |
| Favorite | Starred contact flag |

---

## Gmail Setup (for email features)

To enable email sending, generate a [Gmail App Password](https://myaccount.google.com/apppasswords) and set it as `SMTP_PASSWORD`. Two-factor authentication must be enabled on your Google account.

---

## License

MIT License
