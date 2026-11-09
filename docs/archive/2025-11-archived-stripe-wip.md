Current Stripe Setup: You mentioned you already have a Stripe Payment Link on nomadkaraoke.com. Can you share:
What Stripe product/price ID is currently configured for the $2 payment?
 - I haven't created a product for this yet; depending on your guidance I can do so but I wanted to talk it through to understand how this will work first.
 - I have an existing product (prod_QJUtpNwZBpNOWz) and payment link (plink_1PSsYyJqOK5vtxo4A1gBQUUO) for my manual karaoke production workflow which is exposed to customers at https://buy.stripe.com/dR67sx4wZcdt2DC9AA and I don't want to modify this.

Do you want to keep using Payment Links or switch to Checkout Sessions?
 - Not sure, what are the pros/cons? I've found the Payment Link setup to be pretty easy to configure and use but I don't know much more about other Stripe offerings. Please guide me.

What's the current success/cancel URL setup?
 - Not sure, probably not set up yet, please guide me.


Token Delivery: How do you want to deliver the access token to customers after payment?
 - Email them the token automatically?
 - Show token on a success page?
 Probably both; I'd like to make the user flow frictionless so after payment they should see a success page 

Token Configuration: For the $2 payment, what should the token provide?
How many uses? (1 video generation for $2?)
Any expiration time?
Any special description/branding?


Domain Setup: Do you control the nomadkaraoke.com website, or is this a separate system? I need to understand how to:
Modify the existing payment button
Set up the success/failure flow
Ensure the domains can communicate


Stripe Environment: Are you ready to use live Stripe keys, or should we start with test mode?


Email Service: Do you have any preferred email service (SendGrid, Mailgun, etc.) for sending tokens, or should I implement a simple SMTP solution?

