"""Reviewer 1, Comment 4.

(a)/(b) LPRA v2 was created in response to the s = 6, two-attacker adaptive
case that broke v1.  Evaluating v2 mainly on that same suite is
developmental, not independent.  This implements four attacks that were NOT
used during the repair and were not in the submitted paper, and evaluates
the frozen v2 rule on them:

  inside_envelope  the attacker measures the honest spread and places itself
                   at a fraction of the Stage-1 threshold -- deliberately
                   inside the acceptance region, damaging but never
                   flagged.  This is the "stay inside the honest envelope"
                   adversary Reviewer 3 also raises.
  sign_flip        negate the honest update direction but keep the honest
                   norm exactly, so the magnitude test cannot see it and
                   only the cosine test can.
  backdoor         train on data with a target class relabelled, then submit
                   the honestly-computed update.  Norm and direction are
                   both ordinary; the update is malicious in content only.
                   Global F1 is expected to survive -- that is the point.
  colluding_median two attackers position themselves symmetrically about the
                   honest median so their own median is unchanged, probing
                   whether the v2 median reference can be moved by a pair
                   that brackets it.

(c) Supplementary Table S4 varies gamma only.  This sweeps c_min and gamma
    jointly and reports honest rejection and F1 over the grid.
"""
import os, sys, json, copy
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from poc import byzantine
from poc.byzantine import aggregate, _make_mlp, _weights_of, _set_weights, _flat, _unflat, _bootstrap
from poc.federated import partition
from poc.data_loader import load_ton_iot
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split

NEW_ATTACKS = ("inside_envelope", "sign_flip", "backdoor", "colluding_median")


def run_new_attack(X, y_bin, y_multi, X_test, y_test, k=5, rounds=10, local_epochs=2, seed=42,
                   hidden=(32, 16), attack="inside_envelope", n_att=2, aggregator="lpra",
                   regime="non-iid", lpra_version="v2", c_min=0.2, lpra_gamma=2.5, envelope_frac=0.8,
                   backdoor_class=None):
    rng = np.random.default_rng(seed)
    scaler = StandardScaler().fit(X)
    Xs = scaler.transform(X).astype(np.float32); Xt = scaler.transform(X_test).astype(np.float32)
    parts = partition(y_multi, k, regime, seed)
    attackers = set(range(n_att))
    f = max(n_att, 1)
    loc_tr = []
    for idx in parts:
        idx = rng.permutation(idx); loc_tr.append(idx[:int(0.8 * len(idx))])
    boot = _bootstrap(y_bin, rng, 500)
    g = _make_mlp(seed, hidden); g.fit(Xs[boot], y_bin[boot]); classes = np.array([0, 1])
    tc, ti = _weights_of(g)
    hist, caught, att_rej_tot, hon_rej_tot = [], 0, 0, 0
    # backdoor target: flows of one attack family relabelled benign
    fam = None
    if attack == "backdoor":
        fams = sorted(set(y_multi) - {"normal", "benign", "benigntraffic"})
        fam = backdoor_class or fams[0]

    for r in range(rounds):
        gvec = _flat(*_weights_of(g)); V, ns = [], []
        for i, idx in enumerate(loc_tr):
            m = copy.deepcopy(g); _set_weights(m, *_weights_of(g))
            yb = y_bin[idx].copy()
            if i in attackers and attack == "backdoor":
                yb[y_multi[idx] == fam] = 0          # relabel the target family benign
            for _ in range(local_epochs):
                m.partial_fit(Xs[idx], yb, classes=classes)
            V.append(_flat(*_weights_of(m))); ns.append(len(idx))
        V = np.stack(V); ns = np.array(ns, float)
        honest = np.array([i for i in range(k) if i not in attackers])

        if attack in ("inside_envelope", "sign_flip", "colluding_median"):
            med = np.median(V[honest], axis=0)
            d_h = np.linalg.norm(V[honest] - med, axis=1)
            mad = 1.4826 * np.median(np.abs(d_h - np.median(d_h))) + 1e-9
            thr = max(np.median(d_h) + 3.0 * mad, lpra_gamma * np.median(d_h))
            crowd = V[honest].mean(0) - gvec
            for j, i in enumerate(sorted(attackers)):
                if attack == "inside_envelope":
                    # damaging direction, but length capped inside the threshold
                    r_dir = -crowd / (np.linalg.norm(crowd) + 1e-12)
                    V[i] = med + envelope_frac * thr * r_dir
                elif attack == "sign_flip":
                    # keep this client's own norm, invert its direction
                    delta = V[i] - gvec
                    V[i] = gvec - delta * 1.0
                elif attack == "colluding_median":
                    # bracket the honest median symmetrically
                    off = (1 if j % 2 == 0 else -1) * envelope_frac * thr
                    r_dir = crowd / (np.linalg.norm(crowd) + 1e-12)
                    V[i] = med + off * r_dir

        new, acc, info = aggregate(aggregator, V, ns, gvec, f, lpra_gamma, lpra_version)
        nc, ni = _unflat(new, tc, ti); _set_weights(g, nc, ni)
        pred = g.predict(Xt)
        f1 = f1_score(y_test, pred)
        row = dict(round=r + 1, f1=f1)
        if attack == "backdoor":
            tgt = (y_multi_test == fam)
            row["backdoor_success"] = float((pred[tgt] == 0).mean()) if tgt.sum() else None
        hist.append(row)
        att_rej_tot += sum(1 for i in attackers if not acc[i])
        hon_rej_tot += sum(1 for i in range(k) if i not in attackers and not acc[i])
        caught += (sum(1 for i in attackers if not acc[i]) == len(attackers))
    return dict(attack=attack, k=k, seed=seed, final_f1=hist[-1]["f1"],
                mean_last3=float(np.mean([h["f1"] for h in hist[-3:]])),
                attacker_rejections=att_rej_tot, honest_rejections=hon_rej_tot,
                rounds_all_caught=caught,
                backdoor_success=(hist[-1].get("backdoor_success")), fam=fam)


