-- =====================================================================
-- Starter source registry. Run after 0001_init.sql. Re-runnable.
-- Board slugs are starting points: the pipeline records each source's
-- live health, and a source that fails repeatedly is disabled automatically
-- (see job_sources.status). Verify a slug in your browser before enabling.
-- Aggregator sources (Internshala, Wellfound, Unstop) stay DISABLED until
-- you add listing URLs you have confirmed are permitted by their terms.
-- =====================================================================
insert into public.job_sources (name, adapter, config, enabled) values
  ('greenhouse:stripe',      'greenhouse', '{"board":"stripe","company":"Stripe"}',           true),
  ('greenhouse:databricks',  'greenhouse', '{"board":"databricks","company":"Databricks"}',   true),
  ('greenhouse:cloudflare',  'greenhouse', '{"board":"cloudflare","company":"Cloudflare"}',   true),
  ('greenhouse:figma',       'greenhouse', '{"board":"figma","company":"Figma"}',             true),
  ('greenhouse:coinbase',    'greenhouse', '{"board":"coinbase","company":"Coinbase"}',       true),
  ('greenhouse:airbnb',      'greenhouse', '{"board":"airbnb","company":"Airbnb"}',           true),
  ('greenhouse:robinhood',   'greenhouse', '{"board":"robinhood","company":"Robinhood"}',     true),
  ('greenhouse:discord',     'greenhouse', '{"board":"discord","company":"Discord"}',         true),
  ('lever:spotify',          'lever',      '{"company_slug":"spotify","company":"Spotify"}', true),
  ('lever:mistral',          'lever',      '{"company_slug":"mistral","company":"Mistral AI"}', true),
  ('ashby:ramp',             'ashby',      '{"board":"ramp","company":"Ramp"}',            true),
  ('ashby:linear',           'ashby',      '{"board":"linear","company":"Linear"}',        true),
  ('ashby:supabase',         'ashby',      '{"board":"supabase","company":"Supabase"}',    true),
  ('ashby:openai',           'ashby',      '{"board":"openai","company":"OpenAI"}',        true),
  ('jsonld:internshala',     'jsonld_pages', '{"seed_urls":[]}',                           false),
  ('jsonld:wellfound',       'jsonld_pages', '{"seed_urls":[]}',                           false),
  ('jsonld:unstop',          'jsonld_pages', '{"seed_urls":[]}',                           false),
  ('rss:custom-india-feeds', 'rss',        '{"feed_urls":[],"location":"India"}',          false)
on conflict (name) do nothing;
