"""
TPF AHP-TOPSIS Decision Model for Construction Arbitration Claims in Egypt
ENGINE v4 - FROZEN SPEC (binary: Seek Funding vs Self-Fund)

Changes locked in v4 vs v3:
  * Binary decision: TPF vs Self-Fund (settle / discontinue dropped).
  * p = Legal Strength Index / 100   (linear, bounded) -- logistic REMOVED.
  * net-ratio temper REMOVED.
  * lambda (risk aversion) REMOVED  (risk now a TOPSIS criterion + contractor branch).
  * QM floor REMOVED.
  * "Merits Index" renamed "Legal Strength Index (LSI)".
  * TOPSIS over two branches: Funder perspective + Contractor perspective.
  * AHP weights (1=methods, 2=LSI, 3=TOPSIS criteria) are injected; here illustrative.

Terminology (frozen):
  Pleaded amount | Quantum Multiplier (QM) | Recoverable value | Net Recovery (R)
  Enforcement factor (e) | Claim Strength | Legal Strength Index (LSI) | Probability (p)

Pure standard library + numpy for the TOPSIS step.
"""
from dataclasses import dataclass
import numpy as np

# ----------------------------------------------------------------------
# AHP-1 : method-reliability factors (illustrative; from expert pairwise, CR<=0.10,
#         ordering cross-validated vs SCL Protocol & AACE 29R-03). Scaled top=1.00.
# ----------------------------------------------------------------------
DELAY = {"windows":1.00, "tia":0.64, "as_built":0.39, "impacted_as_planned":0.11, "none":1.00}
DISR  = {"measured_mile":1.00, "global":0.55, "none":1.00}
PROL  = {"actual":1.00, "eichleay":0.55, "hudson":0.30, "none":0.50}
# QM FLOOR removed in v4.

# ----------------------------------------------------------------------
# HEAD OF CLAIM
# ----------------------------------------------------------------------
@dataclass
class Head:
    label: str
    kind: str                      # delay|disruption|prolongation|variation|termination|other
    nominal: float = 0.0           # pleaded amount (non-delay heads)
    substantiation: int = 4        # claim strength 1-5
    delay_method: str = "none"
    disr_method: str = "none"
    prol_method: str = "none"
    delay_days: float = 0.0
    daily_rate: float = 0.0

    def pleaded_amount(self):
        if self.kind == "delay" and (self.delay_days > 0 or self.daily_rate > 0):
            return self.delay_days * self.daily_rate      # prolongation cost
        return self.nominal

    def qm(self):
        """Quantum Multiplier: method reliability only engages where relevant to the head.
        No floor in v4 -- a baseless head is discounted to near zero on its own merits."""
        fd = fs = fp = 1.0
        if self.kind == "delay":
            fd = DELAY[self.delay_method] if self.delay_method != "none" else 1.0
            fp = PROL[self.prol_method]
        elif self.kind == "prolongation":
            fp = PROL[self.prol_method]
            fd = DELAY[self.delay_method] if self.delay_method != "none" else 1.0
        elif self.kind == "disruption":
            fs = DISR[self.disr_method] if self.disr_method != "none" else 1.0
        return fd * fs * fp                                 # (no QM_FLOOR)

    def recoverable_value(self):
        return self.pleaded_amount() * self.qm() * (self.substantiation / 5.0)

# ----------------------------------------------------------------------
# STEP 1 : Net Recovery R
# ----------------------------------------------------------------------
def net_recovery(claim_heads, counterclaim_heads, enforcement_e):
    gross_claim   = sum(h.recoverable_value() for h in claim_heads)
    gross_counter = sum(h.recoverable_value() for h in counterclaim_heads)
    net_before = gross_claim - gross_counter
    R = enforcement_e * max(net_before, 0.0)
    return R, gross_claim, gross_counter, net_before

def claim_strength(claim_heads):
    """Value-weighted substantiation (0-5)."""
    tot = sum(h.pleaded_amount() for h in claim_heads)
    if tot == 0: return 0.0
    return sum(h.substantiation * h.pleaded_amount() for h in claim_heads) / tot

# ----------------------------------------------------------------------
# STEP 2 : Legal Strength Index (AHP-2 weights) -> probability (linear)
# ----------------------------------------------------------------------
def legal_strength_index(counsel, tribunal, claim_strength_0to5,
                         w_counsel=0.40, w_tribunal=0.25, w_claim=0.35):
    """LSI in 0-100. Weights are AHP-2 derived (illustrative defaults here)."""
    return (counsel/5)*w_counsel*100 + (tribunal/5)*w_tribunal*100 + (claim_strength_0to5/5)*w_claim*100

