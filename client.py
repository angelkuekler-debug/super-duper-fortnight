import requests
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

@dataclass
class CapitalConfig:
    identifier: str
    api_key: str
    api_password: str
    use_demo: bool = True

class CapitalAPI:
    def __init__(self, config: CapitalConfig):
        self.config = config
        self.base_url = "https://demo-api-capital.backend-capital.com" if config.use_demo else "https://api-capital.backend-capital.com"
        self.session = requests.Session()
        self.cst = None
        self.security_token = None

    # ---------- Helpers ----------
    def _headers(self) -> Dict[str, str]:
        h = {"X-CAP-API-KEY": self.config.api_key}
        if self.cst and self.security_token:
            h.update({"CST": self.cst, "X-SECURITY-TOKEN": self.security_token})
        return h

    def _json(self, resp: requests.Response):
        try:
            return resp.json()
        except Exception:
            return {"text": resp.text}

    # ---------- Auth ----------
    def login(self) -> None:
        url = f"{self.base_url}/session"
        body = {"identifier": self.config.identifier, "password": self.config.api_password, "encryptedPassword": False}
        r = self.session.post(url, headers={**self._headers(), "Content-Type": "application/json"}, json=body, timeout=15)
        r.raise_for_status()
        self.cst = r.headers.get("CST")
        self.security_token = r.headers.get("X-SECURITY-TOKEN")
        if not (self.cst and self.security_token):
            raise RuntimeError("Login OK, aber keine Tokens (CST/X-SECURITY-TOKEN) erhalten")

    # ---------- Markets ----------
    def search_markets(self, search_term: str) -> List[dict]:
        url = f"{self.base_url}/markets"
        r = self.session.get(url, headers=self._headers(), params={"searchTerm": search_term}, timeout=15)
        r.raise_for_status()
        data = self._json(r)
        return data.get("markets") or data.get("content") or []

    # ---------- Trading: Positions ----------
    def create_position(self, epic: str, direction: str, size: float,
                        stop_level: Optional[float]=None, profit_level: Optional[float]=None,
                        guaranteed_stop: bool=False, trailing_stop: bool=False) -> str:
        url = f"{self.base_url}/api/v1/positions"
        payload = {"epic": epic, "direction": direction, "size": size}
        if stop_level is not None: payload["stopLevel"] = float(stop_level)
        if profit_level is not None: payload["profitLevel"] = float(profit_level)
        if guaranteed_stop: payload["guaranteedStop"] = True
        if trailing_stop: payload["trailingStop"] = True
        r = self.session.post(url, headers={**self._headers(), "Content-Type": "application/json"}, json=payload, timeout=15)
        data = self._json(r)
        if r.status_code >= 300:
            raise RuntimeError(f"Create position failed {r.status_code}: {data}")
        deal_ref = data.get("dealReference")
        if not deal_ref:
            raise RuntimeError(f"No dealReference in response: {data}")
        return deal_ref

    def confirm(self, deal_reference: str) -> Dict[str, Any]:
        url = f"{self.base_url}/api/v1/confirms/{deal_reference}"
        r = self.session.get(url, headers=self._headers(), timeout=15)
        r.raise_for_status()
        return self._json(r)

    def list_positions(self) -> Dict[str, Any]:
        url = f"{self.base_url}/api/v1/positions"
        r = self.session.get(url, headers=self._headers(), timeout=15)
        r.raise_for_status()
        return self._json(r)

    def close_position(self, deal_id: str) -> Dict[str, Any]:
        url = f"{self.base_url}/api/v1/positions/otc"
        # For close, many APIs use a 'position' close endpoint; in Capital.com's public API,
        # closing is done via DELETE to /api/v1/positions/{dealId} or via a specific 'otc' route depending on instrument.
        # We'll use DELETE /api/v1/positions/{dealId} as commonly documented for CFDs; adjust if your account differs.
        url = f"{self.base_url}/api/v1/positions/{deal_id}"
        r = self.session.delete(url, headers=self._headers(), timeout=15)
        r.raise_for_status()
        return self._json(r)

    # ---------- Trading: Working Orders (Limit/Stop pending) ----------
    def create_working_order(self, epic: str, direction: str, order_type: str, size: float, level: float,
                             time_in_force: str="GOOD_TILL_CANCELLED",
                             stop_level: Optional[float]=None, profit_level: Optional[float]=None) -> str:
        url = f"{self.base_url}/api/v1/workingorders"
        payload = {
            "epic": epic,
            "direction": direction,
            "orderType": order_type,   # e.g., LIMIT or STOP
            "size": size,
            "level": float(level),
            "timeInForce": time_in_force
        }
        if stop_level is not None: payload["stopLevel"] = float(stop_level)
        if profit_level is not None: payload["profitLevel"] = float(profit_level)
        r = self.session.post(url, headers={**self._headers(), "Content-Type": "application/json"}, json=payload, timeout=15)
        data = self._json(r)
        if r.status_code >= 300:
            raise RuntimeError(f"Create working order failed {r.status_code}: {data}")
        deal_ref = data.get("dealReference")
        if not deal_ref:
            raise RuntimeError(f"No dealReference in response: {data}")
        return deal_ref

    def delete_working_order(self, deal_id: str) -> Dict[str, Any]:
        url = f"{self.base_url}/api/v1/workingorders/{deal_id}"
        r = self.session.delete(url, headers=self._headers(), timeout=15)
        r.raise_for_status()
        return self._json(r)
