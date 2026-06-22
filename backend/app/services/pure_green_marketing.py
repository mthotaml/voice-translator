import json
import re
from pathlib import Path
import struct
from uuid import uuid4

from app.config import Settings, get_settings
from app.models import (
    Campaign,
    CampaignAsset,
    CampaignBrief,
    Caption,
    ComplianceResult,
    MediaAnalysis,
    PolishNarrationRequest,
    PolishNarrationResponse,
    Scene,
    SocialCaption,
    Storyboard,
)
from app.services.campaign_store import DEFAULT_GOAL
from app.services.music_library import list_music_tracks, select_music_track
from app.services.storage import LocalStorage


AUDIENCE_LABELS = {
    "gym_goers": "gym goers",
    "runners": "runners",
    "yoga_pilates": "yoga and Pilates customers",
    "crossfit": "CrossFit athletes",
    "tennis": "tennis players",
    "hikers": "hikers",
    "middle_aged_wellness": "active adults",
    "seniors": "seniors focused on daily wellness",
    "families": "health-conscious families",
}

PRODUCT_LABELS = {
    "smoothies": "smoothies",
    "acai_bowls": "acai bowls",
    "cold_pressed_juices": "cold-pressed juices",
    "fruits": "fresh fruit",
    "vegetables": "vegetables",
    "superfoods": "superfoods",
    "low_sugar": "lower-sugar choices",
}

CLAIM_REWRITES = {
    r"\bboosts immunity\b": "supports your wellness routine",
    r"\bcures inflammation\b": "fits into a balanced wellness routine",
    r"\bprevents disease\b": "supports everyday wellness choices",
    r"\bguarantees faster recovery\b": "helps you refuel after movement",
    r"\bextends lifespan\b": "supports a balanced lifestyle",
    r"\bnutrition is 80% of longevity\b": "nutrition is an important part of daily wellness",
    r"\bzero sugar\b": "lower-sugar options",
    r"\bno chemicals\b": "made with recognizable ingredients",
    r"\borganic\b": "fresh",
    r"\bgluten-free\b": "wellness-focused",
    r"\bnon-gmo\b": "carefully selected",
}


def analyze_campaign_assets(campaign: Campaign) -> Campaign:
    prepared_assets = [_ensure_asset_format_metadata(asset) for asset in campaign.assets]
    auto_format = _auto_format_for_assets(prepared_assets, campaign.format)
    campaign = campaign.model_copy(update={"assets": prepared_assets, "format": auto_format})
    analyzed_assets = []
    for index, asset in enumerate(campaign.assets):
        text = asset.filename.lower()
        detected_foods = _foods_from_text(text, campaign.productFocus)
        is_video = asset.type == "video"
        has_store_signal = any(token in text for token in ["store", "shop", "counter", "street", "local", "outside", "front"])
        has_fitness_signal = any(token in text for token in ["gym", "run", "runner", "yoga", "pilates", "hike", "tennis", "workout", "fitness", "crossfit"])
        has_people_signal = any(token in text for token in ["people", "person", "customer", "team", "class", "family"])
        recommended_use = "hero" if index == 0 else "b_roll"
        if detected_foods:
            recommended_use = "product_closeup"
        if has_store_signal:
            recommended_use = "hero"
        if has_fitness_signal or has_people_signal:
            recommended_use = "b_roll"

        quality = 88 if detected_foods or has_store_signal or has_fitness_signal else 78
        if is_video:
            quality += 4
        desired_format = _desired_format_key(campaign.format)
        format_warning = []
        if desired_format not in asset.formatFit and asset.orientation != "unknown":
            format_warning.append(f"Skipped for {campaign.format} when better-fitting media is available.")

        analysis = MediaAnalysis(
            detectedObjects=["uploaded video clip" if is_video else "uploaded photo", "brand asset"],
            detectedFoods=detected_foods,
            setting="storefront or local environment" if has_store_signal else "product and lifestyle setting",
            mood=_asset_mood(text, campaign),
            vibe=_asset_vibe(text, campaign),
            lighting="excellent" if any(token in text for token in ["bright", "sun", "fresh", "outdoor"]) else "good",
            backgroundDescription=_asset_background_description(text, asset),
            localContextSignals=[campaign.neighborhood or campaign.locationName or "local neighborhood"],
            fitnessSignals=_audiences(campaign, fitness_only=True) if has_fitness_signal else _audiences(campaign)[:2],
            wellnessSignals=["daily wellness", "nutrient-rich routine", "post-movement refuel"],
            brandSafetyFlags=format_warning,
            qualityScore=quality,
            recommendedUse=recommended_use,
            suggestedCaptionText=_caption_for_asset(detected_foods, campaign),
        )
        analyzed_assets.append(
            asset.model_copy(
                update={
                    "analysis": analysis,
                    "qualityScore": quality,
                    "skipReason": format_warning[0] if format_warning else None,
                }
            )
        )

    return campaign.model_copy(update={"assets": analyzed_assets, "status": "analyzing", "format": auto_format})


def _ensure_asset_format_metadata(asset: CampaignAsset) -> CampaignAsset:
    if asset.orientation != "unknown" and asset.formatFit:
        return asset
    width, height = _image_dimensions(Path("media") / asset.url.replace("/media/", "", 1))
    orientation = _orientation(width, height)
    return asset.model_copy(
        update={
            "width": width,
            "height": height,
            "orientation": orientation,
            "formatFit": _format_fit_for_orientation(orientation),
        }
    )


def generate_campaign_brief(campaign: Campaign) -> CampaignBrief:
    audience = ", ".join(_audiences(campaign)) or "local wellness customers"
    products = ", ".join(_products(campaign)) or "smoothies and nutrient-rich food"
    location = campaign.neighborhood or campaign.locationName or "the neighborhood"
    cta = campaign.cta or f"Visit {campaign.businessName} and make your next healthy choice local."
    return CampaignBrief(
        campaignAngle="Post-movement refuel for the local wellness routine",
        targetAudienceSummary=f"Built for {audience} around {location}.",
        primaryMessage=f"{campaign.businessName} helps active locals make {products} part of a balanced daily routine.",
        secondaryMessages=[
            "Nutrition can be part of how people stay consistent after movement.",
            "Fresh product visuals should appear every few seconds.",
            "The local setting should make the story feel specific, not generic.",
        ],
        visualStrategy="Open with the strongest local or product visual, then alternate product closeups with neighborhood and active-lifestyle cues.",
        hookOptions=[
            "Your workout deserves a better next stop.",
            "Make your wellness routine local.",
            "Fresh fuel for active days.",
        ],
        ctaOptions=[cta, "Refuel local.", f"Stop by {campaign.businessName} after your next class."],
        riskNotes=["Avoid disease, immunity, longevity, organic, non-GMO, and guaranteed recovery claims."],
    )