def probability_of_success(lsi):
    """p = LSI/100, bounded to [0,1]. Linear -- no logistic, no temper."""
    return max(0.0, min(1.0, lsi/100.0))

# ----------------------------------------------------------------------
# STEP 3 : funder lens -- price F (waterfall) + eligibility gate
# ----------------------------------------------------------------------
def duration_multiple(mo): return 2.5 if mo<=12 else 3.0 if mo<=24 else 3.5 if mo<=36 else 4.0
def duration_pct_addon(mo): return 0.0 if mo<=12 else 0.05 if mo<=24 else 0.075 if mo<=36 else 0.10
def base_pct(rec, ff):
    b = 0.25 if rec<=100e6 else 0.15 if rec<=500e6 else 0.10 if rec<=1e9 else 0.05
    return b if ff else b/2

def funder_price(R, deployment, mo, fully_funded=True):
    mult = duration_multiple(mo)
    pct  = base_pct(R, fully_funded) + duration_pct_addon(mo)
    commission = max(deployment*mult, R*pct)
    F = min(R, deployment + commission)                    # limited recourse
    return F, mult, pct

def funder_gate(R, budget, p, cover_target=10.0, p_floor=0.60):
    cover = R/budget if budget > 0 else 0.0
    eligible = (cover >= cover_target) and (p >= p_floor)
    return eligible, cover

# ----------------------------------------------------------------------
# STEP 4 : present value & contractor economics
# ----------------------------------------------------------------------
def pv(x, d, years): return x/(1+d)**years

# ----------------------------------------------------------------------
# STEP 5 : build the TOPSIS decision matrix (2 branches) and rank
# ----------------------------------------------------------------------
# Criteria order (7): Funder branch [E[V], Recovery, Adverse-cost, Duration]
#                     Contractor branch [Liquidity, Opp-cost, Risk-appetite]
CRITERIA = ["E[V]", "Recovery", "Adverse-cost", "Duration",
            "Liquidity", "Opp-cost", "Risk-appetite"]
# benefit(True)=higher better ; cost(False)=lower better
BENEFIT  = np.array([True, True, True, False, True, False, True])

def topsis(X, w, benefit):
    X = X.astype(float)
    den = np.sqrt((X**2).sum(0)); den[den==0] = 1.0
    V = (X/den) * w
    ideal = np.where(benefit, V.max(0), V.min(0))
    anti  = np.where(benefit, V.min(0), V.max(0))
    dpos = np.sqrt(((V-ideal)**2).sum(1))
    dneg = np.sqrt(((V-anti)**2).sum(1))
    return dneg/(dpos+dneg)

@dataclass
class Case:
    claim_heads: list
    counterclaim_heads: list
    counsel: int; tribunal: int
    enforcement_e: float
    budget: float               # legal budget to pursue
    months: int
    adverse_cost_win: float     # own cost exposure if funded & win (small, funder bears)
    adverse_cost_lose: float    # adverse/own cost if lose
    rho: float                  # contractor opportunity-cost rate
    d: float                    # discount rate
    # contractor-branch inputs (rated / supplied by contractor):
    liquidity: float            # 1-5 headroom
    risk_appetite: float        # 1-5 (higher = more risk tolerant)
    settlement: float = 0.0     # settlement sum on the table (0 => none offered)
    settle_months: int = 6      # time to resolve by settling
    fully_funded: bool = True
    r_flag: int = 1             # cost recoverability flag

