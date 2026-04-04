# Filename: BASE/handlers/content_filter.py
"""
Content filtering with profanity replacement for incoming/outgoing data
Key features:
- Replaces profanities with "[filtered]" instead of blocking
- LRU caching for performance
- Pre-compiled regex patterns
- Applies to ALL incoming data (chat, voice, user input)
- Optional AI-based semantic filtering
"""

import re
import requests
from typing import Tuple, Optional
from pathlib import Path
from functools import lru_cache
import hashlib


class ContentFilter:
    """Content filtering with profanity replacement"""
    
    __slots__ = (
        'ollama_endpoint', 'use_ai_filter', 'profanity_patterns',
        'hate_speech_patterns', 'controversial_patterns', '_ai_cache_maxsize'
    )
    
    def __init__(self, ollama_endpoint: str = "http://127.0.0.1:11434", use_ai_filter: bool = True):
        self.ollama_endpoint = ollama_endpoint
        self.use_ai_filter = use_ai_filter
        
        # Pre-compiled patterns (loaded once)
        self.profanity_patterns = self._load_profanity_patterns()
        self.hate_speech_patterns = self._load_hate_speech_patterns()
        self.controversial_patterns = self._load_controversial_patterns()
        
        # AI filter result cache (avoid repeated API calls)
        self._ai_cache_maxsize = 1000
    
    def _load_profanity_patterns(self) -> list:
        """Pre-compile patterns at initialization"""
        patterns = [
            r'\bf+u+c+k+\w*', r'\bs+h+i+t+\w*', r'\bb+i+t+c+h+\w*', r'\ba+s+s+h+o+l+e+\w*',
            r'\bd+a+m+n+\w*', r'\bh+e+l+l+\b', r'\bc+r+a+p+\w*', r'\bp+i+s+s+\w*',
            r'\bc+u+n+t+\w*', r'\bd+i+c+k+\w*', r'\bc+o+c+k+\w*', r'\bp+u+s+s+y+\w*',
            r'\bs+l+u+t+\w*', r'\bw+h+o+r+e+\w*',
        ]
        return [re.compile(p, re.IGNORECASE) for p in patterns]
    
    def _load_hate_speech_patterns(self) -> list:
        patterns = [
            r'\bn+i+g+g+e+r+\w*', r'\bf+a+g+g+o+t+\w*', r'\br+e+t+a+r+d+\w*',
            r'\bk+i+k+e+\w*', r'\bg+o+o+k+\w*', r'\bc+h+i+n+k+\w*',
            r'kill yourself', r'kys\b', r'die in a fire',
        ]
        return [re.compile(p, re.IGNORECASE) for p in patterns]
    
    def _load_controversial_patterns(self) -> list:
        patterns = [
            r'holocaust.{0,20}(hoax|fake|didn)',
            r'(white|black|racial).{0,30}supremac',
            r'(nazi|hitler).{0,20}(right|good|based)',
            r'(genocide|ethnic cleansing).{0,20}(justified|good)',
        ]
        return [re.compile(p, re.IGNORECASE) for p in patterns]
    
    def _replace_profanities(self, text: str) -> Tuple[str, bool, list]:
        """
        Replace profanities with [filtered] tag
        
        Returns:
            (cleaned_text, was_filtered, matched_categories)
        """
        cleaned_text = text
        was_filtered = False
        matched_categories = []
        
        # Check profanity (most common)
        for pattern in self.profanity_patterns:
            if pattern.search(cleaned_text):
                cleaned_text = pattern.sub("[filtered]", cleaned_text)
                was_filtered = True
                if "profanity" not in matched_categories:
                    matched_categories.append("profanity")
        
        # Check hate speech
        for pattern in self.hate_speech_patterns:
            if pattern.search(cleaned_text):
                cleaned_text = pattern.sub("[filtered]", cleaned_text)
                was_filtered = True
                if "hate_speech" not in matched_categories:
                    matched_categories.append("hate_speech")
        
        # Check controversial content
        for pattern in self.controversial_patterns:
            if pattern.search(cleaned_text):
                cleaned_text = pattern.sub("[filtered]", cleaned_text)
                was_filtered = True
                if "controversial" not in matched_categories:
                    matched_categories.append("controversial")
        
        return cleaned_text, was_filtered, matched_categories
    
    @lru_cache(maxsize=1000)
    def _get_text_fingerprint(self, text: str) -> str:
        """Generate fuzzy hash for similar text matching"""
        normalized = ' '.join(text.lower().split())
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]
    
    @lru_cache(maxsize=1000)
    def _check_with_ai_cached(self, text_fingerprint: str, text: str) -> Tuple[bool, str]:
        """Cached AI filter check - avoids redundant API calls"""
        if not self.use_ai_filter:
            return False, ""
        
        try:
            filter_prompt = f"""Analyze this text for harmful content. Respond with ONLY ONE WORD:
- "SAFE" if acceptable
- "PROFANITY" if explicit profanity
- "HATE" if hate speech/slurs
- "CONTROVERSIAL" if harmful ideologies
- "SAFE" for all other cases

Text: "{text}"

Response (one word only):"""

            payload = {
                "model": "llama3.2:3b",
                "prompt": filter_prompt,
                "stream": False,
                "temperature": 0.1,
                "max_tokens": 10,
                "stop": ["\n", ".", ","]
            }
            
            response = requests.post(
                f"{self.ollama_endpoint}/api/generate",
                json=payload,
                timeout=3
            )
            
            if response.status_code == 200:
                result = response.json()
                ai_response = result.get("response", "").strip().upper()
                
                if "PROFANITY" in ai_response:
                    return True, "profanity"
                elif "HATE" in ai_response:
                    return True, "hate_speech"
                elif "CONTROVERSIAL" in ai_response:
                    return True, "controversial"
            
            return False, ""
            
        except requests.Timeout:
            return False, ""
        except Exception as e:
            print(f"[Filter] AI check error: {e}")
            return False, ""
    
    def filter_incoming(self, text: str, log_callback=None) -> Tuple[str, bool, str]:
        """
        Filter incoming data (chat, voice, user input)
        REPLACES profanities instead of blocking
        
        Args:
            text: Incoming text to filter
            log_callback: Optional logging function
            
        Returns:
            (cleaned_text, was_filtered, filter_reason)
        """
        if not text or not text.strip():
            return text, False, ""
        
        # STEP 1: Pattern-based replacement (fast)
        cleaned_text, was_filtered, categories = self._replace_profanities(text)
        
        if was_filtered:
            reason = ", ".join(categories)
            if log_callback:
                log_callback(f"[Filter] Replaced {reason} in incoming data")
            return cleaned_text, True, reason
        
        # STEP 2: AI semantic check (if enabled and no keyword matches)
        if self.use_ai_filter:
            fingerprint = self._get_text_fingerprint(text)
            needs_filtering, reason = self._check_with_ai_cached(fingerprint, text)
            
            if needs_filtering:
                # AI detected semantic issues - replace entire message
                if log_callback:
                    log_callback(f"[Filter] AI detected {reason} - filtering")
                return "[filtered]", True, reason
        
        return text, False, ""
    
    def filter_outgoing(self, text: str, log_callback=None) -> Tuple[str, bool, str]:
        """
        Filter outgoing data (agent responses)
        More lenient - only blocks severe violations
        
        Args:
            text: Outgoing text to filter
            log_callback: Optional logging function
            
        Returns:
            (cleaned_text, was_filtered, filter_reason)
        """
        if not text or not text.strip():
            return text, False, ""
        
        # Only check hate speech and controversial for outgoing
        cleaned_text = text
        was_filtered = False
        matched_categories = []
        
        for pattern in self.hate_speech_patterns:
            if pattern.search(cleaned_text):
                cleaned_text = pattern.sub("[filtered]", cleaned_text)
                was_filtered = True
                if "hate_speech" not in matched_categories:
                    matched_categories.append("hate_speech")
        
        for pattern in self.controversial_patterns:
            if pattern.search(cleaned_text):
                cleaned_text = pattern.sub("[filtered]", cleaned_text)
                was_filtered = True
                if "controversial" not in matched_categories:
                    matched_categories.append("controversial")
        
        if was_filtered:
            reason = ", ".join(matched_categories)
            if log_callback:
                log_callback(f"[Filter] Replaced {reason} in outgoing data")
            return cleaned_text, True, reason
        
        return text, False, ""
    
    def filter_content(self, text: str, log_callback=None, direction: str = "incoming") -> Tuple[str, bool, str]:
        """
        Universal filter that routes to incoming or outgoing
        
        Args:
            text: Text to filter
            log_callback: Optional logging function
            direction: "incoming" or "outgoing"
            
        Returns:
            (cleaned_text, was_filtered, filter_reason)
        """
        if direction == "outgoing":
            return self.filter_outgoing(text, log_callback)
        else:
            return self.filter_incoming(text, log_callback)
    
    def remove_emoji(self, text: str) -> str:
        """Remove emoji characters from text"""
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags (iOS)
            "\U00002702-\U000027B0"  # dingbats
            "\U000024C2-\U0001F251"  # enclosed characters
            "]+",
            flags=re.UNICODE
        )
        return emoji_pattern.sub(r'', text)
    
    def update_ai_filter_setting(self, enabled: bool):
        """Update AI filter setting and clear cache if disabled"""
        self.use_ai_filter = enabled
        if not enabled:
            self._get_text_fingerprint.cache_clear()
            self._check_with_ai_cached.cache_clear()
    
    def get_cache_stats(self) -> dict:
        """Get cache performance statistics"""
        return {
            'fingerprint_cache': self._get_text_fingerprint.cache_info()._asdict(),
            'ai_filter_cache': self._check_with_ai_cached.cache_info()._asdict(),
        }
    
    def clear_caches(self):
        """Manually clear all caches"""
        self._get_text_fingerprint.cache_clear()
        self._check_with_ai_cached.cache_clear()