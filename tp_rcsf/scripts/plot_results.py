#!/usr/bin/env python3
"""Traitement des résultats du TP RCSF (LEACH sous NS3).

Lit les CSV produits par leach.cc, calcule FND/HND/LND, le taux de livraison, le passage à l'échelle,
et trace les figures (PNG, 200 dpi). Option : superposer un autre algorithme (ex. DEEC du binôme).

Exemples :
  python3 plot_results.py                                   # tout avec les valeurs par défaut
  python3 plot_results.py --results ~/tp_rcsf/results --figures ~/tp_rcsf/figures
  python3 plot_results.py --compare ~/deec/deec_n100_run*.csv --label DEEC --other-init 60
"""
import argparse
import glob
import os
import sys

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

C_MAIN = "#1F4E79"   # LEACH
C_OTHER = "#C0504D"  # autre algorithme (comparaison)
C_GREY = "#7F7F7F"

plt.rcParams.update({
    "figure.figsize": (6.4, 3.6), "axes.grid": True, "grid.alpha": 0.3,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 9,
    "axes.titlesize": 10, "legend.frameon": False,
})


def load(pattern):
    files = sorted(glob.glob(os.path.expanduser(pattern)))
    return [pd.read_csv(f) for f in files], files


def stack(dfs, col, rounds=None):
    """Matrice (graines x rounds), complétée par la dernière valeur si une simulation est plus courte."""
    L = rounds or max(len(d) for d in dfs)
    M = np.full((len(dfs), L), np.nan)
    for i, d in enumerate(dfs):
        v = d[col].values[:L]
        M[i, :len(v)] = v
        if len(v) < L:
            M[i, len(v):] = v[-1]
    return M


def first_round(alive, cond_fn):
    idx = np.where(cond_fn(alive))[0]
    return int(idx[0]) + 1 if len(idx) else None


def lifetimes(dfs, n):
    rows = []
    for d in dfs:
        a = d["alive"].values
        rows.append((first_round(a, lambda x: x < n),
                     first_round(a, lambda x: x <= n / 2),
                     first_round(a, lambda x: x == 0)))
    return rows


def fmt_stat(vals, total_rounds):
    ok = [v for v in vals if v is not None]
    if not ok:
        return f"> {total_rounds} (non atteint)"
    s = f"{np.mean(ok):.0f} ± {np.std(ok):.0f}"
    if len(ok) < len(vals):
        s += f"  ({len(ok)}/{len(vals)} graines)"
    return s