def generate_storyboard(campaign: Campaign, brief: CampaignBrief) -> Storyboard:
    duration = campaign.videoLengthSeconds
    scene_count = 6 if duration >= 30 else 4
    scene_length = duration / scene_count
    chosen_assets = _choose_scene_assets(campaign, scene_count)
    strategy = _creative_strategy(campaign)
    products = ", ".join(_products(campaign)[:3]) or "smoothies, bowls, and juices"
    business = campaign.businessName
    location = campaign.neighborhood or campaign.locationName or "your neighborhood"
    cta = campaign.cta or brief.ctaOptions[0]

    default_lines = [
        strategy["hook"],
        f"In {location}, this fits the rhythm of real active days.",
        f"{business} brings together {products} for people who care about what they choose next.",
        "Fresh fruits, vegetables, and superfoods make the routine feel simple.",
        strategy["bridge"],
        cta,
    ][:scene_count]
    lines = _narration_lines(campaign.narrationScript, default_lines, scene_count)
    captions = [
        strategy["caption_hook"],
        "Your local wellness stop",
        "Fresh choices, clearly shown",
        "Nutrient-rich routine fuel",
        "Keep the day moving",
        "Make your next choice local",
    ][:scene_count]

    scenes: list[Scene] = []
    caption_models: list[Caption] = []
    for index, line in enumerate(lines):
        start = round(index * scene_length, 2)
        end = round(duration if index == scene_count - 1 else (index + 1) * scene_length, 2)
        asset_id = [chosen_assets[index].id] if chosen_assets else []
        scenes.append(
            Scene(
                index=index + 1,
                startTime=start,
                endTime=end,
                assetIds=asset_id,
                visualDirection=_visual_direction(index, campaign, chosen_assets[index] if chosen_assets else None),
                onScreenText=captions[index],
                voiceoverLine=line,
                transition=["cut", "fade", "zoom", "slide", "match_cut", "fade"][index % 6],
            )
        )
        caption_models.append(Caption(startTime=start, endTime=end, text=captions[index]))

    script = " ".join(lines)
    clean = run_compliance(script, captions)
    scene_lines = _align_scene_voiceover(clean.rewrittenScript, lines)
    return Storyboard(
        campaignId=campaign.id,
        totalDurationSeconds=duration,
        scenes=[
            scene.model_copy(update={"voiceoverLine": scene_lines[index]})
            for index, scene in enumerate(scenes)
        ],
        voiceoverScript=clean.rewrittenScript,
        captions=[caption.model_copy(update={"text": text}) for caption, text in zip(caption_models, clean.rewrittenCaptions)],
        musicStyle=strategy["music_style"],
        voiceTone=strategy["voice_tone"],
        voiceRecommendation=strategy["voice_recommendation"],
        musicRationale=strategy["music_rationale"],
        complianceNotes=[*clean.notes, strategy["selection_note"]],
        cta=cta,
        qualityScore=_quality_score(campaign),
    )


def _narration_lines(custom_script: str | None, default_lines: list[str], scene_count: int) -> list[str]:
    script = (custom_script or "").strip()
    if not script:
        return default_lines[:scene_count]

    pieces = _split_narration_text(script)
    if len(pieces) == 1 and len(pieces[0].split()) > scene_count * 7:
        pieces = _chunk_words(pieces[0], scene_count)

    if len(pieces) >= scene_count:
        return pieces[: scene_count - 1] + [" ".join(pieces[scene_count - 1 :])]

    return [
        pieces[index] if index < len(pieces) and pieces[index] else default_lines[index]
        for index in range(scene_count)
    ]


def _split_narration_text(text: str) -> list[str]:
    lines = [line.strip() for line in re.split(r"\n+", text) if line.strip()]
    if len(lines) > 1:
        return lines
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]


def _chunk_words(text: str, chunk_count: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunk_size = max(1, round(len(words) / chunk_count))
    return [" ".join(words[index : index + chunk_size]) for index in range(0, len(words), chunk_size)]


def _align_scene_voiceover(clean_script: str, original_lines: list[str]) -> list[str]:
    clean_lines = _split_narration_text(clean_script)
    if len(clean_lines) >= len(original_lines):
        return clean_lines[: len(original_lines) - 1] + [" ".join(clean_lines[len(original_lines) - 1 :])]
    return original_lines


def run_compliance(script: str, captions: list[str]) -> ComplianceResult:
    issues: list[str] = []
    clean_script = script
    clean_captions = captions[:]
    for pattern, replacement in CLAIM_REWRITES.items():
        if re.search(pattern, clean_script, flags=re.IGNORECASE):
            issues.append(f"Rewrote unsupported claim: {pattern.strip('\\b')}")
            clean_script = re.sub(pattern, replacement, clean_script, flags=re.IGNORECASE)
        clean_captions = [re.sub(pattern, replacement, caption, flags=re.IGNORECASE) for caption in clean_captions]

    return ComplianceResult(
        approved=True,
        issues=issues,
        rewrittenScript=clean_script,
        rewrittenCaptions=clean_captions,
        notes=["Approved for lifestyle-oriented wellness language."],
    )


def polish_campaign_narration(payload: PolishNarrationRequest, settings: Settings) -> PolishNarrationResponse:
    rough = payload.roughText.strip()
    if not rough:
        raise ValueError("Enter a rough campaign idea before polishing narration.")

    if settings.demo_mode or not settings.openai_api_key:
        return _demo_polished_narration(payload)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model=settings.openai_translation_model,
            temperature=0.55,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a senior local wellness advertising copywriter. "
                        "Turn rough user intent into polished short-form video narration. "
                        "Avoid unsupported medical, disease, immunity, longevity, recovery guarantee, organic, non-GMO, and zero-sugar claims. "
                        "Return only JSON with polishedNarration, hook, onScreenText, rationale."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "rough_user_words": rough,
                            "business": payload.businessName,
                            "location": payload.locationName,
                            "neighborhood": payload.neighborhood,
                            "audience": [_audience_label(item) for item in payload.targetAudience],
                            "products": [_product_label(item) for item in payload.productFocus],
                            "tone": payload.tone,
                            "cta": payload.cta,
                            "video_length_seconds": payload.videoLengthSeconds,
                            "requirements": [
                                "Make it sound polished, local, and campaign-ready.",
                                "Use natural voiceover language, not corporate copy.",
                                "Keep it concise enough for the selected video length.",
                                "Preserve the user's intent and favorite words where safe.",
                                "Use lifestyle wellness language, not medical claims.",
                            ],
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        )
        data = json.loads(response.choices[0].message.content or "{}")
        polished = str(data.get("polishedNarration") or data.get("polished_narration") or "").strip()
        hook = str(data.get("hook") or "").strip()
        on_screen = data.get("onScreenText") or data.get("on_screen_text") or []
        if isinstance(on_screen, str):
            on_screen = _split_narration_text(on_screen)
        if not isinstance(on_screen, list):
            on_screen = []
        rationale = str(data.get("rationale") or "Polished for a local wellness video campaign.").strip()
        if not polished:
            return _demo_polished_narration(payload)
        clean = run_compliance(polished, [str(item) for item in on_screen if str(item).strip()])
        return PolishNarrationResponse(
            polishedNarration=clean.rewrittenScript,
            hook=hook or _split_narration_text(clean.rewrittenScript)[0],
            onScreenText=clean.rewrittenCaptions[:5],
            rationale=rationale,
            provider="openai",
        )
    except Exception:
        return _demo_polished_narration(payload)


def _demo_polished_narration(payload: PolishNarrationRequest) -> PolishNarrationResponse:
    location = payload.neighborhood or payload.locationName or "your neighborhood"
    products = ", ".join(_product_label(item) for item in payload.productFocus[:3]) or "smoothies, bowls, and cold-pressed juices"
    audience = ", ".join(_audience_label(item) for item in payload.targetAudience[:2]) or "active locals"
    cta = payload.cta or f"Stop by {payload.businessName} and make your next healthy choice local."
    hook = "Your next healthy stop is closer than you think."
    narration = (
        f"{hook} After the workout, the class, the run, or the long day, {payload.businessName} brings {products} "
        f"to {audience} around {location}. Fresh ingredients, bright flavor, and choices that fit an active routine. {cta}"
    )
    clean = run_compliance(narration, [hook, "Fresh local fuel", "Made for active routines", cta])
    return PolishNarrationResponse(
        polishedNarration=clean.rewrittenScript,
        hook=hook,
        onScreenText=clean.rewrittenCaptions,
        rationale="Demo polish used a safe local wellness structure: hook, lifestyle moment, product proof, and CTA.",
        provider="demo",
    )


def _audience_label(value: str) -> str:
    return AUDIENCE_LABELS.get(value, value.replace("_", " "))


def _product_label(value: str) -> str:
    return PRODUCT_LABELS.get(value, value.replace("_", " "))


def generate_social_caption(campaign: Campaign, storyboard: Storyboard) -> SocialCaption:
    location = campaign.neighborhood or campaign.locationName or "your neighborhood"
    products = ", ".join(_products(campaign)[:3]) or "smoothies and bowls"
    return SocialCaption(
        shortCaption=f"Fresh {products} for active days in {location}.",
        longerCaption=(
            f"After the workout, class, run, or long day, make nutrition part of your routine. "
            f"{campaign.businessName} brings fresh, nutrient-rich choices to {location}."
        ),
        hashtags=["#PureGreen", "#LocalWellness", "#PostWorkout", "#Smoothies", "#AcaiBowls", "#ActiveLifestyle"],
    )


def select_campaign_music(campaign: Campaign, storyboard: Storyboard):
    settings = get_settings()
    return select_music_track(campaign, settings, _campaign_energy(campaign))


