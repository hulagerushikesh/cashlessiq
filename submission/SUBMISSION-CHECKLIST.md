# CashlessIQ submission checklist

## Form fields

- **GitHub:** https://github.com/hulagerushikesh/cashlessiq
- **Prototype:** https://cashlessiq.hulage.in
- **Challenges:** Patient and Member 360; Clinical or Regulatory Document Copilot
- **Prototype/MVP brief:** paste the contents of `mvp-brief.md`
- **Demo video:** upload a 2–3 minute recording as Unlisted on YouTube or Loom,
  then paste its share link
- **Prototype deck:** upload `CashlessIQ-Official-Prototype-Deck.pptx`

## Public prototype deployment

1. In Cloudflare, disable the current `CashlessIQ prototype` redirect rule.
2. Go to **Workers & Pages → Create → Pages → Upload assets**.
3. Project name: `cashlessiq`; upload `cashlessiq-public-demo.zip`; deploy.
4. Open the generated `*.pages.dev` URL and test GOL007 and GOL027.
5. In the Pages project, open **Custom domains → Set up a custom domain** and
   enter `cashlessiq.hulage.in`.
6. If Cloudflare reports a DNS conflict, delete only the placeholder
   `cashlessiq` A record (`192.0.2.1`) and retry the custom-domain setup.
7. Confirm `https://cashlessiq.hulage.in` opens in an incognito window without
   a Snowflake login.

The authenticated Snowflake viewer remains linked from the public demo for
judges who receive `CIQ_JUDGE` credentials.
