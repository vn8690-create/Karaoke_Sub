#!/usr/bin/env python3
"""
Inspect Stripe configuration to debug payment method issues.

This script:
1. Shows your payment method configuration details
2. Creates a test checkout session and inspects what methods are enabled
3. Compares with your Payment Links setup

Usage:
    export STRIPE_SECRET_KEY=sk_live_...
    export STRIPE_PAYMENT_METHOD_CONFIG=pmc_...
    python scripts/inspect_stripe_config.py
"""
import json
import os
import sys

try:
    import stripe
except ImportError:
    print("Error: stripe package not installed. Run: pip install stripe")
    sys.exit(1)


def main():
    secret_key = os.getenv("STRIPE_SECRET_KEY")
    pmc_id = os.getenv("STRIPE_PAYMENT_METHOD_CONFIG")

    if not secret_key:
        print("Error: STRIPE_SECRET_KEY not set")
        sys.exit(1)

    stripe.api_key = secret_key
    is_test = secret_key.startswith("sk_test_")
    print(f"Mode: {'TEST' if is_test else 'LIVE'}")
    print("=" * 70)

    # 1. List payment method configurations
    print("\n1. PAYMENT METHOD CONFIGURATIONS")
    print("-" * 70)
    try:
        configs = stripe.PaymentMethodConfiguration.list(limit=10)
        for config in configs.data:
            is_default = " (DEFAULT)" if config.get("is_default") else ""
            active = "Active" if config.get("active") else "Inactive"
            print(f"\n  ID: {config.id}{is_default}")
            print(f"  Name: {config.get('name', 'Unnamed')}")
            print(f"  Status: {active}")

            # Show key payment methods
            for pm in ['google_pay', 'apple_pay', 'link', 'card']:
                pm_config = config.get(pm, {})
                if pm_config:
                    available = pm_config.get('available', False)
                    display_pref = pm_config.get('display_preference', {}).get('preference', 'none')
                    print(f"    {pm}: available={available}, preference={display_pref}")
    except Exception as e:
        print(f"  Error listing configs: {e}")

    # 2. Inspect the specific payment method configuration
    if pmc_id:
        print(f"\n2. YOUR PAYMENT METHOD CONFIGURATION ({pmc_id})")
        print("-" * 70)
        try:
            config = stripe.PaymentMethodConfiguration.retrieve(pmc_id)
            print(f"  Name: {config.get('name', 'Unnamed')}")
            print(f"  Active: {config.get('active')}")
            print(f"  Is Default: {config.get('is_default')}")

            print("\n  Payment Methods:")
            for pm in ['google_pay', 'apple_pay', 'link', 'card', 'cashapp', 'klarna']:
                pm_config = config.get(pm, {})
                if pm_config:
                    available = pm_config.get('available', 'N/A')
                    display_pref = pm_config.get('display_preference', {})
                    pref = display_pref.get('preference', 'N/A')
                    value = display_pref.get('value', 'N/A')
                    print(f"    {pm}:")
                    print(f"      available: {available}")
                    print(f"      display_preference.preference: {pref}")
                    print(f"      display_preference.value: {value}")
        except Exception as e:
            print(f"  Error: {e}")
    else:
        print("\n2. STRIPE_PAYMENT_METHOD_CONFIG not set - skipping config inspection")

    # 3. Create a test checkout session and inspect it
    print("\n3. TEST CHECKOUT SESSION")
    print("-" * 70)
    try:
        session_params = {
            'line_items': [{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': 'Test Product',
                    },
                    'unit_amount': 100,
                },
                'quantity': 1,
            }],
            'mode': 'payment',
            'success_url': 'https://example.com/success',
            'cancel_url': 'https://example.com/cancel',
            'customer_email': 'test@example.com',
        }

        if pmc_id:
            session_params['payment_method_configuration'] = pmc_id

        session = stripe.checkout.Session.create(**session_params)

        print(f"  Session ID: {session.id}")
        print(f"  URL: {session.url[:80]}...")
        print(f"\n  payment_method_types: {session.payment_method_types}")
        print(f"  payment_method_configuration_details: {session.get('payment_method_configuration_details')}")

        # Expire the test session to clean up
        try:
            stripe.checkout.Session.expire(session.id)
            print(f"\n  (Test session expired)")
        except:
            pass

    except Exception as e:
        print(f"  Error creating session: {e}")

    # 4. Check Payment Method Domains
    print("\n4. PAYMENT METHOD DOMAINS")
    print("-" * 70)
    try:
        domains = stripe.PaymentMethodDomain.list(limit=20)
        for domain in domains.data:
            print(f"\n  Domain: {domain.domain_name}")
            print(f"    ID: {domain.id}")
            print(f"    Enabled: {domain.enabled}")
            print(f"    Google Pay: {domain.google_pay.get('status', 'N/A')}")
            print(f"    Apple Pay: {domain.apple_pay.get('status', 'N/A')}")
            print(f"    Link: {domain.link.get('status', 'N/A')}")
    except Exception as e:
        print(f"  Error: {e}")

    # 5. List recent Payment Links for comparison
    print("\n5. PAYMENT LINKS (for comparison)")
    print("-" * 70)
    try:
        links = stripe.PaymentLink.list(limit=3, active=True)
        for link in links.data:
            print(f"\n  Link ID: {link.id}")
            print(f"    URL: {link.url}")
            print(f"    payment_method_types: {link.payment_method_types}")
            print(f"    payment_method_collection: {link.get('payment_method_collection')}")
    except Exception as e:
        print(f"  Error: {e}")

    print("\n" + "=" * 70)
    print("ANALYSIS")
    print("=" * 70)
    print("""
If Google Pay/Apple Pay/Link are not appearing:

1. Check payment_method_configuration_details above - if null, the config
   isn't being applied correctly.

2. Check the Payment Method Domains - your checkout domain must be registered
   with status 'active' for Google Pay, Apple Pay, and Link.

3. Compare payment_method_types between your Checkout Session and Payment Links.
   If Payment Links shows more methods, there may be a config difference.

4. In your Payment Method Configuration, check display_preference.value:
   - 'on' = enabled
   - 'off' = disabled
   - 'none' = use Stripe's default logic

5. For Google Pay specifically, the user must have Google Pay set up on their
   device/browser for it to appear.
""")


if __name__ == "__main__":
    main()
