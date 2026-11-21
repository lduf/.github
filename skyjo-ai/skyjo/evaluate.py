"""Évaluation d'agents en parties complètes, avec placement aléatoire des sièges."""

from __future__ import annotations

from multiprocessing import Pool

import numpy as np

from .agents import make_agent
from .game import Rules, play_game


def _run_chunk(args):
    specs, n_games, seed, rules = args
    rng = np.random.default_rng(seed)
    n = len(specs)
    totals = np.zeros((n_games, n))
    wins = np.zeros(n)
    ranks = np.zeros(n)
    for g in range(n_games):
        perm = rng.permutation(n)  # perm[seat] = index de l'agent
        agents = [make_agent(specs[i], rng) for i in perm]
        res = play_game(agents, rng, rules)
        t = np.empty(n)
        t[perm] = res.totals
        totals[g] = t
        m = t.min()
        winners = np.flatnonzero(t == m)
        wins[winners] += 1.0 / len(winners)
        ranks += 1 + np.array([(t < t[i]).sum() for i in range(n)])
    return totals, wins, ranks


def evaluate(specs, n_games: int = 200, seed: int = 0, rules: Rules = Rules(), workers: int = 1) -> dict:
    """specs : liste de specs d'agents ('random' | 'greedy' | ('nn', theta, arch)).

    Retourne, par agent : score final moyen, taux de victoire, rang moyen.
    """
    workers = max(1, min(workers, n_games))
    sizes = [n_games // workers + (1 if i < n_games % workers else 0) for i in range(workers)]
    jobs = [(specs, s, seed * 1000 + i, rules) for i, s in enumerate(sizes)]
    if workers == 1:
        parts = [_run_chunk(jobs[0])]
    else:
        with Pool(workers) as pool:
            parts = pool.map(_run_chunk, jobs)
    totals = np.vstack([p[0] for p in parts])
    wins = sum(p[1] for p in parts)
    ranks = sum(p[2] for p in parts)
    return {
        "mean_total": totals.mean(0),
        "win_rate": wins / n_games,
        "mean_rank": ranks / n_games,
        "n_games": n_games,
    }
