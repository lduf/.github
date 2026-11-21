"""Algorithme génétique sur les poids du réseau (neuroévolution).

Fitness d'un génome = moyenne sur plusieurs tables (2 à 4 joueurs) de
    (score moyen des adversaires - son score) par manche,
contre un mélange de bots greedy et des meilleurs génomes de la génération
précédente (co-évolution). Les mêmes graines sont utilisées pour tous les
génomes d'une génération afin de comparer à jeu égal.
"""

from __future__ import annotations

import time
from multiprocessing import Pool

import numpy as np

from .agents import FEATURE_DIM, make_agent
from .evaluate import evaluate
from .game import Round, Rules
from .nn import Net


def _fitness(args) -> float:
    theta, arch, opp_thetas, seeds, rounds_per_table, rules = args
    total, count = 0.0, 0
    for k, seed in enumerate(seeds):
        rng = np.random.default_rng(seed)
        n = 2 + k % 3
        seat = k % n
        agents = []
        for i in range(n):
            if i == seat:
                agents.append(make_agent(("nn", theta, arch), rng))
            elif opp_thetas and rng.random() < 0.5:
                agents.append(make_agent(("nn", opp_thetas[int(rng.integers(len(opp_thetas)))], arch), rng))
            else:
                agents.append(make_agent("greedy", rng))
        first = None
        for _ in range(rounds_per_table):
            rnd = Round(n, rng, rules, first)
            s = rnd.play(agents).astype(float)
            total += np.delete(s, seat).mean() - s[seat]
            count += 1
            first = rnd.finisher
    return total / count


def train_ga(
    generations=40,
    pop_size=40,
    elite=4,
    tables=24,
    rounds_per_table=2,
    sigma=0.15,
    mut_prob=0.2,
    seed=0,
    init_thetas=None,
    net=None,
    out=None,
    workers=4,
    eval_games=60,
    log=print,
    rules=Rules(),
):
    rng = np.random.default_rng(seed)
    net = net or Net(FEATURE_DIM)
    pop = []
    if init_thetas:
        for th in init_thetas:
            pop.append(th.copy())
            for _ in range(2):  # voisins du point de départ
                pop.append(th + rng.normal(0, sigma * 0.5, th.shape))
    while len(pop) < pop_size:
        pop.append(net.init(rng))
    pop = pop[:pop_size]
    t0 = time.time()
    opp_pool: list[np.ndarray] = []
    pool = Pool(workers) if workers > 1 else None
    best_theta, best_fit = pop[0], -1e9
    try:
        for gen in range(1, generations + 1):
            seeds = [int(s) for s in rng.integers(0, 2**31, size=tables)]
            jobs = [(th, net.arch, opp_pool, seeds, rounds_per_table, rules) for th in pop]
            fits = np.array(pool.map(_fitness, jobs) if pool else [_fitness(j) for j in jobs])
            order = np.argsort(-fits)
            pop = [pop[i] for i in order]
            fits = fits[order]
            if fits[0] > best_fit or gen == 1:
                best_fit, best_theta = float(fits[0]), pop[0].copy()
            opp_pool = [p.copy() for p in pop[:5]]
            log(f"[GA] gen={gen:3d} fitness best={fits[0]:+6.2f} moy={fits.mean():+6.2f} "
                f"sigma={sigma:.3f} t={time.time() - t0:.0f}s")
            if out:
                net.save(out, pop[0], method="ga", generation=gen, fitness=float(fits[0]))
            # --- reproduction
            new = [p.copy() for p in pop[:elite]]
            while len(new) < pop_size:
                a = _tournament(rng, pop, fits)
                b = _tournament(rng, pop, fits)
                mask = rng.random(a.shape) < 0.5  # croisement uniforme
                child = np.where(mask, a, b)
                mut = rng.random(child.shape) < mut_prob
                child = child + mut * rng.normal(0, sigma, child.shape)
                new.append(child)
            pop = new
            sigma = max(0.03, sigma * 0.97)
    finally:
        if pool:
            pool.close()
    spec = ("nn", best_theta, net.arch)
    r = evaluate([spec, "greedy", "greedy"], eval_games, seed=777, workers=workers, rules=rules)
    log(f"[GA] >>> éval 3 joueurs vs 2 greedy : victoire={r['win_rate'][0]:.2f} "
        f"score moyen={r['mean_total'][0]:.1f} (greedy {r['mean_total'][1:].mean():.1f})")
    if out:
        net.save(out, best_theta, method="ga", fitness=best_fit, win_vs_greedy=float(r["win_rate"][0]))
    return net, best_theta, r


def _tournament(rng, pop, fits, k=3):
    idx = rng.integers(len(pop), size=k)
    return pop[int(idx[np.argmax(fits[idx])])]
