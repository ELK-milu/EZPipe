from pydub import AudioSegment
from io import BytesIO


def convert_audio_to_wav(audio_bytes: bytes) -> bytes:
    """将任意音频字节流转换为标准WAV格式

    参数：
        audio_bytes: 输入的原始音频字节流

    返回：
        bytes: 标准化后的WAV格式字节流（单声道/16kHz/16位）
    """
    # 从字节流加载音频（自动识别格式）
    audio = AudioSegment.from_file(BytesIO(audio_bytes))
    # 创建输出缓冲区
    wav_buffer = BytesIO()
    # 转换为标准WAV格式
    audio.export(wav_buffer,
                 format="wav",
                 parameters=[
                     "-ac", "1",  # 单声道
                     "-ar", "24000",  # 24kHz采样率
                     "-sample_fmt", "s16"  # 16位深度
                 ])
    return wav_buffer.getvalue()
