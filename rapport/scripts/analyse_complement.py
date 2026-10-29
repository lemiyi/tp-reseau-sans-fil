#!/usr/bin/env python3
"""Chiffres complémentaires du rapport (ceux qui ne figurent pas dans figures/resume.txt).

Tout est recalculé à partir des CSV de ../../results et de la simulation Python de référence
(../../tp_rcsf/scripts/ref_leach.py, dont la boucle est reprise ici avec un suivi de l'ordre de mort des nœuds).

Usage :  python3 analyse_complement.py          (dépendances : numpy, pandas)
"""
import glob
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "..", "..", "results")


def load(pattern):
    return [pd.read_csv(f) for f in sorted(glob.glob(os.path.join(RES, pattern)))]


def first(a, cond):
    idx = np.where(cond(a))[0]
    return int(idx[0]) + 1 if len(idx) else None


def stat(values):
    ok = [v for v in values if v is not None]
    return f"{np.mean(ok):.0f} ± {np.std(ok):.0f} ({len(ok)}/{len(values)} graines)" if ok else "non atteint"


# ------------------------------------------------------------------ 1) contrôle des CSV
print("== Contrôle des CSV")
files = sorted(glob.glob(os.path.join(RES, "*.csv")))
for f in files:
    d = pd.read_csv(f)
    assert len(d) == 1000 and not d.isna().any().any(), f
    assert (d["total_energy"].diff().dropna() <= 1e-12).all(), f
print(f"{len(files)} CSV : 1000 lignes, aucune valeur manquante, énergie totale non croissante")

# ------------------------------------------------------------------ 2) FND / HND / LND et échelle
print("\n== FND / HND / LND, énergie restante, consommation initiale, messages (N = 50, 100, 300)")
for N in (50, 100, 300):
    dfs = load(f"leach_n{N}_run*.csv")
    lt = [(first(d.alive.values, lambda x: x < N), first(d.alive.values, lambda x: x <= N / 2),
           first(d.alive.values, lambda x: x == 0)) for d in dfs]
    e0 = 0.5 * N
    e_fnd = [d.total_energy.iloc[r[0] - 1] / e0 * 100 for d, r in zip(dfs, lt)]
    e_hnd = [d.total_energy.iloc[r[1] - 1] / e0 * 100 for d, r in zip(dfs, lt)]
    conso = [(d.total_energy.iloc[0] - d.total_energy.iloc[49]) / 49 for d in dfs]
    nch = np.concatenate([d.nCH.values[d.alive.values == N] for d in dfs])
    pdr = [d.data_recv.iloc[-1] / d.data_sent.iloc[-1] * 100 for d in dfs]
    ok_msgs, ok_alt = [], []
    for d in dfs:  # messages de contrôle d'un round = N + nCH ? (rounds sans nœud mort et avec CH)
        dc = d.ctrl_msgs.diff().fillna(d.ctrl_msgs.iloc[0])
        m = (d.alive == N) & (d.nCH > 0)
        ok_msgs.append(((dc[m] - (N + d.nCH[m])) == 0).mean())
        ok_alt.append(((dc[m] - (N + 2 * d.nCH[m])) == 0).mean())
    print(f"N={N:3d} | FND {stat([r[0] for r in lt])} | HND {stat([r[1] for r in lt])} | LND {stat([r[2] for r in lt])}")
    print(f"      énergie restante au FND {np.mean(e_fnd):.1f} ± {np.std(e_fnd):.1f} %, au HND {np.mean(e_hnd):.1f} %"
          f" | conso. rounds 0-49 : {np.mean(conso)*1000:.1f} mJ/round = {np.mean(conso)/e0*100:.3f} % de E0/round")
    print(f"      nCH (tous vivants) : moy {nch.mean():.2f}, sd {nch.std():.2f}, min {nch.min()}, max {nch.max()}, "
          f"rounds sans CH {int((nch == 0).sum())}/{len(nch)} ({(nch == 0).mean()*100:.1f} %)")
    print(f"      ctrl_msgs/round = N + nCH : {np.mean(ok_msgs)*100:.0f} % des rounds ; = N + 2·nCH : {np.mean(ok_alt)*100:.0f} %")
    print(f"      taux de livraison {np.mean(pdr):.2f} ± {np.std(pdr):.2f} % (min {min(pdr):.2f}, max {max(pdr):.2f})")
    st = np.mean([d.setup_time.iloc[:30].mean() for d in dfs]) * 1000
    chm = np.mean([d.nCH.iloc[:30].mean() for d in dfs])
    print(f"      setup moyen (30 premiers rounds) {st:.2f} ms ; part du terme 2·nCH·0,8 ms : {2*chm*0.8/st*100:.0f} %")
    if N == 300:
        print("      survivants au round 999 :", [int(d.alive.iloc[-1]) for d in dfs])

