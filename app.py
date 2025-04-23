import streamlit as st

st.set_page_config(page_title="Simulador Inversió Turística a Suïssa", layout="centered")
st.title("📊 Simulador de rendibilitat de pis turístic a Suïssa")

st.markdown("""
Aquesta eina ajuda a persones amb **permís C o nacionalitat suïssa** a estimar el retorn de la inversió en pisos turístics a Suïssa.
""")

# --- ZONES PERMESES ---
zones_permeses = ["Interlaken", "Zermatt", "Verbier", "Grindelwald", "Lugano", "Zurich", "Lucerna"]

# --- INPUTS ---
col1, col2 = st.columns(2)

with col1:
    permis = st.selectbox("Permís de residència", ["C", "Suís"])
    zona = st.selectbox("Zona turística", zones_permeses)
    preu_pis = st.number_input("Preu total del pis (CHF)", min_value=200000, value=600000, step=10000)
    aportacio = st.slider("Aportació pròpia (%)", 10, 100, 20)

with col2:
    capacitat = st.selectbox("Capacitat del pis", [2, 4, 6])
    preu_nit = st.number_input("Preu mitjà per nit (CHF)", min_value=50, value=280, step=10)
    ocupacio = st.slider("Ocupació anual (%)", 30, 100, 65)
    any_lloguer = st.checkbox("Està llogat tot l'any?", value=True)

# --- CÀLCULS ---
dies_ocupats = 365 if any_lloguer else 200
nits_ocupades = int((ocupacio / 100) * dies_ocupats)
ingressos_bruts = preu_nit * nits_ocupades

# Hipoteca
hipoteca = preu_pis * (1 - aportacio / 100)
interes_anual = 0.019
quota_hipoteca = hipoteca * interes_anual

# Despeses operatives
neteja = nits_ocupades * 80 / 4  # neteja cada 4 reserves
comissions = ingressos_bruts * 0.13  # ex: Airbnb + Stripe
serveis = 2500  # wifi, assegurances, comunitat
taxes_turistiques = nits_ocupades * 3.5  # taxa per persona i nit (2 pers. de mitjana)
manteniment = 1500

despeses_totals = neteja + comissions + serveis + taxes_turistiques + manteniment
benefici_net = ingressos_bruts - despeses_totals
benefici_despres_hipoteca = benefici_net - quota_hipoteca
roi = (benefici_despres_hipoteca / (preu_pis * (aportacio / 100))) * 100

# --- RESULTATS ---
st.subheader("📈 Resultats anuals de la inversió")
st.markdown(f"**Ingressos bruts estimats:** CHF {ingressos_bruts:,.0f}")
st.markdown(f"**Despeses totals (sense hipoteca):** CHF {despeses_totals:,.0f}")
st.markdown(f"**Quota anual d'interès hipoteca (~1.9%):** CHF {quota_hipoteca:,.0f}")
st.markdown(f"**Benefici net (després de tot):** CHF {benefici_despres_hipoteca:,.0f}")
st.markdown(f"**ROI sobre el capital invertit:** {roi:.2f}%")

# --- DESGLOSSAMENT ---
with st.expander("📑 Detall complet de despeses"):
    st.markdown(f"""
    - 🧹 **Neteja estimada**: CHF {neteja:,.0f}
    - 💼 **Comissions plataformes**: CHF {comissions:,.0f}
    - 💡 **Serveis anuals (assegurances, wifi, etc.)**: CHF {serveis:,.0f}
    - 🏛️ **Taxes turístiques**: CHF {taxes_turistiques:,.0f}
    - 🔧 **Manteniment i petites reparacions**: CHF {manteniment:,.0f}
    """)

# --- AVÍS SI ROI BAIX ---
if roi < 4:
    st.warning("Aquest ROI pot ser baix. Potser cal ajustar preus o despeses.")
