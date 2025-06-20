# BscScan 钱包交易分析器 Web 应用
This project will be updated if I have time, but it is not my main project, so it may not be updated frequently.


这是一个基于 Web 的应用程序，用于分析指定币安智能链 (BSC) 钱包地址在特定时间段内的交易记录。它可以获取交易详情、对交易进行分类（买入/卖出等）、估算交易的USDT价值，并使用FIFO（先进先出）方法计算已实现盈亏和“损耗值”。

## 主要功能

* **按时间段获取交易**: 获取指定钱包地址在北京时间当天早上8点至隔天早上8点（24小时窗口）内的所有交易。
* **BEP-20 代币转账详情**: 解析每笔交易中的 BEP-20 代币转账事件，显示代币名称、符号、数量等。
* **交易分类**: 自动尝试将每笔交易从钱包所有者的角度分类为“买入”、“卖出”、“发送”、“接收”或“其他合约交互”。
* **USDT 价值估算**:
    * 优先使用交易中涉及的 USDT 或 BUSD (作为USDT等价物)。
    * 其次，使用 WBNB 数量并结合 CoinGecko API 获取的当日 BNB 历史价格进行估算。
    * 最后，使用交易本身附带的原生 BNB 数量进行估算。
* **盈亏 (P/L) 计算 (FIFO)**:
    * 对非报价代币（如 ZKJ）的买卖操作，使用简化的 FIFO 方法跟踪持仓和成本。
    * 计算已完成交易（在分析周期内有买有卖）的已实现盈利或亏损。
* **“损耗值”计算**: 计算所有亏损交易的亏损总额。
* **数据汇总**: 提供包括总交易笔数、买入/卖出笔数、总估算USDT交易额、总买入USDT交易额、总已实现盈亏和总损耗值等摘要信息。
* **Web 界面**:
    * 用户可以通过网页前端输入钱包地址和自己的 BscScan API 密钥。
    * 结果以表格和摘要的形式清晰展示。

## 配置

* **BscScan API 密钥**: 用户需要在Web界面的输入框中提供自己的 BscScan API 密钥。此密钥仅用于当次请求，不会被服务器存储。
* **目标钱包地址**: 用户在Web界面输入想要分析的钱包地址。
* 脚本内部 `app.py` 文件顶部的 `API_CALL_DELAY` 等常量可以根据实际情况调整，以更好地管理API请求频率。

## 如何运行应用

1.  确保您已完成上述安装步骤并且虚拟环境已激活（如果使用的话）。
2.  在项目根目录 (`bscscan_webapp/`)下，运行 Flask 应用：
    ```bash
    python app.py
    ```
3.  应用启动后，您会在终端看到类似如下信息：
    ```
     * Running on [http://127.0.0.1:5000/](http://127.0.0.1:5000/) (Press CTRL+C to quit)
    ```
4.  打开您的网络浏览器，访问显示的地址 (通常是 `http://127.0.0.1:5000/`)。