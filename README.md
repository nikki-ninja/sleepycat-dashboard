# Sleepycat product analytics dashboard

Single-page dashboard for D2C + store performance. Layout and written analysis live in
`index.html`; the numbers live in `data/data.js`, regenerated from Snowflake daily.

**Live:** https://<your-user>.github.io/<repo>/

## How it refreshes

`.github/workflows/refresh.yml` runs `scripts/build_data.py` every day at 08:00 IST.
The script queries Snowflake, writes `data/data.js`, sanity-checks it, and commits only if
something changed. Nothing is uploaded by hand.

```
index.html            layout + narrative  (edit when the analysis changes)
data/data.js          numbers             (generated — never edit by hand)
data/data.json        same payload as JSON, for anything else that wants to read it
scripts/build_data.py the Snowflake queries
```

The date stamps in the header read from the data, so they cannot disagree with the table
underneath them.

## One-time setup

1. **Repo → Settings → Pages →** Source: *Deploy from a branch*, branch `main`, folder `/`.
2. **Repo → Settings → Secrets and variables → Actions →** add five repository secrets:

   | Secret | Value |
   |---|---|
   | `SNOWFLAKE_ACCOUNT` | your account identifier, e.g. `ab12345.ap-south-1` |
   | `SNOWFLAKE_USER` | a read-only service user, not a personal login |
   | `SNOWFLAKE_PASSWORD` | that user's password |
   | `SNOWFLAKE_ROLE` | a role with USAGE on **both** `RAW_SHOPIFY_SLEEPYCAT` and `SLEEPYCAT_DB.MAPLEMONK` |
   | `SNOWFLAKE_WAREHOUSE` | e.g. `SLEEPYCAT_WH` |

3. **Actions tab → Refresh dashboard data → Run workflow** to test it once by hand.

Secrets are encrypted and are **not** exposed by a public repo. Workflows triggered from
forked pull requests do not receive them.

## This repo is public

`data/data.js` is readable by anyone with the URL, and so is everything rendered from it:
daily revenue and AOV, SKU-level revenue and return rates, state and city revenue, POS store
revenue, payment failure rates, weekly Meta ad spend and ROAS, cohort sizes, and the
competitor benchmark.

To close that off later: make the repo private and either move to a paid GitHub plan (Pages
on private repos) or point Cloudflare Pages at the repo and put Cloudflare Access in front of
it (free for up to 50 users). No code changes are needed for either — only `index.html` and
`data/` have to ship together.

## Data notes

Definitions, known traps and the reasoning behind each metric are in the project docs, not
here. The ones that bite most often:

- **D2C online** = Shopify `SOURCE_NAME` in `256945782785`, `web`, `326345687041` (GoKwik,
  live 22 Aug 2026), not cancelled. **POS** = `266308321281`.
- `SLEEPYCAT_DB_GOKWIK_SOURCE` has duplicate IDs — always pre-aggregate before joining.
- Order dates are IST (`CONVERT_TIMEZONE('Asia/Kolkata', …)`); session `DAY` is already local.
- Sessions and orders must be bucketed by the *same* CASE expression or the CVR is invalid.
  `scripts/build_data.py` defines it once and injects it into both queries for that reason.
- POS before 22 Jun 2026 is not in Snowflake at all — earlier weekly POS figures are phantom.
