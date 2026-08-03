alter table public.asset_payments
    add column if not exists eur_equivalent_amount numeric;
