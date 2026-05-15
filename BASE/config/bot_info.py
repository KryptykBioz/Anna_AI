# Filename: BASE/config/bot_info.py
"""
Bot identity shim.
All values now live in personality/config.json.
This module re-exports them from the Config singleton so existing imports
across the codebase continue to work unchanged.
"""
from BASE.core.config import Config

_cfg = Config()

agentname     = _cfg.agentname
username      = _cfg.username
game_username = _cfg.game_username

thoughtmodel  = _cfg.thought_model
responsemodel = _cfg.text_model
visionmodel   = _cfg.vision_model
embedmodel    = _cfg.embed_model
toolmodel     = _cfg.tool_model
actionmodel   = _cfg.action_model

voiceIndex    = _cfg.voice_index
vb_cable_name = _cfg.vb_cable_name
voice_sample_filename      = _cfg.voice_sample_filename
user_voice_sample_filename = _cfg.user_voice_sample_filename
xtts_language             = _cfg.xtts_language
xtts_speed                = _cfg.xtts_speed
xtts_temperature          = _cfg.xtts_temperature
xtts_length_penalty       = _cfg.xtts_length_penalty
xtts_repetition_penalty   = _cfg.xtts_repetition_penalty
xtts_top_k                = _cfg.xtts_top_k
xtts_top_p                = _cfg.xtts_top_p
xtts_gpt_cond_len         = _cfg.xtts_gpt_cond_len
xtts_gpt_cond_chunk_len   = _cfg.xtts_gpt_cond_chunk_len
xtts_max_ref_length       = _cfg.xtts_max_ref_length

group_chat_port = _cfg.group_chat_port