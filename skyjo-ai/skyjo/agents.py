"""Agents : aléatoire, heuristique (greedy) et réseau de neurones."""

from __future__ import annotations

import numpy as np

from .game import (
    ACT_FLIP, ACT_PLACE, HIDDEN, MIN_VALUE, N_COLS, N_SLOTS, N_VALUES, REVEALED,
    SRC_DECK, SRC_DISCARD, View, column_slots,
)
from .nn import OUT_FLIP, OUT_PLACE, OUT_SRC, Net, N_OUT, masked_softmax

_VALS = np.arange(MIN_VALUE, MIN_VALUE + N_VALUES)


def expected_unseen(view: View) -> float:
    tot = view.unseen.sum()
    return float((view.unseen * _VALS).sum() / tot) if tot > 0 else 5.0


def match_counts(view: View, card: int) -> np.ndarray:
    """Pour chaque case : nb d'AUTRES cartes visibles de sa colonne égales à `card`."""
    out = np.zeros(N_SLOTS)
    for c in range(N_COLS):
        sl = list(column_slots(c))
        for s in sl:
            out[s] = sum(1 for t in sl if t != s and view.state[t] == REVEALED and view.values[t] == card)
    return out


# --------------------------------------------------------------------- features
def featurize(view: View) -> np.ndarray:
    known = (view.state == REVEALED).astype(np.float64)
    removed = (view.state == 2).astype(np.float64)
    vals = view.values / 12.0
    e = expected_unseen(view)
    cand = view.card if view.stage == 1 else view.discard_top
    match = match_counts(view, cand) / 2.0 * (view.state != 2)
    n_hidden = float((view.state == HIDDEN).sum())
    vis_sum = float(view.values[view.state == REVEALED].sum())
    proj = vis_sum + n_hidden * e
    opp_proj, opp_hidden = [], []
    for v, s in zip(view.opp_values, view.opp_state):
        h = float((s == HIDDEN).sum())
        opp_proj.append(float(v[s == REVEALED].sum()) + h * e)
        opp_hidden.append(h)
    stage = np.zeros(3)
    stage[0 if view.stage == 0 else (2 if view.from_discard else 1)] = 1.0
    x = np.concatenate([
        known, removed, vals, match,
        [cand / 12.0, float(cand <= 0), (cand - e) / 12.0, view.discard_top / 12.0],
        stage,
        [e / 12.0, n_hidden / 12.0, vis_sum / 60.0, proj / 60.0],
        [
            (min(opp_proj) - proj) / 30.0,
            (np.mean(opp_proj) - proj) / 30.0,
            min(opp_hidden) / 12.0,
            np.mean(opp_hidden) / 12.0,
            view.n_players / 8.0,
            view.deck_size / 150.0,
            float(view.final_turn),
        ],
    ])
    return x


FEATURE_DIM = 36 + 12 + 4 + 3 + 4 + 7


# ----------------------------------------------------------------------- agents
class RandomAgent:
    name = "random"

    def __init__(self, rng: np.random.Generator):
        self.rng = rng

    def choose_source(self, view: View) -> int:
        return int(self.rng.integers(2))

    def choose_slot(self, view: View):
        opts = [(ACT_PLACE, s) for s in np.flatnonzero(view.legal_place)]
        if not view.from_discard:
            opts += [(ACT_FLIP, s) for s in np.flatnonzero(view.legal_flip)]
        k, s = opts[int(self.rng.integers(len(opts)))]
        return k, int(s)


class GreedyAgent:
    """Heuristique raisonnable : sert d'adversaire de référence."""

    name = "greedy"

    def __init__(self, rng=None):
        pass

    @staticmethod
    def _known_max(view: View):
        idx = np.flatnonzero(view.state == REVEALED)
        if idx.size == 0:
            return None
        s = idx[np.argmax(view.values[idx])]
        return int(s), int(view.values[s])

    def choose_source(self, view: View) -> int:
        top = view.discard_top
        m = match_counts(view, top)
        if top <= 0 and np.any(view.state != 2):
            return SRC_DISCARD
        if np.any((m >= 2) & (view.state != 2)):
            return SRC_DISCARD
        km = self._known_max(view)
        if top <= 4 and km is not None and km[1] - top >= 4:
            return SRC_DISCARD
        if top <= 3 and np.any(view.state == HIDDEN):
            return SRC_DISCARD
        return SRC_DECK

    def choose_slot(self, view: View):
        c = view.card
        m = match_counts(view, c)
        full = np.flatnonzero((m >= 2) & view.legal_place)
        if full.size:
            return ACT_PLACE, int(full[0])
        km = self._known_max(view)
        hidden = np.flatnonzero(view.state == HIDDEN)
        if view.from_discard:
            if km is not None and km[1] > c:
                return ACT_PLACE, km[0]
            if hidden.size:
                return ACT_PLACE, int(hidden[0])
            legal = np.flatnonzero(view.legal_place)
            return ACT_PLACE, int(legal[np.argmax(view.values[legal])])
        # pioche
        if km is not None and km[1] - c >= 4:
            return ACT_PLACE, km[0]
        if c <= 2 and hidden.size:
            return ACT_PLACE, int(hidden[0])
        if hidden.size:
            return ACT_FLIP, int(hidden[0])
        legal = np.flatnonzero(view.legal_place)
        return ACT_PLACE, int(legal[np.argmax(view.values[legal])])


class NNAgent:
    """Agent piloté par le réseau. `sample=True` pour explorer (RL)."""

    name = "nn"

    def __init__(self, net: Net, theta: np.ndarray, rng: np.random.Generator,
                 sample: bool = False, record: bool = False):
        self.net, self.theta, self.rng = net, theta, rng
        self.sample, self.record = sample, record
        self.records: list[tuple[np.ndarray, np.ndarray, int]] = []

    def _decide(self, view: View, mask: np.ndarray) -> int:
        x = featurize(view)
        logits, _, _ = self.net.forward(self.theta, x[None])
        p = masked_softmax(logits[0], mask)
        a = int(self.rng.choice(N_OUT, p=p)) if self.sample else int(np.argmax(p))
        if self.record:
            self.records.append((x, mask, a))
        return a

    def choose_source(self, view: View) -> int:
        mask = np.zeros(N_OUT, bool)
        mask[OUT_SRC + SRC_DECK] = True
        mask[OUT_SRC + SRC_DISCARD] = True
        return self._decide(view, mask) - OUT_SRC

    def choose_slot(self, view: View):
        mask = np.zeros(N_OUT, bool)
        mask[OUT_PLACE : OUT_PLACE + N_SLOTS] = view.legal_place
        mask[OUT_FLIP : OUT_FLIP + N_SLOTS] = view.legal_flip
        a = self._decide(view, mask)
        if a >= OUT_FLIP:
            return ACT_FLIP, a - OUT_FLIP
        return ACT_PLACE, a - OUT_PLACE


def make_agent(spec, rng: np.random.Generator, sample: bool = False, record: bool = False):
    """spec : 'random' | 'greedy' | ('nn', theta, arch_dict)"""
    if spec == "random":
        return RandomAgent(rng)
    if spec == "greedy":
        return GreedyAgent(rng)
    kind, theta, arch = spec
    assert kind == "nn"
    return NNAgent(Net(**arch), theta, rng, sample=sample, record=record)
