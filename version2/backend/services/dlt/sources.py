"""
dlt Source Registry
===================

Maps connector type keys to dlt source factory functions.

Each factory function receives:
  - credentials: dict of decrypted credentials (API key, tokens, etc.)
  - incremental: bool — whether to use incremental loading

And returns a dlt source object (iterable of dlt resources) that can be
passed directly to ``pipeline.run(source)``.

Architecture:
  - Verified sources (Salesforce, HubSpot, Jira, etc.) use dlt's built-in sources
  - Generic REST API sources (LinkedIn Ads, Mailchimp, etc.) use
    ``dlt.sources.rest_api.rest_api_source`` with pre-configured endpoint dicts
  - Custom/internal sources declare endpoints in a config dict

Adding a new source type:
  1. Find or write the dlt source function
  2. Register it in ``SOURCE_REGISTRY``'s ``get_source_registry()``
  3. Add the ``source_type`` to the appropriate frozenset in ``runner.py``
     (``API_KEY_SOURCE_TYPES`` or ``PASSWORD_SOURCE_TYPES``)
  4. Add the connector card to the frontend ``ConnectorsPage``
"""

from __future__ import annotations

import logging
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Type alias for source factory functions
# ---------------------------------------------------------------------------
SourceFactory = Callable[[dict[str, Any], bool], Any]

logger = logging.getLogger(__name__)


# ===================================================================
#  VERIFIED SOURCES (dedicated dlt packages)
#  Each uses a specific dlt.sources.* module with tailored logic
# ===================================================================


def _salesforce_source(credentials: dict[str, Any], incremental: bool) -> Any:
    """Salesforce connector via dlt verified source."""
    from dlt.sources.salesforce import salesforce_source

    return salesforce_source(
        credentials={
            "client_id": credentials.get("client_id", ""),
            "client_secret": credentials.get("client_secret", ""),
            "username": credentials.get("username", ""),
            "password": credentials.get("password", ""),
            "security_token": credentials.get("security_token", ""),
            "instance_url": credentials.get("instance_url", ""),
        },
    )


def _hubspot_source(credentials: dict[str, Any], incremental: bool) -> Any:
    """HubSpot connector via dlt verified source."""
    from dlt.sources.hubspot import hubspot_source

    return hubspot_source(
        api_key=credentials.get("api_key", ""),
    )


def _shopify_source(credentials: dict[str, Any], incremental: bool) -> Any:
    """Shopify connector via dlt verified source."""
    from dlt.sources.shopify import shopify_source

    return shopify_source(
        api_key=credentials.get("api_key", ""),
        subdomain=credentials.get("subdomain", ""),
    )


def _stripe_source(credentials: dict[str, Any], incremental: bool) -> Any:
    """Stripe connector via dlt verified source."""
    from dlt.sources.stripe import stripe_source

    return stripe_source(
        api_key=credentials.get("api_key", ""),
        incremental=incremental,
    )


def _zendesk_source(credentials: dict[str, Any], incremental: bool) -> Any:
    """Zendesk connector via dlt verified source."""
    from dlt.sources.zendesk import zendesk_source

    return zendesk_source(
        api_key=credentials.get("api_key", ""),
        subdomain=credentials.get("subdomain", ""),
    )


def _github_source(credentials: dict[str, Any], incremental: bool) -> Any:
    """GitHub connector via dlt verified source."""
    from dlt.sources.github import github_source

    return github_source(
        access_token=credentials.get("api_key", ""),
    )


def _notion_source(credentials: dict[str, Any], incremental: bool) -> Any:
    """Notion connector via dlt verified source."""
    from dlt.sources.notion import notion_source

    return notion_source(
        api_key=credentials.get("api_key", ""),
    )


def _slack_source(credentials: dict[str, Any], incremental: bool) -> Any:
    """Slack connector via dlt verified source."""
    from dlt.sources.slack import slack_source

    return slack_source(
        api_key=credentials.get("api_key", ""),
    )


def _airtable_source(credentials: dict[str, Any], incremental: bool) -> Any:
    """Airtable connector via dlt verified source."""
    from dlt.sources.airtable import airtable_source

    return airtable_source(
        api_key=credentials.get("api_key", ""),
    )


