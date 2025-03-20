# EZPipe 🚰

一个高度自定义化的可并发的流式响应的PipeLine服务框架。可用于AI服务间的交互。

## 诞生背景

这个模块最初的诞生目的是为了解决一个语音交互AGENT的场景，众所周知语音交互的整个流程是ASR->LLM->TTS。最初的设计是以各个服务的请求信息互通作为交互逻辑的。但是在开发的过程中，由于尝试了很多不同的方案，而且模型是完全本地部署的，因此就有了很多问题：

- 比如我想要用Dify来做一个语音交互的AGENT流程，但是Dify返回的响应通常只有最终结果，我想要进行流式的语音传输来提高响应速度，或者想要本地搭建的服务端使用websocket服务嵌入到dify的工作流里就很难实现了。

- 在使用这些模型进行二次开发的时候，我选择了搭建服务端，再向服务端收发请求，但是服务端的请求在不同前端处理也很麻烦，unity，python，UE，JavaScript......这些前端的语言各不相同，如果从项目管理的视角来看，如果全部把请求放在前端处理，那么显然是不适合的。

- 在用Unity的时候有一些较为灵活的需求：例如生成文字时需要实时显示，然后进行语音识别时需要实时显示识别的文字。这样的工作用dify也挺难实现。

出于这些诸多的考虑，我编写了EZPipe，这个框架的诞生是为了解决以上问题的，它允许用户自定义各种pipe，服务模块，以及服务端，然后通过pipe的组合，实现各种复杂的逻辑。在向服务端发送请求后，由于这个pipeline内部的Module是支持并行的，因此服务端可以返回给用户混合的数据，用户只需要通过流式响应逐条接收数据并将其分类到相应的队列，就可以在客户端自定义处理逻辑。并且支持客户端的数据从服务端的Pipeline中任意入口进入，大大提高了灵活性。

------

## 特性

- 内外输出逻辑分离——数据在pipeline内的传输逻辑是分离的，你可以让Module将处理好的数据一边用json包装成响应格式让服务端返回流式响应；一边将未包装的数据传递给下一个功能模块。就不需要在客户端将不同API返回的请求拆包再封装传递
- 并行逻辑——想要实现快速响应需要使用流式传输，由于内部的每个Module都由用户专属的独立的线程进行管理，因此可以独立工作，你可以将流式收到的对话以每句为终点传输给TTS Module，实现逐句合成。并同时向响应队列返回文字chunk和音频chunk。你就可以在客户端一边接收文字一边播放音频了
- 模块化设计——模块是独立的，你可以将Module进行组合，实现各种复杂的逻辑，比如将ASR Module和TTS Module组合成一个完整的语音交互模块，或者将ASR Module和LLM Module组合成一个完整的对话模块。只需要保证模块连接时的输出类型和输出类型匹配即可。由于不同模块是高度解耦的，只负责单一服务。所以你可以在任何地方调用这些模块。配合docker使用可以快速部署。
- 高自由度——你可以使用预设的Module，也可以自己编写Module，只需要为模块设置好处理逻辑以及参数输出即可。包括Pipeline和API Service也可以通过继承并实现抽象方法和重写函数实现自定义，这完全取决于你的需要。
- 完全支持——较优的实现方式是直接调用Post或者Get或者ws请求来实现模块，这样可以将模型的服务端进行分离。所以对于所有模型都是完全支持的，只要你肯写代码。

--------

## 快速开始

在pipeline目录下输入下列命令启动服务

```bash
python Pipeline.py --host 127.0.0.1 --port 3421
```

你可以通过在代码中添加或删除模块来选择pipeline启用的服务：
```python
pipeline = PipeLine.create_pipeline(
    Ollama_LLM_Module,
    GPTSoVit_TTS_Module
)
```

服务启动时会根据你当前使用的Pipeline进行连接可行性验证，只需要保证模型需要的输入类型和输出类型相符即可：

```bash
✅ Pipeline验证通过
当前Pipeline: Ollama_LLM_Module -> GPTSoVit_TTS_Module
类型详情:
Ollama_LLM_Module (输入: <class 'str'>, 输出: <class 'str'>)
GPTSoVit_TTS_Module (输入: <class 'str'>, 输出: <class 'bytes'>)
```

在自定义模块的时候，需要继承基类`BaseModule`,并实现抽象方法：
```python
    # 每个子模块需要实现的抽象方法，自定义输入数据，返回服务端请求体处理后的数据
    @abstractmethod
    def HandleInput(self,request: Any) -> Any:
        processed_data = request
        return processed_data

    @abstractmethod
    def Thread_Task(self, streamly: bool, user: str, input_data: Any, response_func, next_func) -> Any:
        """模块的主要处理逻辑，子类必须实现"""
        # 在定义这个方法的时候需要指定input_data和函数输出的类型，用于pipeline检验当前模块所需的输入输出类型
        pass
```


服务端的post请求所需的基础参数如下：

```bash
    class APIRequest(BaseModel):
        """API请求模型"""
        streamly: bool = False  # 是否流式输出
        user: str  # 用户标识
        Input: Any  # 输入数据
        Entry: int
```

`streamly`代表了是否是流式请求(服务端目前返回的始终是流式的)。

`user`是用户标识，通过user名这一字符串来管理用户线程和请求

`Input`是输入，可以是任何类型，也可以由你指定（我建议以Any类型输出，因为不同的Entry所需的输入类型不同）

`Entry`是服务入口，以0为起点。通过这个标识来告知服务器你的请求是从哪个模块进入的

你可以通过继承`BasePipeAPI`然后重写内部类`APIRequest`来实现自己的请求体，通过[http://127.0.0.1:3421/schema](http://127.0.0.1:3421/schema)来查看你当前服务的请求体

------------

## 贡献者

欢迎来为这个项目作出贡献，杰出的贡献者将会被口头表扬

<table>
    <tr>
        <td align="center">
            <a href="https://github.com/ELK-milu">
                <img src="https://avatars.githubusercontent.com/u/56761558?v=4" width="100px;" alt="" style="max-width: 100%;">
                <br>
                <sub>
                    <b>ELK-milu</b>
                </sub>
            </a>
        </td>
    </tr>
</table>

