"""Interface en ligne de commande : python -m skyjo <commande>."""

from __future__ import annotations

import argparse

import numpy as np

from .agents import make_agent
from .evaluate import evaluate
from .game import ACT_FLIP, Rules, play_game
from .nn import Net


def parse_spec(token: str):
    if token in ("random", "greedy"):
        return token
    path = token[3:] if token.startswith("nn:") else token
    net, theta, _ = Net.load(path)
    return ("nn", theta, net.arch)


def cmd_evaluate(a):
    specs = [parse_spec(t) for t in a.agents.split(",")]
    names = a.agents.split(",")
    r = evaluate(specs, a.games, seed=a.seed, workers=a.workers)
    print(f"{a.games} parties, {len(specs)} joueurs (sièges tirés au sort)")
    for i, nm in enumerate(names):
        print(f"  {nm:<28} victoires={r['win_rate'][i]:.3f}  score moyen={r['mean_total'][i]:6.1f}  rang moyen={r['mean_rank'][i]:.2f}")


def cmd_demo(a):
    rng = np.random.default_rng(a.seed)
    names = a.agents.split(",")
    agents = [make_agent(parse_spec(t), rng) for t in names]

    def trace(rnd, p, src, card, kind, slot):
        src_s = "défausse" if src else "pioche"
        act = f"défausse et retourne case {slot}" if kind == ACT_FLIP else f"place en case {slot}"
        print(f"  J{p} ({names[p]}) prend {card:>2} ({src_s}) -> {act}")

    res = play_game(agents, rng, Rules(), trace if a.verbose else None)
    for i, s in enumerate(res.rounds):
        print(f"manche {i + 1}: {s.tolist()}")
    print("totaux:", res.totals.tolist(), "gagnant(s):", res.winners)


def cmd_rl(a):
    from .rl import train_rl

    init = Net.load(a.init)[1] if a.init else None
    train_rl(iterations=a.iterations, rounds_per_iter=a.rounds, lr=a.lr, seed=a.seed,
             n_range=(a.min_players, a.max_players), greedy_prob=a.greedy_prob,
             init_theta=init, imitate_rounds=a.imitate, out=a.out, eval_every=a.eval_every, eval_games=a.eval_games, workers=a.workers)


def cmd_ga(a):
    from .ga import train_ga

    inits = [Net.load(p)[1] for p in a.init.split(",")] if a.init else None
    train_ga(generations=a.generations, pop_size=a.pop, tables=a.tables, sigma=a.sigma, seed=a.seed,
             init_thetas=inits, out=a.out, workers=a.workers)


def main():
    p = argparse.ArgumentParser(prog="skyjo")
    sub = p.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("evaluate", help="tournoi d'agents")
    e.add_argument("--agents", default="greedy,greedy,random", help="ex: nn:best.npz,greedy,greedy")
    e.add_argument("--games", type=int, default=200)
    e.add_argument("--seed", type=int, default=0)
    e.add_argument("--workers", type=int, default=1)
    e.set_defaults(f=cmd_evaluate)

    d = sub.add_parser("demo", help="une partie commentée")
    d.add_argument("--agents", default="greedy,greedy,random")
    d.add_argument("--seed", type=int, default=0)
    d.add_argument("--verbose", action="store_true")
    d.set_defaults(f=cmd_demo)

    r = sub.add_parser("train-rl", help="apprentissage par renforcement")
    r.add_argument("--iterations", type=int, default=300)
    r.add_argument("--rounds", type=int, default=32, help="manches par itération")
    r.add_argument("--lr", type=float, default=3e-3)
    r.add_argument("--seed", type=int, default=0)
    r.add_argument("--min-players", type=int, default=2)
    r.add_argument("--max-players", type=int, default=5)
    r.add_argument("--greedy-prob", type=float, default=0.25)
    r.add_argument("--init", default=None)
    r.add_argument("--imitate", type=int, default=0, help="manches de clonage du bot greedy avant le RL")
    r.add_argument("--out", default="models/rl.npz")
    r.add_argument("--eval-every", type=int, default=25)
    r.add_argument("--eval-games", type=int, default=60)
    r.add_argument("--workers", type=int, default=1)
    r.set_defaults(f=cmd_rl)

    g = sub.add_parser("train-ga", help="algorithme génétique")
    g.add_argument("--generations", type=int, default=40)
    g.add_argument("--pop", type=int, default=40)
    g.add_argument("--tables", type=int, default=24)
    g.add_argument("--seed", type=int, default=0)
    g.add_argument("--sigma", type=float, default=0.15, help="écart-type des mutations (0.02 conseillé pour affiner un modèle RL)")
    g.add_argument("--init", default=None, help="modèles .npz (séparés par ,) pour amorcer la population (hybride RL->GA)")
    g.add_argument("--out", default="models/ga.npz")
    g.add_argument("--workers", type=int, default=4)
    g.set_defaults(f=cmd_ga)

    a = p.parse_args()
    a.f(a)