def _google_analytics_source(credentials: dict[str, Any], incremental: bool) -> Any:
    """Google Analytics (GA4) connector via dlt verified source."""
    from dlt.sources.google_analytics import google_analytics_source

    return google_analytics_source(
        property_id=credentials.get("property_id", ""),
        credentials={
            "client_id": credentials.get("client_id", ""),
            "client_secret": credentials.get("client_secret", ""),
            "refresh_token": credentials.get("refresh_token", ""),
        },
    )


def _google_ads_source(credentials: dict[str, Any], incremental: bool) -> Any:
    """Google Ads connector via dlt verified source."""
    from dlt.sources.google_ads import google_ads_source

    return google_ads_source(
        developer_token=credentials.get("developer_token", ""),
        client_id=credentials.get("client_id", ""),
        client_secret=credentials.get("client_secret", ""),
        refresh_token=credentials.get("refresh_token", ""),
        login_customer_id=credentials.get("login_customer_id", ""),
    )


def _facebook_ads_source(credentials: dict[str, Any], incremental: bool) -> Any:
    """Facebook / Meta Ads connector via dlt verified source."""
    from dlt.sources.facebook_ads import facebook_ads_source

    return facebook_ads_source(
        access_token=credentials.get("api_key", ""),
        account_id=credentials.get("account_id", ""),
    )


def _jira_source(credentials: dict[str, Any], incremental: bool) -> Any:
    """Jira connector via dlt verified source."""
    from dlt.sources.jira import jira_source

    return jira_source(
        subdomain=credentials.get("subdomain", ""),
        email=credentials.get("username", ""),
        api_token=credentials.get("api_key", ""),
    )


def _asana_source(credentials: dict[str, Any], incremental: bool) -> Any:
    """Asana connector via dlt verified source."""
    from dlt.sources.asana import asana_source

    return asana_source(
        access_token=credentials.get("api_key", ""),
    )


def _pipedrive_source(credentials: dict[str, Any], incremental: bool) -> Any:
    """Pipedrive CRM connector via dlt verified source."""
    from dlt.sources.pipedrive import pipedrive_source

    return pipedrive_source(
        api_token=credentials.get("api_key", ""),
    )


def _freshdesk_source(credentials: dict[str, Any], incremental: bool) -> Any:
    """Freshdesk connector via dlt verified source."""
    from dlt.sources.freshdesk import freshdesk_source

    return freshdesk_source(
        api_key=credentials.get("api_key", ""),
        subdomain=credentials.get("subdomain", ""),
    )


def _mixpanel_source(credentials: dict[str, Any], incremental: bool) -> Any:
    """Mixpanel connector via dlt verified source."""
    from dlt.sources.mixpanel import mixpanel_source

    return mixpanel_source(
        api_secret=credentials.get("api_key", ""),
        project_id=credentials.get("project_id", ""),
    )


def _mongodb_source(credentials: dict[str, Any], incremental: bool) -> Any:
    """MongoDB connector via dlt verified source."""
    from dlt.sources.mongodb import mongodb_source

    return mongodb_source(
        connection_url=credentials.get("connection_url", ""),
        database=credentials.get("database", ""),
    )


# ===================================================================
#  DATABASE SOURCES (dlt sql_database)
# ===================================================================


def _postgres_source(credentials: dict[str, Any], incremental: bool) -> Any:
    """
    PostgreSQL connector via dlt sql_database source.

    For databases, dlt can discover tables and incrementally sync them.
    """
    from dlt.sources.sql_database import sql_database

    connection_url = credentials.get(
        "connection_url",
        f"postgresql://{credentials.get('username', '')}:{credentials.get('password', '')}"
        f"@{credentials.get('host', '')}:{credentials.get('port', 5432)}"
        f"/{credentials.get('database', '')}",
    )

    return sql_database(connection_url, reflect_tables=True)


def _snowflake_source(credentials: dict[str, Any], incremental: bool) -> Any:
    """Snowflake connector via dlt sql_database source."""
    from dlt.sources.sql_database import sql_database

    connection_url = (
        f"snowflake://{credentials.get('username', '')}:{credentials.get('password', '')}"
        f"@{credentials.get('host', '')}/{credentials.get('database', '')}"
    )
    return sql_database(connection_url, reflect_tables=True)