def generate_narration(campaign: Campaign, settings: Settings, storage: LocalStorage) -> str:
    if settings.demo_mode or not settings.elevenlabs_api_key:
        return storage.create_demo_audio()

    import httpx

    voice_id = campaign.voiceId or _select_elevenlabs_voice_id(campaign, settings) or settings.elevenlabs_voice_id
    if not voice_id:
        return storage.create_demo_audio()
    text = campaign.compliance.rewrittenScript if campaign.compliance else campaign.storyboard.voiceoverScript
    try:
        response = httpx.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={"xi-api-key": settings.elevenlabs_api_key, "accept": "audio/mpeg", "content-type": "application/json"},
            json={
                "model_id": settings.elevenlabs_tts_model,
                "text": text,
                "voice_settings": _voice_settings_for_campaign(campaign),
            },
            timeout=20,
        )
        response.raise_for_status()
        return storage.save_generated_bytes(response.content, suffix=".mp3")
    except Exception:
        return storage.create_demo_audio()


def render_manifest(campaign: Campaign, settings: Settings) -> str:
    render_dir = settings.media_root / "generated"
    render_dir.mkdir(parents=True, exist_ok=True)
    path = render_dir / f"{uuid4()}-campaign-preview.html"
    path.write_text(_render_preview_html(campaign), encoding="utf-8")
    return f"/media/generated/{path.name}"


def inspect_media_dimensions(settings: Settings, media_url: str) -> tuple[int | None, int | None, str, list[str]]:
    path = settings.media_root / media_url.replace("/media/", "", 1)
    width, height = _image_dimensions(path)
    orientation = _orientation(width, height)
    return width, height, orientation, _format_fit_for_orientation(orientation)


