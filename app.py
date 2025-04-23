import streamlit as st

st.set_page_config(page_title="Simulador Inversió Turística a Suïssa", layout="centered")
st.title("Simulador de rendibilitat de pis turístic a Suïssa")

st.markdown("""
Aquesta eina t'ajuda a estimar els beneficis anuals d'un pis de lloguer turístic a zones com Interlaken, tenint en compte el teu permís de residència, hipoteca, i més.
""")

# --- DEFINICIÓ DE ZONES PERMESES SEGONS PERMÍS ---
zones_permeses = {
    "B": ["Interlaken", "Zermatt", "Verbier", "Grindelwald"],
    "C": ["Interlaken", "Zermatt", "Verbier", "Grindelwald", "Lugano", "Zurich", "Lucerna"],
    "Suís": ["Interlaken", "Zermatt", "Verbier", "Grindelwald", "Lugano", "Zurich", "Lucerna", "Totes"]
}

# --- INPUTS ---
col1, col2 = st.columns(2)

with col1:
    permis = st.selectbox("Permís de residència", ["B", "C", "Suís"])
    zona = st.selectbox("Zona disponible segons permís", zones_permeses[permis])
    preu_pis = st.number_input("Preu del pis (CHF)", min_value=100000, value=600000, step=10000)
    aportacio = st.slider("% Aportació pròpia", 10, 100, 20)

with col2:
    capacitat = st.selectbox("Capacitat del pis", [2, 4, 6])
    preu_nit = st.number_input("Preu mitjà per nit (CHF)", min_value=50, value=280, step=10)
    ocupacio = st.slider("Ocupació mitjana anual (%)", 30, 100, 65)
    any_lloguer = st.checkbox("Lloguer tot l'any", value=True)

# --- CÀLCULS ---
dies_ocupats = 365 if any_lloguer else 200
nits_ocupades = int((ocupacio / 100) * dies_ocupats)
ingressos_bruts = preu_nit * nits_ocupades

hipoteca = preu_pis * (1 - aportacio / 100)
interes_anual = 0.019
quota_hipoteca = hipoteca * interes_anual

neteja = nits_ocupades * 80 / 4  # neteja cada 4 reserves aprox.
comissions = ingressos_bruts * 0.13
serveis = 2500
taxes = 2000
manteniment = 1500

despeses_totals = neteja + comissions + serveis + taxes + manteniment
benefici_net = ingressos_bruts - despeses_totals
benefici_despres_hipoteca = benefici_net - quota_hipoteca
roi = (benefici_despres_hipoteca / (preu_pis * (aportacio / 100))) * 100

# --- RESULTATS ---
st.subheader("Resultats")
st.markdown(f"**Ingressos bruts anuals:** CHF {ingressos_bruts:,.0f}")
st.markdown(f"**Despeses totals (sense hipoteca):** CHF {despeses_totals:,.0f}")
st.markdown(f"**Quota hipoteca (interès):** CHF {quota_hipoteca:,.0f}")
st.markdown(f"**Benefici net (després de despeses i hipoteca):** CHF {benefici_despres_hipoteca:,.0f}")
st.markdown(f"**ROI sobre capital aportat:** {roi:.1f}%")

if permis == "B" and zona not in zones_permeses["B"]:
    st.warning("Amb permís B només pots comprar en zones turístiques específiques designades per la llei suïssa.")

if roi < 5:
    st.info("Aquest projecte pot tenir un rendiment baix. Considera ajustar preus o reduir despeses.")

