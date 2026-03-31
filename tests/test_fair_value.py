from services.fair_value_models import BaselineFairValueModel


def test_probability_increases_when_price_is_above_strike() -> None:
    model = BaselineFairValueModel()
    below = model.probability_yes(current_price=84450, strike_price=84500, realized_vol=0.01, time_remaining_seconds=60)
    above = model.probability_yes(current_price=84550, strike_price=84500, realized_vol=0.01, time_remaining_seconds=60)
    assert above > below
