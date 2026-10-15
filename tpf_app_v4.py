"""
TPF AHP-TOPSIS Decision-Support Application  (thesis demonstration)
Wraps the frozen v4 engine (tpf_model_v4.py) -- no logic re-implemented.

Run:   pip install streamlit numpy
       streamlit run tpf_app_v4.py
"""
import numpy as np
import streamlit as st
import tpf_model_v4 as M

st.set_page_config(page_title="TPF Decision Support", page_icon="scale", layout="wide")

NAVY = "#03395F"
st.markdown(f"""
<style>
 .block-container {{padding-top:2rem;}}
 h1,h2,h3 {{color:{NAVY};}}
 .rec-box {{background:{NAVY};color:#fff;padding:1rem 1.4rem;border-radius:10px;font-size:1.3rem;font-weight:700;}}
 .muted {{color:#6B7785;font-size:0.85rem;}}
</style>""", unsafe_allow_html=True)

st.title("Third-Party Funding Decision-Support Model")
st.markdown("<span class='muted'>AHP–TOPSIS model for construction arbitration claims in Egypt "
            "· Seek Funding / Self-Fund / Settle · thesis demonstration</span>", unsafe_allow_html=True)

# ---------------- SIDEBAR : weights (provisional, editable) ----------------
st.sidebar.header("AHP weights (provisional)")
st.sidebar.caption("Pending expert calibration. Edit here once the expert survey is complete. "
                   "Weights need not sum to 1 — they are normalised automatically.")
st.sidebar.markdown("**Funder perspective**")
w_ev   = st.sidebar.number_input("Expected value E[V]", 0.0, 1.0, 0.28, 0.01)
w_rec  = st.sidebar.number_input("Recovery value",      0.0, 1.0, 0.14, 0.01)
w_adv  = st.sidebar.number_input("Adverse-cost / downside", 0.0, 1.0, 0.12, 0.01)
w_dur  = st.sidebar.number_input("Duration",            0.0, 1.0, 0.06, 0.01)
st.sidebar.markdown("**Contractor perspective**")
w_liq  = st.sidebar.number_input("Liquidity",           0.0, 1.0, 0.18, 0.01)
w_opp  = st.sidebar.number_input("Opportunity cost",    0.0, 1.0, 0.14, 0.01)
w_risk = st.sidebar.number_input("Risk appetite",       0.0, 1.0, 0.08, 0.01)
W = np.array([w_ev,w_rec,w_adv,w_dur,w_liq,w_opp,w_risk])

st.sidebar.markdown("---")
st.sidebar.markdown("**Legal Strength Index weights (AHP-2)**")
w_counsel = st.sidebar.number_input("Counsel / firm", 0.0, 1.0, 0.40, 0.01)
w_trib    = st.sidebar.number_input("Tribunal",       0.0, 1.0, 0.25, 0.01)
w_claimw  = st.sidebar.number_input("Claim strength", 0.0, 1.0, 0.35, 0.01)

st.sidebar.markdown("---")
cover_target = st.sidebar.number_input("Funder cover-ratio target (:1)", 1.0, 20.0, 10.0, 0.5)
p_floor      = st.sidebar.number_input("Funder min. probability", 0.0, 1.0, 0.60, 0.05)

# ---------------- STAGE A : heads of claim ----------------
st.header("1 · Heads of claim")
st.caption("Add each head. Delay heads use delay-method + prolongation-method; "
           "disruption uses a disruption method; variations/termination/other stand on records.")

if "heads" not in st.session_state:
    st.session_state.heads = [
        dict(label="Prolongation", kind="delay", nominal=0.0, substantiation=4,
             delay_method="windows", prol_method="actual", disr_method="none",
             delay_days=200.0, daily_rate=50000.0),
    ]

KINDS = ["delay","disruption","prolongation","variation","termination","other"]
DELAYM = list(M.DELAY.keys()); DISRM = list(M.DISR.keys()); PROLM = list(M.PROL.keys())

