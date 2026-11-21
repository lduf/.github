"""Apprentissage par renforcement : acteur-critique (REINFORCE + baseline) en self-play.

Un épisode = une manche à N joueurs. Chaque siège « apprenant » joue avec le même
réseau (partage des poids) et reçoit en récompense terminale
    (score moyen des adversaires - son score) / 10
(le doublement du finisseur est donc bien pris en compte).
"""

from __future__ import annotations

import time

import numpy as np

from .agents import FEATURE_DIM, GreedyAgent, NNAgent
from .evaluate import evaluate
from .game import Round, Rules
from .nn import Adam, N_OUT, Net, masked_softmax


def collect(net, theta, rng, rounds, n_range, greedy_prob, rules):
    X, M, A, R = [], [], [], []
    margin = []
    for _ in range(rounds):
        n = int(rng.integers(n_range[0], n_range[1] + 1))
        learner = rng.random(n) >= greedy_prob
        if not learner.any():
            learner[rng.integers(n)] = True
        agents = [NNAgent(net, theta, rng, sample=True, record=True) if learner[i] else GreedyAgent()
                  for i in range(n)]
        rnd = Round(n, rng, rules)
        s = rnd.play(agents).astype(float)
        for i in range(n):
            if not learner[i]:
                continue
            ret = (np.delete(s, i).mean() - s[i]) / 10.0
            margin.append(ret * 10)
            for x, m, a in agents[i].records:
                X.append(x); M.append(m); A.append(a); R.append(ret)
    return np.array(X), np.array(M), np.array(A), np.array(R), float(np.mean(margin))


def update(net, theta, opt, X, M, A, R, beta, vcoef=0.5, clip=5.0):
    B = len(X)
    logits, V, cache = net.forward(theta, X)
    P = masked_softmax(logits, M)
    adv = R - V
    advn = (adv - adv.mean()) / (adv.std() + 1e-8)
    onehot = np.zeros_like(P)
    onehot[np.arange(B), A] = 1.0
    dlogits = advn[:, None] * (P - onehot)
    logP = np.log(P + 1e-12)
    H = -(P * logP).sum(1)
    dlogits += beta * P * (logP + H[:, None])
    dlogits /= B
    dV = vcoef * (V - R) / B
    g = net.backward(theta, cache, dlogits, dV)
    norm = np.linalg.norm(g)
    if norm > clip:
        g *= clip / norm
    return opt.step(theta, g), float(H.mean()), float(np.mean((V - R) ** 2))


def train_rl(
    iterations=300,
    rounds_per_iter=32,
    lr=3e-3,
    seed=0,
    n_range=(2, 5),
    greedy_prob=0.25,
    init_theta=None,
    net=None,
    out=None,
    eval_every=25,
    eval_games=60,
    workers=1,
    log=print,
    rules=Rules(),
):
    rng = np.random.default_rng(seed)
    net = net or Net(FEATURE_DIM)
    theta = init_theta.copy() if init_theta is not None else net.init(rng)
    opt = Adam(net.n_params, lr=lr)
    t0 = time.time()
    best = None
    for it in range(1, iterations + 1):
        beta = 0.02 * (1 - it / iterations) + 0.002
        X, M, A, R, margin = collect(net, theta, rng, rounds_per_iter, n_range, greedy_prob, rules)
        theta, ent, vmse = update(net, theta, opt, X, M, A, R, beta)
        if it % 5 == 0 or it == 1:
            log(f"[RL] it={it:4d} décisions={len(X):5d} marge/manche={margin:+6.2f} "
                f"entropie={ent:.2f} vmse={vmse:.3f} t={time.time() - t0:.0f}s")
        if it % eval_every == 0 or it == iterations:
            spec = ("nn", theta, net.arch)
            r = evaluate([spec, "greedy", "greedy"], eval_games, seed=10_000 + it, workers=workers, rules=rules)
            log(f"[RL] >>> éval 3 joueurs vs 2 greedy : victoire={r['win_rate'][0]:.2f} "
                f"score moyen={r['mean_total'][0]:.1f} (greedy {r['mean_total'][1:].mean():.1f})")
            if out:
                net.save(out, theta, method="rl", iteration=it, win_vs_greedy=float(r["win_rate"][0]))
            best = r
    return net, theta, best
