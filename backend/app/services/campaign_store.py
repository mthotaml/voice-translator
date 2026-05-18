from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.models import Campaign, CampaignAsset, CampaignCreate


DEFAULT_GOAL = (
    "Create a compelling hyperlocal wellness video that promotes health and well-being "
    "through natural, nutrient-rich food and drinks such as smoothies, acai bowls, fruits, "
    "vegetables, cold-pressed juices, and superfoods. Emphasize active lifestyles, "
    "post-workout refueling, clean nutrition choices, and daily wellness without making "
    "unsupported medical claims."
)


class CampaignStore:
    def __init__(self):
        self._campaigns: dict[str, Campaign] = {}
        self._path = Path("data/pure_green_campaigns.json")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def create(self, payload: CampaignCreate) -> Campaign:
        now = _now()
        campaign_id = str(uuid4())
        location = payload.neighborhood or payload.locationName or "local market"
        campaign = Campaign(
            id=campaign_id,
            name=f"{payload.businessName} {location} wellness video",
            businessName=payload.businessName,
            locationName=payload.locationName,
            neighborhood=payload.neighborhood,
            goal=payload.goal or DEFAULT_GOAL,
            targetAudience=payload.targetAudience,
            videoLengthSeconds=payload.videoLengthSeconds,
            format=payload.format,
            tone=payload.tone,
            productFocus=payload.productFocus,
            cta=payload.cta,
            musicStyle=payload.musicStyle,
            voiceId=payload.voiceId,
            narrationScript=payload.narrationScript,
            createdAt=now,
            updatedAt=now,
        )
        self._campaigns[campaign_id] = campaign
        self._save()
        return campaign

    def list(self) -> list[Campaign]:
        return sorted(self._campaigns.values(), key=lambda item: item.createdAt, reverse=True)

    def get(self, campaign_id: str) -> Campaign | None:
        return self._campaigns.get(campaign_id)

    def require(self, campaign_id: str) -> Campaign:
        campaign = self.get(campaign_id)
        if not campaign:
            raise KeyError(campaign_id)
        return campaign

    def update(self, campaign: Campaign, **changes) -> Campaign:
        updated = campaign.model_copy(update={**changes, "updatedAt": _now()})
        self._campaigns[campaign.id] = updated
        self._save()
        return updated

    def add_asset(self, campaign_id: str, asset: CampaignAsset) -> Campaign:
        campaign = self.require(campaign_id)
        assets = [*campaign.assets, asset]
        return self.update(campaign, assets=assets)

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            import json

            payload = json.loads(self._path.read_text(encoding="utf-8"))
            self._campaigns = {item["id"]: Campaign.model_validate(item) for item in payload}
        except Exception:
            self._campaigns = {}

    def _save(self) -> None:
        self._path.write_text(
            "[" + ",".join(campaign.model_dump_json() for campaign in self._campaigns.values()) + "]",
            encoding="utf-8",
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


campaign_store = CampaignStore()
