# Nenolink AI Marker — Sales and Secure Download Setup

Status: production setup documented after live end-to-end test on 2026-09-09.

This document describes the commercial checkout and protected download flow for Nenolink AI Marker. It intentionally excludes secrets, customer data, payment card data, and Checkout Session IDs.

## 1. Production flow

Customer flow:

1. Product page: `https://nenolink.com/en/about/ai-marker/`
2. Buy buttons open the Stripe Payment Link.
3. Stripe Checkout collects payment, VAT-related information and terms acceptance.
4. Stripe redirects after successful checkout to:
   `https://nenolink.com/en/thankyou/?session_id={CHECKOUT_SESSION_ID}`
5. JavaScript on the thank-you page reads the `session_id` query parameter.
6. If the session ID is missing or invalid, the download button is disabled.
7. If present, the button points to:
   `/download-ai-marker.php?session_id=...`
8. `download-ai-marker.php` verifies the Checkout Session server-side with Stripe.
9. Only after successful verification is the protected ZIP streamed to the customer.

The browser is never trusted to decide whether payment succeeded.

## 2. Stripe configuration

Current commercial setup:

- Product: Nenolink AI Marker Professional
- Release line: 1.x
- Launch price: EUR 39
- One-time payment
- Price shown to the customer includes VAT
- Stripe Tax enabled
- Promotion codes allowed
- Customer name required
- Business name optional
- Billing address collected
- Business customers may provide tax IDs
- Terms of service acceptance required
- No subscription

The Payment Link must redirect to the thank-you URL with Stripe's Checkout Session placeholder:

`https://nenolink.com/en/thankyou/?session_id={CHECKOUT_SESSION_ID}`

Do not redirect directly to the ZIP or EXE.

## 3. Server layout

Production server structure:

```text
/var/www/nenolink.com/
├── private/
│   └── stripe-config.php
└── public_html/
    ├── download-ai-marker.php
    └── downloads/
        └── ai-marker/
            └── Nenolink-AI-Marker-1.0.0-Windows.zip
```

The Stripe secret key is stored outside the public web root in:

`/private/stripe-config.php`

Example structure only:

```php
<?php
return [
    'stripe_secret_key' => 'sk_live_REDACTED',
];
```

Never commit a real `sk_live_...` or `sk_test_...` value to GitHub.

## 4. Protected download endpoint

Production endpoint:

`/public_html/download-ai-marker.php`

The endpoint performs these checks before serving the file:

- Session ID has an expected Stripe Checkout Session format.
- The Checkout Session can be retrieved from Stripe using the server-side secret key.
- `status` is `complete`.
- `payment_status` is `paid`.
- The Checkout Session line items contain the expected Nenolink AI Marker product.
- The expected ZIP exists and is readable.

The server then streams the ZIP with download headers.

The endpoint must never accept an arbitrary filesystem path or filename from the browser.

## 5. Direct file protection

The release ZIP and EXE are stored under:

`/public_html/downloads/ai-marker/`

Direct HTTP access to `.zip` and `.exe` is blocked by server configuration / `.htaccess`.

A direct request to the EXE was tested and returned HTTP 403 Forbidden. This is expected.

PHP may still read and stream the ZIP from the filesystem after successful Stripe verification.

## 6. Thank-you page JavaScript

The thank-you page contains JavaScript that:

- reads `session_id` from the page URL;
- requires the value to begin with a Stripe Checkout Session prefix;
- disables the download button when no valid session ID is present;
- appends the encoded session ID to `/download-ai-marker.php` when present.

This JavaScript is a user-interface guard only. Payment authorization is performed server-side in PHP.

## 7. Live end-to-end test — 2026-09-09

The production chain was tested with a live Stripe Checkout payment at a heavily discounted test amount.

Verified sequence:

1. Customer opened the live Stripe Checkout page.
2. Promotion-code support was visible and functional after correct setup.
3. Payment completed successfully.
4. Stripe redirected to the Nenolink thank-you page with a live Checkout Session ID.
5. The download button became active.
6. The PHP endpoint received the Checkout Session ID.
7. The PHP endpoint verified the session with Stripe.
8. The protected ZIP downloaded successfully.
9. The downloaded archive opened correctly and contained the expected release files and folders.

Expected top-level archive contents include:

- `Nenolink-AI-Marker-1.0.0.exe`
- `assets/`
- `docs/`
- `locales/`
- `THIRD_PARTY_NOTICES/`
- `tools/`

## 8. Test failure found and resolved

Initial live download attempts returned:

`Server configuration is unavailable.`

A temporary diagnostic PHP file was used to inspect the PHP runtime paths.

The server reported:

- `__DIR__`: `/var/www/nenolink.com/public_html`
- parent: `/var/www/nenolink.com`
- private directory: `/var/www/nenolink.com/private`

The root cause was a filename typo:

`stripe-config.pnp`

instead of:

`stripe-config.php`

After renaming the file correctly, the production download flow worked.

The temporary diagnostic file must not remain in production after testing.

## 9. Release 1.0.0 integrity

Approved Windows archive:

`Nenolink-AI-Marker-1.0.0-Windows.zip`

Expected SHA-256:

`1669569D27B4E6EB738D4A0D4A44A165EC05E7FF2AA03AFB12D675D82946F84E`

Approved EXE SHA-256:

`B6B5B26F408C8CF1C68B819EB6E7545C5799FE61D2FA34621965B42F062FD256`

The customer-facing download should provide the ZIP rather than the bare EXE because the ZIP contains the application plus documentation, third-party notices and runtime components.

## 10. Release/update checklist

For a future release such as 1.0.1 or 1.1.0:

1. Freeze and verify the application build.
2. Run the complete automated and manual release tests.
3. Record EXE and ZIP SHA-256 values.
4. Confirm the ZIP contains all required runtime files, guides, licences and third-party notices.
5. Upload the new ZIP to the protected server directory.
6. Update the fixed release filename in `download-ai-marker.php` if the filename changes.
7. Update version text and SHA-256 shown on the thank-you/download page.
8. Update product-page version information if relevant.
9. Keep direct `.zip` and `.exe` HTTP access blocked.
10. Perform a checkout test and verify Stripe redirect, session verification and protected download.
11. Confirm the downloaded ZIP hash matches the approved release hash.
12. Remove any temporary diagnostic files and disable temporary test promotion codes.
13. Do not expose or commit Stripe secret keys, customer data or Checkout Session IDs.

## 11. Security notes and future improvements

Current protection is based on a valid paid Stripe Checkout Session and the expected product.

A Checkout Session ID is high-entropy but can be reused or shared if someone obtains it. A future stronger fulfilment architecture may add:

- Stripe webhooks for durable fulfilment;
- an order database;
- generated one-time or expiring download tokens;
- download limits;
- audit logging with an explicit retention policy;
- a restricted Stripe API key with only the permissions required for Checkout Session verification.

These are improvements to consider for a later release or higher sales volume. They are not required to change the frozen 1.0.0 application binary itself.

## 12. Operational rule

Never place Stripe secret keys in:

- Joomla article HTML;
- browser JavaScript;
- public GitHub files;
- public web directories;
- screenshots or support messages.

Only the server-side PHP process should have access to the secret key used for Stripe verification.
