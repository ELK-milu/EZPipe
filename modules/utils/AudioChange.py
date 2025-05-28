from io import BytesIO

import soundfile as sf
import numpy as np
import resampy
from .logger import get_logger

logger = get_logger(__name__)

def convert_audio_to_wav(audio_bytes: bytes,set_sample_rate: int) -> bytes:
    """将任意音频字节流转换为标准WAV格式的字节流

    参数：
        audio_bytes: 输入的原始音频字节流

    返回：
        bytes: 标准化后的WAV格式字节流（单声道/16kHz/16位）
    """
    # 从字节流加载音频（自动识别格式）
    try:
        with BytesIO(audio_bytes) as input_stream, BytesIO() as output_stream:
            stream, sample_rate = sf.read(input_stream)
            logger.info(f'[INFO]put audio stream {sample_rate}: {stream.shape}')

            if sample_rate == set_sample_rate:
                return audio_bytes

            stream = stream.astype(np.float32)

            if stream.ndim > 1:
                logger.info(f'[WARN] audio has {stream.shape[1]} channels, only use the first.')
                stream = stream[:, 0]

            if stream.shape[0] > 0:
                logger.info(f'[WARN] audio sample rate is {sample_rate}, resampling into {set_sample_rate}.')
                stream = resampy.resample(x=stream, sr_orig=sample_rate, sr_new=set_sample_rate)

            sf.write(output_stream, stream, samplerate=set_sample_rate,
                     subtype='PCM_16', format='WAV', closefd=False)
            return output_stream.getvalue()
    except Exception as e:
        logger.error(f"[ERROR] 音频转换失败: {str(e)}")
        return audio_bytes