# ===================================================================
#  REST API SOURCES (generic — configured per service)
#  Each factory configures rest_api_source with the correct base URL,
#  auth method, and common resource endpoints for that service.
# ===================================================================

# ── Helper ────────────────────────────────────────────────────────────────


def _make_rest_source(
    base_url: str,
    credentials: dict[str, Any],
    resources: list[dict[str, Any]] | None = None,
    auth_type: str = "bearer",
    paginator: dict[str, Any] | None = None,
) -> Any:
    """
    Build a configured ``rest_api_source`` for a generic service.

    Args:
        base_url: The API base URL (e.g. ``"https://api.linkedin.com/v2"``).
        credentials: Decrypted credentials dict (must include ``api_key`` or
                     ``username``/``password`` depending on auth_type).
        resources: List of resource endpoint configs. If None, uses the root.
        auth_type: Authentication method — ``"bearer"``, ``"basic"``,
                   ``"api_key"`` (header-based), or ``"none"``.
        paginator: Pagination config dict (defaults to ``json_link``).
    """
    from dlt.sources.rest_api import rest_api_source

    client_config: dict[str, Any] = {
        "base_url": base_url,
    }

    # Authentication
    api_key = credentials.get("api_key") or credentials.get("token")
    if auth_type == "bearer" and api_key:
        client_config["auth"] = {"type": "bearer", "token": api_key}
    elif auth_type == "basic" and credentials.get("username"):
        client_config["auth"] = {
            "type": "basic",
            "username": credentials.get("username", ""),
            "password": credentials.get("password", ""),
        }
    elif auth_type == "api_key" and api_key:
        # API key passed as a header (common pattern)
        header_name = credentials.get("auth_header", "Authorization")
        client_config["auth"] = {
            "type": "api_key",
            "name": header_name,
            "api_key": api_key,
            "location": "header",
        }

    # Pagination
    p = paginator or {"type": "json_link", "next_url_path": "paging.next"}
    client_config["paginator"] = p

    source_config: dict[str, Any] = {
        "client": client_config,
        "resources": resources or ["."],
    }

    return rest_api_source(source_config)


# ── LinkedIn Ads ──────────────────────────────────────────────────────────


def _linkedin_ads_source(credentials: dict[str, Any], incremental: bool) -> Any:
    """LinkedIn Ads connector via dlt REST API source."""
    return _make_rest_source(
        base_url="https://api.linkedin.com/v2",
        credentials=credentials,
        resources=[
            {"name": "ad_accounts", "endpoint": "adAccounts"},
            {"name": "campaigns", "endpoint": "adCampaignsV2"},
            {"name": "creatives", "endpoint": "adCreativesV2"},
            {"name": "analytics", "endpoint": "adAnalyticsV2"},
        ],
        paginator={"type": "json_link", "next_url_path": "paging.start"},
    )


# ── Mailchimp ─────────────────────────────────────────────────────────────


def _mailchimp_source(credentials: dict[str, Any], incremental: bool) -> Any:
    """Mailchimp connector via dlt REST API source.

    Mailchimp uses HTTP Basic auth where the username is arbitrary
    (commonly ``"dlt"`` or ``"anystring"``) and the password is the API key.
    The data center is extracted from the API key (e.g. ``us1`` from
    ``abc123-us1``) or from the ``data_center`` field.
    """
    api_key = credentials.get("api_key", "")
    # Mailchimp API keys contain the data center suffix: "key-us1"
    dc = credentials.get("data_center", "")
    if not dc and "-" in api_key:
        dc = api_key.split("-")[-1]
    dc = dc or "us1"

    return _make_rest_source(
        base_url=f"https://{dc}.api.mailchimp.com/3.0",
        credentials={
            "username": "dlt",
            "password": api_key,
        },
        auth_type="basic",
        resources=[
            {"name": "lists", "endpoint": "lists"},
            {"name": "campaigns", "endpoint": "campaigns"},
            {"name": "reports", "endpoint": "reports"},
            {"name": "automations", "endpoint": "automations"},
            {"name": "templates", "endpoint": "templates"},
        ],
    )


