import random
import time
from pathlib import Path
from shutil import copy2
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.config import Settings, get_settings
from app.models import AutoCampaignCreate, Campaign, CampaignAsset, CampaignCreate, PolishNarrationRequest
from app.services.campaign_store import campaign_store
from app.services.pure_green_marketing import (
    analyze_campaign_assets,
    asset_type,
    inspect_media_dimensions,
    generate_campaign_brief,
    generate_narration,
    polish_campaign_narration,
    generate_social_caption,
    generate_storyboard,
    render_manifest,
    run_compliance,
    save_upload,
    select_campaign_music,
)
from app.services.storage import LocalStorage

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".m4v"}
MUSIC_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".webm"}
MAX_AUTO_VISUAL_ASSETS = 18
MAX_AUTO_AUDIO_FILES = 40
AUTO_CONTEXT_PICK_SECONDS = 8
AUTO_RANDOM_FALLBACK_VISUAL_COUNT = 80


@router.get("")
def list_campaigns():
    return campaign_store.list()


@router.post("")
def create_campaign(payload: CampaignCreate):
    return campaign_store.create(payload)


@router.post("/polish-narration")
def polish_narration(payload: PolishNarrationRequest, settings: Settings = Depends(get_settings)):
    try:
        return polish_campaign_narration(payload, settings)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/auto-folder")
def create_auto_campaign(payload: AutoCampaignCreate, settings: Settings = Depends(get_settings)):
    folder = _resolve_auto_folder(payload.folderPath, settings)
    campaign = campaign_store.create(CampaignCreate(**payload.model_dump(exclude={"folderPath"})))
    imported_assets = _import_folder_media(campaign, folder, settings)
    if not imported_assets:
        raise HTTPException(
            status_code=400,
            detail=f"No supported photos or videos found in {folder}. Add JPG, PNG, WEBP, MP4, MOV, or WEBM files.",
        )

    campaign = campaign_store.update(campaign, assets=imported_assets)
    campaign = analyze_campaign_assets(campaign)
    campaign = campaign_store.update(campaign, status="analyzing", assets=campaign.assets, format=campaign.format)
    brief = generate_campaign_brief(campaign)
    storyboard = generate_storyboard(campaign, brief)
    social = generate_social_caption(campaign, storyboard)
    music_track = select_campaign_music(campaign, storyboard)
    compliance_result = run_compliance(storyboard.voiceoverScript, [caption.text for caption in storyboard.captions])
    campaign = campaign_store.update(
        campaign,
        status="script_ready",
        brief=brief,
        storyboard=storyboard,
        musicTrack=music_track,
        compliance=compliance_result,
        socialCaption=social,
    )
    narration_url = generate_narration(campaign, settings, LocalStorage(settings))
    campaign = campaign_store.update(campaign, narrationUrl=narration_url)
    render_url = render_manifest(campaign, settings)
    return campaign_store.update(campaign, status="complete", renderUrl=render_url)