def _render_preview_html(campaign: Campaign) -> str:
    storyboard = campaign.storyboard
    scenes = storyboard.scenes if storyboard else []
    geometry = _render_geometry(campaign.format)
    asset_by_id = {asset.id: asset for asset in campaign.assets}
    scene_data = [
        {
            "caption": scene.onScreenText,
            "line": scene.voiceoverLine,
            "start": scene.startTime,
            "end": scene.endTime,
            "assetUrl": _asset_url_for_scene(scene, asset_by_id),
            "assetType": _asset_type_for_scene(scene, asset_by_id),
        }
        for scene in scenes
    ]
    scene_markup = "\n".join(
        f"""
        <section class="scene" style="--i:{scene.index - 1}; --total:{len(scenes) or 1};">
          {_scene_media_markup(scene, asset_by_id)}
          <div class="caption">{_escape(scene.onScreenText)}</div>
          <div class="time">{scene.startTime:g}s - {scene.endTime:g}s</div>
        </section>
        """
        for scene in scenes
    )
    duration = storyboard.totalDurationSeconds if storyboard else campaign.videoLengthSeconds
    script = storyboard.voiceoverScript if storyboard else ""
    voice_tone = storyboard.voiceTone if storyboard else "Warm, conversational wellness narrator"
    voice_recommendation = storyboard.voiceRecommendation if storyboard else "Use a clear, friendly voice."
    music_style = storyboard.musicStyle if storyboard else campaign.musicStyle
    music_rationale = storyboard.musicRationale if storyboard else "Selected to match the visual energy."
    music_track = campaign.musicTrack
    music_track_title = music_track.title if music_track else "Generated quiet preview bed"
    music_track_url = music_track.file if music_track else ""
    music_default_volume = music_track.defaultVolume if music_track else 0.1
    music_ducked_volume = music_track.duckedVolume if music_track else 0.03
    music_options = _music_options_for_preview(campaign)
    hashtags = " ".join(campaign.socialCaption.hashtags) if campaign.socialCaption else "#PureGreen #LocalWellness"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{_escape(campaign.name)} Preview</title>
  <style>
    :root {{
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #14211c;
      background: #f5f7f4;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; padding: 28px; display: grid; place-items: start center; gap: 20px; }}
    .workflow {{
      width: min(92vw, 760px);
      display: grid;
      gap: 12px;
    }}
    .step {{
      display: grid;
      gap: 10px;
      padding: 14px;
      border: 1px solid #dce5dd;
      border-radius: 8px;
      background: #fff;
      box-shadow: 0 12px 30px rgba(29, 55, 39, .07);
    }}
    .step-head {{
      display: flex;
      align-items: center;
      gap: 10px;
      color: #617067;
      font-weight: 750;
    }}
    .step-head span:first-child {{
      width: 28px;
      height: 28px;
      display: grid;
      place-items: center;
      border-radius: 999px;
      background: #118846;
      color: #fff;
      font-size: .88rem;
      font-weight: 900;
    }}
    .step-actions {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }}
    button, a.button {{
      border: 0;
      border-radius: 8px;
      background: #118846;
      color: white;
      padding: 12px 14px;
      font: inherit;
      font-weight: 800;
      cursor: pointer;
      text-decoration: none;
    }}
    button:disabled {{ opacity: .45; cursor: not-allowed; }}
    button.secondary {{
      background: #20372b;
    }}
    #preview-status,
    #export-status {{
      color: #617067;
      font-size: .95rem;
      line-height: 1.45;
    }}
    #music-preview {{
      width: min(92vw, 760px);
      display: none;
    }}
    #rough-video,
    #rendered-video {{
      display: none;
      width: 100%;
      border-radius: 8px;
      box-shadow: 0 18px 46px rgba(29,55,39,.09);
    }}
    .stage {{
      position: relative;
      width: min(92vw, {geometry["preview_width"]}px);
      aspect-ratio: {geometry["aspect_ratio"]};
      overflow: hidden;
      border-radius: 8px;
      color: white;
      background:
        linear-gradient(160deg, rgba(11, 98, 53, .86), rgba(239, 111, 79, .35)),
        url("https://images.unsplash.com/photo-1512621776951-a57141f2eefd?auto=format&fit=crop&w=1200&q=80");
      background-size: cover;
      background-position: center;
      box-shadow: 0 22px 60px rgba(20, 33, 28, .18);
    }}
    .brand {{
      position: absolute;
      left: 28px;
      right: 28px;
      bottom: 30px;
      font-size: clamp(2.4rem, 12vw, 4.8rem);
      line-height: .92;
      font-weight: 900;
      text-shadow: 0 8px 28px rgba(0,0,0,.32);
      z-index: 3;
    }}
    .asset-media {{
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      object-fit: cover;
      transform: scale(1.04);
      animation: mediaMove {duration}s linear infinite;
      z-index: -2;
    }}
    .scene {{
      position: absolute;
      inset: 0;
      padding: 34px 28px;
      display: flex;
      flex-direction: column;
      justify-content: flex-start;
      gap: 12px;
      opacity: 0;
      animation: showScene {duration}s linear infinite;
      animation-delay: calc((var(--i) * {duration}s) / var(--total));
      z-index: 2;
    }}
    .scene::before {{
      content: "";
      position: absolute;
      inset: 0;
      background: linear-gradient(180deg, rgba(0,0,0,.52), rgba(0,0,0,.14) 46%, rgba(0,0,0,.48));
      z-index: -1;
    }}
    .caption {{
      width: fit-content;
      max-width: 92%;
      border-radius: 8px;
      padding: 10px 12px;
      background: rgba(8, 24, 16, .76);
      font-size: 1.45rem;
      line-height: 1.12;
      font-weight: 850;
    }}
    .time {{
      width: fit-content;
      border-radius: 999px;
      background: #d8f36a;
      color: #173016;
      padding: 6px 9px;
      font-size: .82rem;
      font-weight: 800;
    }}
    .progress {{
      position: absolute;
      left: 0;
      right: 0;
      bottom: 0;
      height: 7px;
      background: rgba(255,255,255,.22);
      z-index: 4;
    }}
    .progress::after {{
      content: "";
      display: block;
      width: 100%;
      height: 100%;
      background: #d8f36a;
      transform-origin: left;
      animation: progress {duration}s linear infinite;
    }}
    .details {{
      width: min(92vw, 760px);
      background: white;
      border: 1px solid #dce5dd;
      border-radius: 8px;
      padding: 18px;
      box-shadow: 0 18px 46px rgba(29, 55, 39, .09);
    }}
    h1 {{ margin: 0 0 10px; font-size: 1.35rem; }}
    p {{ margin: 0 0 12px; color: #617067; line-height: 1.55; }}
    ul {{ margin: 0; padding-left: 20px; color: #617067; line-height: 1.55; }}
    @keyframes progress {{ from {{ transform: scaleX(0); }} to {{ transform: scaleX(1); }} }}
    @keyframes mediaMove {{
      0% {{ transform: scale(1.04) translateX(0); }}
      50% {{ transform: scale(1.10) translateX(-1.5%); }}
      100% {{ transform: scale(1.04) translateX(0); }}
    }}
    @keyframes showScene {{
      0% {{ opacity: 0; transform: scale(1.04); }}
      2% {{ opacity: 1; transform: scale(1); }}
      14% {{ opacity: 1; transform: scale(1.015); }}
      16.5% {{ opacity: 0; transform: scale(1.03); }}
      100% {{ opacity: 0; }}
    }}
  </style>
</head>
<body>
  <div class="workflow">
    <section class="step">
      <div class="step-head"><span>1</span><span>Preview the video first</span></div>
      <div class="step-actions">
        <button id="preview-video">Create video preview</button>
      </div>
      <span id="preview-status">Start here. This creates a silent rough preview so you can judge the visuals before choosing music.</span>
      <video id="rough-video" controls playsinline muted></video>
    </section>
    <section class="step">
      <div class="step-head"><span>2</span><span>Choose background music</span></div>
      <div class="step-actions">
        <button id="preview-music" disabled>Preview music</button>
        <button id="shuffle-music" class="secondary" disabled>Try another track</button>
        <button id="accept-music" class="secondary" disabled>Use this music</button>
      </div>
      <span id="music-status">After watching the rough preview, preview the selected track. Export keeps music below the voiceover.</span>
    </section>
    <section class="step">
      <div class="step-head"><span>3</span><span>Generate and view the final video</span></div>
      <div class="step-actions">
        <button id="export" disabled>Generate final video</button>
      </div>
      <span id="export-status">After music is accepted, generate the final video. The app will use MP4/H.264 when your browser supports it.</span>
      <video id="rendered-video" controls playsinline></video>
    </section>
    <section class="step">
      <div class="step-head"><span>4</span><span>Download the finished video</span></div>
      <div class="step-actions">
        <button id="download" class="secondary" disabled>Download video</button>
      </div>
    </section>
  </div>
  <audio id="music-preview" controls preload="none"></audio>
  <main class="stage" aria-label="Animated campaign preview">
    {scene_markup}
    <div class="brand">{_escape(campaign.businessName)}</div>
    <div class="progress"></div>
  </main>
  <aside class="details">
    <h1>{_escape(campaign.name)}</h1>
    <p><strong>Detected render:</strong> {_escape(geometry["label"])}. Media is selected to match this format; mismatched assets are skipped when better-fitting files exist.</p>
    <p><strong>Preview length:</strong> {duration} seconds. Click “Generate final video” to create the downloadable campaign video. MP4/H.264 is preferred when the browser supports it.</p>
    <p><strong>Voiceover:</strong> {_escape(script)}</p>
    <p><strong>Voice direction:</strong> {_escape(voice_tone)}. {_escape(voice_recommendation)}</p>
    <p><strong>Music direction:</strong> {_escape(music_style)}. {_escape(music_rationale)}</p>
    <p><strong>Selected music:</strong> <span id="selected-track-name">{_escape(music_track_title)}</span>. Preview it, try another approved track, then use the one that feels right for this campaign.</p>
    <p><strong>Social:</strong> {_escape(hashtags)}</p>
  </aside>
  <script>
    const scenes = {json.dumps(scene_data)};
    const brand = {json.dumps(campaign.businessName)};
    const duration = {json.dumps(duration)};
    const narrationUrl = {json.dumps(campaign.narrationUrl or "")};
    const musicEnergy = {json.dumps(_campaign_energy(campaign))};
    const initialMusic = {{
      title: {json.dumps(music_track_title)},
      file: {json.dumps(music_track_url)},
      defaultVolume: {json.dumps(music_default_volume)},
      duckedVolume: {json.dumps(music_ducked_volume)}
    }};
    const musicOptions = {json.dumps(music_options)};
    const canvas = document.createElement("canvas");
    canvas.width = {geometry["width"]};
    canvas.height = {geometry["height"]};
    const ctx = canvas.getContext("2d");
    const W = canvas.width;
    const H = canvas.height;
    const previewMusicButton = document.getElementById("preview-music");
    const shuffleMusicButton = document.getElementById("shuffle-music");
    const acceptMusicButton = document.getElementById("accept-music");
    const previewVideoButton = document.getElementById("preview-video");
    const exportButton = document.getElementById("export");
    const downloadButton = document.getElementById("download");
    const roughVideo = document.getElementById("rough-video");
    const renderedVideo = document.getElementById("rendered-video");
    const musicPreview = document.getElementById("music-preview");
    const musicStatus = document.getElementById("music-status");
    const previewStatus = document.getElementById("preview-status");
    const exportStatus = document.getElementById("export-status");
    const loadedImages = new Map();
    const loadedVideos = new Map();
    let currentMusic = initialMusic;
    let musicAccepted = false;
    let renderedVideoUrl = "";
    let renderedMimeType = "";
    let roughVideoUrl = "";
    let previewPromise = null;
    let renderPromise = null;

    function loadSceneMedia() {{
      for (const scene of scenes) {{
        if (!scene.assetUrl) continue;
        if (scene.assetType === "image" && !loadedImages.has(scene.assetUrl)) {{
          const img = new Image();
          img.crossOrigin = "anonymous";
          img.src = scene.assetUrl;
          loadedImages.set(scene.assetUrl, img);
        }}
        if (scene.assetType === "video" && !loadedVideos.has(scene.assetUrl)) {{
          const video = document.createElement("video");
          video.crossOrigin = "anonymous";
          video.muted = true;
          video.loop = true;
          video.playsInline = true;
          video.preload = "auto";
          video.src = scene.assetUrl;
          video.style.display = "none";
          document.body.appendChild(video);
          loadedVideos.set(scene.assetUrl, video);
          video.play().catch(() => {{}});
        }}
      }}
    }}

    function roundRect(x, y, w, h, r) {{
      ctx.beginPath();
      ctx.moveTo(x + r, y);
      ctx.arcTo(x + w, y, x + w, y + h, r);
      ctx.arcTo(x + w, y + h, x, y + h, r);
      ctx.arcTo(x, y + h, x, y, r);
      ctx.arcTo(x, y, x + w, y, r);
      ctx.closePath();
    }}

    function wrapText(text, x, y, maxWidth, lineHeight) {{
      const words = text.split(" ");
      let line = "";
      for (const word of words) {{
        const test = line ? `${{line}} ${{word}}` : word;
        if (ctx.measureText(test).width > maxWidth && line) {{
          ctx.fillText(line, x, y);
          line = word;
          y += lineHeight;
        }} else {{
          line = test;
        }}
      }}
      if (line) ctx.fillText(line, x, y);
      return y;
    }}

    function drawFrame(time) {{
      const scene = scenes.find((item) => time >= item.start && time < item.end) || scenes[scenes.length - 1] || {{caption: "Pure Green", line: "", start: 0, end: duration}};
      const pulse = 1 + Math.sin(time * 0.8) * 0.018;
      const img = scene.assetType === "image" ? loadedImages.get(scene.assetUrl) : null;
      const video = scene.assetType === "video" ? loadedVideos.get(scene.assetUrl) : null;
      if (img && img.complete && img.naturalWidth > 0) {{
        drawCoverImage(img, pulse);
      }} else if (video && video.readyState >= 2 && video.videoWidth > 0) {{
        drawCoverVideo(video, pulse);
      }} else {{
        const grad = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
        grad.addColorStop(0, "#0b6235");
        grad.addColorStop(0.52, "#118846");
        grad.addColorStop(1, "#ef6f4f");
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, canvas.width, canvas.height);
      }}

      ctx.save();
      ctx.translate(canvas.width / 2, canvas.height / 2);
      ctx.scale(pulse, pulse);
      ctx.translate(-canvas.width / 2, -canvas.height / 2);
      for (let i = 0; i < 18; i++) {{
        ctx.globalAlpha = 0.10;
        ctx.fillStyle = i % 3 === 0 ? "#d8f36a" : i % 3 === 1 ? "#ffffff" : "#ffb199";
        ctx.beginPath();
        const x = (i * 173 + time * 34) % (W + 220) - 110;
        const y = (i * 277 + time * 21) % (H + 220) - 110;
        ctx.ellipse(x, y, W * 0.11 + i * 6, H * 0.04 + i * 3, i, 0, Math.PI * 2);
        ctx.fill();
      }}
      ctx.restore();
      ctx.globalAlpha = 1;
      ctx.fillStyle = "rgba(0,0,0,.36)";
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      ctx.fillStyle = "rgba(8, 24, 16, 0.78)";
      const pad = Math.max(46, W * 0.055);
      const captionWidth = Math.min(W - pad * 2, W * 0.78);
      const captionHeight = Math.max(124, H * 0.09);
      roundRect(pad, pad, captionWidth, captionHeight, 24);
      ctx.fill();
      ctx.fillStyle = "#ffffff";
      ctx.font = `900 ${{Math.max(40, Math.round(W * 0.054))}}px Inter, system-ui, sans-serif`;
      wrapText(scene.caption, pad + 32, pad + Math.max(58, H * 0.04), captionWidth - 64, Math.max(48, W * 0.06));

      ctx.fillStyle = "#ffffff";
      ctx.font = `950 ${{Math.max(78, Math.round(W * 0.105))}}px Inter, system-ui, sans-serif`;
      wrapText(brand, pad, H - Math.max(140, H * 0.14), W - pad * 2, Math.max(82, W * 0.11));

      ctx.fillStyle = "#d8f36a";
      ctx.fillRect(0, H - 14, W * (time / duration), 14);
    }}

    function drawCoverImage(img, pulse) {{
      const scale = Math.max(canvas.width / img.naturalWidth, canvas.height / img.naturalHeight) * pulse;
      const width = img.naturalWidth * scale;
      const height = img.naturalHeight * scale;
      const x = (canvas.width - width) / 2;
      const y = (canvas.height - height) / 2;
      ctx.drawImage(img, x, y, width, height);
    }}

    function drawCoverVideo(video, pulse) {{
      const scale = Math.max(canvas.width / video.videoWidth, canvas.height / video.videoHeight) * pulse;
      const width = video.videoWidth * scale;
      const height = video.videoHeight * scale;
      const x = (canvas.width - width) / 2;
      const y = (canvas.height - height) / 2;
      ctx.drawImage(video, x, y, width, height);
    }}

    async function exportVideo() {{
      if (renderedVideoUrl) {{
        exportStatus.textContent = "Video is ready.";
        return renderedVideoUrl;
      }}
      if (renderPromise) return renderPromise;
      renderPromise = doExportVideo();
      try {{
        renderedVideoUrl = await renderPromise;
        return renderedVideoUrl;
      }} finally {{
        renderPromise = null;
      }}
    }}

    async function doExportVideo() {{
      if (!window.MediaRecorder) {{
        exportStatus.textContent = "This browser cannot export video with MediaRecorder.";
        throw new Error("MediaRecorder unavailable");
      }}
      const mimeTypes = [
        "video/mp4;codecs=avc1.42E01E,mp4a.40.2",
        "video/mp4;codecs=h264,aac",
        "video/mp4",
        "video/webm;codecs=vp9",
        "video/webm;codecs=vp8",
        "video/webm"
      ];
      const mimeType = mimeTypes.find((type) => MediaRecorder.isTypeSupported(type));
      if (!mimeType) {{
        exportStatus.textContent = "This browser cannot export MP4 or WebM video.";
        throw new Error("Video export unavailable");
      }}
      exportButton.disabled = true;
      exportButton.textContent = "Generating video...";
      downloadButton.disabled = true;
      exportStatus.textContent = "Generating the video. Keep this tab open.";
      const videoStream = canvas.captureStream(30);
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      await audioContext.resume();
      const audioDestination = audioContext.createMediaStreamDestination();
      const stopAudio = await startAudioBed(audioContext, audioDestination);
      const stream = new MediaStream([
        ...videoStream.getVideoTracks(),
        ...audioDestination.stream.getAudioTracks()
      ]);
      const chunks = [];
      const recorder = new MediaRecorder(stream, {{ mimeType }});
      recorder.ondataavailable = (event) => event.data.size && chunks.push(event.data);
      return await new Promise((resolve, reject) => {{
        recorder.onstop = () => {{
          stopAudio();
          const blob = new Blob(chunks, {{ type: mimeType }});
          const url = URL.createObjectURL(blob);
          renderedMimeType = mimeType;
          renderedVideo.src = url;
          renderedVideo.style.display = "block";
          exportButton.textContent = "Generate final video";
          exportButton.disabled = true;
          exportButton.style.display = "none";
          downloadButton.disabled = false;
          exportStatus.textContent = `Video ready as ${{downloadExtensionForMime(mimeType).toUpperCase()}} (${{Math.round(blob.size / 1024)}} KB). Watch it below, then download it.`;
          resolve(url);
        }};
        recorder.onerror = () => {{
          stopAudio();
          exportButton.textContent = "Try again";
          exportButton.disabled = false;
          downloadButton.disabled = true;
          exportStatus.textContent = "The browser stopped video generation. Try again with the tab visible.";
          reject(new Error("Export stopped"));
        }};
        recorder.start();
        const fps = 30;
        let frame = 0;
        const totalFrames = Math.ceil(duration * fps);
        const timer = setInterval(() => {{
          drawFrame(frame / fps);
          frame += 1;
          if (frame > totalFrames) {{
            clearInterval(timer);
            recorder.stop();
          }}
        }}, 1000 / fps);
      }});
    }}

    async function createRoughPreview() {{
      if (roughVideoUrl) {{
        previewStatus.textContent = "Video preview is ready. Choose a music track that fits the visuals.";
        return roughVideoUrl;
      }}
      if (previewPromise) return previewPromise;
      previewPromise = doCreateRoughPreview();
      try {{
        roughVideoUrl = await previewPromise;
        return roughVideoUrl;
      }} finally {{
        previewPromise = null;
      }}
    }}

    async function doCreateRoughPreview() {{
      if (!window.MediaRecorder) {{
        previewStatus.textContent = "This browser cannot create the video preview.";
        throw new Error("MediaRecorder unavailable");
      }}
      const mimeTypes = [
        "video/webm;codecs=vp9",
        "video/webm;codecs=vp8",
        "video/webm"
      ];
      const mimeType = mimeTypes.find((type) => MediaRecorder.isTypeSupported(type));
      if (!mimeType) {{
        previewStatus.textContent = "This browser cannot create WebM video previews.";
        throw new Error("WebM unavailable");
      }}
      previewVideoButton.disabled = true;
      previewVideoButton.textContent = "Creating preview...";
      previewStatus.textContent = "Creating a silent rough preview. Keep this tab open.";
      const stream = canvas.captureStream(30);
      const chunks = [];
      const recorder = new MediaRecorder(stream, {{ mimeType }});
      recorder.ondataavailable = (event) => event.data.size && chunks.push(event.data);
      return await new Promise((resolve, reject) => {{
        recorder.onstop = () => {{
          const blob = new Blob(chunks, {{ type: "video/webm" }});
          const url = URL.createObjectURL(blob);
          roughVideo.src = url;
          roughVideo.style.display = "block";
          previewVideoButton.textContent = "Preview ready";
          previewVideoButton.disabled = true;
          previewMusicButton.disabled = false;
          shuffleMusicButton.disabled = false;
          acceptMusicButton.disabled = false;
          previewStatus.textContent = "Watch this rough preview, then choose the background music below.";
          musicStatus.textContent = "Now preview music against the video feel, or try another track.";
          resolve(url);
        }};
        recorder.onerror = () => {{
          previewVideoButton.textContent = "Try preview again";
          previewVideoButton.disabled = false;
          previewStatus.textContent = "The browser stopped preview creation. Try again with the tab visible.";
          reject(new Error("Preview stopped"));
        }};
        recorder.start();
        const fps = 30;
        let frame = 0;
        const totalFrames = Math.ceil(duration * fps);
        const timer = setInterval(() => {{
          drawFrame(frame / fps);
          frame += 1;
          if (frame > totalFrames) {{
            clearInterval(timer);
            recorder.stop();
          }}
        }}, 1000 / fps);
      }});
    }}

    async function downloadVideo() {{
      try {{
        const url = await exportVideo();
        const link = document.createElement("a");
        link.href = url;
        link.download = `${{downloadBaseName}}.${{downloadExtensionForMime(renderedMimeType)}}`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        exportStatus.textContent = `Download started. Check your browser downloads for the ${{downloadExtensionForMime(renderedMimeType).toUpperCase()}} video file.`;
      }} catch (error) {{}}
    }}

    const downloadBaseName = {json.dumps(campaign.name.replace(" ", "-").lower() + "-campaign")};

    function downloadExtensionForMime(mimeType) {{
      return mimeType && mimeType.includes("mp4") ? "mp4" : "webm";
    }}

    async function startAudioBed(audioContext, destination) {{
      const master = audioContext.createGain();
      master.gain.value = 1.0;
      master.connect(destination);

      const musicGain = audioContext.createGain();
      musicGain.gain.value = Math.max(currentMusic.duckedVolume, 0.06);
      musicGain.connect(master);

      const stopCallbacks = [];
      let approvedMusicSource = null;
      if (currentMusic.file) {{
        try {{
          const response = await fetch(currentMusic.file);
          if (response.ok) {{
            const buffer = await response.arrayBuffer();
            const decoded = await audioContext.decodeAudioData(buffer);
            approvedMusicSource = audioContext.createBufferSource();
            approvedMusicSource.buffer = decoded;
            approvedMusicSource.loop = true;
            approvedMusicSource.connect(musicGain);
            approvedMusicSource.start();
            stopCallbacks.push(() => approvedMusicSource.stop());
          }}
        }} catch (error) {{
          exportStatus.textContent = "Approved music file unavailable, using generated quiet preview bed.";
        }}
      }}

      if (!approvedMusicSource) {{
        const frequencies = musicEnergy === "high" ? [196, 247, 294, 330] : musicEnergy === "calm" ? [147, 196, 220, 294] : [174, 220, 262, 330];
        frequencies.forEach((frequency, index) => {{
          const oscillator = audioContext.createOscillator();
          const gain = audioContext.createGain();
          oscillator.type = index % 2 === 0 ? "sine" : "triangle";
          oscillator.frequency.value = frequency;
          gain.gain.value = index === 0 ? 0.8 : 0.18;
          oscillator.connect(gain).connect(musicGain);
          oscillator.start();
          stopCallbacks.push(() => oscillator.stop());
        }});
      }}

      let voiceSource = null;
      if (narrationUrl) {{
        try {{
          const response = await fetch(narrationUrl);
          const buffer = await response.arrayBuffer();
          const decoded = await audioContext.decodeAudioData(buffer);
          voiceSource = audioContext.createBufferSource();
          voiceSource.buffer = decoded;
          const voiceGain = audioContext.createGain();
          voiceGain.gain.value = 0.9;
          voiceSource.connect(voiceGain).connect(destination);
          voiceSource.start();
          // Keep the music low while the voiceover is active.
          musicGain.gain.setValueAtTime(musicGain.gain.value, audioContext.currentTime);
          musicGain.gain.linearRampToValueAtTime(Math.max(currentMusic.duckedVolume, 0.055), audioContext.currentTime + 0.4);
          musicGain.gain.linearRampToValueAtTime(Math.min(Math.max(currentMusic.defaultVolume, 0.12), 0.16), audioContext.currentTime + Math.min(duration, decoded.duration));
          stopCallbacks.push(() => voiceSource.stop());
        }} catch (error) {{
          exportStatus.textContent = "Narration could not be mixed, exporting with quiet background music.";
        }}
      }}

      return () => {{
        stopCallbacks.forEach((callback) => {{
          try {{ callback(); }} catch (error) {{}}
        }});
        try {{ audioContext.close(); }} catch (error) {{}}
      }};
    }}

    function setCurrentMusic(track, accepted = false) {{
      currentMusic = track;
      musicAccepted = accepted;
      if (accepted) {{
        musicPreview.pause();
        musicPreview.currentTime = 0;
        musicPreview.style.display = "none";
      }}
      renderedVideoUrl = "";
      renderedMimeType = "";
      renderedVideo.removeAttribute("src");
      renderedVideo.style.display = "none";
      downloadButton.disabled = true;
      exportButton.disabled = !accepted;
      exportButton.style.display = "inline-flex";
      exportButton.textContent = "Generate final video";
      document.getElementById("selected-track-name").textContent = track.title || "Generated quiet preview bed";
      musicStatus.textContent = accepted ? "Music accepted. Preview stopped. Now generate the video." : "Preview this track or try another one.";
      exportStatus.textContent = accepted ? "Ready to generate the video." : "Accept a track, then generate the video.";
    }}

    async function previewCurrentMusic() {{
      if (!currentMusic.file) {{
        musicStatus.textContent = "No approved music file is available for preview.";
        return;
      }}
      previewMusicButton.disabled = true;
      musicPreview.pause();
      musicPreview.src = currentMusic.file;
      musicPreview.volume = 0.38;
      musicPreview.style.display = "block";
      musicStatus.textContent = `Playing ${{currentMusic.title || "selected music"}} at preview volume.`;
      exportStatus.textContent = "Export will keep music quieter under the voiceover.";
      try {{
        await musicPreview.play();
      }} catch (error) {{
        musicStatus.textContent = "The browser blocked autoplay. Press play on the audio bar below.";
      }} finally {{
        previewMusicButton.disabled = false;
      }}
    }}

    function shuffleMusic() {{
      const choices = musicOptions.filter((track) => track.file && track.file !== currentMusic.file);
      if (!choices.length) {{
        musicStatus.textContent = "No other approved music files are available yet.";
        return;
      }}
      const next = choices[Math.floor(Math.random() * choices.length)];
      setCurrentMusic(next, false);
      previewCurrentMusic();
    }}

    function acceptMusic() {{
      setCurrentMusic(currentMusic, true);
    }}

    previewMusicButton.addEventListener("click", previewCurrentMusic);
    shuffleMusicButton.addEventListener("click", shuffleMusic);
    acceptMusicButton.addEventListener("click", acceptMusic);
    previewVideoButton.addEventListener("click", createRoughPreview);
    exportButton.addEventListener("click", exportVideo);
    downloadButton.addEventListener("click", downloadVideo);
    loadSceneMedia();
  </script>
</body>
</html>"""


def _music_options_for_preview(campaign: Campaign) -> list[dict[str, object]]:
    settings = get_settings()
    try:
        tracks = list_music_tracks(settings)
    except Exception:
        return []

    desired_energy = _campaign_energy(campaign)
    options = []
    for track in tracks:
        path = settings.media_root / track.file.replace("/media/", "", 1) if track.file.startswith("/media/") else None
        if path is None or not path.exists():
            continue
        options.append(
            {
                "title": track.title,
                "file": track.file,
                "energy": track.energy,
                "defaultVolume": track.defaultVolume,
                "duckedVolume": track.duckedVolume,
                "bpm": track.bpm,
            }
        )

    options.sort(key=lambda track: 0 if track["energy"] == desired_energy else 1)
    return options[:24]


def _escape(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def save_upload(settings: Settings, campaign_id: str, filename: str, content: bytes) -> str:
    suffix = Path(filename or "asset.bin").suffix or ".bin"
    safe_name = f"{campaign_id}-{uuid4()}{suffix}"
    path = settings.media_root / "uploads" / safe_name
    path.write_bytes(content)
    return f"/media/uploads/{safe_name}"


def asset_type(filename: str, content_type: str | None) -> str:
    value = f"{filename} {content_type or ''}".lower()
    return "video" if any(token in value for token in [".mp4", ".mov", ".webm", "video/"]) else "image"


def _choose_scene_assets(campaign: Campaign, scene_count: int) -> list[CampaignAsset]:
    desired_format = _desired_format_key(campaign.format)
    fit_assets = [asset for asset in campaign.assets if _asset_fits_format(asset, desired_format)]
    assets = fit_assets or campaign.assets[:]
    if not assets:
        return []

    def score(asset: CampaignAsset, scene_index: int) -> int:
        analysis = asset.analysis
        use = analysis.recommendedUse if analysis else ""
        quality = asset.qualityScore or (analysis.qualityScore if analysis else 70)
        value = quality
        if scene_index == 0 and use == "hero":
            value += 18
        if scene_index in {2, 3} and use == "product_closeup":
            value += 18
        if scene_index in {1, 4} and use in {"b_roll", "hero"}:
            value += 10
        if asset.type == "video":
            value += 8
        if desired_format in asset.formatFit:
            value += 35
        elif asset.orientation != "unknown":
            value -= 45
        return value

    selected: list[CampaignAsset] = []
    used_ids: set[str] = set()
    for index in range(scene_count):
        candidates = sorted(assets, key=lambda item: score(item, index), reverse=True)
        pick = next((item for item in candidates if item.id not in used_ids), candidates[0])
        selected.append(pick)
        used_ids.add(pick.id)
    return selected


def _asset_fits_format(asset: CampaignAsset, desired_format: str) -> bool:
    return asset.orientation == "unknown" or desired_format in asset.formatFit


def _desired_format_key(format_name: str) -> str:
    return {
        "vertical_9_16": "vertical",
        "horizontal_16_9": "horizontal",
        "square_1_1": "square",
    }.get(format_name, "vertical")


def _format_fit_for_orientation(orientation: str) -> list[str]:
    if orientation == "vertical":
        return ["vertical", "square"]
    if orientation == "horizontal":
        return ["horizontal", "square"]
    if orientation == "square":
        return ["square", "vertical", "horizontal"]
    return ["vertical", "square", "horizontal"]


def _auto_format_for_assets(assets: list[CampaignAsset], current_format: str) -> str:
    counts = {"vertical": 0, "horizontal": 0, "square": 0}
    for asset in assets:
        if asset.orientation in counts:
            counts[asset.orientation] += 1
    if not any(counts.values()):
        return current_format
    winner = max(counts, key=counts.get)
    if counts[winner] == 0:
        return current_format
    return {
        "vertical": "vertical_9_16",
        "horizontal": "horizontal_16_9",
        "square": "square_1_1",
    }[winner]


def _render_geometry(format_name: str) -> dict[str, str | int]:
    if format_name == "horizontal_16_9":
        return {
            "width": 1920,
            "height": 1080,
            "preview_width": 760,
            "aspect_ratio": "16 / 9",
            "label": "16:9 web / iPad landscape",
        }
    if format_name == "square_1_1":
        return {
            "width": 1080,
            "height": 1080,
            "preview_width": 520,
            "aspect_ratio": "1 / 1",
            "label": "1:1 square social feed",
        }
    return {
        "width": 1080,
        "height": 1920,
        "preview_width": 420,
        "aspect_ratio": "9 / 16",
        "label": "9:16 phone / Reels / Shorts",
    }


def _orientation(width: int | None, height: int | None) -> str:
    if not width or not height:
        return "unknown"
    ratio = width / height
    if 0.82 <= ratio <= 1.22:
        return "square"
    return "horizontal" if ratio > 1.22 else "vertical"


def _creative_strategy(campaign: Campaign) -> dict[str, str]:
    energy = _campaign_energy(campaign)
    has_video = any(asset.type == "video" for asset in campaign.assets)
    has_fitness = any(
        asset.analysis and asset.analysis.fitnessSignals
        for asset in campaign.assets
    )
    has_product = any(
        asset.analysis and asset.analysis.recommendedUse == "product_closeup"
        for asset in campaign.assets
    )

    if energy == "high":
        voice_tone = "Energetic, confident fitness narrator"
        voice_recommendation = "Ask ElevenLabs for a bright, athletic voice with quick pacing, strong articulation, and a motivating but not shouty delivery."
        music_style = "Energetic licensed fitness pop, 112-124 BPM, light percussion, ducked under voiceover"
        music_rationale = "The uploaded media suggests movement and higher energy, so the track should create momentum in the first three seconds."
        hook = "Your next workout deserves a fresh finish."
        caption_hook = "Fresh fuel after movement"
        bridge = "Keep it simple: real ingredients, bright flavor, and a local stop that fits your routine."
    elif energy == "calm":
        voice_tone = "Calm, premium wellness narrator"
        voice_recommendation = "Ask ElevenLabs for a warm female or calm narrator voice with smooth pacing, soft emphasis, and a polished wellness tone."
        music_style = "Calm premium wellness groove, 82-96 BPM, warm keys, soft organic percussion"
        music_rationale = "The uploaded media feels more restorative, so the music should support trust, freshness, and local routine."
        hook = "Make your wellness routine feel simple."
        caption_hook = "Wellness made local"
        bridge = "Clean ingredients and calm choices can make wellness feel easier to keep close."
    else:
        voice_tone = "Friendly everyday wellness narrator"
        voice_recommendation = "Ask ElevenLabs for a friendly, natural voice that sounds local, clear, and conversational."
        music_style = "Upbeat wellness pop, 98-108 BPM, clean beat, optimistic but restrained"
        music_rationale = "The media has balanced lifestyle and product energy, so the track should hold attention without overpowering the food visuals."
        hook = "Fresh choices can fit the busiest days."
        caption_hook = "Fresh choices, local routine"
        bridge = "From product closeups to daily movement, make the better choice feel close and convenient."

    if has_video:
        music_rationale += " Uploaded video clips should anchor motion-heavy scenes."
    if has_fitness:
        voice_recommendation += " Emphasize active lifestyle words like movement, refuel, and routine."
    if has_product:
        music_rationale += " Product closeups should land on beat changes every few seconds."

    return {
        "energy": energy,
        "voice_tone": voice_tone,
        "voice_recommendation": voice_recommendation,
        "music_style": music_style,
        "music_rationale": music_rationale,
        "hook": hook,
        "caption_hook": caption_hook,
        "bridge": bridge,
        "selection_note": f"Creative choices selected from uploaded media energy: {energy}.",
    }


def _campaign_energy(campaign: Campaign) -> str:
    text = " ".join(asset.filename.lower() for asset in campaign.assets)
    high_tokens = ["gym", "run", "runner", "workout", "fitness", "crossfit", "tennis", "kickbox", "energy", "fast"]
    calm_tokens = ["yoga", "pilates", "calm", "senior", "family", "walk", "wellness", "soft", "premium"]
    high = sum(token in text for token in high_tokens)
    calm = sum(token in text for token in calm_tokens)
    if campaign.tone == "energetic" or high > calm:
        return "high"
    if campaign.tone in {"calm", "premium"} or calm > high:
        return "calm"
    return "balanced"


def _asset_url_for_scene(scene: Scene, asset_by_id: dict[str, CampaignAsset]) -> str:
    if not scene.assetIds:
        return ""
    asset = asset_by_id.get(scene.assetIds[0])
    return asset.url if asset else ""


def _asset_type_for_scene(scene: Scene, asset_by_id: dict[str, CampaignAsset]) -> str:
    if not scene.assetIds:
        return ""
    asset = asset_by_id.get(scene.assetIds[0])
    return asset.type if asset else ""


def _scene_media_markup(scene: Scene, asset_by_id: dict[str, CampaignAsset]) -> str:
    url = _asset_url_for_scene(scene, asset_by_id)
    asset_type = _asset_type_for_scene(scene, asset_by_id)
    if not url:
        return ""
    if asset_type == "video":
        return f'<video class="asset-media" src="{_escape(url)}" muted autoplay loop playsinline></video>'
    return f'<img class="asset-media" src="{_escape(url)}" alt="" />'


def _select_elevenlabs_voice_id(campaign: Campaign, settings: Settings) -> str | None:
    if not settings.elevenlabs_api_key:
        return None
    try:
        import httpx

        response = httpx.get(
            "https://api.elevenlabs.io/v1/voices",
            headers={"xi-api-key": settings.elevenlabs_api_key},
            timeout=12,
        )
        response.raise_for_status()
        voices = response.json().get("voices", [])
    except Exception:
        return None

    strategy = _creative_strategy(campaign)
    preferred_terms = {
        "high": ["energetic", "fitness", "confident", "bright", "young", "sports"],
        "calm": ["calm", "warm", "wellness", "premium", "soft", "narrator"],
        "balanced": ["friendly", "natural", "warm", "conversational"],
    }[strategy["energy"]]

    def voice_score(voice: dict) -> int:
        labels = voice.get("labels") or {}
        text = " ".join(
            [
                str(voice.get("name", "")),
                str(voice.get("description", "")),
                " ".join(str(value) for value in labels.values()),
            ]
        ).lower()
        return sum(term in text for term in preferred_terms)

    best = max(voices, key=voice_score, default=None)
    if best and voice_score(best) > 0:
        return best.get("voice_id")
    return None


def _voice_settings_for_campaign(campaign: Campaign) -> dict:
    energy = _campaign_energy(campaign)
    if energy == "high":
        return {"stability": 0.36, "similarity_boost": 0.82, "style": 0.68, "use_speaker_boost": True}
    if energy == "calm":
        return {"stability": 0.66, "similarity_boost": 0.86, "style": 0.24, "use_speaker_boost": True}
    return {"stability": 0.50, "similarity_boost": 0.84, "style": 0.42, "use_speaker_boost": True}


def _foods_from_text(text: str, focus: list[str]) -> list[str]:
    foods = [PRODUCT_LABELS[item] for item in focus if item in PRODUCT_LABELS]
    if any(token in text for token in ["smoothie", "juice", "acai", "bowl", "fruit", "green"]):
        return foods[:4] or ["smoothie", "fresh fruit"]
    return foods[:2]


def _asset_mood(text: str, campaign: Campaign) -> str:
    if any(token in text for token in ["gym", "run", "workout", "crossfit", "tennis", "kickbox"]):
        return "energetic and motivating"
    if any(token in text for token in ["yoga", "pilates", "calm", "walk", "family", "senior"]):
        return "calm and approachable"
    if any(token in text for token in ["smoothie", "juice", "acai", "bowl", "fruit", "green"]):
        return "fresh and appetizing"
    return _mood_for_tone(campaign.tone)


def _asset_vibe(text: str, campaign: Campaign) -> str:
    if any(token in text for token in ["store", "shop", "street", "front", "local"]):
        return "hyperlocal neighborhood wellness"
    if any(token in text for token in ["smoothie", "juice", "acai", "bowl", "fruit", "green"]):
        return "fresh product-forward wellness"
    if any(token in text for token in ["gym", "run", "workout", "yoga", "pilates"]):
        return "active lifestyle and post-movement refuel"
    return "fresh, active, neighborhood wellness"


def _asset_background_description(text: str, asset: CampaignAsset) -> str:
    media = "video clip" if asset.type == "video" else "photo"
    if any(token in text for token in ["smoothie", "juice", "acai", "bowl", "fruit", "green"]):
        return f"Uploaded {media} appears best suited for product-focused scenes and appetite appeal."
    if any(token in text for token in ["store", "shop", "street", "front", "local"]):
        return f"Uploaded {media} appears best suited for local context and opening hook scenes."
    if any(token in text for token in ["gym", "run", "workout", "yoga", "pilates"]):
        return f"Uploaded {media} appears best suited for active lifestyle pacing and audience relevance."
    return f"Uploaded {media} can support B-roll, transitions, or a caption-backed scene."


def _caption_for_asset(foods: list[str], campaign: Campaign) -> str:
    if foods:
        return f"Fresh {foods[0]} for active days"
    return f"{campaign.businessName} fits your local routine"


def _audiences(campaign: Campaign, fitness_only: bool = False) -> list[str]:
    labels = [AUDIENCE_LABELS.get(item, item.replace("_", " ")) for item in campaign.targetAudience]
    if fitness_only:
        return [label for label in labels if any(word in label for word in ["gym", "runner", "CrossFit", "tennis", "hiker"])] or labels
    return labels


def _products(campaign: Campaign) -> list[str]:
    return [PRODUCT_LABELS.get(item, item.replace("_", " ")) for item in campaign.productFocus]


def _mood_for_tone(tone: str) -> str:
    return {
        "energetic": "bright and motivating",
        "premium": "polished and confident",
        "calm": "calm and restorative",
        "educational": "clear and helpful",
        "inspirational": "uplifting and focused",
    }.get(tone, "fresh and welcoming")


def _visual_direction(index: int, campaign: Campaign, asset: CampaignAsset | None = None) -> str:
    if asset and asset.analysis:
        fit_note = f" It matches {campaign.format} as {asset.orientation} media." if asset.orientation != "unknown" else ""
        if asset.analysis.recommendedUse == "hero":
            return f"Use uploaded asset '{asset.filename}' as the opening/local hero with a subtle push-in and high-contrast caption.{fit_note}"
        if asset.analysis.recommendedUse == "product_closeup":
            return f"Use uploaded asset '{asset.filename}' as a product closeup; time the caption to the most appetizing visual moment.{fit_note}"
        if asset.type == "video":
            return f"Use uploaded video '{asset.filename}' for motion and retention; keep the overlay short and centered in the safe area.{fit_note}"
        return f"Use uploaded asset '{asset.filename}' as lifestyle B-roll with restrained motion and readable text.{fit_note}"
    directions = [
        "Use the strongest product or local exterior visual with a subtle push-in.",
        "Show neighborhood context or active-lifestyle B-roll with clean caption space.",
        "Feature a close product crop with bright ingredients and gentle motion.",
        "Highlight fruit, greens, or superfood detail without medical claims.",
        "Return to lifestyle rhythm: post-class, workday, family, or daily routine.",
        f"End on {campaign.businessName} branding, CTA, and a clear download-safe composition.",
    ]
    return directions[index % len(directions)]


def _quality_score(campaign: Campaign) -> int:
    base = 82
    if campaign.assets:
        base += 4
    if campaign.locationName or campaign.neighborhood:
        base += 4
    if len(campaign.productFocus) >= 2:
        base += 3
    return min(base, 96)


def _image_dimensions(path: Path) -> tuple[int | None, int | None]:
    try:
        with path.open("rb") as file:
            header = file.read(64)
            if header.startswith(b"\x89PNG\r\n\x1a\n"):
                return struct.unpack(">II", header[16:24])
            if header[:3] == b"\xff\xd8\xff":
                return _jpeg_dimensions(path)
            if header[:6] in {b"GIF87a", b"GIF89a"}:
                return struct.unpack("<HH", header[6:10])
            if header[:2] == b"BM":
                return struct.unpack("<II", header[18:26])
            if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
                return _webp_dimensions(path)
    except Exception:
        return None, None
    return None, None


def _jpeg_dimensions(path: Path) -> tuple[int | None, int | None]:
    try:
        with path.open("rb") as file:
            file.read(2)
            while True:
                marker_prefix = file.read(1)
                if marker_prefix != b"\xff":
                    return None, None
                marker = file.read(1)
                while marker == b"\xff":
                    marker = file.read(1)
                if marker in {b"\xc0", b"\xc1", b"\xc2", b"\xc3", b"\xc5", b"\xc6", b"\xc7", b"\xc9", b"\xca", b"\xcb", b"\xcd", b"\xce", b"\xcf"}:
                    file.read(3)
                    height, width = struct.unpack(">HH", file.read(4))
                    return width, height
                segment_length = struct.unpack(">H", file.read(2))[0]
                file.seek(segment_length - 2, 1)
    except Exception:
        return None, None


def _webp_dimensions(path: Path) -> tuple[int | None, int | None]:
    try:
        data = path.read_bytes()[:64]
        chunk = data[12:16]
        if chunk == b"VP8X":
            width = 1 + int.from_bytes(data[24:27], "little")
            height = 1 + int.from_bytes(data[27:30], "little")
            return width, height
        if chunk == b"VP8 ":
            width, height = struct.unpack("<HH", data[26:30])
            return width & 0x3FFF, height & 0x3FFF
        if chunk == b"VP8L":
            bits = int.from_bytes(data[21:25], "little")
            width = (bits & 0x3FFF) + 1
            height = ((bits >> 14) & 0x3FFF) + 1
            return width, height
    except Exception:
        return None, None
    return None, None
