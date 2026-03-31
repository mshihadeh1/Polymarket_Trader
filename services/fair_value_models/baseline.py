from __future__ import annotations

from math import erf, sqrt


class BaselineFairValueModel:
    def probability_yes(
        self,
        current_price: float,
        strike_price: float,
        realized_vol: float,
        time_remaining_seconds: float,
    ) -> float:
        if strike_price <= 0 or current_price <= 0:
            return 0.5
        if time_remaining_seconds <= 0:
            return 1.0 if current_price > strike_price else 0.0
        sigma = max(realized_vol, 1e-6) * sqrt(max(time_remaining_seconds, 1.0) / 300.0)
        z_score = (current_price - strike_price) / (strike_price * sigma)
        return max(min(0.5 * (1.0 + erf(z_score / sqrt(2.0))), 0.999), 0.001)
