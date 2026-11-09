#!/usr/bin/env python3
"""
Test Stripe checkout session creation with payment method configuration.

This script creates a test checkout session and opens it in your browser
to verify that Google Pay, Apple Pay, Link, and other payment methods appear.

Usage:
    # Test with your live/test Stripe keys
    export STRIPE_SECRET_KEY=sk_test_...
    export STRIPE_PAYMENT_METHOD_CONFIG=pmc_...  # Optional but recommended

    # Create a credit purchase checkout
    python scripts/test_stripe_checkout.py

    # Create a made-for-you checkout
    python scripts/test_stripe_checkout.py --made-for-you

    # Just print the URL without opening browser
    python scripts/test_stripe_checkout.py --no-open

    # Test different credit packages
    python scripts/test_stripe_checkout.py --package 3_credits

Requirements:
    pip install stripe
"""
import argparse
import os
import sys
import webbrowser

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import stripe


def get_env_or_prompt(var_name: str, prompt: str, secret: bool = False) -> str:
    """Get environment variable or prompt user."""
    value = os.getenv(var_name)
    if value:
        if secret:
            print(f"  {var_name}: {'*' * 8}...{value[-4:]}")
        else:
            print(f"  {var_name}: {value}")
        return value

    print(f"\n{var_name} not set in environment.")
    if secret:
        import getpass
        return getpass.getpass(f"{prompt}: ")
    else:
        return input(f"{prompt}: ")


def create_credit_checkout(
    secret_key: str,
    payment_method_config: str | None,
    package_id: str,
    email: str,
) -> str:
    """Create a credit purchase checkout session."""
    stripe.api_key = secret_key

    packages = {
        "1_credit": {"credits": 1, "price_cents": 500, "name": "1 Karaoke Credit"},
        "3_credits": {"credits": 3, "price_cents": 1200, "name": "3 Karaoke Credits"},
        "5_credits": {"credits": 5, "price_cents": 1750, "name": "5 Karaoke Credits"},
        "10_credits": {"credits": 10, "price_cents": 3000, "name": "10 Karaoke Credits"},
    }

    package = packages.get(package_id)
    if not package:
        raise ValueError(f"Invalid package: {package_id}. Choose from: {list(packages.keys())}")

    session_params = {
        'line_items': [{
            'price_data': {
                'currency': 'usd',
                'product_data': {
                    'name': package['name'],
                    'description': f"Create {package['credits']} professional karaoke video(s)",
                    'images': ['https://gen.nomadkaraoke.com/nomad-logo.png'],
                },
                'unit_amount': package['price_cents'],
            },
            'quantity': 1,
        }],
        'mode': 'payment',
        'success_url': 'https://gen.nomadkaraoke.com/payment/success?session_id={CHECKOUT_SESSION_ID}',
        'cancel_url': 'https://gen.nomadkaraoke.com/?cancelled=true',
        'customer_email': email,
        'metadata': {
            'package_id': package_id,
            'credits': str(package['credits']),
            'user_email': email,
            'test': 'true',
        },
        'allow_promotion_codes': True,
    }

    if payment_method_config:
        session_params['payment_method_configuration'] = payment_method_config
        print(f"\n  Using payment_method_configuration: {payment_method_config}")
    else:
        print("\n  WARNING: No payment_method_configuration set!")
        print("  Google Pay, Apple Pay, and Link may not appear.")

    session = stripe.checkout.Session.create(**session_params)
    return session.url


def create_made_for_you_checkout(
    secret_key: str,
    payment_method_config: str | None,
    email: str,
    artist: str = "Test Artist",
    title: str = "Test Song",
) -> str:
    """Create a made-for-you checkout session."""
    stripe.api_key = secret_key

    session_params = {
        'line_items': [{
            'price_data': {
                'currency': 'usd',
                'product_data': {
                    'name': f"Karaoke Video: {artist} - {title}",
                    'description': "Professional 4K karaoke video with perfectly synced lyrics",
                    'images': ['https://gen.nomadkaraoke.com/nomad-logo.png'],
                },
                'unit_amount': 5000,  # $50.00
            },
            'quantity': 1,
        }],
        'mode': 'payment',
        'success_url': 'https://nomadkaraoke.com/order/success/?session_id={CHECKOUT_SESSION_ID}',
        'cancel_url': 'https://nomadkaraoke.com/#do-it-for-me',
        'customer_email': email,
        'metadata': {
            'order_type': 'made_for_you',
            'customer_email': email,
            'artist': artist,
            'title': title,
            'source_type': 'search',
            'test': 'true',
        },
        'allow_promotion_codes': True,
    }

    if payment_method_config:
        session_params['payment_method_configuration'] = payment_method_config
        print(f"\n  Using payment_method_configuration: {payment_method_config}")
    else:
        print("\n  WARNING: No payment_method_configuration set!")
        print("  Google Pay, Apple Pay, and Link may not appear.")

    session = stripe.checkout.Session.create(**session_params)
    return session.url