# ------------------------------------------------------------------ 3) détails N = 100
print("\n== N = 100 : énergie des CH, débit utile, coût par paquet")
dfs = load("leach_n100_run*.csv")
ratio = [(d.mean_energy_CH[(d.nCH > 0) & (d.alive > 20)] / d.mean_energy_alive[(d.nCH > 0) & (d.alive > 20)]).mean() for d in dfs]
print(f"rapport énergie des CH / énergie moyenne (alive > 20) : {np.mean(ratio):.3f}")
per_round = [np.diff(d.data_recv.values, prepend=0) for d in dfs]
for a, b in ((0, 10), (400, 450), (700, 750), (950, 1000)):
    print(f"paquets livrés/round, rounds {a}-{b} : {np.mean([x[a:b].mean() for x in per_round]):.1f}")
recv = np.mean([d.data_recv.iloc[-1] for d in dfs]); sent = np.mean([d.data_sent.iloc[-1] for d in dfs])
used = np.mean([50 - d.total_energy.iloc[-1] for d in dfs])
print(f"livrés {recv:.0f} / émis {sent:.0f} ; énergie consommée {used:.1f} J -> {used / recv * 1000:.2f} mJ par paquet livré")
conso = lambda a, b: np.mean([(d.total_energy.iloc[a] - d.total_energy.iloc[b]) / (b - a) * 1000 for d in dfs])
print(f"consommation (mJ/round) rounds 0-100 : {conso(0, 100):.1f} ; 200-300 : {conso(200, 300):.1f} ; 400-500 : {conso(400, 500):.1f}")
nch = np.concatenate([d.nCH.values[d.alive.values == 100] for d in dfs])
print(f"rounds avec nCH >= 10 : {int((nch >= 10).sum())}/{len(nch)} ; rounds sans CH : {int((nch == 0).sum())}")
print(f"round 0 (graine 1) : nCH = {dfs[0].nCH.iloc[0]}, énergie consommée = {(50 - dfs[0].total_energy.iloc[0]) * 1000:.1f} mJ")

print("\n== Variante avec 2 % de pertes")
dp = load("leach_per_n100_run*.csv")
lt = [(first(d.alive.values, lambda x: x < 100), first(d.alive.values, lambda x: x <= 50),
       first(d.alive.values, lambda x: x == 0)) for d in dp]
pdr = [d.data_recv.iloc[-1] / d.data_sent.iloc[-1] * 100 for d in dp]
print(f"FND {stat([r[0] for r in lt])} | HND {stat([r[1] for r in lt])} | LND {stat([r[2] for r in lt])}")
print(f"taux de livraison {np.mean(pdr):.2f} ± {np.std(pdr):.2f} %")

