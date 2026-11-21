import numpy as np
import pytest

from skyjo.agents import GreedyAgent, NNAgent, RandomAgent, FEATURE_DIM, featurize
from skyjo.game import (CARD_COUNTS, HIDDEN, REMOVED, REVEALED, Round, Rules, build_deck, play_game)
from skyjo.nn import Net


def test_deck():
    d = build_deck(np.random.default_rng(0))
    assert len(d) == 150 and min(d) == -2 and max(d) == 12
    assert np.bincount(np.array(d) + 2).tolist() == CARD_COUNTS.tolist()


@pytest.mark.parametrize("n", range(2, 9))
def test_card_conservation_and_termination(n):
    rng = np.random.default_rng(n)
    agents = [RandomAgent(rng) if i % 2 else GreedyAgent() for i in range(n)]
    for _ in range(5):
        r = Round(n, rng)
        r.play(agents)
        total = r.grid.size - int((r.state == REMOVED).sum()) + len(r.deck) + len(r.discard)
        assert total == 150
        assert r.finisher is not None


def test_column_removal_and_scoring():
    rng = np.random.default_rng(1)
    r = Round(2, rng)
    r.grid[0, :3] = 5
    r.state[0, :3] = REVEALED
    r._clear_columns(0)
    assert (r.state[0, :3] == REMOVED).all()


def test_final_scores_double_only_if_not_strictly_best():
    rng = np.random.default_rng(2)
    r = Round(2, rng)
    r.grid[:] = 1
    r.state[:] = REVEALED
    r.grid[0, [0, 3]] = [7, 8]  # évite les colonnes identiques
    r.grid[1, [0, 3]] = [7, 8]
    r.grid[0] = np.arange(12) % 5 + (np.arange(12) // 3)  # joueur 0 : somme > 0
    r.grid[1] = r.grid[0]
    r.finisher = 0
    s = r.scores()
    assert s[0] == 2 * s[1]  # égalité -> doublé
    r.grid[1, 0] += 20
    assert r.scores()[0] == r.scores()[0] and r.scores()[0] < r.scores()[1]  # strictement meilleur -> pas doublé
    # score négatif jamais doublé
    r.grid[0] = -1
    r.grid[0, [0, 3, 6, 9]] = [-2, -1, 0, -2]
    r.grid[0, [1, 4, 7, 10]] = [-1, 0, -2, -1]
    r.grid[0, [2, 5, 8, 11]] = [0, -2, -1, 0]
    r.grid[1] = r.grid[0]
    r.grid[1, 0] = -1
    sc = r.scores()
    assert sc[0] <= 0 and sc[0] == r.grid[0].sum()


def test_nn_agent_plays_and_features():
    rng = np.random.default_rng(3)
    net = Net(FEATURE_DIM)
    theta = net.init(rng)
    agents = [NNAgent(net, theta, rng, sample=True, record=True) for _ in range(4)]
    r = Round(4, rng)
    r.play(agents)
    assert all(a.records for a in agents)
    x, m, a = agents[0].records[0]
    assert x.shape == (FEATURE_DIM,) and m[a]


def test_full_game_ends_at_100():
    rng = np.random.default_rng(4)
    res = play_game([GreedyAgent(), GreedyAgent(), RandomAgent(rng)], rng)
    assert res.totals.max() >= 100
    assert len(res.winners) >= 1


def test_gradient_check():
    rng = np.random.default_rng(5)
    net = Net(6, 5, 4)
    theta = net.init(rng) + rng.normal(0, 0.1, net.n_params)
    X = rng.normal(size=(7, 6))
    w = rng.normal(size=(7, 26))
    wv = rng.normal(size=7)

    def loss(th):
        l, v, _ = net.forward(th, X)
        return float((l * w).sum() + (v * wv).sum())

    _, _, cache = net.forward(theta, X)
    g = net.backward(theta, cache, w, wv)
    for i in rng.choice(net.n_params, 20, replace=False):
        e = np.zeros_like(theta); e[i] = 1e-6
        num = (loss(theta + e) - loss(theta - e)) / 2e-6
        assert abs(num - g[i]) < 1e-5