def head_editor(i, h):
    c = st.columns([2,1.4,1.2,1.2,1.4,1.4,1.4,0.6])
    h["label"]=c[0].text_input("Label", h["label"], key=f"lbl{i}")
    h["kind"]=c[1].selectbox("Kind", KINDS, index=KINDS.index(h["kind"]), key=f"knd{i}")
    if h["kind"]=="delay":
        h["delay_days"]=c[2].number_input("Delay days", 0.0, value=float(h["delay_days"]), key=f"dd{i}")
        h["daily_rate"]=c[3].number_input("Daily rate $", 0.0, value=float(h["daily_rate"]), key=f"dr{i}")
        h["delay_method"]=c[4].selectbox("Delay method", DELAYM, index=DELAYM.index(h["delay_method"]), key=f"dm{i}")
        h["prol_method"]=c[5].selectbox("Prol. method", PROLM, index=PROLM.index(h["prol_method"]), key=f"pm{i}")
    elif h["kind"]=="disruption":
        h["nominal"]=c[2].number_input("Pleaded $", 0.0, value=float(h["nominal"]), key=f"nm{i}")
        h["disr_method"]=c[4].selectbox("Disr. method", DISRM, index=DISRM.index(h["disr_method"]), key=f"sm{i}")
    elif h["kind"]=="prolongation":
        h["nominal"]=c[2].number_input("Pleaded $", 0.0, value=float(h["nominal"]), key=f"nm{i}")
        h["prol_method"]=c[5].selectbox("Prol. method", PROLM, index=PROLM.index(h["prol_method"]), key=f"pm{i}")
    else:
        h["nominal"]=c[2].number_input("Pleaded $", 0.0, value=float(h["nominal"]), key=f"nm{i}")
    h["substantiation"]=c[6].slider("Substantiation", 1, 5, int(h["substantiation"]), key=f"sb{i}")
    if c[7].button("x", key=f"del{i}"):
        return False
    return True

keep=[]
for i,h in enumerate(st.session_state.heads):
    if head_editor(i,h): keep.append(h)
st.session_state.heads = keep if keep else st.session_state.heads
if st.button("+ Add head of claim"):
    st.session_state.heads.append(dict(label="New head", kind="variation", nominal=1_000_000.0,
        substantiation=4, delay_method="none", prol_method="none", disr_method="none",
        delay_days=0.0, daily_rate=0.0))
    st.rerun()

# ---------------- counterclaims ----------------
st.header("2 · Counterclaims (respondent)")
cc_total = st.number_input("Total recoverable counterclaims (USD)", 0.0, value=3_000_000.0, step=500_000.0,
                           help="Enter the realistic (method/evidence-adjusted) value of the respondent's counterclaims.")

# ---------------- case context ----------------
st.header("3 · Case context")
cc = st.columns(4)
enforcement_e = cc[0].slider("Enforcement factor e", 0.0, 1.0, 0.90, 0.05,
    help="Likelihood the award is actually enforced/collected in Egypt.")
budget        = cc[1].number_input("Legal budget to pursue (USD)", 0.0, value=4_000_000.0, step=500_000.0)
months        = cc[2].number_input("Expected duration (months)", 1, value=28)
counsel       = cc[3].slider("Counsel / firm quality (1-5)", 1, 5, 4)
cc2 = st.columns(4)
tribunal      = cc2[0].slider("Tribunal disposition (1-5)", 1, 5, 4)
adverse_lose  = cc2[1].number_input("Adverse/own cost if lost (USD)", 0.0, value=1_500_000.0, step=250_000.0)
settlement    = cc2[2].number_input("Settlement on the table (USD, 0=none)", 0.0, value=0.0, step=1_000_000.0)
settle_months = cc2[3].number_input("Months to settle", 1, value=6)

# ---------------- contractor position ----------------
st.header("4 · Contractor position")
cp = st.columns(3)
liquidity    = cp[0].slider("Liquidity headroom (1-5)", 1, 5, 2,
    help="1 = cash-constrained, 5 = cash-rich.")
risk_app     = cp[1].slider("Risk appetite (1-5)", 1, 5, 3,
    help="1 = very risk-averse, 5 = very risk-tolerant.")
rho          = cp[2].number_input("Opportunity-cost rate (annual)", 0.0, 1.0, 0.15, 0.01,
    help="Return the contractor could earn on capital deployed elsewhere.")
