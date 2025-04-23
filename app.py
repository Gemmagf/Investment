import streamlit as st
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

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

# --- PIE CHART DE DESPESES ---
st.subheader("📊 Distribució de les despeses")
labels = ['Neteja', 'Comissions', 'Serveis', 'Taxes turístiques', 'Manteniment']
sizes = [neteja, comissions, serveis, taxes_turistiques, manteniment]
colors = ['#ff9999','#66b3ff','#99ff99','#ffcc99','#c2c2f0']
explode = (0.05, 0.05, 0.05, 0.05, 0.05)

fig1, ax1 = plt.subplots()
ax1.pie(sizes, labels=labels, colors=colors, explode=explode, autopct='%1.1f%%', startangle=140, shadow=True)
ax1.axis('equal')
st.pyplot(fig1)

# --- EVOLUCIÓ DEL BENEFICI I COSTOS ---
st.subheader("📊 Evolució del benefici acumulat vs costos")
years = np.arange(1, 21)
profit = benefici_despres_hipoteca
accumulated_profit = np.cumsum([profit]*20)
costs = np.cumsum([despeses_totals + quota_hipoteca]*20)
initial_investment = preu_pis * (aportacio / 100)

fig2, ax2 = plt.subplots()
bar_width = 0.35
ax2.bar(years - bar_width/2, accumulated_profit, bar_width, label='Benefici acumulat', color='#8fd694')
ax2.bar(years + bar_width/2, costs, bar_width, label='Costos acumulats', color='#f08080')
ax2.axhline(y=initial_investment, color='black', linestyle='--', label='Inversió inicial')
ax2.set_title("Evolució de la inversió i punt d'equilibri")
ax2.set_xlabel("Anys")
ax2.set_ylabel("CHF")
ax2.legend()
st.pyplot(fig2)

break_even_year = next((i for i, total in enumerate(accumulated_profit) if total >= initial_investment), None)
if break_even_year is not None:
    st.success(f"🎯 Break-even estimat: any {break_even_year+1}")
else:
    st.warning("No s'arriba a recuperar la inversió en 20 anys.")
