"""HD-1104 probe: are the ledger's settings changeable after the genesis?

Run under the EXCLUSIVE lane lock. Pin API only (engine.ledger.enable/disable/set_strict/meta).
Predictions from Ledger.cls:252-329,360-380 (as built):
  - enable() on an enabled ledger ignores every argument (idempotent branch :255-260)
  - re-enable after disable keeps max_ops/recon_bound and OVERWRITES strict with the argument (default False) (:271-275)
  - set_strict() on a disabled ledger is accepted (only never-enabled is refused, :362) and is lost on re-enable
Contract (ledger-api.md:22-24): enable returns genesis or current head (idempotent); set_strict raises
LedgerNotEnabledError (errors.py:18-19: "requires an enabled ledger and none exists", i.e. never-enabled).
Alternatives: (a) setters / enable() updates given settings and keeps strict unless passed; (b) fixed at genesis,
strict reset documented; (c) as built undocumented.
"""
from _ib3_common import Conn, engine_on, meta, out, purge_ledger, cleanup, foreign_rows


def m(c):
    d = meta(c)
    return {k: d[k] for k in ("state", "strict", "max_ops", "recon_bound", "head_seq")}


def main():
    c = Conn("AUDITIB")
    try:
        out("foreign rows at start", foreign_rows(c))
        cleanup(c)
        e = engine_on(c)
        obs = {}
        e.ledger.enable(strict=False, max_ops=50_000, recon_bound=250_000)
        obs["1 genesis"] = m(c)
        e.ledger.enable(strict=True, max_ops=7, recon_bound=11)
        obs["2 enable(strict=True,max_ops=7,recon_bound=11) while enabled"] = m(c)
        e.ledger.set_strict(True)
        obs["3 set_strict(True)"] = m(c)
        e.ledger.disable()
        e.ledger.enable()
        obs["4 disable(); enable()  (no strict argument)"] = m(c)
        e.ledger.disable()
        try:
            e.ledger.set_strict(True)
            obs["5 set_strict(True) while disabled"] = ("accepted", m(c))
        except Exception as ex:  # noqa: BLE001
            obs["5 set_strict(True) while disabled"] = f"refused {type(ex).__name__}"
        e.ledger.enable()
        obs["6 enable() after set_strict(True) while disabled"] = m(c)
        e.ledger.disable()
        e.ledger.enable(strict=True, max_ops=7, recon_bound=11)
        obs["7 disable(); enable(strict=True,max_ops=7,recon_bound=11)"] = m(c)
        for k, v in obs.items():
            out(k, v)
        s = obs
        out("VERDICT enabled re-enable ignores all args", s["2 enable(strict=True,max_ops=7,recon_bound=11) while enabled"]["strict"] is False
            and s["2 enable(strict=True,max_ops=7,recon_bound=11) while enabled"]["max_ops"] == 50000)
        out("VERDICT strict reset by plain re-enable", s["4 disable(); enable()  (no strict argument)"]["strict"] is False)
        out("VERDICT strict set while disabled lost on re-enable", s["6 enable() after set_strict(True) while disabled"]["strict"] is False)
        out("VERDICT max_ops/recon_bound fixed at genesis", s["7 disable(); enable(strict=True,max_ops=7,recon_bound=11)"]["max_ops"] == 50000
            and s["7 disable(); enable(strict=True,max_ops=7,recon_bound=11)"]["recon_bound"] == 250000)
    finally:
        cleanup(c)
        c.close()


if __name__ == "__main__":
    main()
