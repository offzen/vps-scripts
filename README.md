## 自用工具集
其中tcpQualityCanvas已更新 请使用新版 
```
curl -fsSL https://raw.githubusercontent.com/offzen/TcpQCanvas/main/run | bash
```
带参数运行的示例 （-t 0 持续运行/手动终止后开始httping检测） 
```
curl -fsSL https://raw.githubusercontent.com/offzen/TcpQCanvas/main/run -o TcpQCanvas.sh && bash TcpQCanvas.sh -v4 -gd -sh -cq -t 240
```