if __name__ == "__main__":
    ton = load_ton_iot(sample=60000)
    Xall, yall, mall = ton["X_native"].values.astype(np.float32), ton["y_bin"], ton["y_multi"]
    tr, te = train_test_split(np.arange(len(yall)), test_size=0.3, stratify=mall, random_state=42)
    X, yb, ym, Xt, yt = Xall[tr], yall[tr], mall[tr], Xall[te], yall[te]
    y_multi_test = mall[te]
    globals()["y_multi_test"] = y_multi_test

    print("=== (a)(b) frozen LPRA v2 on four attacks not used in its development ===")
    out_att = []
    for attack in NEW_ATTACKS:
        for seed in (42, 43, 44):
            for agg in ("fedavg", "lpra"):
                r = run_new_attack(X, yb, ym, Xt, yt, seed=seed, attack=attack, aggregator=agg, n_att=2)
                r["aggregator"] = agg
                out_att.append(r)
                bd = f"  backdoor_success={r['backdoor_success']:.3f}" if r["backdoor_success"] is not None else ""
                print(f"  {attack:17} seed={seed} {agg:7}  F1={r['mean_last3']:.4f}  "
                      f"att_rej={r['attacker_rejections']:2}/20 hon_rej={r['honest_rejections']:2} "
                      f"caught={r['rounds_all_caught']}/10{bd}", flush=True)
        print()

    # The c_min sweep that was here passed c_min to run_byzantine(), which does
    # not accept it, so screen_updates() used its default throughout and the
    # sweep varied nothing.  It is replaced by compare_sensitivity.py, which
    # patches screen_updates directly.

    json.dump(dict(attacks=out_att),
              open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "independent_attacks.json"), "w"), indent=1, default=str)
    print("\nwrote independent_attacks.json")