def run(tag, c: Case, W=None):
    # ---- sub-model computes everything ----
    R, gclaim, gcounter, net_before = net_recovery(c.claim_heads, c.counterclaim_heads, c.enforcement_e)
    cs  = claim_strength(c.claim_heads)
    lsi = legal_strength_index(c.counsel, c.tribunal, cs)
    p   = probability_of_success(lsi)
    F, mult, pct = funder_price(R, c.budget, c.months, c.fully_funded)
    eligible, cover = funder_gate(R, c.budget, p)
    years = c.months/12.0
    opp = pv(c.budget*((1+c.rho)**years - 1), c.d, years)

    # per-option criterion values
    tpf_win  = pv(R - F + c.r_flag*F, c.d, years); tpf_lose = -pv(c.adverse_cost_lose*0.0, c.d, years)  # funded: adverse cost borne by funder (approx 0 to contractor)
    self_win = pv(R, c.d, years) - c.budget - opp; self_lose = -c.budget - opp - pv(c.adverse_cost_lose, c.d, years)
    tpf_EV  = p*tpf_win  + (1-p)*tpf_lose
    self_EV = p*self_win + (1-p)*self_lose

    # Settle: certain, fast, no downside; genuine criterion values (not placeholders).
    # recovery taken as settlement sum; present-valued over the short settle horizon.
    settle_years = c.settle_months/12.0
    settle_val = pv(c.settlement, c.d, settle_years)
    # settling frees capital quickly -> small opportunity cost over the short horizon
    settle_opp = pv(c.budget*((1+c.rho)**settle_years - 1), c.d, settle_years) * 0.25

    # decision matrix rows x 7 criteria
    rows = {
      #          E[V]       Recovery   Adverse       Duration         Liquidity              Opp-cost     Risk-app
      "TPF":    [tpf_EV,    R,         tpf_lose,     c.months,        c.liquidity,           0.0,         c.risk_appetite],
      "Self":   [self_EV,   R,         self_lose,    c.months,        max(1,c.liquidity-2),  opp,         c.risk_appetite],
      "Settle": [settle_val,settle_val,0.0,          c.settle_months, c.liquidity,           settle_opp,  c.risk_appetite],
    }
    # funder gate: if not eligible, TPF leaves the option set (Self / Settle remain)
    options = ["TPF","Self","Settle"]
    if not eligible:
        options = ["Self","Settle"]
    if c.settlement <= 0:
        options = [o for o in options if o != "Settle"]   # no settlement on the table

    if W is None:
        W = np.array([0.28,0.14,0.12,0.06, 0.18,0.14,0.08])  # illustrative AHP-3 weights (sum=1)
    W = W/ W.sum()

    print(f"=== {tag} ===")
    print(f"  Pleaded/QM-adjusted gross claim = ${gclaim:,.0f}  (AHP-1 method factors applied)")
    print(f"  gross counterclaims = ${gcounter:,.0f}   enforcement e = {c.enforcement_e}")
    print(f"  NET RECOVERY R = ${R:,.0f}")
    print(f"  Claim Strength = {cs:.2f}/5   LSI = {lsi:.1f}/100   ->  p = {p:.2f}")
    print(f"  funder price F = ${F:,.0f}   cover ratio = {cover:.1f}   funder eligible = {eligible}")
    print(f"  opportunity cost (self-fund) = ${opp:,.0f}")
    if len(options) == 1:
        nm = {"TPF":"Seek Third-Party Funding","Self":"Self-Fund","Settle":"Settle"}[options[0]]
        print(f"  >> Only one option available -> DECISION: {nm}\n")
        return
    X = np.array([rows[o] for o in options])
    C = topsis(X, W, BENEFIT)
    order = np.argsort(-C)
    print("  TOPSIS decision matrix (2 branches, 7 criteria):")
    print("     " + f"{'opt':5s}" + "".join(f"{h:>13s}" for h in CRITERIA))
    for o in options:
        print("     " + f"{o:5s}" + "".join(f"{v:>13,.0f}" for v in rows[o]))
    print(f"  AHP-3 weights: " + "  ".join(f"{h}={w:.2f}" for h,w in zip(CRITERIA,W)))
    print("  Closeness coefficient Ci:")
    for i in order:
        print(f"     {options[i]:5s}  Ci = {C[i]:.4f}" + ("  <= RECOMMEND" if i==order[0] else ""))
    name = {"TPF":"Seek Third-Party Funding","Self":"Self-Fund","Settle":"Settle"}[options[order[0]]]
    print(f"  DECISION: {name}\n")


if __name__ == "__main__":
    claim = [
        Head("Prolongation","delay",substantiation=4,delay_method="windows",prol_method="actual",
             delay_days=200,daily_rate=47_500),
        Head("Disruption","disruption",8_000_000,substantiation=4,disr_method="measured_mile"),
        Head("HO overhead","prolongation",6_200_000,substantiation=4,prol_method="eichleay"),
        Head("Variations","variation",12_500_000,substantiation=5),
    ]
    counter = [Head("Defects CC","other",3_500_000,substantiation=4)]
    case = Case(claim_heads=claim, counterclaim_heads=counter,
                counsel=4, tribunal=4, enforcement_e=0.90, budget=3.0e6, months=30,
                adverse_cost_win=0.0, adverse_cost_lose=1.2e6, rho=0.15, d=0.08,
                liquidity=2, risk_appetite=3, settlement=9.0e6, settle_months=6,
                fully_funded=True)
    run("WORKED EXAMPLE - strong claim, settlement on the table", case)
