"""Shared enums and types for Meta Ads MCP."""

from __future__ import annotations

from enum import Enum


META_API_VERSION = "v23.0"
META_GRAPH_URL = f"https://graph.facebook.com/{META_API_VERSION}"


class CampaignObjective(str, Enum):
    """Meta campaign objectives."""
    OUTCOME_AWARENESS = "OUTCOME_AWARENESS"
    OUTCOME_ENGAGEMENT = "OUTCOME_ENGAGEMENT"
    OUTCOME_LEADS = "OUTCOME_LEADS"
    OUTCOME_SALES = "OUTCOME_SALES"
    OUTCOME_TRAFFIC = "OUTCOME_TRAFFIC"
    OUTCOME_APP_PROMOTION = "OUTCOME_APP_PROMOTION"


class CampaignStatus(str, Enum):
    """Campaign / Ad Set / Ad status."""
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    DELETED = "DELETED"
    ARCHIVED = "ARCHIVED"


class EffectiveStatus(str, Enum):
    """Effective status (read-only, computed by Meta)."""
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    DELETED = "DELETED"
    ARCHIVED = "ARCHIVED"
    IN_PROCESS = "IN_PROCESS"
    WITH_ISSUES = "WITH_ISSUES"
    PENDING_REVIEW = "PENDING_REVIEW"
    DISAPPROVED = "DISAPPROVED"
    PREAPPROVED = "PREAPPROVED"
    PENDING_BILLING_INFO = "PENDING_BILLING_INFO"
    CAMPAIGN_PAUSED = "CAMPAIGN_PAUSED"
    ADSET_PAUSED = "ADSET_PAUSED"


class OptimizationGoal(str, Enum):
    """Ad set optimization goals."""
    NONE = "NONE"
    APP_INSTALLS = "APP_INSTALLS"
    AD_RECALL_LIFT = "AD_RECALL_LIFT"
    ENGAGED_USERS = "ENGAGED_USERS"
    EVENT_RESPONSES = "EVENT_RESPONSES"
    IMPRESSIONS = "IMPRESSIONS"
    LEAD_GENERATION = "LEAD_GENERATION"
    QUALITY_LEAD = "QUALITY_LEAD"
    LINK_CLICKS = "LINK_CLICKS"
    OFFSITE_CONVERSIONS = "OFFSITE_CONVERSIONS"
    PAGE_LIKES = "PAGE_LIKES"
    POST_ENGAGEMENT = "POST_ENGAGEMENT"
    QUALITY_CALL = "QUALITY_CALL"
    REACH = "REACH"
    LANDING_PAGE_VIEWS = "LANDING_PAGE_VIEWS"
    VISIT_INSTAGRAM_PROFILE = "VISIT_INSTAGRAM_PROFILE"
    VALUE = "VALUE"
    THRUPLAY = "THRUPLAY"
    DERIVED_EVENTS = "DERIVED_EVENTS"
    CONVERSATIONS = "CONVERSATIONS"


class BillingEvent(str, Enum):
    """Ad set billing events."""
    APP_INSTALLS = "APP_INSTALLS"
    CLICKS = "CLICKS"
    IMPRESSIONS = "IMPRESSIONS"
    LINK_CLICKS = "LINK_CLICKS"
    NONE = "NONE"
    OFFER_CLAIMS = "OFFER_CLAIMS"
    PAGE_LIKES = "PAGE_LIKES"
    POST_ENGAGEMENT = "POST_ENGAGEMENT"
    THRUPLAY = "THRUPLAY"
    LISTING_INTERACTION = "LISTING_INTERACTION"


class BidStrategy(str, Enum):
    """Campaign bid strategies."""
    LOWEST_COST_WITHOUT_CAP = "LOWEST_COST_WITHOUT_CAP"
    LOWEST_COST_WITH_BID_CAP = "LOWEST_COST_WITH_BID_CAP"
    COST_CAP = "COST_CAP"
    LOWEST_COST_WITH_MIN_ROAS = "LOWEST_COST_WITH_MIN_ROAS"


