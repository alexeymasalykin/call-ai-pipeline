# CRM Integration: Companies + Deals (replacing Leads)

## Context

The current pipeline creates/updates Leads in Bitrix24. The actual business workflow has no leads — companies are pre-loaded, managers call them, and create deals manually after successful calls. The pipeline should attach call analysis to the deal (or company if no deal exists yet).

## Design

### New Bitrix24Client methods

**`find_company_by_phone(phone: str) -> dict | None`**
- API: `crm.company.list`
- No retries — company either exists or doesn't
- Returns first match or None
- Logs: `company_found` (info) / `company_not_found` (warning)

```python
{
    "filter": {"PHONE": phone},
    "select": ["ID", "TITLE"],
}
```

**`find_open_deal(company_id: int) -> dict | None`**
- API: `crm.deal.list`
- Open deal = any deal where STAGE_ID is NOT WON or LOSE (all other stages are considered open)
- With retries: up to 2 extra attempts with 30s delay (manager may still be creating the deal after the call ends)
- Returns the most recent open deal or None
- Logs: `deal_found` (info) / `deal_not_found_retry` (info) / `deal_not_found` (warning)

```python
{
    "filter": {"COMPANY_ID": company_id, "!STAGE_ID": ["WON", "LOSE"]},
    "select": ["ID", "TITLE", "STAGE_ID"],
    "order": {"DATE_CREATE": "DESC"},
}
```

### Phone field selection

Which phone to search by depends on call direction:
- **Outgoing** (manager calls client): search by `called_number` — the company being called
- **Incoming** (client calls us): search by `caller_number` — the calling company

Currently only outgoing calls are used, but the logic handles both.

### Pipeline step 6 (CRM) — new flow

```
phone = called_number if outgoing else caller_number
company = find_company_by_phone(phone)
  not found → log warning, save_failed_crm, return (non-fatal)

deal = find_open_deal(company.id)
  found    → add_timeline_comment("deal", deal.id, analysis)
  not found → add_timeline_comment("company", company.id, analysis)
```

Analysis is always attached — to the deal if one exists, otherwise to the company.
Timeline comment failure is non-fatal: caught and saved to `/data/failed_crm/`, same as current.

### Removed

- `LeadData` schema from schemas.py
- `find_lead_by_phone`, `create_lead`, `update_lead` from Bitrix24Client
- All lead logic from pipeline.py step 6
- `skip_spam` parameter from `process_call` and `worker.py` — rejected/spam are skipped unconditionally at step 5
- `SKIP_SPAM_LEADS` setting from config.py

### Unchanged

- `_format_comment` — works as-is
- `_save_failed_crm_result` — works as-is
- `add_timeline_comment` — already supports any entity type (`company`, `deal`)
- `_call` with retry logic — reused by new methods
- Pipeline steps 1-5 (download → S3 → STT → LLM → skip filter)

### Error handling

- Company not found: log warning, save to `/data/failed_crm/`, return (non-fatal, pipeline succeeds)
- Deal search API error: raise `Bitrix24APIError`, caught by existing best-effort wrapper in pipeline
- Timeline comment failure: caught, saved to `/data/failed_crm/` (non-fatal)

### Tests

- `test_bitrix24.py`: replace lead method tests with:
  - `TestFindCompanyByPhone`: found, not found, API error
  - `TestFindOpenDeal`: found, not found after retries, API error
- `test_pipeline.py`: replace lead tests with company+deal flow:
  - deal found → comment on deal
  - deal not found → comment on company
  - company not found → save_failed_crm
  - rejected/spam always skipped (no skip_spam param)
- `test_schemas.py`: remove `TestLeadData`
- `test_worker.py`: remove `SKIP_SPAM_LEADS` from settings mock
