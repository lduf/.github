"""Petit MLP en numpy (acteur-critique) avec paramètres en vecteur plat.

Le vecteur plat sert aux deux méthodes : gradient (RL) et génétique (GA).
Sorties politique (26 logits) :
    0..1   : source (0 = pioche, 1 = défausse)
    2..13  : placer la carte sur la case i
    14..25 : défausser la carte et retourner la case i
"""

from __future__ import annotations

import json

import numpy as np

N_OUT = 26
OUT_SRC, OUT_PLACE, OUT_FLIP = 0, 2, 14


class Net:
    def __init__(self, d_in: int, h1: int = 64, h2: int = 32):
        self.d_in, self.h1, self.h2 = d_in, h1, h2
        self.shapes = [
            ("W1", (d_in, h1)), ("b1", (h1,)),
            ("W2", (h1, h2)), ("b2", (h2,)),
            ("Wp", (h2, N_OUT)), ("bp", (N_OUT,)),
            ("Wv", (h2, 1)), ("bv", (1,)),
        ]
        self.sizes = [int(np.prod(s)) for _, s in self.shapes]
        self.n_params = int(sum(self.sizes))

    @property
    def arch(self) -> dict:
        return {"d_in": self.d_in, "h1": self.h1, "h2": self.h2}

    def init(self, rng: np.random.Generator) -> np.ndarray:
        parts = []
        for name, shape in self.shapes:
            if name.startswith("W"):
                scale = 1.0 / np.sqrt(shape[0])
                if name == "Wp":
                    scale *= 0.1
                parts.append(rng.normal(0, scale, size=shape).ravel())
            else:
                parts.append(np.zeros(shape).ravel())
        return np.concatenate(parts)

    def unpack(self, theta: np.ndarray) -> dict[str, np.ndarray]:
        out, i = {}, 0
        for (name, shape), size in zip(self.shapes, self.sizes):
            out[name] = theta[i : i + size].reshape(shape)
            i += size
        return out

    def forward(self, theta: np.ndarray, X: np.ndarray):
        w = self.unpack(theta)
        a1 = np.tanh(X @ w["W1"] + w["b1"])
        a2 = np.tanh(a1 @ w["W2"] + w["b2"])
        logits = a2 @ w["Wp"] + w["bp"]
        value = (a2 @ w["Wv"] + w["bv"])[:, 0]
        return logits, value, (X, a1, a2)

    def backward(self, theta, cache, dlogits, dvalue) -> np.ndarray:
        X, a1, a2 = cache
        w = self.unpack(theta)
        g = {}
        g["Wp"] = a2.T @ dlogits
        g["bp"] = dlogits.sum(0)
        g["Wv"] = a2.T @ dvalue[:, None]
        g["bv"] = np.array([dvalue.sum()])
        da2 = dlogits @ w["Wp"].T + dvalue[:, None] @ w["Wv"].T
        dz2 = da2 * (1 - a2 ** 2)
        g["W2"] = a1.T @ dz2
        g["b2"] = dz2.sum(0)
        da1 = dz2 @ w["W2"].T
        dz1 = da1 * (1 - a1 ** 2)
        g["W1"] = X.T @ dz1
        g["b1"] = dz1.sum(0)
        return np.concatenate([g[name].ravel() for name, _ in self.shapes])

    # --------------------------------------------------------------- persistance
    def save(self, path: str, theta: np.ndarray, **meta) -> None:
        np.savez(path, theta=theta, arch=json.dumps(self.arch), meta=json.dumps(meta))

    @staticmethod
    def load(path: str) -> tuple["Net", np.ndarray, dict]:
        z = np.load(path, allow_pickle=False)
        arch = json.loads(str(z["arch"]))
        net = Net(**arch)
        return net, z["theta"].astype(np.float64), json.loads(str(z["meta"]))


def masked_softmax(logits: np.ndarray, mask: np.ndarray) -> np.ndarray:
    l = np.where(mask, logits, -1e9)
    l = l - l.max(axis=-1, keepdims=True)
    e = np.exp(l) * mask
    return e / e.sum(axis=-1, keepdims=True)


class Adam:
    def __init__(self, n: int, lr: float = 3e-3, b1=0.9, b2=0.999, eps=1e-8):
        self.m = np.zeros(n)
        self.v = np.zeros(n)
        self.t = 0
        self.lr, self.b1, self.b2, self.eps = lr, b1, b2, eps

    def step(self, theta: np.ndarray, grad: np.ndarray) -> np.ndarray:
        self.t += 1
        self.m = self.b1 * self.m + (1 - self.b1) * grad
        self.v = self.b2 * self.v + (1 - self.b2) * grad ** 2
        mh = self.m / (1 - self.b1 ** self.t)
        vh = self.v / (1 - self.b2 ** self.t)
        return theta - self.lr * mh / (np.sqrt(vh) + self.eps)