def main():
    parser = argparse.ArgumentParser(
        description="Test Stripe checkout with payment method configuration"
    )
    parser.add_argument(
        "--made-for-you",
        action="store_true",
        help="Create a made-for-you checkout instead of credit purchase",
    )
    parser.add_argument(
        "--package",
        default="1_credit",
        choices=["1_credit", "3_credits", "5_credits", "10_credits"],
        help="Credit package to test (default: 1_credit)",
    )
    parser.add_argument(
        "--email",
        default="test@example.com",
        help="Customer email for the checkout (default: test@example.com)",
    )
    parser.add_argument(
        "--artist",
        default="Avril Lavigne",
        help="Artist name for made-for-you checkout (default: Avril Lavigne)",
    )
    parser.add_argument(
        "--title",
        default="Things I'll Never Say",
        help="Song title for made-for-you checkout (default: Things I'll Never Say)",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Don't open the URL in browser, just print it",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Stripe Checkout Test")
    print("=" * 60)

    # Get configuration
    print("\nConfiguration:")
    secret_key = get_env_or_prompt(
        "STRIPE_SECRET_KEY",
        "Enter your Stripe secret key",
        secret=True,
    )
    payment_method_config = os.getenv("STRIPE_PAYMENT_METHOD_CONFIG")
    if payment_method_config:
        print(f"  STRIPE_PAYMENT_METHOD_CONFIG: {payment_method_config}")
    else:
        print("  STRIPE_PAYMENT_METHOD_CONFIG: (not set)")

    # Detect test vs live mode
    is_test_mode = secret_key.startswith("sk_test_")
    mode_str = "TEST MODE" if is_test_mode else "LIVE MODE"
    print(f"\n  Mode: {mode_str}")

    if not is_test_mode:
        print("\n  WARNING: You are using LIVE keys!")
        confirm = input("  Type 'yes' to continue: ")
        if confirm.lower() != 'yes':
            print("  Aborted.")
            sys.exit(1)

    # Create checkout session
    print("\n" + "-" * 60)
    if args.made_for_you:
        print(f"Creating made-for-you checkout...")
        print(f"  Artist: {args.artist}")
        print(f"  Title: {args.title}")
        print(f"  Email: {args.email}")
        checkout_url = create_made_for_you_checkout(
            secret_key,
            payment_method_config,
            args.email,
            args.artist,
            args.title,
        )
    else:
        print(f"Creating credit purchase checkout...")
        print(f"  Package: {args.package}")
        print(f"  Email: {args.email}")
        checkout_url = create_credit_checkout(
            secret_key,
            payment_method_config,
            args.package,
            args.email,
        )

    print("\n" + "=" * 60)
    print("Checkout URL:")
    print(checkout_url)
    print("=" * 60)

    if not args.no_open:
        print("\nOpening in browser...")
        webbrowser.open(checkout_url)
        print("\nCheck that you see:")
        print("  - Google Pay (if you have it set up)")
        print("  - Apple Pay (on Safari/iOS)")
        print("  - Link (Stripe's one-click checkout)")
        print("  - Other enabled payment methods")
    else:
        print("\nCopy the URL above and open it in your browser to test.")

    print("\nIf wallet methods don't appear:")
    print("  1. Ensure STRIPE_PAYMENT_METHOD_CONFIG is set to your config ID")
    print("  2. Verify wallets are enabled in Stripe Dashboard")
    print("  3. Google Pay requires Chrome + Google Pay setup on device")
    print("  4. Apple Pay requires Safari + Apple Pay setup on device")


if __name__ == "__main__":
    main()
