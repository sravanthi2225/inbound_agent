from api.services.configuration.registry import SarvamTTSConfiguration

# Languages Sarvam's /text-to-speech accepts: 10 Indian languages plus English,
# per https://docs.sarvam.ai/api-reference-docs/text-to-speech/convert (the same
# 11 codes as sarvamai's TextToSpeechLanguage).
SARVAM_TTS_SUPPORTED = {
    "bn-IN",
    "en-IN",
    "gu-IN",
    "hi-IN",
    "kn-IN",
    "ml-IN",
    "mr-IN",
    "od-IN",
    "pa-IN",
    "ta-IN",
    "te-IN",
}


def test_sarvam_tts_offers_only_languages_sarvam_can_speak():
    # service_factory maps an unknown code to Language.HI, so offering a code
    # Sarvam TTS lacks makes the agent speak Hindi without any error.
    offered = SarvamTTSConfiguration.model_json_schema()["properties"]["language"][
        "examples"
    ]
    assert offered and set(offered) <= SARVAM_TTS_SUPPORTED


def test_sarvam_tts_auto_detects_language_script():
    from pipecat.services.sarvam.tts import detect_script_language

    assert detect_script_language("నమస్కారం, డాక్టర్ శర్మతో అపాయింట్‌మెంట్ కావాలి") == "te-IN"
    assert detect_script_language("नमस्ते, डॉक्टर से मिलना है") == "hi-IN"
    assert detect_script_language("I want to book an appointment") == "en-IN"
    assert detect_script_language("வணக்கம்") == "ta-IN"
    assert detect_script_language("ನಮಸ್ಕಾರ") == "kn-IN"

