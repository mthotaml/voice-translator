import json

from app.config import Settings
from app.models import Campaign, MusicTrack


def list_music_tracks(settings: Settings) -> list[MusicTrack]:
    _ensure_catalog(settings)
    try:
        payload = json.loads(settings.music_catalog_path.read_text(encoding="utf-8"))
    except Exception:
        payload = []
    catalog_tracks = [MusicTrack.model_validate(item) for item in payload]
    discovered_tracks = _discover_music_files(settings, {track.file for track in catalog_tracks})
    return [*catalog_tracks, *discovered_tracks]


def select_music_track(campaign: Campaign, settings: Settings, energy: str) -> MusicTrack | None:
    tracks = list_music_tracks(settings)
    if not tracks:
        return None

    theme = infer_campaign_theme(campaign, energy)
    signals = _campaign_music_signals(campaign, theme, energy)
    desired = theme["energy"]

    def score(track: MusicTrack) -> int:
        value = 0
        mood_text = " ".join(track.mood).lower()
        search_text = f"{track.id} {track.title} {track.energy} {mood_text}".lower()

        if track.energy == desired:
            value += 36
        if track.energy == energy:
            value += 18

        value += _weighted_token_score(search_text, signals["primary"], 10)
        value += _weighted_token_score(search_text, signals["secondary"], 5)
        value += _weighted_token_score(search_text, signals["avoid"], -12)

        if track.bpm:
            value += _bpm_fit_score(track.bpm, theme["bpm_min"], theme["bpm_max"])

        if _file_exists(settings, track.file):
            value += 30
        else:
            # Missing files can still be selected for planning, but existing licensed
            # files should win when otherwise close.
            value -= 40
        return value

    selected = max(tracks, key=score)
    return selected.model_copy(
        update={
            "matchTheme": theme["label"],
            "matchReason": _match_reason(selected, theme, energy, settings),
        }
    )


def infer_campaign_theme(campaign: Campaign, energy: str) -> dict:
    text = _campaign_text(campaign)

    theme_defs = [
        {
            "id": "post_workout_refuel",
            "label": "Post-workout refuel",
            "energy": "high",
            "bpm_min": 108,
            "bpm_max": 128,
            "keywords": ["gym", "runner", "runners", "run", "crossfit", "tennis", "workout", "fitness", "post", "movement", "refuel"],
            "primary": ["fitness", "upbeat", "post-workout", "movement", "gym", "running", "high-energy"],
            "secondary": ["electronic", "pop", "confident", "bright"],
            "avoid": ["sleep", "sad", "dark", "ambient-only"],
        },
        {
            "id": "local_wellness_routine",
            "label": "Local wellness routine",
            "energy": "balanced",
            "bpm_min": 92,
            "bpm_max": 112,
            "keywords": ["local", "community", "family", "routine", "wellness", "daily", "neighborhood", "professionals"],
            "primary": ["community", "friendly", "local", "wellness", "warm"],
            "secondary": ["acoustic", "pop", "optimistic", "natural"],
            "avoid": ["aggressive", "hard", "dark"],
        },
        {
            "id": "better_smoothie_choice",
            "label": "Better smoothie choice",
            "energy": "balanced",
            "bpm_min": 96,
            "bpm_max": 116,
            "keywords": ["smoothie", "smoothies", "juice", "acai", "bowl", "fruit", "vegetables", "superfoods", "low_sugar", "product"],
            "primary": ["fresh", "upbeat", "wellness", "friendly", "clean"],
            "secondary": ["pop", "light", "bright"],
            "avoid": ["heavy", "industrial", "dark"],
        },
        {
            "id": "calm_premium_wellness",
            "label": "Calm premium wellness",
            "energy": "calm",
            "bpm_min": 76,
            "bpm_max": 98,
            "keywords": ["yoga", "pilates", "senior", "seniors", "calm", "premium", "educational", "inspirational", "walk"],
            "primary": ["wellness", "premium", "yoga", "pilates", "restorative", "calm"],
            "secondary": ["warm", "soft", "organic"],
            "avoid": ["aggressive", "hard", "high-energy"],
        },
    ]

    best = max(theme_defs, key=lambda theme: sum(token in text for token in theme["keywords"]))
    if sum(token in text for token in best["keywords"]) == 0:
        if energy == "high" or campaign.tone == "energetic":
            best = theme_defs[0]
        elif energy == "calm" or campaign.tone in {"calm", "premium", "educational"}:
            best = theme_defs[3]
        else:
            best = theme_defs[1]
    return best


def _campaign_music_signals(campaign: Campaign, theme: dict, energy: str) -> dict[str, list[str]]:
    text_tokens = _campaign_text(campaign).replace("_", " ").split()
    product_tokens = [item.replace("_", " ") for item in campaign.productFocus]
    audience_tokens = [item.replace("_", " ") for item in campaign.targetAudience]
    asset_tokens = []
    for asset in campaign.assets:
        asset_tokens.extend(asset.filename.lower().replace("_", " ").replace("-", " ").split())
        if asset.analysis:
            asset_tokens.extend(asset.analysis.fitnessSignals)
            asset_tokens.extend(asset.analysis.wellnessSignals)
            asset_tokens.extend(asset.analysis.detectedFoods)
            asset_tokens.append(asset.analysis.recommendedUse)

    primary = [*theme["primary"], energy, campaign.tone, *audience_tokens]
    secondary = [*theme["secondary"], *product_tokens, *asset_tokens, *text_tokens]
    return {"primary": primary, "secondary": secondary, "avoid": theme["avoid"]}