@router.get("/{campaign_id}")
def get_campaign(campaign_id: str):
    try:
        return campaign_store.require(campaign_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Campaign not found") from exc


@router.post("/{campaign_id}/assets")
async def upload_assets(
    campaign_id: str,
    files: list[UploadFile] = File(...),
    settings: Settings = Depends(get_settings),
):
    try:
        campaign_store.require(campaign_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Campaign not found") from exc

    campaign = None
    for upload in files:
        content = await upload.read()
        url = save_upload(settings, campaign_id, upload.filename or "asset", content)
        width, height, orientation, format_fit = inspect_media_dimensions(settings, url)
        from datetime import datetime, timezone
        from uuid import uuid4

        asset = CampaignAsset(
            id=str(uuid4()),
            campaignId=campaign_id,
            type=asset_type(upload.filename or "", upload.content_type),
            url=url,
            filename=upload.filename or "asset",
            width=width,
            height=height,
            orientation=orientation,
            formatFit=format_fit,
            createdAt=datetime.now(timezone.utc).isoformat(),
        )
        campaign = campaign_store.add_asset(campaign_id, asset)
    return campaign or campaign_store.require(campaign_id)


@router.post("/{campaign_id}/folder-assets")
def add_folder_assets(
    campaign_id: str,
    payload: AutoCampaignCreate,
    settings: Settings = Depends(get_settings),
):
    campaign = _campaign_or_404(campaign_id)
    folder = _resolve_auto_folder(payload.folderPath, settings)
    imported_assets = _import_folder_media(campaign, folder, settings)
    if not imported_assets:
        return campaign

    existing_names = {asset.filename for asset in campaign.assets}
    supplemental = [asset for asset in imported_assets if asset.filename not in existing_names]
    remaining_slots = max(0, MAX_AUTO_VISUAL_ASSETS - len(campaign.assets))
    assets = [*campaign.assets, *supplemental[:remaining_slots]]
    return campaign_store.update(campaign, assets=assets)


@router.post("/{campaign_id}/analyze")
def analyze_assets(campaign_id: str):
    campaign = _campaign_or_404(campaign_id)
    updated = analyze_campaign_assets(campaign)
    return campaign_store.update(updated, status="analyzing", assets=updated.assets)


@router.post("/{campaign_id}/storyboard")
def create_storyboard(campaign_id: str):
    campaign = _campaign_or_404(campaign_id)
    brief = generate_campaign_brief(campaign)
    storyboard = generate_storyboard(campaign, brief)
    social = generate_social_caption(campaign, storyboard)
    music_track = select_campaign_music(campaign, storyboard)
    return campaign_store.update(
        campaign,
        status="script_ready",
        brief=brief,
        storyboard=storyboard,
        musicTrack=music_track,
        compliance=run_compliance(storyboard.voiceoverScript, [caption.text for caption in storyboard.captions]),
        socialCaption=social,
    )


@router.post("/{campaign_id}/compliance")
def compliance(campaign_id: str):
    campaign = _campaign_or_404(campaign_id)
    if not campaign.storyboard:
        raise HTTPException(status_code=400, detail="Generate a storyboard before compliance review")
    result = run_compliance(campaign.storyboard.voiceoverScript, [caption.text for caption in campaign.storyboard.captions])
    storyboard = campaign.storyboard.model_copy(update={"voiceoverScript": result.rewrittenScript})
    return campaign_store.update(campaign, storyboard=storyboard, compliance=result)


@router.post("/{campaign_id}/narration")
def narration(campaign_id: str, settings: Settings = Depends(get_settings)):
    campaign = _campaign_or_404(campaign_id)
    if not campaign.storyboard:
        raise HTTPException(status_code=400, detail="Generate a storyboard before narration")
    url = generate_narration(campaign, settings, LocalStorage(settings))
    return campaign_store.update(campaign, narrationUrl=url)


@router.post("/{campaign_id}/render")
def render(campaign_id: str, settings: Settings = Depends(get_settings)):
    campaign = _campaign_or_404(campaign_id)
    if not campaign.storyboard:
        raise HTTPException(status_code=400, detail="Generate a storyboard before rendering")
    url = render_manifest(campaign, settings)
    return campaign_store.update(campaign, status="complete", renderUrl=url)


@router.get("/{campaign_id}/download")
def download(campaign_id: str, settings: Settings = Depends(get_settings)):
    campaign = _campaign_or_404(campaign_id)
    if not campaign.renderUrl:
        raise HTTPException(status_code=404, detail="Render is not ready")
    path = settings.media_root / campaign.renderUrl.replace("/media/", "", 1)
    return FileResponse(
        path,
        media_type="text/html",
        filename=f"{campaign.name.replace(' ', '-').lower()}-preview.html",
        content_disposition_type="inline",
    )


def _campaign_or_404(campaign_id: str):
    try:
        return campaign_store.require(campaign_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Campaign not found") from exc


def _resolve_auto_folder(folder_path: str | None, settings: Settings) -> Path:
    folder = Path(folder_path).expanduser() if folder_path else settings.auto_campaign_folder
    if not folder.is_absolute():
        folder = Path.cwd() / folder
    if not folder.exists() or not folder.is_dir():
        raise HTTPException(status_code=400, detail=f"Folder not found: {folder}")
    return folder


def _import_folder_media(campaign: Campaign, folder: Path, settings: Settings) -> list[CampaignAsset]:
    started = time.monotonic()
    files = _scan_auto_folder(folder)
    for path in files["audio"][:MAX_AUTO_AUDIO_FILES]:
        _copy_music_file(path, settings)

    if len(files["visual"]) > AUTO_RANDOM_FALLBACK_VISUAL_COUNT or time.monotonic() - started > AUTO_CONTEXT_PICK_SECONDS:
        selected_paths = _random_visual_selection(files["visual"], campaign.id)
        return [_copy_visual_asset(campaign.id, path, settings) for path in selected_paths]

    scored_visuals = sorted(
        ((_context_score(path, campaign, folder), path) for path in files["visual"]),
        key=lambda item: (item[0], item[1].name.lower()),
        reverse=True,
    )
    if time.monotonic() - started > AUTO_CONTEXT_PICK_SECONDS:
        selected_paths = _random_visual_selection(files["visual"], campaign.id)
        return [_copy_visual_asset(campaign.id, path, settings) for path in selected_paths]

    selected_paths = _balanced_visual_selection(scored_visuals)
    return [_copy_visual_asset(campaign.id, path, settings) for path in selected_paths]


def _scan_auto_folder(folder: Path) -> dict[str, list[Path]]:
    files: dict[str, list[Path]] = {"audio": [], "visual": []}
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        if any(part.startswith(".") for part in path.relative_to(folder).parts):
            continue

        suffix = path.suffix.lower()
        parts = {part.lower() for part in path.relative_to(folder).parts[:-1]}
        if suffix in MUSIC_EXTENSIONS and ("audio" in parts or suffix != ".webm"):
            files["audio"].append(path)
        elif suffix in IMAGE_EXTENSIONS or suffix in VIDEO_EXTENSIONS:
            files["visual"].append(path)
    return files


def _balanced_visual_selection(scored_visuals: list[tuple[int, Path]]) -> list[Path]:
    if not scored_visuals:
        return []

    videos = [(score, path) for score, path in scored_visuals if path.suffix.lower() in VIDEO_EXTENSIONS]
    images = [(score, path) for score, path in scored_visuals if path.suffix.lower() in IMAGE_EXTENSIONS]
    chosen: list[tuple[int, Path]] = []

    # A sticky short-form campaign benefits from motion, but still needs clean
    # product and CTA photos. Keep both pools represented when available.
    chosen.extend(videos[:8])
    chosen.extend(images[:10])

    if videos and not any(path.suffix.lower() in VIDEO_EXTENSIONS for _, path in chosen):
        chosen.append(videos[0])
    if images and not any(path.suffix.lower() in IMAGE_EXTENSIONS for _, path in chosen):
        chosen.append(images[0])

    deduped: dict[Path, int] = {}
    for score, path in chosen:
        deduped[path] = max(score, deduped.get(path, score))

    for score, path in scored_visuals:
        if len(deduped) >= MAX_AUTO_VISUAL_ASSETS:
            break
        deduped.setdefault(path, score)

    return [path for path, _ in sorted(deduped.items(), key=lambda item: (item[1], item[0].name.lower()), reverse=True)]


def _random_visual_selection(paths: list[Path], seed: str) -> list[Path]:
    if not paths:
        return []
    rng = random.Random(seed)
    videos = [path for path in paths if path.suffix.lower() in VIDEO_EXTENSIONS]
    images = [path for path in paths if path.suffix.lower() in IMAGE_EXTENSIONS]
    rng.shuffle(videos)
    rng.shuffle(images)

    chosen: list[Path] = []
    chosen.extend(videos[:8])
    chosen.extend(images[:10])
    if videos and not any(path.suffix.lower() in VIDEO_EXTENSIONS for path in chosen):
        chosen.append(videos[0])
    if images and not any(path.suffix.lower() in IMAGE_EXTENSIONS for path in chosen):
        chosen.append(images[0])

    remaining = [path for path in [*videos, *images] if path not in chosen]
    chosen.extend(remaining[: max(0, MAX_AUTO_VISUAL_ASSETS - len(chosen))])
    return chosen[:MAX_AUTO_VISUAL_ASSETS]


def _copy_visual_asset(campaign_id: str, path: Path, settings: Settings) -> CampaignAsset:
    from datetime import datetime, timezone

    suffix = path.suffix.lower()
    upload_name = f"{campaign_id}-{uuid4()}{suffix}"
    target = settings.media_root / "uploads" / upload_name
    copy2(path, target)
    url = f"/media/uploads/{upload_name}"
    width, height, orientation, format_fit = inspect_media_dimensions(settings, url)
    return CampaignAsset(
        id=str(uuid4()),
        campaignId=campaign_id,
        type="video" if suffix in VIDEO_EXTENSIONS else "image",
        url=url,
        filename=path.name,
        width=width,
        height=height,
        orientation=orientation,
        formatFit=format_fit,
        createdAt=datetime.now(timezone.utc).isoformat(),
    )


def _context_score(path: Path, campaign: Campaign, folder: Path) -> int:
    relative = path.relative_to(folder)
    text = _normalize_path_text(relative)
    suffix = path.suffix.lower()
    score = 0

    if suffix in VIDEO_EXTENSIONS:
        score += 18
    if suffix in IMAGE_EXTENSIONS:
        score += 8

    parts = {part.lower() for part in relative.parts[:-1]}
    if "audio" in parts:
        score -= 100
    if "photos" in parts and suffix in IMAGE_EXTENSIONS:
        score += 18
    if {"video", "videos"} & parts and suffix in VIDEO_EXTENSIONS:
        score += 18

    for token, weight in _campaign_context_terms(campaign).items():
        if token in text:
            score += weight

    product_terms = ["smoothie", "acai", "açaí", "bowl", "juice", "fruit", "green", "greens", "vegetable", "superfood", "drink", "blender", "pour"]
    lifestyle_terms = ["workout", "gym", "runner", "running", "yoga", "pilates", "hike", "tennis", "athlete", "fitness", "stretch"]
    local_terms = ["local", "store", "storefront", "interior", "neighborhood", "cafe", "shop", "street"]
    cta_terms = ["cta", "lineup", "preview", "end", "hero"]
    negative_terms = ["trash", "dirty", "blurry", "dark", "competitor", "logo", "test", "draft", "bad"]

    score += sum(10 for term in product_terms if term in text)
    score += sum(8 for term in lifestyle_terms if term in text)
    score += sum(7 for term in local_terms if term in text)
    score += sum(5 for term in cta_terms if term in text)
    score -= sum(24 for term in negative_terms if term in text)

    if campaign.tone == "energetic" and any(term in text for term in ["energy", "workout", "gym", "running", "dance", "cardio"]):
        score += 14
    if campaign.tone in {"calm", "premium", "educational"} and any(term in text for term in ["yoga", "pilates", "walk", "interior", "calm", "premium"]):
        score += 12

    return score


def _campaign_context_terms(campaign: Campaign) -> dict[str, int]:
    terms: dict[str, int] = {
        "pure": 8,
        "green": 8,
        "wellness": 8,
        "healthy": 6,
        "fresh": 6,
        "clean": 5,
        "local": 5,
    }

    for value in [campaign.businessName, campaign.locationName, campaign.neighborhood, campaign.goal, campaign.cta, campaign.musicStyle]:
        for token in _tokenize(value or ""):
            terms[token] = max(terms.get(token, 0), 6)

    audience_terms = {
        "gym_goers": ["gym", "workout", "fitness", "post-workout", "athlete"],
        "runners": ["run", "runner", "running", "race", "cardio"],
        "yoga_pilates": ["yoga", "pilates", "studio", "stretch"],
        "crossfit": ["crossfit", "gym", "training", "workout"],
        "tennis": ["tennis", "court", "active"],
        "hikers": ["hike", "hiker", "trail", "outdoor", "nature"],
        "middle_aged_wellness": ["walk", "wellness", "routine", "active", "adult"],
        "seniors": ["senior", "elderly", "walk", "wellness"],
        "families": ["family", "kids", "community", "local"],
    }
    product_terms = {
        "smoothies": ["smoothie", "shake", "blender", "drink"],
        "acai_bowls": ["acai", "açaí", "bowl", "berry", "blueberry"],
        "cold_pressed_juices": ["juice", "pressed", "citrus", "drink"],
        "fruits": ["fruit", "banana", "berry", "citrus"],
        "vegetables": ["vegetable", "greens", "green"],
        "superfoods": ["superfood", "chia", "protein", "greens"],
        "low_sugar": ["low", "sugar", "clean", "better"],
    }

    for audience in campaign.targetAudience:
        for token in audience_terms.get(audience, _tokenize(audience)):
            terms[token] = max(terms.get(token, 0), 12)
    for focus in campaign.productFocus:
        for token in product_terms.get(focus, _tokenize(focus)):
            terms[token] = max(terms.get(token, 0), 14)

    return terms


def _normalize_path_text(path: Path) -> str:
    return " ".join(_tokenize(" ".join(path.parts)))


def _tokenize(value: str) -> list[str]:
    normalized = value.lower().replace("_", " ").replace("-", " ").replace("/", " ")
    return [token.strip(".,:;()[]{}'\"") for token in normalized.split() if len(token.strip(".,:;()[]{}'\"")) >= 3]


def _copy_music_file(path: Path, settings: Settings) -> None:
    target = settings.media_root / "music" / path.name
    if target.resolve() == path.resolve():
        return
    copy2(path, target)