# ── GitLab ────────────────────────────────────────────────────────────────


def _gitlab_source(credentials: dict[str, Any], incremental: bool) -> Any:
    """GitLab connector via dlt REST API source."""
    return _make_rest_source(
        base_url=credentials.get("base_url", "https://gitlab.com/api/v4"),
        credentials=credentials,
        auth_type="bearer",
        resources=[
            {"name": "projects", "endpoint": "projects"},
            {"name": "groups", "endpoint": "groups"},
            {"name": "users", "endpoint": "users"},
            {"name": "merge_requests", "endpoint": "merge_requests"},
            {"name": "pipelines", "endpoint": "pipelines"},
            {"name": "jobs", "endpoint": "jobs"},
        ],
    )


# ── Monday.com ────────────────────────────────────────────────────────────


def _monday_source(credentials: dict[str, Any], incremental: bool) -> Any:
    """Monday.com connector via dlt REST API source."""
    return _make_rest_source(
        base_url="https://api.monday.com/v2",
        credentials=credentials,
        auth_type="bearer",
        resources=[
            {"name": "boards", "endpoint": "boards"},
            {"name": "items", "endpoint": "items"},
            {"name": "workspaces", "endpoint": "workspaces"},
            {"name": "users", "endpoint": "users"},
            {"name": "updates", "endpoint": "updates"},
        ],
    )


# ── Trello ────────────────────────────────────────────────────────────────


def _trello_source(credentials: dict[str, Any], incremental: bool) -> Any:
    """Trello connector via dlt REST API source."""
    api_key = credentials.get("api_key", "")
    token = credentials.get("token", "")
    return _make_rest_source(
        base_url="https://api.trello.com/1",
        credentials=credentials,
        auth_type="api_key",
        resources=[
            {
                "name": "boards",
                "endpoint": {"path": f"members/me/boards?key={api_key}&token={token}"},
            },
            {"name": "organizations", "endpoint": "organizations"},
        ],
    )


# ── Confluence ────────────────────────────────────────────────────────────


def _confluence_source(credentials: dict[str, Any], incremental: bool) -> Any:
    """Confluence connector via dlt REST API source."""
    subdomain = credentials.get("subdomain", "")
    return _make_rest_source(
        base_url=f"https://{subdomain}.atlassian.net/wiki/rest/api",
        credentials=credentials,
        auth_type="basic",
        resources=[
            {"name": "spaces", "endpoint": "space"},
            {"name": "pages", "endpoint": "content?type=page"},
            {"name": "blogposts", "endpoint": "content?type=blogpost"},
            {"name": "attachments", "endpoint": "content?type=attachment"},
            {"name": "labels", "endpoint": "label"},
            {"name": "audit", "endpoint": "audit"},
        ],
    )


# ── Intercom ──────────────────────────────────────────────────────────────


def _intercom_source(credentials: dict[str, Any], incremental: bool) -> Any:
    """Intercom connector via dlt REST API source."""
    return _make_rest_source(
        base_url="https://api.intercom.io",
        credentials=credentials,
        auth_type="bearer",
        resources=[
            {"name": "contacts", "endpoint": "contacts"},
            {"name": "conversations", "endpoint": "conversations"},
            {"name": "companies", "endpoint": "companies"},
            {"name": "tags", "endpoint": "tags"},
            {"name": "segments", "endpoint": "segments"},
            {"name": "articles", "endpoint": "articles"},
            {"name": "tickets", "endpoint": "tickets"},
        ],
    )


# ── WooCommerce ───────────────────────────────────────────────────────────


def _woocommerce_source(credentials: dict[str, Any], incremental: bool) -> Any:
    """WooCommerce connector via dlt REST API source."""
    domain = credentials.get("domain", "")
    consumer_key = credentials.get("consumer_key", "")
    consumer_secret = credentials.get("consumer_secret", "")
    # Basic auth with consumer key:secret
    return _make_rest_source(
        base_url=f"https://{domain}/wp-json/wc/v3",
        credentials={
            "username": consumer_key,
            "password": consumer_secret,
        },
        auth_type="basic",
        resources=[
            {"name": "orders", "endpoint": "orders"},
            {"name": "products", "endpoint": "products"},
            {"name": "customers", "endpoint": "customers"},
            {"name": "categories", "endpoint": "products/categories"},
            {"name": "coupons", "endpoint": "coupons"},
            {"name": "reports", "endpoint": "reports"},
        ],
    )


