from polymarket_trader.bootstrap import build_container
from packages.config import Settings


def main() -> None:
    container = build_container(Settings())
    print(f"Loaded {len(container.state.markets)} markets into in-memory seed state")


if __name__ == "__main__":
    main()