def _campaign_text(campaign: Campaign) -> str:
    parts = [
        campaign.tone,
        campaign.musicStyle,
        campaign.goal or "",
        campaign.cta or "",
        " ".join(campaign.targetAudience),
        " ".join(campaign.productFocus),
        " ".join(asset.filename for asset in campaign.assets),
    ]
    return " ".join(parts).lower()


def _weighted_token_score(text: str, tokens: list[str], weight: int) -> int:
    total = 0
    for token in tokens:
        normalized = str(token).lower().replace("_", " ").strip()
        if normalized and normalized in text:
            total += weight
    return total


def _bpm_fit_score(bpm: int, bpm_min: int, bpm_max: int) -> int:
    if bpm_min <= bpm <= bpm_max:
        return 16
    distance = min(abs(bpm - bpm_min), abs(bpm - bpm_max))
    if distance <= 8:
        return 8
    if distance <= 16:
        return 2
    return -6


def _match_reason(track: MusicTrack, theme: dict, energy: str, settings: Settings) -> str:
    parts = [f"Matched {theme['label']} theme", f"{track.energy} energy"]
    if track.bpm:
        parts.append(f"{track.bpm} BPM target fit {theme['bpm_min']}-{theme['bpm_max']}")
    if _file_exists(settings, track.file):
        parts.append("licensed file found locally")
    else:
        parts.append("metadata match; add the file locally to use the track")
    if energy != track.energy:
        parts.append(f"campaign energy inferred as {energy}")
    return "; ".join(parts) + "."


def _ensure_catalog(settings: Settings) -> None:
    if settings.music_catalog_path.exists():
        return
    settings.music_catalog_path.parent.mkdir(parents=True, exist_ok=True)
    settings.music_catalog_path.write_text("[]", encoding="utf-8")


def _file_exists(settings: Settings, file_url: str) -> bool:
    prefix = "/media/"
    if not file_url.startswith(prefix):
        return False
    return (settings.media_root / file_url.removeprefix(prefix)).exists()


def _discover_music_files(settings: Settings, catalog_files: set[str]) -> list[MusicTrack]:
    music_dir = settings.media_root / "music"
    tracks: list[MusicTrack] = []
    for path in sorted(music_dir.glob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        if path.suffix.lower() not in {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".webm"}:
            continue
        file_url = f"/media/music/{path.name}"
        if file_url in catalog_files:
            continue
        tracks.append(_track_from_file(path.name, file_url))
    return tracks


def _track_from_file(filename: str, file_url: str) -> MusicTrack:
    stem = filename.rsplit(".", 1)[0]
    clean = stem.replace("mixkit-", "").replace("-", " ").replace("_", " ")
    text = clean.lower()
    energy = _infer_energy(text)
    bpm = _infer_bpm(text, energy)
    mood = _infer_moods(text, energy)
    return MusicTrack(
        id=stem.lower().replace(" ", "_").replace("-", "_"),
        title=clean.title(),
        file=file_url,
        energy=energy,
        bpm=bpm,
        mood=mood,
        license="owned_or_licensed",
        defaultVolume=0.1 if energy == "high" else 0.09,
        duckedVolume=0.032 if energy == "high" else 0.024 if energy == "calm" else 0.03,
    )


def _infer_energy(text: str) -> str:
    high_tokens = ["game", "ambition", "courage", "gear", "trance", "storm", "house", "dance", "positive", "techno", "party", "fest", "infected"]
    calm_tokens = ["minimal", "emotion", "forest", "sun", "dream", "tears", "joy", "ups and downs"]
    if any(token in text for token in high_tokens):
        return "high"
    if any(token in text for token in calm_tokens):
        return "calm"
    return "balanced"


def _infer_bpm(text: str, energy: str) -> int:
    explicit = {
        "techno": 124,
        "trance": 128,
        "house": 122,
        "dance": 118,
        "positive": 112,
        "ambition": 116,
        "courage": 110,
        "forest": 88,
        "sun": 92,
        "dream": 86,
        "minimal": 84,
    }
    for token, bpm in explicit.items():
        if token in text:
            return bpm
    return 118 if energy == "high" else 88 if energy == "calm" else 100


def _infer_moods(text: str, energy: str) -> list[str]:
    moods = [energy]
    mappings = {
        "positive": ["upbeat", "fitness", "wellness", "bright"],
        "ambition": ["fitness", "confident", "movement", "post-workout"],
        "courage": ["confident", "inspirational", "active"],
        "dance": ["upbeat", "movement", "pop"],
        "house": ["fitness", "electronic", "high-energy"],
        "techno": ["gym", "electronic", "high-energy"],
        "trance": ["energetic", "electronic", "movement"],
        "forest": ["wellness", "calm", "organic"],
        "sun": ["warm", "wellness", "optimistic"],
        "dream": ["calm", "premium", "soft"],
        "minimal": ["calm", "premium", "wellness"],
        "joy": ["friendly", "community", "warm"],
        "pop": ["friendly", "upbeat", "clean"],
    }
    for token, tags in mappings.items():
        if token in text:
            moods.extend(tags)
    if len(moods) == 1:
        moods.extend(["wellness", "local", "friendly"])
    return list(dict.fromkeys(moods))