# ── Klaviyo ───────────────────────────────────────────────────────────────


def _klaviyo_source(credentials: dict[str, Any], incremental: bool) -> Any:
    """Klaviyo connector via dlt REST API source."""
    return _make_rest_source(
        base_url="https://a.klaviyo.com/api",
        credentials=credentials,
        auth_type="api_key",
        resources=[
            {"name": "lists", "endpoint": "lists"},
            {"name": "profiles", "endpoint": "profiles"},
            {"name": "campaigns", "endpoint": "campaigns"},
            {"name": "flows", "endpoint": "flows"},
            {"name": "segments", "endpoint": "segments"},
            {"name": "metrics", "endpoint": "metrics"},
            {"name": "events", "endpoint": "events"},
        ],
    )


# ── Marketo ───────────────────────────────────────────────────────────────


def _marketo_source(credentials: dict[str, Any], incremental: bool) -> Any:
    """Marketo connector via dlt REST API source."""
    base_url = credentials.get("base_url", "https://<munchkin-id>.mktorest.com")
    return _make_rest_source(
        base_url=f"{base_url}/rest/v1",
        credentials=credentials,
        auth_type="bearer",
        resources=[
            {"name": "leads", "endpoint": "leads.json"},
            {"name": "campaigns", "endpoint": "campaigns.json"},
            {"name": "programs", "endpoint": "programs.json"},
            {"name": "activities", "endpoint": "activities.json"},
            {"name": "lists", "endpoint": "lists.json"},
            {"name": "companies", "endpoint": "companies.json"},
        ],
    )


# ── Zoho CRM ──────────────────────────────────────────────────────────────


def _zoho_crm_source(credentials: dict[str, Any], incremental: bool) -> Any:
    """Zoho CRM connector via dlt REST API source."""
    dc = credentials.get("data_center", "com")
    return _make_rest_source(
        base_url=f"https://www.zohoapis.{dc}/crm/v2",
        credentials=credentials,
        auth_type="bearer",
        resources=[
            {"name": "accounts", "endpoint": "Accounts"},
            {"name": "contacts", "endpoint": "Contacts"},
            {"name": "leads", "endpoint": "Leads"},
            {"name": "deals", "endpoint": "Deals"},
            {"name": "campaigns", "endpoint": "Campaigns"},
            {"name": "tasks", "endpoint": "Tasks"},
            {"name": "notes", "endpoint": "Notes"},
        ],
    )


# ── Xero ──────────────────────────────────────────────────────────────────


def _xero_source(credentials: dict[str, Any], incremental: bool) -> Any:
    """Xero connector via dlt REST API source."""
    return _make_rest_source(
        base_url="https://api.xero.com/api.xro/2.0",
        credentials=credentials,
        auth_type="bearer",
        resources=[
            {"name": "accounts", "endpoint": "Accounts"},
            {"name": "contacts", "endpoint": "Contacts"},
            {"name": "invoices", "endpoint": "Invoices"},
            {"name": "credit_notes", "endpoint": "CreditNotes"},
            {"name": "bank_transactions", "endpoint": "BankTransactions"},
            {"name": "journals", "endpoint": "Journals"},
            {"name": "reports", "endpoint": "Reports"},
        ],
    )


# ── QuickBooks ────────────────────────────────────────────────────────────


def _quickbooks_source(credentials: dict[str, Any], incremental: bool) -> Any:
    """QuickBooks connector via dlt REST API source."""
    company_id = credentials.get("company_id", "")
    return _make_rest_source(
        base_url=f"https://quickbooks.api.intuit.com/v3/company/{company_id}",
        credentials=credentials,
        auth_type="bearer",
        resources=[
            {"name": "accounts", "endpoint": "query?query=SELECT * FROM Account"},
            {"name": "customers", "endpoint": "query?query=SELECT * FROM Customer"},
            {"name": "invoices", "endpoint": "query?query=SELECT * FROM Invoice"},
            {"name": "items", "endpoint": "query?query=SELECT * FROM Item"},
            {"name": "vendors", "endpoint": "query?query=SELECT * FROM Vendor"},
            {"name": "bills", "endpoint": "query?query=SELECT * FROM Bill"},
            {"name": "payments", "endpoint": "query?query=SELECT * FROM Payment"},
        ],
    )


