"""
agenda.py — Gestion des rendez-vous (Partie 9)
Lancer : python agenda.py
"""
import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk
import os
from datetime import date, timedelta, datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "address_book.db")

# Créneaux de 30 minutes de 08h00 à 18h00
CRENEAUX = [
    f"{h:02d}:{m:02d}"
    for h in range(8, 18)
    for m in (0, 30)
]

JOURS_FR = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
MOIS_FR  = ["", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
             "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]


# ── Base de données ────────────────────────────────────────────────────────────

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def rdv_du_jour(date_str: str) -> list:
    """Retourne la liste des créneaux déjà pris pour une date."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT r.heure_rdv, r.motif, r.id, c.nom "
        "FROM rendez_vous r "
        "JOIN contacts c ON c.id = r.contact_id "
        "WHERE r.date_rdv = ?",
        (date_str,)
    ).fetchall()
    conn.close()
    return rows


def reserver(contact_id: int, date_str: str, heure: str, motif: str) -> bool:
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO rendez_vous (contact_id, date_rdv, heure_rdv, motif) VALUES (?, ?, ?, ?)",
            (contact_id, date_str, heure, motif)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False          # Créneau déjà pris
    finally:
        conn.close()


def annuler_rdv(rdv_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM rendez_vous WHERE id = ?", (rdv_id,))
    conn.commit()
    conn.close()


def get_contacts() -> list:
    conn = get_conn()
    rows = conn.execute("SELECT id, nom FROM contacts ORDER BY nom").fetchall()
    conn.close()
    return rows


# ── Interface principale ───────────────────────────────────────────────────────

class AgendaApp:
    def __init__(self, root: tk.Tk):
        self.root  = root
        self.root.title("Agenda — Gestion des RDV")
        self.root.geometry("900x640")
        self.root.configure(bg="#f0f4f8")

        # Date courante du calendrier
        today = date.today()
        self.current_year  = today.year
        self.current_month = today.month
        self.selected_date = today
        self._pending_slot = None   # créneau sélectionné mais pas encore confirmé

        self._build_ui()
        self._refresh_all()

    # ── Construction de l'interface ────────────────────────────────────────────

    def _build_ui(self):
        # ── Panneau gauche : Calendrier ────────────────────────────────────────
        left = tk.Frame(self.root, bg="#f0f4f8", width=320)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=12, pady=12)
        left.pack_propagate(False)

        # Navigation mois
        nav = tk.Frame(left, bg="#f0f4f8")
        nav.pack(fill=tk.X, pady=(0, 6))
        tk.Button(nav, text="◀", command=self._prev_month,
                  bg="#4361ee", fg="white", relief="flat", cursor="hand2",
                  font=("Arial", 10, "bold"), padx=8).pack(side=tk.LEFT)
        self.lbl_mois = tk.Label(nav, text="", bg="#f0f4f8",
                                 font=("Arial", 12, "bold"), fg="#1a1a2e")
        self.lbl_mois.pack(side=tk.LEFT, expand=True)
        tk.Button(nav, text="▶", command=self._next_month,
                  bg="#4361ee", fg="white", relief="flat", cursor="hand2",
                  font=("Arial", 10, "bold"), padx=8).pack(side=tk.RIGHT)

        # Grille du calendrier
        self.cal_frame = tk.Frame(left, bg="#f0f4f8")
        self.cal_frame.pack(fill=tk.BOTH)

        # Séparateur
        tk.Frame(left, height=1, bg="#dee2e6").pack(fill=tk.X, pady=10)

        # Formulaire de réservation
        tk.Label(left, text="Nouvelle réservation", bg="#f0f4f8",
                 font=("Arial", 11, "bold"), fg="#1a1a2e").pack(anchor="w")

        tk.Label(left, text="Contact :", bg="#f0f4f8",
                 font=("Arial", 9), fg="#555").pack(anchor="w", pady=(6, 0))
        self.combo_contact = ttk.Combobox(left, state="readonly", width=32)
        self.combo_contact.pack(anchor="w")

        tk.Label(left, text="Créneau :", bg="#f0f4f8",
                 font=("Arial", 9), fg="#555").pack(anchor="w", pady=(6, 0))
        self.combo_creneau = ttk.Combobox(left, state="readonly", width=10)
        self.combo_creneau.pack(anchor="w")
        self.combo_creneau.bind("<<ComboboxSelected>>", self._on_creneau_selected)

        tk.Label(left, text="Motif :", bg="#f0f4f8",
                 font=("Arial", 9), fg="#555").pack(anchor="w", pady=(6, 0))
        self.entry_motif = tk.Entry(left, width=35)
        self.entry_motif.pack(anchor="w")

        tk.Button(left, text="  ✔ Réserver  ", command=self._reserver,
                  bg="#2d6a4f", fg="white", relief="flat", cursor="hand2",
                  font=("Arial", 10, "bold"), pady=6
                  ).pack(anchor="w", pady=10)

        # ── Panneau droit : Créneaux du jour ──────────────────────────────────
        right = tk.Frame(self.root, bg="white",
                         relief="flat", bd=0)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 12), pady=12)

        self.lbl_jour = tk.Label(right, text="", bg="white",
                                 font=("Arial", 13, "bold"), fg="#1a1a2e", anchor="w")
        self.lbl_jour.pack(fill=tk.X, padx=16, pady=(12, 4))

        # Tableau des créneaux
        cols = ("heure", "contact", "motif", "action")
        self.tree = ttk.Treeview(right, columns=cols, show="headings",
                                 selectmode="browse", height=20)
        self.tree.heading("heure",   text="Heure")
        self.tree.heading("contact", text="Contact")
        self.tree.heading("motif",   text="Motif")
        self.tree.heading("action",  text="")
        self.tree.column("heure",   width=70,  anchor="center")
        self.tree.column("contact", width=200)
        self.tree.column("motif",   width=260)
        self.tree.column("action",  width=80,  anchor="center")

        # Style : libre=vert, pris=rouge, en_cours=orange (sélectionné non confirmé)
        self.tree.tag_configure("libre",   background="#f0fff4", foreground="#2d6a4f")
        self.tree.tag_configure("pris",    background="#fff0f0", foreground="#e63946")
        self.tree.tag_configure("en_cours", background="#fff3cd", foreground="#664d03")

        sb = ttk.Scrollbar(right, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(16, 0), pady=8)
        sb.pack(side=tk.LEFT, fill=tk.Y, pady=8, padx=(0, 8))

        self.tree.bind("<ButtonRelease-1>", self._on_tree_click)

    # ── Navigation calendrier ──────────────────────────────────────────────────

    def _prev_month(self):
        if self.current_month == 1:
            self.current_month = 12
            self.current_year -= 1
        else:
            self.current_month -= 1
        self._build_calendar()

    def _next_month(self):
        if self.current_month == 12:
            self.current_month = 1
            self.current_year += 1
        else:
            self.current_month += 1
        self._build_calendar()

    def _build_calendar(self):
        """Reconstruit la grille mensuelle."""
        for w in self.cal_frame.winfo_children():
            w.destroy()

        self.lbl_mois.config(
            text=f"{MOIS_FR[self.current_month]} {self.current_year}"
        )

        today = date.today()

        # En-têtes jours
        for i, j in enumerate(JOURS_FR):
            tk.Label(self.cal_frame, text=j, bg="#f0f4f8",
                     font=("Arial", 8, "bold"), fg="#666",
                     width=4).grid(row=0, column=i, pady=2)

        # Premier jour du mois
        first = date(self.current_year, self.current_month, 1)
        start_col = first.weekday()   # 0 = lundi

        # Nombre de jours
        if self.current_month == 12:
            last = date(self.current_year + 1, 1, 1) - timedelta(days=1)
        else:
            last = date(self.current_year, self.current_month + 1, 1) - timedelta(days=1)
        nb_days = last.day

        row, col = 1, start_col
        for day in range(1, nb_days + 1):
            d = date(self.current_year, self.current_month, day)
            is_today    = (d == today)
            is_selected = (d == self.selected_date)

            if is_selected:
                bg, fg, relief = "#4361ee", "white", "flat"
            elif is_today:
                bg, fg, relief = "#e8ecff", "#4361ee", "flat"
            elif d < today:
                bg, fg, relief = "#f0f4f8", "#aaa", "flat"
            else:
                bg, fg, relief = "#f0f4f8", "#1a1a2e", "flat"

            btn = tk.Button(
                self.cal_frame, text=str(day), width=3,
                bg=bg, fg=fg, relief=relief,
                font=("Arial", 9, "bold" if is_today or is_selected else "normal"),
                cursor="hand2" if d >= today else "arrow",
                command=lambda dd=d: self._select_date(dd)
            )
            if d < today:
                btn.config(state="disabled")
            btn.grid(row=row, column=col, padx=1, pady=1)

            col += 1
            if col > 6:
                col = 0
                row += 1

    def _select_date(self, d: date):
        self.selected_date = d
        self._build_calendar()
        self._refresh_creneaux()

    # ── Rafraîchissement ───────────────────────────────────────────────────────

    def _refresh_all(self):
        self._refresh_contacts()
        self._build_calendar()
        self._refresh_creneaux()

    def _refresh_contacts(self):
        contacts = get_contacts()
        self._contacts = {f"{c['nom']}": c['id'] for c in contacts}
        self.combo_contact["values"] = list(self._contacts.keys())
        if self._contacts:
            self.combo_contact.current(0)

    def _refresh_creneaux(self):
        """Met à jour le tableau des créneaux pour la date sélectionnée."""
        date_str = self.selected_date.strftime("%Y-%m-%d")
        self.lbl_jour.config(
            text=f"Agenda du {self.selected_date.strftime('%A %d %B %Y').capitalize()}"
        )

        # Index des RDV existants
        rdvs = rdv_du_jour(date_str)
        rdv_map = {r["heure_rdv"]: r for r in rdvs}

        # Créneaux disponibles pour le formulaire
        libres = [h for h in CRENEAUX if h not in rdv_map]
        self.combo_creneau["values"] = libres
        if libres:
            self.combo_creneau.current(0)

        # Remplissage du tableau
        for row in self.tree.get_children():
            self.tree.delete(row)

        for heure in CRENEAUX:
            if heure in rdv_map:
                r = rdv_map[heure]
                self.tree.insert("", "end",
                                 values=(heure, r["nom"], r["motif"] or "—", "🗑 Annuler"),
                                 tags=("pris",),
                                 iid=f"rdv_{r['id']}")
            else:
                tag = "en_cours" if heure == self._pending_slot else "libre"
                self.tree.insert("", "end",
                                 values=(heure, "— Libre —", "", ""),
                                 tags=(tag,))

    # ── Actions ────────────────────────────────────────────────────────────────

    def _reserver(self):
        nom_contact = self.combo_contact.get()
        heure       = self.combo_creneau.get()
        motif       = self.entry_motif.get().strip()
        date_str    = self.selected_date.strftime("%Y-%m-%d")

        if not nom_contact:
            messagebox.showwarning("Attention", "Sélectionnez un contact.")
            return
        if not heure:
            messagebox.showwarning("Attention", "Aucun créneau disponible pour ce jour.")
            return

        contact_id = self._contacts[nom_contact]
        ok = reserver(contact_id, date_str, heure, motif)
        if ok:
            messagebox.showinfo(
                "Réservé",
                f"RDV confirmé avec {nom_contact}\nle {date_str} à {heure}"
            )
            self.entry_motif.delete(0, tk.END)
            self._pending_slot = None
            self._refresh_creneaux()
        else:
            messagebox.showerror("Erreur", "Ce créneau vient d'être pris. Actualisez.")

    def _on_tree_click(self, event):
        """Sélectionne un créneau libre ou annule un RDV au clic."""
        region = self.tree.identify_region(event.x, event.y)
        col    = self.tree.identify_column(event.x)
        iid    = self.tree.identify_row(event.y)

        if region == "cell" and col == "#4" and iid.startswith("rdv_"):
            rdv_id  = int(iid.split("_")[1])
            valeurs = self.tree.item(iid, "values")
            heure   = valeurs[0]
            contact = valeurs[1]
            if messagebox.askyesno(
                "Confirmation",
                f"Annuler le RDV de {contact} à {heure} ?"
            ):
                annuler_rdv(rdv_id)
                self._refresh_creneaux()
        elif region == "cell" and iid:
            tags = self.tree.item(iid, "tags")
            if "libre" in tags or "en_cours" in tags:
                heure = self.tree.item(iid, "values")[0]
                self.combo_creneau.set(heure)
                self._set_pending_slot(heure)


    def _on_creneau_selected(self, event=None):
        self._set_pending_slot(self.combo_creneau.get())

    def _set_pending_slot(self, heure):
        """Surligne en orange le créneau sélectionné dans le tableau."""
        # Remettre l'ancien en "libre"
        if self._pending_slot:
            for iid in self.tree.get_children():
                if (self.tree.item(iid, "values")[0] == self._pending_slot
                        and "en_cours" in self.tree.item(iid, "tags")):
                    self.tree.item(iid, tags=("libre",))
                    break
        self._pending_slot = heure
        # Appliquer le nouveau surlignage
        for iid in self.tree.get_children():
            if self.tree.item(iid, "values")[0] == heure:
                if "libre" in self.tree.item(iid, "tags"):
                    self.tree.item(iid, tags=("en_cours",))
                    self.tree.see(iid)
                break


# ── Point d'entrée ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()
    app  = AgendaApp(root)
    root.mainloop()