def band(ax, x, M, color, label):
    m, s = np.nanmean(M, 0), np.nanstd(M, 0)
    ax.plot(x, m, color=color, label=label, lw=1.6)
    ax.fill_between(x, m - s, m + s, color=color, alpha=0.18, lw=0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="~/tp_rcsf/results")
    ap.add_argument("--figures", default="~/tp_rcsf/figures")
    ap.add_argument("--prefix", default="leach")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--init-energy", type=float, default=None, help="énergie initiale totale LEACH (J), défaut 0.5*n")
    ap.add_argument("--compare", default=None, help="motif glob des CSV de l'autre algorithme (n=100)")
    ap.add_argument("--label", default="DEEC")
    ap.add_argument("--other-init", type=float, default=None, help="énergie initiale totale de l'autre algo (J), défaut 0.6*n")
    ap.add_argument("--window", type=int, default=50, help="fenêtre (rounds) du taux de livraison")
    ap.add_argument("--setup-rounds", type=int, default=30, help="rounds utilisés pour le setup/messages")
    a = ap.parse_args()

    res = os.path.expanduser(a.results)
    figs = os.path.expanduser(a.figures)
    os.makedirs(figs, exist_ok=True)
    n = a.n
    e_init = a.init_energy or 0.5 * n
    out_txt = []

    def say(s=""):
        print(s)
        out_txt.append(s)

    dfs, files = load(f"{res}/{a.prefix}_n{n}_run*.csv")
    if not dfs:
        sys.exit(f"Aucun fichier {res}/{a.prefix}_n{n}_run*.csv : lancez d'abord scripts/run_all.sh")
    R = max(len(d) for d in dfs)
    x = np.arange(1, R + 1)
    say(f"== Expérience A : énergie (n={n}, {len(dfs)} graines, {R} rounds) ==")

    E = stack(dfs, "total_energy")
    A = stack(dfs, "alive")

    # -------- Figure 1 : énergie résiduelle totale --------
    other = None
    if a.compare:
        other, ofiles = load(a.compare)
        if not other:
            sys.exit(f"Aucun fichier pour --compare {a.compare}")
    fig, ax = plt.subplots()
    band(ax, x, E, C_MAIN, "LEACH")
    if other:
        band(ax, np.arange(1, max(len(d) for d in other) + 1), stack(other, "total_energy"), C_OTHER, a.label)
    ax.set_xlabel("Round"); ax.set_ylabel("Énergie résiduelle totale (J)")
    ax.set_title("Énergie résiduelle du réseau"); ax.legend()
    fig.tight_layout(); fig.savefig(f"{figs}/energie.png", dpi=200); plt.close(fig)

    # -------- Figure 2 : nœuds vivants --------
    fig, ax = plt.subplots()
    band(ax, x, A, C_MAIN, "LEACH")
    if other:
        band(ax, np.arange(1, max(len(d) for d in other) + 1), stack(other, "alive"), C_OTHER, a.label)
    ax.set_xlabel("Round"); ax.set_ylabel("Nœuds vivants"); ax.set_title("Nombre de nœuds vivants"); ax.legend()
    fig.tight_layout(); fig.savefig(f"{figs}/vivants.png", dpi=200); plt.close(fig)

    # -------- FND / HND / LND --------
    lt = lifetimes(dfs, n)
    say("Graine | FND | HND | LND")
    for i, r in enumerate(lt, 1):
        say(f"  {i}    | {r[0]} | {r[1]} | {r[2]}")
    say(f"LEACH  FND = {fmt_stat([r[0] for r in lt], R)}")
    say(f"LEACH  HND = {fmt_stat([r[1] for r in lt], R)}")
    say(f"LEACH  LND = {fmt_stat([r[2] for r in lt], R)}")
    say(f"Énergie restante au round {R} : {np.mean(E[:, -1]):.2f} J sur {e_init:.1f} J")
    if other:
        n_o = int(other[0]["alive"].iloc[0] + 0)  # approx : nœuds vivants au round 0
        n_o = max(n_o, n)
        lt_o = lifetimes(other, n_o)
        say(f"{a.label} FND = {fmt_stat([r[0] for r in lt_o], R)}")
        say(f"{a.label} HND = {fmt_stat([r[1] for r in lt_o], R)}")
        say(f"{a.label} LND = {fmt_stat([r[2] for r in lt_o], R)}")

    # -------- Figure 3 : énergie normalisée (comparaison équitable) --------
    if other:
        e_o = a.other_init or 0.6 * n
        fig, ax = plt.subplots()
        band(ax, x, E / e_init, C_MAIN, "LEACH")
        band(ax, np.arange(1, max(len(d) for d in other) + 1), stack(other, "total_energy") / e_o, C_OTHER, a.label)
        ax.set_xlabel("Round"); ax.set_ylabel("Énergie résiduelle / énergie initiale")
        ax.set_title("Énergie normalisée"); ax.legend()
        fig.tight_layout(); fig.savefig(f"{figs}/energie_normalisee.png", dpi=200); plt.close(fig)

    # -------- Figure 4 : nombre de CH par round --------
    nch = np.concatenate([d["nCH"].values[d["alive"].values == n] for d in dfs])
    if len(nch):
        fig, ax = plt.subplots()
        bins = np.arange(-0.5, max(nch.max(), 12) + 1.5, 1)
        ax.hist(nch, bins=bins, color=C_MAIN, alpha=0.85)
        ax.axvline(0.05 * n, color=C_GREY, ls="--", lw=1)
        ax.text(0.05 * n + 0.15, ax.get_ylim()[1] * 0.92, "p·N = %.0f" % (0.05 * n), color=C_GREY)
        ax.set_xlabel("Nombre de CH élus dans un round"); ax.set_ylabel("Nombre de rounds")
        ax.set_title("Variabilité du nombre de CH (rounds où tous les nœuds sont vivants)")
        fig.tight_layout(); fig.savefig(f"{figs}/nch_histogramme.png", dpi=200); plt.close(fig)
        say(f"Nombre de CH par round (nœuds tous vivants) : moyenne {nch.mean():.2f}, écart-type {nch.std():.2f}, "
            f"min {nch.min()}, max {nch.max()}, rounds sans CH : {(nch == 0).sum()}/{len(nch)}")

    # -------- Figure 5 : énergie des CH élus vs moyenne --------
    ma = stack(dfs, "mean_energy_alive"); mc = stack(dfs, "mean_energy_CH")
    fig, ax = plt.subplots()
    ax.plot(x, np.nanmean(ma, 0), color=C_MAIN, label="Énergie moyenne des nœuds vivants")
    ax.plot(x, np.array([np.nanmean(col) if np.isfinite(col).any() else np.nan for col in np.where(mc > 0, mc, np.nan).T]), color=C_OTHER, label="Énergie moyenne des CH élus")
    ax.set_xlabel("Round"); ax.set_ylabel("Énergie (J)")
    ax.set_title("LEACH élit des CH sans tenir compte de l'énergie résiduelle"); ax.legend()
    fig.tight_layout(); fig.savefig(f"{figs}/energie_ch_vs_moyenne.png", dpi=200); plt.close(fig)

    # -------- Expérience C : taux de livraison --------
    say(); say("== Expérience C : taux de livraison ==")
    S = stack(dfs, "data_sent"); Rv = stack(dfs, "data_recv")
    glob_pdr = Rv[:, -1] / np.maximum(S[:, -1], 1)
    say(f"Taux de livraison global : {100*glob_pdr.mean():.2f} % ± {100*glob_pdr.std():.2f}")
    w = a.window
    edges = np.arange(0, R + 1, w)
    if len(edges) > 1:
        S0 = np.concatenate([np.zeros((S.shape[0], 1)), S], axis=1); R0 = np.concatenate([np.zeros((Rv.shape[0], 1)), Rv], axis=1)
        dS = np.diff(S0[:, edges], axis=1); dR = np.diff(R0[:, edges], axis=1)
        pdr = np.where(dS > 0, dR / np.maximum(dS, 1), np.nan)
        fig, ax = plt.subplots()
        ax.plot(edges[1:], 100 * np.nanmean(pdr, 0), color=C_MAIN, marker="o", ms=3, label="LEACH")
        ax.set_ylim(0, 105); ax.set_xlabel("Round (fin de fenêtre)"); ax.set_ylabel(f"Taux de livraison (%), fenêtres de {w} rounds")
        ax.set_title("Taux de livraison des paquets de données"); ax.legend()
        fig.tight_layout(); fig.savefig(f"{figs}/livraison.png", dpi=200); plt.close(fig)

    # paquets livrés par round : montre l'effondrement du réseau même si le taux reste proche de 100 %
    per_round = np.diff(Rv, axis=1, prepend=0)
    fig, ax = plt.subplots()
    band(ax, x, per_round, C_MAIN, "LEACH")
    ax.set_xlabel("Round"); ax.set_ylabel("Paquets de données livrés à la BS par round")
    ax.set_title("Quantité de données collectées par round"); ax.legend()
    fig.tight_layout(); fig.savefig(f"{figs}/livraison_par_round.png", dpi=200); plt.close(fig)
    say(f"Paquets livrés par round : {per_round[:, :10].mean():.0f} (rounds 1-10) -> {per_round[:, -50:].mean():.1f} (50 derniers rounds)")

    # variante avec pertes
    dfs_per, _ = load(f"{res}/{a.prefix}_per_n{n}_run*.csv")
    if dfs_per:
        Sp = stack(dfs_per, "data_sent"); Rp = stack(dfs_per, "data_recv")
        say(f"Taux de livraison global avec pertes aléatoires : {100*np.mean(Rp[:, -1]/np.maximum(Sp[:, -1], 1)):.2f} %")

    # -------- Expérience B : passage à l'échelle --------
    say(); say("== Expérience B : passage à l'échelle ==")
    rows = []
    for N in (50, 100, 300):
        rs, _ = load(f"{res}/{a.prefix}_n{N}_run*.csv")
        if not rs:
            continue
        W = a.setup_rounds
        st = np.mean([d["setup_time"].iloc[:W].mean() for d in rs])
        mg = np.mean([d["ctrl_msgs"].iloc[min(W, len(d)) - 1] / min(W, len(d)) for d in rs])
        nch_m = np.mean([d["nCH"].iloc[:W].mean() for d in rs])
        fnd = fmt_stat([first_round(d["alive"].values, lambda v, N=N: v < N) for d in rs], R)
        rows.append((N, st, mg, nch_m, fnd, len(rs)))
        say(f"N={N:3d} | setup moyen = {st*1000:.3f} ms | messages de contrôle/round = {mg:.1f} | CH/round = {nch_m:.1f} | FND = {fnd} | {len(rs)} graines")
    if len(rows) >= 2:
        Ns = [r[0] for r in rows]
        fig, axs = plt.subplots(1, 2, figsize=(7.4, 3.3))
        axs[0].plot(Ns, [r[1] * 1000 for r in rows], marker="o", color=C_MAIN)
        axs[0].set_xlabel("Nombre de nœuds"); axs[0].set_ylabel("Temps de setup (ms simulées)"); axs[0].set_title("Temps de setup")
        axs[1].plot(Ns, [r[2] for r in rows], marker="o", color=C_MAIN)
        axs[1].set_xlabel("Nombre de nœuds"); axs[1].set_ylabel("Messages de contrôle par round"); axs[1].set_title("Messages de clustering")
        for ax in axs:
            ax.set_xticks(Ns)
        fig.tight_layout(); fig.savefig(f"{figs}/echelle.png", dpi=200); plt.close(fig)

    with open(f"{figs}/resume.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(out_txt) + "\n")
    print(f"\nFigures et resume.txt écrits dans {figs}")


if __name__ == "__main__":
    main()
