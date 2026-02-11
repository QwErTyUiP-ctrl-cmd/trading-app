import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import matplotlib.pyplot as plt
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="Prop Firm Tracker", layout="wide")

# --- CONNEXION GOOGLE SHEETS ---
def get_google_sheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    
    if "gcp_service_account" in st.secrets:
        creds_dict = st.secrets["gcp_service_account"]
    else:
        st.error("⚠️ Clé introuvable ! Configure les 'Secrets' sur Streamlit Cloud.")
        st.stop()

    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    
    # 👇👇👇 COLLE TON LIEN GOOGLE SHEET ICI ENTRE LES GUILLEMETS 👇👇👇
    SHEET_URL = "https://docs.google.com/spreadsheets/d/1KnEQC__Q9U6bdJF0AzPPuwApfCgGS5-Qt_svtWSWxEE/edit?gid=0#gid=0" 
    
    try:
        sheet = client.open_by_url(SHEET_URL).sheet1
        return sheet
    except Exception as e:
        st.error(f"Erreur d'accès : {e}")
        st.stop()

# --- CHARGEMENT DES DONNÉES ---
def load_data(sheet):
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    # Si le dataframe est vide, on crée les colonnes requises (avec User en plus)
    if df.empty:
        return pd.DataFrame(columns=["Date", "Account", "Firm", "Initial", "Target", "Balance", "User"])
    
    df["Date"] = pd.to_datetime(df["Date"], errors='coerce').dt.date
    
    # Sécurité : Si la colonne User n'existe pas encore dans les données lues, on la crée vide
    if "User" not in df.columns:
        df["User"] = "Inconnu"
        
    return df

# --- INTERFACE ---
st.title("👥 Suivi Prop Firm")

try:
    sheet = get_google_sheet()
    df = load_data(sheet)
except:
    st.stop()

# --- SÉLECTION DE L'UTILISATEUR (SIDEBAR) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/476/476863.png", width=50) # Petite icône sympa
    st.write("### Qui est connecté ?")
    # C'est ici qu'on choisit l'interface
    current_user = st.radio("", ["Romain", "Sacha"])
    st.divider()

# --- CRÉATION DE COMPTE (Filtré par utilisateur) ---
with st.sidebar:
    st.header(f"➕ Ajouter pour {current_user}")
    with st.form("add_account"):
        name = st.text_input("Nom (ex: Eval 1)")
        firm = st.text_input("Prop Firm (ex: Apex)")
        initial = st.number_input("Capital Initial ($)", 25000.0, step=100.0)
        target = st.number_input("Objectif Cible ($)", 26600.0, step=100.0)
        submitted = st.form_submit_button("Créer le compte")
        
        if submitted:
            # On vérifie si ce nom de compte existe déjà (globalement pour éviter les conflits)
            if not df.empty and name in df["Account"].unique():
                st.error("Ce nom de compte existe déjà (peut-être chez l'autre utilisateur) !")
            else:
                # On ajoute la ligne AVEC le nom de l'utilisateur en fin de ligne
                new_row = [str(datetime.now().date()), name, firm, initial, target, initial, current_user]
                sheet.append_row(new_row)
                st.success(f"Compte {name} créé pour {current_user} !")
                st.rerun()

# --- FILTRAGE DES DONNÉES ---
# On ne garde que les comptes qui appartiennent à l'utilisateur sélectionné
if not df.empty:
    user_df = df[df["User"] == current_user]
else:
    user_df = pd.DataFrame()

# --- DASHBOARD ---
if user_df.empty:
    st.info(f"Bonjour {current_user} ! Tu n'as pas encore de compte. Ajoute-en un à gauche.")
else:
    accounts_list = user_df["Account"].unique()
    selected_acc = st.selectbox(f"Comptes de {current_user}", accounts_list)
    
    # Récupération des données du compte choisi
    acc_data = df[df["Account"] == selected_acc].sort_values("Date")
    
    if not acc_data.empty:
        last_entry = acc_data.iloc[-1]
        current_bal = last_entry["Balance"]
        initial_bal = last_entry["Initial"]
        target_bal = last_entry["Target"]
        firm_name = last_entry["Firm"]
        
        total_pnl = current_bal - initial_bal
        distance = target_bal - current_bal
        prog_pct = max(0.0, min(1.0, total_pnl / (target_bal - initial_bal))) if (target_bal - initial_bal) > 0 else 0

        # En-tête
        st.markdown(f"## {selected_acc} <span style='font-size:0.6em; color:gray'>({firm_name})</span>", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Solde Total", f"${current_bal:,.2f}", f"{total_pnl:+.2f}$ global")
        c2.metric("Objectif", f"${target_bal:,.2f}")
        c3.metric("Progression", f"{prog_pct*100:.1f}%")
        c4.metric("Manque", f"${distance:,.2f}")
        st.progress(prog_pct)
        st.divider()

        col_left, col_right = st.columns([2, 1])

        with col_left:
            st.subheader("📈 Évolution")
            fig, ax = plt.subplots(figsize=(10, 4))
            fig.patch.set_facecolor('#0E1117')
            ax.set_facecolor('#0E1117')
            ax.plot(acc_data["Date"], acc_data["Balance"], marker='o', color='#00CC96', linewidth=2)
            ax.axhline(initial_bal, color='white', linestyle='--', alpha=0.3, label="Départ")
            ax.axhline(target_bal, color='#636EFA', linestyle='--', label="Objectif")
            ax.tick_params(colors='white')
            for spine in ax.spines.values(): spine.set_edgecolor('white')
            ax.legend(facecolor='#0E1117', labelcolor='white')
            st.pyplot(fig)

            st.subheader("📅 Historique des Gains")
            hist_df = acc_data[["Date", "Balance"]].copy()
            hist_df["Gain Journalier ($)"] = hist_df["Balance"].diff().fillna(0)
            hist_df = hist_df.sort_values("Date", ascending=False)
            st.dataframe(hist_df, column_config={"Balance": st.column_config.NumberColumn(format="$%.2f"), "Gain Journalier ($)": st.column_config.NumberColumn(format="$%.2f")}, use_container_width=True, hide_index=True)

        with col_right:
            st.subheader("📝 Ajouter une journée")
            with st.form("update_pnl"):
                u_date = st.date_input("Date du trade", datetime.now())
                daily_pnl = st.number_input("Gain ou Perte du jour ($)", value=0.0, step=10.0)
                submit = st.form_submit_button("Valider")
                if submit:
                    new_balance_calc = float(current_bal) + daily_pnl
                    # IMPORTANT : On ajoute aussi le current_user dans la nouvelle ligne
                    new_entry = [str(u_date), selected_acc, firm_name, float(initial_bal), float(target_bal), new_balance_calc, current_user]
                    sheet.append_row(new_entry)
                    st.success("Ajouté !")
                    st.rerun()
            
            # --- ZONE DE SUPPRESSION ---
            st.divider()
            with st.expander("🚨 Zone Danger"):
                st.write(f"Supprimer le compte **{selected_acc}** ?")
                if st.button("Oui, supprimer", type="primary"):
                    # On garde tout sauf ce compte
                    new_df = df[df["Account"] != selected_acc]
                    sheet.clear()
                    # On remet les entêtes AVEC USER
                    sheet.append_row(["Date", "Account", "Firm", "Initial", "Target", "Balance", "User"])
                    if not new_df.empty:
                        new_df['Date'] = new_df['Date'].astype(str)
                        sheet.append_rows(new_df.values.tolist())
                    st.success("Compte supprimé !")
                    st.rerun()