d_rate = 0.08  # discount rate (fixed market default)

# ---------------- RUN ----------------
st.markdown("---")
if st.button("Run the model", type="primary"):
    # patch AHP-2 weights into the engine
    def lsi(counsel,tribunal,cs):
        return M.legal_strength_index(counsel,tribunal,cs,w_counsel,w_trib,w_claimw)
    M.legal_strength_index = lsi

    heads = [M.Head(**h) for h in st.session_state.heads]
    # represent counterclaims as a single 'other' head at its recoverable value
    counters = [M.Head("Counterclaims","other", nominal=cc_total, substantiation=5)]

    R,gclaim,gcounter,net_before = M.net_recovery(heads, counters, enforcement_e)
    cs  = M.claim_strength(heads)
    L   = M.legal_strength_index(counsel, tribunal, cs)
    p   = M.probability_of_success(L)
    F,mult,pct = M.funder_price(R, budget, months, True)
    eligible, cover = M.funder_gate(R, budget, p, cover_target, p_floor)
    years = months/12.0
    opp = M.pv(budget*((1+rho)**years-1), d_rate, years)

    tpf_win  = M.pv(R - F + F, d_rate, years); tpf_lose = 0.0
    self_win = M.pv(R, d_rate, years) - budget - opp
    self_lose= -budget - opp - M.pv(adverse_lose, d_rate, years)
    tpf_EV  = p*tpf_win + (1-p)*tpf_lose
    self_EV = p*self_win + (1-p)*self_lose
    sy = settle_months/12.0
    settle_val = M.pv(settlement, d_rate, sy)
    settle_opp = M.pv(budget*((1+rho)**sy-1), d_rate, sy)*0.25

    rows = {
      "Seek TPF": [tpf_EV, R, tpf_lose, months, liquidity, 0.0, risk_app],
      "Self-Fund":[self_EV, R, self_lose, months, max(1,liquidity-2), opp, risk_app],
      "Settle":   [settle_val, settle_val, 0.0, settle_months, liquidity, settle_opp, risk_app],
    }
    options = ["Seek TPF","Self-Fund","Settle"]
    if not eligible: options = ["Self-Fund","Settle"]
    if settlement<=0: options=[o for o in options if o!="Settle"]

    # ---- sub-model panel ----
    cS = st.columns(4)
    cS[0].metric("Net Recovery R", f"${R:,.0f}")
    cS[1].metric("Legal Strength Index", f"{L:.0f}/100")
    cS[2].metric("Probability p", f"{p:.0%}")
    cS[3].metric("Cover ratio", f"{cover:.1f} : 1", delta="eligible" if eligible else "funder declines",
                 delta_color="normal" if eligible else "inverse")

    if len(options)==1:
        st.markdown(f"<div class='rec-box'>Recommendation: {options[0]}</div>", unsafe_allow_html=True)
    else:
        Wn = W/W.sum()
        X = np.array([rows[o] for o in options])
        C = M.topsis(X, Wn, M.BENEFIT)
        order = np.argsort(-C)
        rec = options[order[0]]
        st.markdown(f"<div class='rec-box'>Recommendation: {rec}</div>", unsafe_allow_html=True)
        st.write("")
        # ranking
        st.subheader("Ranking (TOPSIS closeness coefficient)")
        for i in order:
            st.write(f"**{options[i]}** — Cᵢ = {C[i]:.3f}")
            st.progress(float(C[i]))
        # decision matrix
        st.subheader("Decision matrix")
        import pandas as pd
        df = pd.DataFrame(rows, index=M.CRITERIA).T
        df = df.loc[options]
        st.dataframe(df.style.format("{:,.0f}"))
        st.caption("Funder-perspective criteria: E[V], Recovery, Adverse-cost, Duration. "
                   "Contractor-perspective criteria: Liquidity, Opp-cost, Risk-appetite. "
                   "Values computed by the financial sub-model; weights from the expert panel (AHP).")

    st.caption("Provisional weights pending expert calibration. This tool supports, and does not replace, "
               "professional judgement.")
