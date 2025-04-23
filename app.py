import streamlit as st
import matplotlib.pyplot as plt

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

hipoteca = preu_pis * (1 - aportacio / 100)
interes_anual = 0.019
quota_hipoteca = hipoteca * interes_anual

neteja = nits_ocupades * 80 / 4
comissions = ingressos_bruts * 0.13
serveis = 2500
taxes_turistiques = nits_ocupades * 3.5
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

with st.expander("📑 Detall complet de despeses"):
    st.markdown(f"""
    - 🧹 **Neteja estimada**: CHF {neteja:,.0f}
    - 💼 **Comissions plataformes**: CHF {comissions:,.0f}
    - 💡 **Serveis anuals (assegurances, wifi, etc.)**: CHF {serveis:,.0f}
    - 🏛️ **Taxes turístiques**: CHF {taxes_turistiques:,.0f}
    - 🔧 **Manteniment i petites reparacions**: CHF {manteniment:,.0f}
    """)

# --- PIE CHART ---
st.subheader("📊 Gràfic: Distribució de les despeses")
labels = ['Neteja', 'Comissions', 'Serveis', 'Taxes turístiques', 'Manteniment']
sizes = [neteja, comissions, serveis, taxes_turistiques, manteniment]
colors = ['#ff9999','#66b3ff','#99ff99','#ffcc99','#dddddd']
fig1, ax1 = plt.subplots()
ax1.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=140)
ax1.axis('equal')
st.pyplot(fig1)

# --- EVOLUCIÓ DEL BENEFICI ---
st.subheader("📈 Evolució del benefici acumulat")
years = list(range(1, 21))
accumulated_profit = []
profit = benefici_despres_hipoteca
accumulated = 0
break_even_year = None
for year in years:
    accumulated += profit
    accumulated_profit.append(accumulated)
    if break_even_year is None and accumulated >= (preu_pis * (aportacio / 100)):
        break_even_year = year

fig2, ax2 = plt.subplots()
ax2.plot(years, accumulated_profit, label='Benefici acumulat', linewidth=2)
ax2.axhline(y=(preu_pis * (aportacio / 100)), color='red', linestyle='--', label='Inversió inicial')
ax2.set_title("Evolució de l'inversió i punt d'equilibri")
ax2.set_xlabel("Anys")
ax2.set_ylabel("CHF")
ax2.legend()
st.pyplot(fig2)

if break_even_year:
    st.success(f"🎯 Break-even estimat: any {break_even_year}")
else:
    st.warning("No s'arriba a recuperar la inversió en 20 anys.")