# ── Amplitude ─────────────────────────────────────────────────────────────


def _amplitude_source(credentials: dict[str, Any], incremental: bool) -> Any:
    """Amplitude connector via dlt REST API source."""
    return _make_rest_source(
        base_url="https://amplitude.com/api/2",
        credentials=credentials,
        auth_type="bearer",
        resources=[
            {"name": "events", "endpoint": "events"},
            {"name": "users", "endpoint": "users"},
            {"name": "cohorts", "endpoint": "cohorts"},
            {"name": "charts", "endpoint": "charts"},
            {"name": "dashboards", "endpoint": "dashboards"},
        ],
    )


# ── Heap ──────────────────────────────────────────────────────────────────


def _heap_source(credentials: dict[str, Any], incremental: bool) -> Any:
    """Heap connector via dlt REST API source."""
    return _make_rest_source(
        base_url="https://heapanalytics.com/api/v1",
        credentials=credentials,
        auth_type="bearer",
        resources=[
            {"name": "events", "endpoint": "events"},
            {"name": "users", "endpoint": "users"},
            {"name": "sessions", "endpoint": "sessions"},
            {"name": "pages", "endpoint": "pages"},
        ],
    )


# ── Linear ────────────────────────────────────────────────────────────────


def _linear_source(credentials: dict[str, Any], incremental: bool) -> Any:
    """Linear connector via dlt REST API source.

    Linear uses a GraphQL API at ``https://api.linear.app/graphql``.
    The REST API source sends ``GET`` requests to endpoints, but GraphQL
    uses ``POST`` with a JSON body. This factory overrides the default
    paginator settings and passes resources as GraphQL query endpoints.

    Note: Linear's GraphQL API requires query definitions in the endpoint
    payload. This factory provides the base connectivity — for complex
    queries, use the ``rest_api`` generic source with a custom endpoint
    config that includes the ``"data_selector"`` and ``"post_body"``.
    """
    from dlt.sources.rest_api import rest_api_source

    client_config: dict[str, Any] = {
        "base_url": "https://api.linear.app/graphql",
    }

    api_key = credentials.get("api_key") or credentials.get("token")
    if api_key:
        client_config["auth"] = {"type": "bearer", "token": api_key}

    source_config = {
        "client": client_config,
        "resources": [
            {
                "name": "issues",
                "endpoint": {
                    "path": "",
                    "method": "POST",
                    "json": {
                        "query": "{ issues { nodes { id title description createdAt updatedAt } } }"
                    },
                },
            },
            {
                "name": "projects",
                "endpoint": {
                    "path": "",
                    "method": "POST",
                    "json": {
                        "query": "{ projects { nodes { id name description createdAt updatedAt } } }"
                    },
                },
            },
            {
                "name": "teams",
                "endpoint": {
                    "path": "",
                    "method": "POST",
                    "json": {
                        "query": "{ teams { nodes { id name key description } } }"
                    },
                },
            },
            {
                "name": "users",
                "endpoint": {
                    "path": "",
                    "method": "POST",
                    "json": {
                        "query": "{ users { nodes { id name email displayName } } }"
                    },
                },
            },
            {
                "name": "cycles",
                "endpoint": {
                    "path": "",
                    "method": "POST",
                    "json": {
                        "query": "{ cycles { nodes { id name startsAt endsAt completedAt } } }"
                    },
                },
            },
        ],
    }

    return rest_api_source(source_config)


# ===================================================================
#  REGISTRY — maps source_type keys to factory functions
# ===================================================================


