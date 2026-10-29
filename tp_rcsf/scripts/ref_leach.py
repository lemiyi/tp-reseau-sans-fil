#!/usr/bin/env python3
"""Simulation Python de référence (simplifiée) de LEACH, pour VÉRIFIER l'ordre de grandeur de votre simulation NS3.
Mêmes formules et paramètres que leach.cc ; le générateur aléatoire diffère, donc les valeurs ne sont pas identiques.
Usage : python3 ref_leach.py [--k 4000] [--kc 200] [--seeds 10]
"""
import argparse
import numpy as np

E_ELEC, E_FS, E_MP, E_DA = 50e-9, 10e-12, 0.0013e-12, 5e-9
D0 = np.sqrt(E_FS / E_MP)


def tx(b, d):
    return E_ELEC * b + (E_FS * b * d * d if d < D0 else E_MP * b * d ** 4)


def run(n=100, rounds=1000, p=0.05, seed=0, e0=0.5, k=4000, kc=200, area=200, bs=(100, 250), adv=100.0):
    rng = np.random.default_rng(seed)
    xy = rng.uniform(0, area, (n, 2))
    E = np.full(n, e0)
    last = np.full(n, -1)
    period = round(1 / p)
    bsx = np.array(bs, float)
    fnd = hnd = lnd = None
    for r in range(rounds):
        alive = E > 0
        T = p / (1 - p * (r % period))
        ch = [i for i in range(n) if alive[i] and last[i] < r // period and rng.random() < T]
        for i in ch:
            last[i] = r // period
        isch = np.zeros(n, bool); isch[ch] = True
        got = {c: 0 for c in ch}
        for c in ch:
            E[c] -= tx(kc, adv) * 2            # ADV + SCHEDULE
            E[(alive) & (~isch)] -= E_ELEC * kc  # réception de l'ADV par les non-CH
        for i in range(n):
            if not alive[i] or isch[i] or E[i] <= 0:
                continue
            if ch:
                c = min(ch, key=lambda c: np.hypot(*(xy[i] - xy[c])))
                d = np.hypot(*(xy[i] - xy[c]))
                E[i] -= tx(kc, d) + tx(k, d)
                if E[c] > 0:
                    E[c] -= E_ELEC * (kc + k); got[c] += 1
            else:
                E[i] -= tx(k, np.hypot(*(xy[i] - bsx)))
        for c in ch:
            if E[c] > 0:
                E[c] -= E_DA * k * (got[c] + 1) + tx(k, np.hypot(*(xy[c] - bsx)))
        E = np.maximum(E, 0)
        a = int((E > 0).sum())
        fnd = fnd or (r + 1 if a < n else None)
        hnd = hnd or (r + 1 if a <= n / 2 else None)
        lnd = lnd or (r + 1 if a == 0 else None)
    return fnd, hnd, lnd, float(E.sum())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=4000)
    ap.add_argument("--kc", type=int, default=200)
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--n", type=int, default=100)
    a = ap.parse_args()
    R = [run(n=a.n, seed=s, k=a.k, kc=a.kc) for s in range(a.seeds)]
    f = lambda i: [x[i] for x in R if x[i]]
    print(f"d0 = {D0:.1f} m")
    print(f"FND moyen = {np.mean(f(0)):.0f}  HND moyen = {np.mean(f(1)) if f(1) else float('nan'):.0f} "
          f"({len(f(1))}/{a.seeds} graines)  LND atteint : {len(f(2))}/{a.seeds}")
    print(f"Énergie restante moyenne au round 1000 = {np.mean([x[3] for x in R]):.2f} J")
