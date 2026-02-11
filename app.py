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
    
    # 👇👇👇 REMETS TON LIEN GOOGLE SHEET ICI ENTRE LES GUILLEMETS 👇👇👇
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
    if df.empty:
        return pd.DataFrame(columns=["Date", "Account", "Firm", "Initial", "Target", "Balance"])
    df["Date"] = pd.to_datetime(df["Date"], errors='coerce').dt.date
    return df

# --- INTERFACE ---
st.title("☁️ Suivi Prop Firm")

try:
    sheet = get_google_sheet()
    df = load_data(sheet)
except:
    st.stop()

# --- SIDEBAR : CRÉATION DE COMPTE ---
with st.sidebar:
    st.header("➕ Nouveau Compte")
    with st.form("add_account"):
        name = st.text_input("Nom (ex: Eval 1)")
        firm = st.text_input("Prop Firm (ex: Apex)")
        initial = st.number_input("Capital Initial", 25000.0, step=100.0)
        target = st.number_input("Objectif Cible (Total)", 26600.0, step=100.0)
        submitted = st.form_submit_button("Créer")
        
        if submitted:
            if not df.empty and name in df["Account"].unique():
                st.error("Ce compte existe déjà !")
            else:
                new_row = [str(datetime.now().date()), name, firm, initial, target, initial]
                sheet.append_row(new_row)
                st.success(f"Compte {name} créé !")
                st.rerun()

# --- DASHBOARD ---
if df.empty:
    st.info("Ajoute un compte à gauche pour commencer.")
else:
    accounts_list = df["Account"].unique()
    selected_acc = st.selectbox("Choisir le compte", accounts_list)
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
                    new_entry = [str(u_date), selected_acc, firm_name, float(initial_bal), float(target_bal), new_balance_calc]
                    sheet.append_row(new_entry)
                    st.success("Ajouté !")
                    st.rerun()
            
            # --- ZONE DE SUPPRESSION ---
            st.divider()
            with st.expander("🚨 Zone Danger (Suppression)"):
                st.write(f"Voulez-vous vraiment supprimer le compte **{selected_acc}** et tout son historique ?")
                if st.button("Oui, supprimer définitivement", type="primary"):
                    # Logique de suppression propre dans Google Sheets
                    # 1. On garde tout sauf ce compte
                    new_df = df[df["Account"] != selected_acc]
                    
                    # 2. On efface le sheet
                    sheet.clear()
                    
                    # 3. On remet les entêtes
                    sheet.append_row(["Date", "Account", "Firm", "Initial", "Target", "Balance"])
                    
                    # 4. On remet les données (s'il en reste)
                    if not new_df.empty:
                        # Convertir les dates en chaînes pour éviter les erreurs JSON
                        new_df['Date'] = new_df['Date'].astype(str)
                        sheet.append_rows(new_df.values.tolist())
                    
                    st.success(f"Compte {selected_acc} supprimé !")
                    st.rerun()