def get_source_registry() -> dict[str, SourceFactory]:
    """
    Return the mapping of source type keys to factory functions.

    The registry is rebuilt on every call so that new source types added
    at runtime are picked up. This dict is small and cheap to construct.

    Returns:
        dict: ``{source_type_str: factory_function}``
    """
    return {
        # ── Verified SaaS sources ──────────────────────────────────────
        "salesforce": _salesforce_source,
        "hubspot": _hubspot_source,
        "shopify": _shopify_source,
        "stripe": _stripe_source,
        "zendesk": _zendesk_source,
        "github": _github_source,
        "notion": _notion_source,
        "slack": _slack_source,
        "airtable": _airtable_source,
        "google_analytics": _google_analytics_source,
        "google_ads": _google_ads_source,
        "facebook_ads": _facebook_ads_source,
        "jira": _jira_source,
        "asana": _asana_source,
        "pipedrive": _pipedrive_source,
        "freshdesk": _freshdesk_source,
        "mixpanel": _mixpanel_source,
        "mongodb": _mongodb_source,
        # ── Database sources ───────────────────────────────────────────
        "postgresql": _postgres_source,
        "snowflake": _snowflake_source,
        # ── REST API configured sources ───────────────────────────────
        "linkedin_ads": _linkedin_ads_source,
        "mailchimp": _mailchimp_source,
        "gitlab": _gitlab_source,
        "monday": _monday_source,
        "trello": _trello_source,
        "confluence": _confluence_source,
        "intercom": _intercom_source,
        "woocommerce": _woocommerce_source,
        "klaviyo": _klaviyo_source,
        "marketo": _marketo_source,
        "zoho_crm": _zoho_crm_source,
        "xero": _xero_source,
        "quickbooks": _quickbooks_source,
        "amplitude": _amplitude_source,
        "heap": _heap_source,
        "linear": _linear_source,
        # ── Generic REST API (catch-all for any HTTP API) ──────────────
        "rest_api": _make_rest_source,
    }


def list_available_sources() -> list[dict[str, str]]:
    """
    Return a list of available source types with metadata.

    Used by the API to populate the frontend connector catalog.
    """
    registry = get_source_registry()
    return [
        {
            "id": key,
            "name": _source_display_name(key),
            "type": "saas_api",
            "verified": _is_verified_source(key),
        }
        for key in sorted(registry.keys())
    ]


def _source_display_name(source_type: str) -> str:
    """Convert a source_type key to a human-readable display name."""
    names = {
        "salesforce": "Salesforce",
        "hubspot": "HubSpot",
        "shopify": "Shopify",
        "stripe": "Stripe",
        "zendesk": "Zendesk",
        "github": "GitHub",
        "notion": "Notion",
        "slack": "Slack",
        "airtable": "Airtable",
        "google_analytics": "Google Analytics 4",
        "google_ads": "Google Ads",
        "facebook_ads": "Facebook / Meta Ads",
        "jira": "Jira",
        "asana": "Asana",
        "pipedrive": "Pipedrive",
        "freshdesk": "Freshdesk",
        "mixpanel": "Mixpanel",
        "mongodb": "MongoDB",
        "postgresql": "PostgreSQL",
        "snowflake": "Snowflake",
        "linkedin_ads": "LinkedIn Ads",
        "mailchimp": "Mailchimp",
        "gitlab": "GitLab",
        "monday": "Monday.com",
        "trello": "Trello",
        "confluence": "Confluence",
        "intercom": "Intercom",
        "woocommerce": "WooCommerce",
        "klaviyo": "Klaviyo",
        "marketo": "Marketo",
        "zoho_crm": "Zoho CRM",
        "xero": "Xero",
        "quickbooks": "QuickBooks",
        "amplitude": "Amplitude",
        "heap": "Heap",
        "linear": "Linear",
    }
    return names.get(
        source_type,
        source_type.replace("_", " ").title(),
    )


def _is_verified_source(source_type: str) -> bool:
    """Return True if the source has a dedicated dlt verified source."""
    verified_keys = {
        "salesforce",
        "hubspot",
        "shopify",
        "stripe",
        "zendesk",
        "github",
        "notion",
        "slack",
        "airtable",
        "google_analytics",
        "google_ads",
        "facebook_ads",
        "jira",
        "asana",
        "pipedrive",
        "freshdesk",
        "mixpanel",
        "mongodb",
        "postgresql",
        "snowflake",
    }
    return source_type in verified_keys