class DatePreset(str, Enum):
    """Insights date presets."""
    TODAY = "today"
    YESTERDAY = "yesterday"
    THIS_MONTH = "this_month"
    LAST_MONTH = "last_month"
    THIS_QUARTER = "this_quarter"
    LAST_QUARTER = "last_quarter"
    THIS_WEEK_SUN_TODAY = "this_week_sun_today"
    THIS_WEEK_MON_TODAY = "this_week_mon_today"
    LAST_WEEK_SUN_SAT = "last_week_sun_sat"
    LAST_WEEK_MON_SUN = "last_week_mon_sun"
    THIS_YEAR = "this_year"
    LAST_YEAR = "last_year"
    LAST_3D = "last_3d"
    LAST_7D = "last_7d"
    LAST_14D = "last_14d"
    LAST_28D = "last_28d"
    LAST_30D = "last_30d"
    LAST_90D = "last_90d"
    MAXIMUM = "maximum"


class InsightsLevel(str, Enum):
    """Insights aggregation level."""
    ACCOUNT = "account"
    CAMPAIGN = "campaign"
    ADSET = "adset"
    AD = "ad"


class AudienceSubtype(str, Enum):
    """Custom audience subtypes."""
    CUSTOM = "CUSTOM"
    WEBSITE = "WEBSITE"
    APP = "APP"
    OFFLINE = "OFFLINE"
    CLAIM = "CLAIM"
    PARTNER = "PARTNER"
    MANAGED = "MANAGED"
    VIDEO = "VIDEO"
    LOOKALIKE = "LOOKALIKE"
    ENGAGEMENT = "ENGAGEMENT"


class InsightsBreakdown(str, Enum):
    """Available breakdowns for insights."""
    AGE = "age"
    GENDER = "gender"
    COUNTRY = "country"
    REGION = "region"
    PLACEMENT = "publisher_platform"
    DEVICE = "device_platform"
    IMPRESSION_DEVICE = "impression_device"


# Default fields for insights queries
DEFAULT_INSIGHTS_FIELDS = [
    "account_currency",
    "impressions",
    "clicks",
    "spend",
    "ctr",
    "cpc",
    "cpm",
    "reach",
    "frequency",
    "actions",
    "cost_per_action_type",
    "conversions",
    "cost_per_conversion",
]

# Default fields when fetching campaigns
DEFAULT_CAMPAIGN_FIELDS = [
    "id",
    "name",
    "objective",
    "status",
    "effective_status",
    "daily_budget",
    "lifetime_budget",
    "budget_remaining",
    "start_time",
    "stop_time",
    "created_time",
    "updated_time",
    "bid_strategy",
    "special_ad_categories",
]

# Default fields for ad sets
DEFAULT_ADSET_FIELDS = [
    "id",
    "name",
    "campaign_id",
    "status",
    "effective_status",
    "daily_budget",
    "lifetime_budget",
    "budget_remaining",
    "optimization_goal",
    "billing_event",
    "bid_amount",
    "start_time",
    "end_time",
    "targeting",
    "created_time",
]

# Default fields for ads
DEFAULT_AD_FIELDS = [
    "id",
    "name",
    "adset_id",
    "campaign_id",
    "status",
    "effective_status",
    "created_time",
    "updated_time",
    "creative",
]

# Default fields for creatives
DEFAULT_CREATIVE_FIELDS = [
    "id",
    "name",
    "title",
    "body",
    "image_url",
    "video_id",
    "call_to_action_type",
    "object_story_spec",
    "thumbnail_url",
    "status",
]

# Default fields for audiences
DEFAULT_AUDIENCE_FIELDS = [
    "id",
    "name",
    "subtype",
    "description",
    "approximate_count_lower_bound",
    "approximate_count_upper_bound",
    "operation_status",
    "delivery_status",
    "retention_days",
    "time_created",
    "time_updated",
]