# ------------------------------------------------------------------ 4) calculs à la main du modèle radio
print("\n== Modèle radio (4000 bits)")
E_ELEC, E_FS, E_MP = 50e-9, 10e-12, 0.0013e-12
D0 = np.sqrt(E_FS / E_MP)
tx = lambda k, d: E_ELEC * k + (E_FS * k * d * d if d < D0 else E_MP * k * d ** 4)
print(f"d0 = {D0:.2f} m (si εmp était en nJ : {np.sqrt(10e-12 / 0.0013e-9):.2f} m)")
for lab, k, d in (("membre -> CH à 30 m", 4000, 30), ("CH -> BS à 150 m", 4000, 150),
                  ("CH -> BS à 200 m", 4000, 200), ("CH -> BS à 270 m", 4000, 270)):
    print(f"{lab} : {tx(k, d) * 1e6:.1f} µJ")
print(f"réception : {E_ELEC * 4000 * 1e6:.0f} µJ ; rapport 270 m / 30 m = {tx(4000, 270) / tx(4000, 30):.0f}")
print(f"round 0 : émission membres 99x200 µJ = {99 * 200e-6 * 1e3:.1f} mJ, réception CH = {99 * 200e-6 * 1e3:.1f} mJ, "
      f"agrégation = {5e-9 * 4000 * 100 * 1e3:.1f} mJ")

# ------------------------------------------------------------------ 5) simulation Python de référence avec suivi des morts
def run(n=100, rounds=1000, p=0.05, seed=0, e0=0.5, k=4000, kc=200, area=200, bs=(100, 250), adv=100.0):
    """Même boucle que tp_rcsf/scripts/ref_leach.py ; renvoie en plus distance à la BS et round de mort de chaque nœud."""
    rng = np.random.default_rng(seed)
    xy = rng.uniform(0, area, (n, 2))
    E = np.full(n, e0)
    last = np.full(n, -1)
    period = round(1 / p)
    bsx = np.array(bs, float)
    death = np.full(n, np.nan)
    for r in range(rounds):
        alive = E > 0
        T = p / (1 - p * (r % period))
        ch = [i for i in range(n) if alive[i] and last[i] < r // period and rng.random() < T]
        for i in ch:
            last[i] = r // period
        isch = np.zeros(n, bool)
        isch[ch] = True
        got = {c: 0 for c in ch}
        for c in ch:
            E[c] -= tx(kc, adv) * 2
            E[alive & ~isch] -= E_ELEC * kc
        for i in range(n):
            if not alive[i] or isch[i] or E[i] <= 0:
                continue
            if ch:
                c = min(ch, key=lambda c: np.hypot(*(xy[i] - xy[c])))
                d = np.hypot(*(xy[i] - xy[c]))
                E[i] -= tx(kc, d) + tx(k, d)
                if E[c] > 0:
                    E[c] -= E_ELEC * (kc + k)
                    got[c] += 1
            else:
                E[i] -= tx(k, np.hypot(*(xy[i] - bsx)))
        for c in ch:
            if E[c] > 0:
                E[c] -= 5e-9 * k * (got[c] + 1) + tx(k, np.hypot(*(xy[c] - bsx)))
        E = np.maximum(E, 0)
        death[(E <= 0) & np.isnan(death)] = r + 1
    return np.hypot(*(xy - bsx).T), death


print("\n== Référence Python (10 graines) : la distance à la BS prédit-elle l'ordre de mort ?")
rho, d10, dall = [], [], []
for s in range(10):
    dist, death = run(seed=s)
    m = ~np.isnan(death)
    rho.append(np.corrcoef(pd.Series(dist[m]).rank(), pd.Series(death[m]).rank())[0, 1])  # Spearman (rangs moyens)
    d10.append(dist[np.argsort(death)[:10]].mean())
    dall.append(dist.mean())
print(f"corrélation de Spearman (distance à la BS, round de mort) : {np.mean(rho):.2f} (min {min(rho):.2f}, max {max(rho):.2f})")
print(f"distance moyenne à la BS : 10 premiers morts {np.mean(d10):.0f} m, tous les nœuds {np.mean(dall):.0f} m")

print("\n== Sensibilité à la taille de paquet (référence Python, 10 graines)")
print("à lancer : python3 ../../tp_rcsf/scripts/ref_leach.py --k 4000|2000 --kc 200 ; --k 500 --kc 50")
