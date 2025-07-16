import re


def clean_markdown(text):
    """
    清除markdown格式，输出纯文本
    处理完整和不完整的markdown语法
    """
    if not text:
        return text

    # 先处理一些特殊情况
    result = text

    # 清除标题语法 (# ## ### 等)
    result = re.sub(r'^#{1,6}\s*', '', result, flags=re.MULTILINE)

    # 清除粗体语法 **text** 和 __text__
    result = re.sub(r'\*\*(.*?)\*\*', r'\1', result)
    result = re.sub(r'__(.*?)__', r'\1', result)

    # 清除斜体语法 *text* 和 _text_
    result = re.sub(r'\*(.*?)\*', r'\1', result)
    result = re.sub(r'_(.*?)_', r'\1', result)

    # 清除行内代码 `code`
    result = re.sub(r'`(.*?)`', r'\1', result)

    # 清除链接语法 [text](url)
    result = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', result)

    # 清除图片语法 ![alt](url)
    result = re.sub(r'!\[(.*?)\]\(.*?\)', r'\1', result)

    # 清除删除线 ~~text~~
    result = re.sub(r'~~(.*?)~~', r'\1', result)

    # 清除代码块语法 ```
    result = re.sub(r'```[\s\S]*?```', '', result)
    result = re.sub(r'```.*', '', result)  # 处理不完整的代码块

    # 清除引用语法 >
    result = re.sub(r'^>\s*', '', result, flags=re.MULTILINE)

    # 清除无序列表语法 - * +
    result = re.sub(r'^[-*+]\s*', '', result, flags=re.MULTILINE)

    # 清除有序列表语法 1. 2. 等
    result = re.sub(r'^\d+\.\s*', '', result, flags=re.MULTILINE)

    # 清除不完整的markdown语法符号
    # 清除孤立的 * _ ** __ 等符号
    result = re.sub(r'(?<!\S)\*+(?!\S)', '', result)  # 孤立的星号
    result = re.sub(r'(?<!\S)_+(?!\S)', '', result)  # 孤立的下划线
    result = re.sub(r'(?<!\S)~+(?!\S)', '', result)  # 孤立的波浪线

    # 清除行首或行尾的不完整语法
    result = re.sub(r'^[\*_~`]+', '', result, flags=re.MULTILINE)
    result = re.sub(r'[\*_~`]+$', '', result, flags=re.MULTILINE)

    # 清除水平线语法
    result = re.sub(r'^[-*_]{3,}$', '', result, flags=re.MULTILINE)

    # 清除HTML标签（如果有）
    result = re.sub(r'<[^>]+>', '', result)

    # 清除多余的空行
    result = re.sub(r'\n\s*\n', '\n\n', result)

    # 清除行首行尾空白
    result = '\n'.join(line.strip() for line in result.split('\n'))

    return result.strip()


def clean_markdown_segments(segments):
    """
    处理分段的markdown文本列表
    """
    if not segments:
        return []

    # 先合并所有段落
    full_text = ''.join(segments)

    # 清理完整文本
    cleaned_full = clean_markdown(full_text)

    # 同时清理每个段落
    cleaned_segments = [clean_markdown(segment) for segment in segments]

    return cleaned_segments


def clean_special_symbols(text):
    """
    清除文本中的特殊符号
    """
    if not text:
        return text

    # 定义需要清除的特殊符号
    # 可以根据需要调整这个列表
    special_symbols = [
        # 常见标点符号变体
        "*","-","+"
    ]

    # 清除特殊符号
    result = text
    for symbol in special_symbols:
        result = result.replace(symbol, '')

    return result



# 测试示例
if __name__ == "__main__":
    # 测试单个文本
    test_text = "1.**你好,测试。**这是一个*斜体*文本和`代码`。"
    print("原文:", test_text)
    print("清理后:", clean_markdown(test_text))
    print()

    # 测试分段文本
    segments = ["1.**你好，", "测试。**", "这是*不完整", "的语法*"]
    print("分段原文:", segments)
    print("分段清理后:", clean_markdown_segments(segments))
    print()

    # 更多测试用例
    test_cases = [
        "# 标题\n**粗体**文本",
        "这是一个[链接](http://example.com)",
        "```python\nprint('hello')\n```",
        "- 列表项1\n- 列表项2",
        "**不完整的粗体",
        "*不完整的斜体",
        "~~删除线~~文本",
        "> 引用文本",
        "孤立的 ** 符号",
        "1. 有序列表\n2. 第二项"
    ]

    print("更多测试用例:")
    for i, case in enumerate(test_cases, 1):
        print(f"{i}. 原文: {repr(case)}")
        print(f"   清理后: {repr(clean_markdown(case))}")
        print()