from src.state_classes.arb_holder import ArbHolder


if __name__ == "__main__":
    try:
        holder = ArbHolder()
    except Exception as exc:
        print(f"Failed to create ArbHolder: {type(exc).__name__}: {exc}")
        raise

    print("ArbHolder created")
    print("arb_groups:", getattr(holder, "arb_groups", None))
    print("arb_pairs:", getattr(holder, "arb_pairs", None))
