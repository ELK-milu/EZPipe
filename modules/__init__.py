# 模块的调用逻辑：所有的基础服务模块继承于BaseModule，可高度自定义，本质上最好用Post请求调用API
# PipeLine的逻辑：PipeLine是一个自动化调用BaseModule服务的管线，只需要第一个模块的输入，就可以进行自动化调用，最后封装出一个统一的管线入口和出口
# 当前PipeLine暂时只支持串行调度，后续可以更加自由的定义
# PipeAPI是用FastAPI做的后端服务接口封装，可以封装一个或多个PipeLine进行统一的调用
# 也就是将模型服务通过Post请求抽象为模块，将多个模块整合成PipeLine实现自动化调用，最后将PipeLine再抽象为一个大模块，通过PipeAPI进行调用
# PipeAPI可以对一个或多个PipeLine再封装，通过Post请求调用

# 举个例子，我需要做一个AI语音交互数字人，那么数字人的3D部分属于前端，用Unity或UE实现
# 中间的语音交互逻辑：从ASR -> LLM -> TTS 需要调用三个模型服务。我将这些服务封装到一个MetaPeoplePipeLine中，然后用PipeAPI创建了这个PipeLine的API服务
# 这样我无论用Unity还是UE实现，都只需要向PipeAPI返回Post请求即可。如果我只想要ASR -> LLM服务，可以创建一个包含ASR -> LLM的PipeLine，甚至可以用同一个PipeAPI类进行调用。
# BaseModule返回Response，PipeLine返回当前BaseModule的Response，PipeAPI提供一个接口持续返回PipeLine的Response