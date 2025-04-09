import queue
import time

class Pipeline:
    def ProcessQueue(self):
        while True:
            try:
                # 使用非阻塞方式获取队列数据
                data = self.Queue.get_nowait()
                if data is None:
                    continue
                    
                # 直接处理数据，不进行额外的检查
                self.ProcessData(data)
                
            except queue.Empty:
                # 队列为空时短暂休眠
                time.sleep(0.01)
                continue
                
            except Exception as e:
                self.logger.error(f"队列处理错误: {str(e)}")
                continue 