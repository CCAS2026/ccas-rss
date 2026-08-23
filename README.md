# CCAS Automatic Blog RSS Feed

This project creates an automatic RSS 2.0 feed for the CCAS Blog & Media Center:

https://ccas.global/ccas-%7C-blogs-%26-media

## What it does

- Checks CCAS.global automatically every hour.
- Discovers blog posts through the site's XML sitemap when available.
- Falls back to scanning the CCAS blog page for `/f/` post links.
- Opens each discovered blog post.
- Extracts the title, canonical URL, description, publication date and category when available.
- Produces `docs/rss.xml`.
- Commits changes only when the generated feed changes.
- Can be published as a permanent public RSS URL with GitHub Pages.

## Recommended public feed address

After you create a GitHub repository, enable GitHub Pages from the `docs` folder.

Your feed will then look like:

https://YOUR-GITHUB-USERNAME.github.io/YOUR-REPOSITORY/rss.xml

You may later map a custom subdomain, for example:

https://feeds.ccas.global/rss.xml

That is preferable to trying to overwrite GoDaddy's site files.

## Setup

1. Create a new GitHub repository, for example `ccas-rss`.
2. Upload every file and folder in this package to the repository.
3. Make sure the default branch is named `main`.
4. Open **Settings → Pages**.
5. Under **Build and deployment**, choose **Deploy from a branch**.
6. Select branch **main** and folder **/docs**.
7. Save.
8. Open **Actions** and run **Update CCAS RSS Feed** once manually.
9. GitHub will then check CCAS.global every hour automatically.

## Important: update the self URL

Once GitHub Pages gives you the final public URL, open `generate_rss.py` and replace:

https://YOUR-GITHUB-PAGES-URL/rss.xml

with the actual RSS address.

## Custom CCAS feed domain

For stronger branding, create a DNS subdomain such as `feeds.ccas.global` and point it to your GitHub Pages site following GitHub Pages custom-domain instructions.

The resulting RSS address could be:

https://feeds.ccas.global/rss.xml

## How new blogs appear

Nothing needs to be added manually to this project.

When a new article is published on the CCAS GoDaddy blog, the scheduled workflow discovers the new `/f/` blog URL, extracts its metadata, regenerates `rss.xml`, and publishes the update.

## Feed positioning

Feed title:
**CCAS Global Compliance Blog**

The feed is intentionally excerpt-based. It sends readers to the original CCAS.global blog post instead of copying the full article into third-party readers. This preserves CCAS.global as the primary traffic destination.

## Troubleshooting

If GoDaddy materially changes its blog HTML or blocks automated requests, the GitHub Actions run will fail rather than silently publish an empty feed. The generator uses both sitemap discovery and blog-page scanning to reduce that risk.

## Current check frequency

Once per hour at minute 17.

You can change the cron expression in:

`.github/workflows/update-rss.yml`

GitHub Actions does not guarantee exact minute-level start times for scheduled workflows.
