"""Moteur de jeu Skyjo, N joueurs (2 à 8), règles classiques.

Règles implémentées
-------------------
* 150 cartes : 5x(-2), 10x(-1), 15x(0), 10x chacune des valeurs 1..12.
* Chaque joueur reçoit 12 cartes face cachée, en grille 4 colonnes x 3 lignes
  (indice de case = colonne*3 + ligne). Deux cartes sont retournées au départ.
* Une carte est retournée de la pioche pour démarrer la défausse.
* Premier joueur de la 1re manche : la plus grosse somme de cartes retournées ;
  ensuite, celui qui a terminé la manche précédente.
* Un tour : soit on prend la carte du dessus de la défausse (on DOIT l'échanger
  contre une carte de sa grille), soit on pioche et on peut
    - l'échanger contre une carte de sa grille (visible ou cachée), l'ancienne
      carte va sur la défausse, ou
    - la défausser et retourner une carte cachée.
* Dès que les trois cartes d'une colonne sont visibles et identiques, la colonne
  est retirée (cartes sur la défausse) et ne compte plus.
* Quand un joueur n'a plus de carte cachée, les autres jouent un dernier tour.
  Toutes les cartes sont alors révélées et on compte les points.
* Le joueur qui a déclenché la fin voit son score de manche DOUBLÉ s'il est
  positif et qu'il n'a pas strictement le plus petit score de la manche.
* La partie s'arrête quand un joueur atteint 100 points ou plus ; le plus petit
  total gagne.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

HIDDEN, REVEALED, REMOVED = 0, 1, 2
N_SLOTS = 12
N_COLS = 4
MIN_VALUE, MAX_VALUE = -2, 12
N_VALUES = MAX_VALUE - MIN_VALUE + 1  # 15

CARD_COUNTS = np.array([5, 10, 15] + [10] * 12, dtype=np.int64)  # valeurs -2..12
assert CARD_COUNTS.sum() == 150

SRC_DECK, SRC_DISCARD = 0, 1
ACT_PLACE, ACT_FLIP = 0, 1


@dataclass(frozen=True)
class Rules:
    min_players: int = 2
    max_players: int = 8
    end_score: int = 100
    double_penalty: bool = True
    # appliquer le retrait des colonnes identiques lors de la révélation finale
    clear_on_final_reveal: bool = True
    # un seul joueur doit avoir strictement le plus bas pour éviter le doublement
    double_on_tie: bool = True


def build_deck(rng: np.random.Generator) -> list[int]:
    deck = np.repeat(np.arange(MIN_VALUE, MAX_VALUE + 1), CARD_COUNTS)
    rng.shuffle(deck)
    return [int(c) for c in deck]


@dataclass
class View:
    """Ce que voit un joueur au moment de décider (information imparfaite)."""

    player: int
    n_players: int
    stage: int  # 0 = choix de la source, 1 = choix de la case
    values: np.ndarray  # (12,) valeurs visibles, 0 si cachée / retirée
    state: np.ndarray  # (12,) HIDDEN / REVEALED / REMOVED
    discard_top: int
    card: int | None  # carte en main (stage 1)
    from_discard: bool
    opp_values: list[np.ndarray]
    opp_state: list[np.ndarray]
    deck_size: int
    final_turn: bool  # quelqu'un a déjà terminé : c'est un dernier tour
    unseen: np.ndarray  # (15,) comptes des cartes inconnues (pioche + cachées)
    legal_place: np.ndarray  # (12,) bool
    legal_flip: np.ndarray  # (12,) bool


def column_slots(col: int) -> range:
    return range(col * 3, col * 3 + 3)


class Round:
    """Une manche de Skyjo."""

    def __init__(
        self,
        n_players: int,
        rng: np.random.Generator,
        rules: Rules = Rules(),
        first_player: int | None = None,
    ):
        if not rules.min_players <= n_players <= rules.max_players:
            raise ValueError(f"Nombre de joueurs invalide : {n_players}")
        self.n = n_players
        self.rng = rng
        self.rules = rules
        deck = build_deck(rng)
        self.grid = np.array(deck[: self.n * N_SLOTS], dtype=np.int64).reshape(self.n, N_SLOTS)
        self.deck: list[int] = deck[self.n * N_SLOTS :]
        self.state = np.zeros((self.n, N_SLOTS), dtype=np.int8)
        for p in range(self.n):
            for s in rng.choice(N_SLOTS, size=2, replace=False):
                self.state[p, s] = REVEALED
        self.discard: list[int] = [self.deck.pop()]
        if first_player is None:
            sums = [int(self.grid[p][self.state[p] == REVEALED].sum()) for p in range(self.n)]
            # plus grosse somme ; égalité -> au hasard
            best = max(sums)
            first_player = int(rng.choice([p for p, v in enumerate(sums) if v == best]))
        self.current = first_player
        self.starter = first_player
        self.finisher: int | None = None
        self.turns_left = 0
        self.turn_count = 0
        self.done = False
        self.timed_out = False

    # ------------------------------------------------------------------ pioche
    def _draw(self) -> int:
        if not self.deck:
            top = self.discard.pop()
            self.deck = self.discard
            self.rng.shuffle(self.deck)
            self.discard = [top]
        return self.deck.pop()

    # --------------------------------------------------------------- observation
    def observe(self, p: int, stage: int, card: int | None = None, from_discard: bool = False) -> View:
        vis = self.state == REVEALED
        seen = np.zeros(N_VALUES, dtype=np.int64)
        vals = self.grid[vis]
        if vals.size:
            seen += np.bincount(vals - MIN_VALUE, minlength=N_VALUES)
        if self.discard:
            seen += np.bincount(np.asarray(self.discard) - MIN_VALUE, minlength=N_VALUES)
        if card is not None:
            seen[card - MIN_VALUE] += 1
        unseen = np.maximum(CARD_COUNTS - seen, 0)

        st = self.state[p].copy()
        values = np.where(st == REVEALED, self.grid[p], 0)
        legal_place = st != REMOVED
        legal_flip = (st == HIDDEN) & (stage == 1) & (not from_discard)
        opps = [q for q in range(self.n) if q != p]
        return View(
            player=p,
            n_players=self.n,
            stage=stage,
            values=values,
            state=st,
            discard_top=self.discard[-1] if self.discard else 0,
            card=card,
            from_discard=from_discard,
            opp_values=[np.where(self.state[q] == REVEALED, self.grid[q], 0) for q in opps],
            opp_state=[self.state[q].copy() for q in opps],
            deck_size=len(self.deck),
            final_turn=self.finisher is not None,
            unseen=unseen,
            legal_place=legal_place if stage == 1 else np.zeros(N_SLOTS, bool),
            legal_flip=legal_flip,
        )

    # --------------------------------------------------------------------- tour
    def _clear_columns(self, p: int) -> None:
        for c in range(N_COLS):
            sl = list(column_slots(c))
            if np.all(self.state[p, sl] == REVEALED):
                v = self.grid[p, sl]
                if v[0] == v[1] == v[2]:
                    self.state[p, sl] = REMOVED
                    self.discard.extend(int(x) for x in v)

    def play_turn(self, agent, trace=None) -> None:
        p = self.current
        src = agent.choose_source(self.observe(p, 0))
        if src == SRC_DISCARD:
            card, from_discard = self.discard.pop(), True
        else:
            card, from_discard = self._draw(), False
        view = self.observe(p, 1, card=card, from_discard=from_discard)
        kind, slot = agent.choose_slot(view)
        if kind == ACT_PLACE:
            if not view.legal_place[slot]:
                raise ValueError("Placement illégal")
            old = int(self.grid[p, slot])
            self.grid[p, slot] = card
            self.state[p, slot] = REVEALED
            self.discard.append(old)
        else:
            if not view.legal_flip[slot]:
                raise ValueError("Retournement illégal")
            self.discard.append(card)
            self.state[p, slot] = REVEALED
        if trace:
            trace(self, p, src, card, kind, slot)
        self._clear_columns(p)

        if self.finisher is None:
            if not np.any(self.state[p] == HIDDEN):
                self.finisher = p
                self.turns_left = self.n - 1
        else:
            self.turns_left -= 1
        self.turn_count += 1
        if self.finisher is not None and self.turns_left == 0:
            self.done = True
        else:
            self.current = (p + 1) % self.n

    def play(self, agents, trace=None, max_turns: int | None = None) -> np.ndarray:
        """Joue la manche. Au-delà de `max_turns` (agent qui boucle), la manche est
        arrêtée sans finisseur : toutes les cartes sont révélées et comptées."""
        max_turns = max_turns or 40 * self.n
        while not self.done:
            self.play_turn(agents[self.current], trace)
            if self.turn_count >= max_turns:
                self.timed_out = True
                self.done = True
        return self.scores()

    # ------------------------------------------------------------------- scores
    def scores(self) -> np.ndarray:
        """Scores de la manche (avec pénalité du finisseur)."""
        state = self.state.copy()
        grid = self.grid
        st_final = state.copy()
        st_final[st_final == HIDDEN] = REVEALED
        raw = np.zeros(self.n, dtype=np.int64)
        for p in range(self.n):
            st = st_final[p].copy()
            if self.rules.clear_on_final_reveal:
                for c in range(N_COLS):
                    sl = list(column_slots(c))
                    if np.all(st[sl] == REVEALED) and grid[p, sl[0]] == grid[p, sl[1]] == grid[p, sl[2]]:
                        st[sl] = REMOVED
            raw[p] = int(grid[p][st == REVEALED].sum())
        out = raw.copy()
        f = self.finisher
        if f is not None and self.rules.double_penalty and raw[f] > 0:
            others = np.delete(raw, f)
            if self.rules.double_on_tie:
                not_best = others.min() <= raw[f]
            else:
                not_best = others.min() < raw[f]
            if not_best:
                out[f] = raw[f] * 2
        return out


@dataclass
class GameResult:
    totals: np.ndarray
    rounds: list[np.ndarray]

    @property
    def winners(self) -> list[int]:
        m = self.totals.min()
        return [i for i, t in enumerate(self.totals) if t == m]


def play_game(agents, rng: np.random.Generator, rules: Rules = Rules(), trace=None) -> GameResult:
    n = len(agents)
    totals = np.zeros(n, dtype=np.int64)
    rounds: list[np.ndarray] = []
    first = None
    while totals.max() < rules.end_score:
        r = Round(n, rng, rules, first)
        s = r.play(agents, trace)
        totals += s
        rounds.append(s)
        first = r.finisher
    return GameResult(totals, rounds)
