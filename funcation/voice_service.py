"""
语音服务模块
支持Edge TTS（免费）和本地TTS切换
"""
import asyncio
import io
import logging
import os
from typing import Dict, Optional, Union
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class TTSProvider(Enum):
    """TTS提供商枚举"""
    EDGE = "edge"
    COQUI = "coqui"
    # 可以添加更多TTS提供商

@dataclass
class VoiceConfig:
    """语音配置"""
    provider: TTSProvider = TTSProvider.EDGE
    voice_name: str = "zh-CN-XiaoxiaoNeural"
    speaking_rate: float = 1.0
    pitch: float = 0.0
    volume: float = 1.0

class VoiceService:
    """语音服务类"""

    def __init__(self):
        self.config = self._load_config()
        self.cache: Dict[str, bytes] = {}  # 简单的内存缓存

    def _load_config(self) -> VoiceConfig:
        """加载语音配置"""
        provider_str = os.getenv("TTS_PROVIDER", "edge")
        provider = TTSProvider(provider_str)

        # 根据提供商获取不同的默认语音
        voice_map = {
            TTSProvider.EDGE: {
                "linwan": "zh-CN-XiaoxiaoNeural",
                "maid": "zh-CN-XiaoxueNeural",
                "xiaomei": "zh-CN-XiaomengNeural"
            },
            TTSProvider.COQUI: {
                "linwan": "female_en",
                "maid": "female_en",
                "xiaomei": "female_en"
            }
        }

        default_voice = voice_map.get(provider, {}).get("linwan", "zh-CN-XiaoxiaoNeural")

        return VoiceConfig(
            provider=provider,
            voice_name=os.getenv("VOICE_NAME", default_voice),
            speaking_rate=float(os.getenv("SPEAKING_RATE", "1.0")),
            pitch=float(os.getenv("PITCH", "0.0")),
            volume=float(os.getenv("VOLUME", "1.0"))
        )

    async def synthesize_speech(self, text: str, character_id: str, config: Optional[VoiceConfig] = None) -> bytes:
        """合成语音"""
        if config is None:
            config = self.config

        # 生成缓存键
        cache_key = f"{character_id}_{hash(text)}"

        # 检查缓存
        if cache_key in self.cache:
            logger.debug(f"Using cached audio for character {character_id}")
            return self.cache[cache_key]

        # 根据提供商选择TTS方法
        if config.provider == TTSProvider.EDGE:
            audio_data = await self._edge_tts(text, character_id, config)
        elif config.provider == TTSProvider.COQUI:
            audio_data = await self._coqui_tts(text, character_id, config)
        else:
            raise ValueError(f"Unsupported TTS provider: {config.provider}")

        # 缓存结果（限制缓存大小）
        if len(self.cache) < 100:  # 最多缓存100个音频
            self.cache[cache_key] = audio_data

        return audio_data

    async def _edge_tts(self, text: str, character_id: str, config: VoiceConfig) -> bytes:
        """使用Edge TTS合成语音"""
        try:
            # 动态导入，避免在没有edge-tts时报错
            from edge_tts import Communicate

            # 根据角色获取语音
            character_voices = {
                "linwan": "zh-CN-XiaoxiaoNeural",
                "maid": "zh-CN-XiaoxueNeural",
                "xiaomei": "zh-CN-XiaomengNeural"
            }

            voice = character_voices.get(character_id, config.voice_name)

            # 创建Communicate实例
            # Edge TTS rate/volume 格式: "+0%", "+10%", "-20%"
            rate_pct = int((config.speaking_rate - 1.0) * 100)
            rate_str = f"{rate_pct:+d}%"
            pitch_pct = int(config.pitch)
            pitch_str = f"{pitch_pct:+d}Hz"
            volume_pct = int((config.volume - 1.0) * 100)
            volume_str = f"{volume_pct:+d}%"
            communicate = Communicate(
                text=text,
                voice=voice,
                rate=rate_str,
                pitch=pitch_str,
                volume=volume_str,
            )

            # 使用内存流保存音频
            audio_bytes = io.BytesIO()

            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_bytes.write(chunk["data"])

            return audio_bytes.getvalue()

        except ImportError:
            logger.error("edge-tts not installed. Install with: pip install edge-tts")
            raise
        except Exception as e:
            logger.error(f"Edge TTS error: {e}")
            raise

    async def _coqui_tts(self, text: str, character_id: str, config: VoiceConfig) -> bytes:
        """使用Coqui TTS合成语音（本地）"""
        try:
            # 动态导入
            from TTS.api import TTS

            # 初始化TTS
            tts = TTS(model_name="tts_models/multilingual/multi-dataset/your_tts", progress_bar=False)

            # 保存到内存
            audio_bytes = io.BytesIO()

            # 生成语音
            tts.tts_to_file(
                text=text,
                speaker=tts.speakers[0] if tts.speakers else None,
                language=config.voice_name,
                file_object=audio_bytes
            )

            return audio_bytes.getvalue()

        except ImportError:
            logger.error("coqui-TTS not installed. Install with: pip install TTS")
            raise
        except Exception as e:
            logger.error(f"Coqui TTS error: {e}")
            raise

    async def get_available_voices(self, character_id: str) -> Dict[str, str]:
        """获取可用的语音列表"""
        voices = {
            "edge": {
                "linwan": "zh-CN-XiaoxiaoNeural (晓晓)",
                "maid": "zh-CN-XiaoxueNeural (晓雪)",
                "xiaomei": "zh-CN-XiaomengNeural (晓梦)"
            },
            "coqui": {
                "linwan": "female_en (英语女声)",
                "maid": "female_en (英语女声)",
                "xiaomei": "female_en (英语女声)"
            }
        }

        return voices.get(self.config.provider.value, {})

    def clear_cache(self):
        """清除音频缓存"""
        self.cache.clear()

# 全局语音服务实例
voice_service = VoiceService()