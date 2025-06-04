import json
import os
import re
import time
from SovitsPost import PostChat


class SoVITSBatchGenerator:
    def __init__(self, ref_audio_path, prompt_text, output_dir="generated_audio"):
        """
        初始化批量生成器

        Args:
            ref_audio_path: 参考音频路径
            prompt_text: 提示文本
            output_dir: 输出目录
        """
        self.ref_audio_path = ref_audio_path
        self.prompt_text = prompt_text
        self.output_dir = output_dir

        # 创建输出目录
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"创建输出目录: {output_dir}")

    def sanitize_filename(self, filename):
        """
        清理文件名，移除不允许的字符

        Args:
            filename: 原始文件名

        Returns:
            清理后的安全文件名
        """
        # 替换Windows和Linux文件名中不允许的字符
        filename = re.sub(r'[\\/*?:"<>|]', "_", filename)
        # 移除连续的点和空格
        filename = re.sub(r'\.{2,}', ".", filename)
        filename = re.sub(r' {2,}', " ", filename)
        # 移除开头和结尾的空格和点
        filename = filename.strip(". ")
        # 限制文件名长度
        if len(filename) > 100:
            filename = filename[:100]
        return filename

    def generate_single_audio(self, emotion, text, index=None):
        """
        生成单个音频文件

        Args:
            emotion: 情感类型
            text: 要合成的文本
            index: 文本索引（可选）

        Returns:
            bool: 是否生成成功
        """
        try:
            # 生成文件名
            safe_text = self.sanitize_filename(text)
            if index is not None:
                filename = f"{emotion}_{index:03d}_{safe_text[:50]}.wav"
            else:
                filename = f"{emotion}_{safe_text[:50]}.wav"

            filepath = os.path.join(self.output_dir, filename)

            # 检查文件是否已存在
            if os.path.exists(filepath):
                print(f"文件已存在，跳过: {filename}")
                return True

            # 发送TTS请求
            print(f"正在生成: {emotion} - {text[:30]}...")
            start_time = time.time()

            chat = PostChat(
                streamly=False,
                user="batch_generator",
                text=text,
                ref_audio_path="./GPT_SoVITS/models/佼佼仔_中立.wav",
                prompt_text="今天，我将带领大家穿越时空，去到未来的杭州。"
            )

            response = chat.GetResponse()
            elapsed = time.time() - start_time

            # 检查响应状态
            if response.status_code == 200:
                # 保存音频文件
                with open(filepath, "wb") as f:
                    f.write(response.content)
                print(f"✓ 生成成功: {filename} (耗时: {elapsed:.2f}秒)")
                return True
            else:
                print(f"✗ 生成失败: {filename}, 状态码: {response.status_code}")
                print(f"错误信息: {response.text}")
                return False

        except Exception as e:
            print(f"✗ 生成异常: {emotion} - {text[:30]}..., 错误: {str(e)}")
            return False

    def generate_batch_audio(self, samples_file="samples.json", emotions=None, max_per_emotion=None):
        """
        批量生成音频文件

        Args:
            samples_file: samples.json文件路径
            emotions: 指定要生成的情感列表，None表示全部
            max_per_emotion: 每种情感最多生成的数量，None表示全部
        """
        try:
            # 读取samples.json文件
            with open(samples_file, 'r', encoding='utf-8') as f:
                samples = json.load(f)
            print(f"成功读取样本文件: {samples_file}")

            # 统计信息
            total_generated = 0
            total_failed = 0

            # 遍历每种情感
            for emotion, texts in samples.items():
                # 检查是否需要生成这种情感
                if emotions and emotion not in emotions:
                    print(f"跳过情感: {emotion}")
                    continue

                print(f"\n开始生成情感类型: {emotion} (共{len(texts)}条)")

                # 限制每种情感的生成数量
                texts_to_process = texts
                if max_per_emotion and len(texts) > max_per_emotion:
                    texts_to_process = texts[:max_per_emotion]
                    print(f"限制生成数量为: {max_per_emotion}")

                # 为每种情感创建子目录
                emotion_dir = os.path.join(self.output_dir, emotion)
                if not os.path.exists(emotion_dir):
                    os.makedirs(emotion_dir)

                # 生成该情感的所有文本
                emotion_success = 0
                for i, text in enumerate(texts_to_process, 1):
                    # 更新文件路径到情感子目录
                    original_output_dir = self.output_dir
                    self.output_dir = emotion_dir

                    success = self.generate_single_audio(emotion, text, i)

                    # 恢复原始输出目录
                    self.output_dir = original_output_dir

                    if success:
                        emotion_success += 1
                        total_generated += 1
                    else:
                        total_failed += 1

                    # 添加延迟避免请求过于频繁
                    time.sleep(0.5)

                print(f"情感 {emotion} 完成: 成功 {emotion_success}/{len(texts_to_process)}")

            # 输出总结
            print(f"\n" + "=" * 50)
            print(f"批量生成完成!")
            print(f"总成功: {total_generated}")
            print(f"总失败: {total_failed}")
            print(f"输出目录: {os.path.abspath(self.output_dir)}")
            print(f"=" * 50)

        except FileNotFoundError:
            print(f"错误: 找不到文件 {samples_file}")
        except json.JSONDecodeError:
            print(f"错误: {samples_file} 不是有效的JSON文件")
        except Exception as e:
            print(f"批量生成异常: {str(e)}")


def main():
    """
    主函数 - 配置和启动批量生成
    """
    # 配置参数
    REF_AUDIO_PATH = "./GPT_SoVITS/models/佼佼仔_中立.wav"  # 参考音频路径
    PROMPT_TEXT = "今天，我将带领大家穿越时空，去到未来的杭州。"  # 提示文本
    OUTPUT_DIR = "./GeneralAudio"  # 输出目录
    SAMPLES_FILE = "samples.json"  # 样本文件路径

    # 可选配置
    SPECIFIC_EMOTIONS = None  # ["中立", "开心"]  # 指定生成的情感，None表示全部
    MAX_PER_EMOTION = None  # 5  # 每种情感最多生成数量，None表示全部

    print("SoVITS 批量音频生成器")
    print(f"参考音频: {REF_AUDIO_PATH}")
    print(f"提示文本: {PROMPT_TEXT}")
    print(f"输出目录: {OUTPUT_DIR}")
    print(f"样本文件: {SAMPLES_FILE}")


    # 检查样本文件是否存在
    if not os.path.exists(SAMPLES_FILE):
        print(f"错误: 样本文件不存在: {SAMPLES_FILE}")
        return

    # 创建生成器并开始生成
    generator = SoVITSBatchGenerator(
        ref_audio_path=REF_AUDIO_PATH,
        prompt_text=PROMPT_TEXT,
        output_dir=OUTPUT_DIR
    )

    # 开始批量生成
    generator.generate_batch_audio(
        samples_file=SAMPLES_FILE,
        emotions=SPECIFIC_EMOTIONS,
        max_per_emotion=MAX_PER_EMOTION
    )


if __name__ == "__main__":
    main()